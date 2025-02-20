addi sp, zero, 380
lui s0, 0x10000
addi s0, s0, 0
addi s1, zero, 5
addi s2, zero, 10
add s3, s1, s2
sw s3, 0(s0)
lw s4, 0(s0)
beq s4, s4, loop
loop:
addi s5, zero, 1
beq zero, zero, 0x00000000