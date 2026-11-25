"""
Hack Assembler for the Nand2Tetris Part B capstone.

Usage:
    python assembler.py Add.asm
    python assembler.py Add.asm -o Add.hack
    python assembler.py Add.asm Max.asm Rect.asm Pong.asm

The assembler converts Hack assembly (.asm) files into 16-bit binary
machine-code files (.hack).

Capstone extra feature for K = 26:
    K % 3 == 2, so the assembler warns when a label is declared more than once.
    If a duplicate label is found, the first declaration is kept.
"""

import argparse
import sys
from pathlib import Path


# Predefined Hack symbols.
PREDEFINED_SYMBOLS = {
    "SP": 0,
    "LCL": 1,
    "ARG": 2,
    "THIS": 3,
    "THAT": 4,
    "SCREEN": 16384,
    "KBD": 24576,
}
for register_number in range(16):
    PREDEFINED_SYMBOLS[f"R{register_number}"] = register_number


# Hack C-instruction comp field (7 bits, including the a-bit).
COMP_BITS = {
    "0":   "0101010",
    "1":   "0111111",
    "-1":  "0111010",
    "D":   "0001100",
    "A":   "0110000",
    "M":   "1110000",
    "!D":  "0001101",
    "!A":  "0110001",
    "!M":  "1110001",
    "-D":  "0001111",
    "-A":  "0110011",
    "-M":  "1110011",
    "D+1": "0011111",
    "A+1": "0110111",
    "M+1": "1110111",
    "D-1": "0001110",
    "A-1": "0110010",
    "M-1": "1110010",
    "D+A": "0000010",
    "D+M": "1000010",
    "D-A": "0010011",
    "D-M": "1010011",
    "A-D": "0000111",
    "M-D": "1000111",
    "D&A": "0000000",
    "D&M": "1000000",
    "D|A": "0010101",
    "D|M": "1010101",
}

DEST_BITS = {
    "":    "000",
    "M":   "001",
    "D":   "010",
    "MD":  "011",
    "A":   "100",
    "AM":  "101",
    "AD":  "110",
    "AMD": "111",
}

JUMP_BITS = {
    "":    "000",
    "JGT": "001",
    "JEQ": "010",
    "JGE": "011",
    "JLT": "100",
    "JNE": "101",
    "JLE": "110",
    "JMP": "111",
}


def clean_line(raw_line):
    """Remove a // comment and surrounding whitespace."""
    return raw_line.split("//", 1)[0].strip()


def is_valid_symbol(symbol):
    """Check the Hack symbol naming rules."""
    if not symbol:
        return False
    if not (symbol[0].isalpha() or symbol[0] in "_.$:"):
        return False
    return all(char.isalnum() or char in "_.$:" for char in symbol)


def first_pass(source_lines):
    """
    Build the symbol table from labels.

    ROM addresses count instructions only; label declarations do not
    increase the ROM address. Duplicate labels produce a warning and
    the first declaration is retained.
    """
    symbols = dict(PREDEFINED_SYMBOLS)
    rom_address = 0

    for line_number, raw_line in enumerate(source_lines, start=1):
        line = clean_line(raw_line)
        if not line:
            continue

        if line.startswith("(") and line.endswith(")"):
            label = line[1:-1].strip()
            if not is_valid_symbol(label):
                raise ValueError(
                    f"Line {line_number}: invalid label declaration: {line}"
                )

            if label in symbols:
                print(
                    f"Warning: Line {line_number}: label '{label}' is already "
                    f"defined; keeping its first address ({symbols[label]}).",
                    file=sys.stderr,
                )
            else:
                symbols[label] = rom_address
        else:
            if "(" in line or ")" in line:
                raise ValueError(
                    f"Line {line_number}: invalid label declaration: {line}"
                )
            rom_address += 1

    return symbols


def to_binary(value):
    """Convert an integer to a 16-bit binary string."""
    if not 0 <= value <= 32767:
        raise ValueError(f"A-instruction value must be between 0 and 32767, got {value}")
    return format(value, "016b")


def assemble_a_instruction(line, symbols, next_variable_address, line_number):
    """Translate @value or @symbol into a 16-bit A-instruction."""
    value_text = line[1:].strip()
    if not value_text:
        raise ValueError(f"Line {line_number}: missing value after '@'")

    if value_text.isdigit():
        value = int(value_text)
    else:
        if not is_valid_symbol(value_text):
            raise ValueError(f"Line {line_number}: invalid symbol '{value_text}'")

        if value_text not in symbols:
            if next_variable_address[0] > 16383:
                raise ValueError(
                    f"Line {line_number}: no available RAM address for variable "
                    f"'{value_text}'"
                )
            symbols[value_text] = next_variable_address[0]
            next_variable_address[0] += 1

        value = symbols[value_text]

    try:
        return to_binary(value)
    except ValueError as error:
        raise ValueError(f"Line {line_number}: {error}") from error


def assemble_c_instruction(line, line_number):
    """Translate a C-instruction into 111 + comp + dest + jump."""
    if line.count("=") > 1 or line.count(";") > 1:
        raise ValueError(f"Line {line_number}: invalid C-instruction: {line}")

    if "=" in line:
        dest, remainder = line.split("=", 1)
        dest = dest.strip()
    else:
        dest, remainder = "", line

    if ";" in remainder:
        comp, jump = remainder.split(";", 1)
        jump = jump.strip()
    else:
        comp, jump = remainder, ""

    comp = comp.strip()

    # Accept equivalent commutative spellings commonly used in Hack code.
    comp_aliases = {
        "A+D": "D+A",
        "M+D": "D+M",
        "A&D": "D&A",
        "M&D": "D&M",
        "A|D": "D|A",
        "M|D": "D|M",
    }
    comp = comp_aliases.get(comp, comp)

    if dest not in DEST_BITS:
        raise ValueError(f"Line {line_number}: invalid dest field '{dest}'")
    if comp not in COMP_BITS:
        raise ValueError(f"Line {line_number}: invalid comp field '{comp}'")
    if jump not in JUMP_BITS:
        raise ValueError(f"Line {line_number}: invalid jump field '{jump}'")

    return "111" + COMP_BITS[comp] + DEST_BITS[dest] + JUMP_BITS[jump]


def assemble_lines(source_lines):
    """Assemble source lines and return a list of 16-bit instructions."""
    symbols = first_pass(source_lines)
    machine_code = []
    next_variable_address = [16]

    for line_number, raw_line in enumerate(source_lines, start=1):
        line = clean_line(raw_line)
        if not line or (line.startswith("(") and line.endswith(")")):
            continue

        if line.startswith("@"):
            binary = assemble_a_instruction(
                line, symbols, next_variable_address, line_number
            )
        else:
            binary = assemble_c_instruction(line, line_number)

        machine_code.append(binary)

    return machine_code, symbols


def assemble_file(input_path, output_path=None):
    """Read one .asm file and write the corresponding .hack file."""
    input_path = Path(input_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    if input_path.suffix.lower() != ".asm":
        raise ValueError(f"Input file must have an .asm extension: {input_path}")

    source_lines = input_path.read_text(encoding="utf-8").splitlines()
    machine_code, _ = assemble_lines(source_lines)

    if output_path is None:
        output_path = input_path.with_suffix(".hack")
    else:
        output_path = Path(output_path)

    output_path.write_text(
        "\n".join(machine_code) + ("\n" if machine_code else ""),
        encoding="utf-8",
    )

    print(f"Success: {input_path} -> {output_path} ({len(machine_code)} instructions)")
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Convert Hack assembly (.asm) files into binary (.hack) files."
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="One or more .asm files, for example Add.asm Max.asm",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output filename (use only when assembling one input file).",
    )
    args = parser.parse_args()

    if args.output and len(args.files) != 1:
        parser.error("--output can only be used with one input file")

    had_error = False
    for filename in args.files:
        try:
            output = args.output if args.output else None
            assemble_file(filename, output)
        except (OSError, ValueError) as error:
            had_error = True
            print(f"Error: {error}", file=sys.stderr)

    if had_error:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
