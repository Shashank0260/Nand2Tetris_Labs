// Box.asm  K=26

(LOOP)
    @KBD
    D=M
    @FILL
    D;JNE
    @CLEAR
    0;JMP

(FILL)
    @17216
    D=A
    @addr
    M=D
    @20
    D=A
    @rowcount
    M=D

(FILLROW)
    @addr
    A=M
    M=-1
    A=A+1
    M=-1
    A=A+1
    M=-1

    @addr
    D=M
    @32
    D=D+A
    @addr
    M=D

    @rowcount
    M=M-1
    D=M
    @FILLROW
    D;JGT

    @LOOP
    0;JMP

(CLEAR)
    @17216
    D=A
    @addr
    M=D
    @20
    D=A
    @rowcount
    M=D

(CLEARROW)
    @addr
    A=M
    M=0
    A=A+1
    M=0
    A=A+1
    M=0

    @addr
    D=M
    @32
    D=D+A
    @addr
    M=D

    @rowcount
    M=M-1
    D=M
    @CLEARROW
    D;JGT

    @LOOP
    0;JMP
