#!/usr/bin/env python3
import sys
import re

# Helper: Return two's complement binary representation of n in "bits" bits.
def to_binary(n, bits):
    if n < 0:
        n = (1 << bits) + n
    if n >= (1 << bits) or n < 0:
        raise ValueError("Immediate {} out of range for {} bits".format(n, bits))
    return format(n, '0{}b'.format(bits))

# Register mapping as per Table 15 in the project document.
registers = {
    "zero": 0,
    "ra": 1,
    "sp": 2,
    "gp": 3,
    "tp": 4,
    "t0": 5,
    "t1": 6,
    "t2": 7,
    "s0": 8, "fp": 8,
    "s1": 9,
    "a0": 10,
    "a1": 11,
    "a2": 12,
    "a3": 13,
    "a4": 14,
    "a5": 15,
    "a6": 16,
    "a7": 17,
    "s2": 18,
    "s3": 19,
    "s4": 20,
    "s5": 21,
    "s6": 22,
    "s7": 23,
    "s8": 24,
    "s9": 25,
    "s10": 26,
    "s11": 27,
    "t3": 28,
    "t4": 29,
    "t5": 30,
    "t6": 31
}

# Encoding information for each instruction type (based on Tables 3–11).
R_instructions = {
    "add": {"funct7": "0000000", "funct3": "000", "opcode": "0110011"},
    "sub": {"funct7": "0100000", "funct3": "000", "opcode": "0110011"},
    "slt": {"funct7": "0000000", "funct3": "010", "opcode": "0110011"},
    "srl": {"funct7": "0000000", "funct3": "101", "opcode": "0110011"},
    "or":  {"funct7": "0000000", "funct3": "110", "opcode": "0110011"},
    "and": {"funct7": "0000000", "funct3": "111", "opcode": "0110011"}
}

I_instructions = {
    "addi": {"opcode": "0010011", "funct3": "000"},
    "lw":   {"opcode": "0000011", "funct3": "010"},
    "jalr": {"opcode": "1100111", "funct3": "000"}
}

S_instructions = {
    "sw": {"opcode": "0100011", "funct3": "010"}
}

B_instructions = {
    "beq": {"opcode": "1100011", "funct3": "000"},
    "bne": {"opcode": "1100011", "funct3": "001"},
    "blt": {"opcode": "1100011", "funct3": "100"}
}

J_instructions = {
    "jal": {"opcode": "1101111"}
}

# Parse a register name; throw an error if invalid.
def parse_register(reg_str, line_num):
    reg_str = reg_str.strip()
    if reg_str in registers:
        return registers[reg_str]
    else:
        raise ValueError("Line {}: Invalid register name '{}'".format(line_num, reg_str))

# Parse an immediate (in decimal or hexadecimal).
def parse_immediate(imm_str, bits, line_num):
    imm_str = imm_str.strip()
    try:
        if imm_str.startswith("0x") or imm_str.startswith("-0x"):
            return int(imm_str, 16)
        else:
            return int(imm_str, 10)
    except:
        raise ValueError("Line {}: Invalid immediate '{}'".format(line_num, imm_str))

# R-type encoding: {funct7}{rs2}{rs1}{funct3}{rd}{opcode}
def encode_R_type(mnemonic, rd, rs1, rs2, line_num):
    info = R_instructions[mnemonic]
    rd_bin = to_binary(rd, 5)
    rs1_bin = to_binary(rs1, 5)
    rs2_bin = to_binary(rs2, 5)
    return info["funct7"] + rs2_bin + rs1_bin + info["funct3"] + rd_bin + info["opcode"]

# I-type encoding: {imm[11:0]}{rs1}{funct3}{rd}{opcode}
def encode_I_type(mnemonic, rd, rs1, immediate, line_num):
    info = I_instructions[mnemonic]
    try:
        imm_bin = to_binary(immediate, 12)
    except Exception:
        raise ValueError("Line {}: Immediate {} out of range for 12 bits".format(line_num, immediate))
    return imm_bin + to_binary(rs1, 5) + info["funct3"] + to_binary(rd, 5) + info["opcode"]

# S-type encoding: {imm[11:5]}{rs2}{rs1}{funct3}{imm[4:0]}{opcode}
def encode_S_type(mnemonic, rs1, rs2, immediate, line_num):
    info = S_instructions[mnemonic]
    try:
        imm_bin = to_binary(immediate, 12)
    except Exception:
        raise ValueError("Line {}: Immediate {} out of range for 12 bits".format(line_num, immediate))
    imm_high = imm_bin[:7]  # bits 11-5
    imm_low = imm_bin[7:]   # bits 4-0
    return imm_high + to_binary(rs2, 5) + to_binary(rs1, 5) + info["funct3"] + imm_low + info["opcode"]

# B-type encoding (branch): {imm[12], imm[10:5]}{rs2}{rs1}{funct3}{imm[4:1], imm[11]}{opcode}
def encode_B_type(mnemonic, rs1, rs2, immediate, line_num):
    info = B_instructions[mnemonic]
    # For branch instructions, require that the immediate is even.
    if immediate % 2 != 0:
        raise ValueError("Line {}: Branch immediate {} is not aligned".format(line_num, immediate))
    # Standard RISC-V branch immediates are encoded after shifting right by 1.
    imm_val = immediate >> 1
    try:
        imm_bin = to_binary(imm_val, 12)
    except Exception:
        raise ValueError("Line {}: Immediate {} out of range for 12 bits".format(line_num, immediate))
    bit12    = imm_bin[0]      # this will be placed at bit 31
    bits10_5 = imm_bin[1:7]    # placed in bits 30-25
    bits4_1  = imm_bin[7:11]   # placed in bits 11-8
    bit11    = imm_bin[11]     # placed at bit 7
    return bit12 + bits10_5 + to_binary(rs2, 5) + to_binary(rs1, 5) + info["funct3"] + bits4_1 + bit11 + info["opcode"]

# J-type encoding: {imm[20], imm[10:1], imm[11], imm[19:12]}{rd}{opcode}
def encode_J_type(mnemonic, rd, immediate, line_num):
    info = J_instructions[mnemonic]
    # For JAL, require immediate alignment.
    if immediate % 2 != 0:
        raise ValueError("Line {}: JAL immediate {} is not aligned".format(line_num, immediate))
    try:
        imm_bin = to_binary(immediate, 20)
    except Exception:
        raise ValueError("Line {}: Immediate {} out of range for 20 bits".format(line_num, immediate))
    # Rearrange bits as per Table 11: imm[20|10:1|11|19:12]
    imm_20    = imm_bin[0]       # most significant bit
    imm_19_12 = imm_bin[1:9]     # next 8 bits
    imm_11    = imm_bin[9]       # next 1 bit
    imm_10_1  = imm_bin[10:]     # remaining 10 bits
    return imm_20 + imm_10_1 + imm_11 + imm_19_12 + to_binary(rd, 5) + info["opcode"]

# Process a single instruction (without any label) and return its 32-bit binary string.
def process_instruction(instr, current_address, labels, line_num):
    instr = instr.strip()
    if not instr:
        return None
    # Split into mnemonic and operand string.
    parts = instr.split(None, 1)
    mnemonic = parts[0]
    operands = parts[1] if len(parts) > 1 else ""
    # Split operands (by commas) and strip spaces.
    operands_list = [op.strip() for op in operands.split(",") if op.strip() != ""]
    
    if mnemonic in R_instructions:
        # Expected format: opcode rd, rs1, rs2
        if len(operands_list) != 3:
            raise ValueError("Line {}: R-type instruction '{}' requires 3 operands".format(line_num, mnemonic))
        rd  = parse_register(operands_list[0], line_num)
        rs1 = parse_register(operands_list[1], line_num)
        rs2 = parse_register(operands_list[2], line_num)
        return encode_R_type(mnemonic, rd, rs1, rs2, line_num)
    elif mnemonic in I_instructions:
        if mnemonic == "lw":
            # Format: lw rd, offset(rs1)
            if len(operands_list) != 2:
                raise ValueError("Line {}: lw instruction requires 2 operands".format(line_num))
            rd = parse_register(operands_list[0], line_num)
            m = re.match(r"(-?\w+)\((\w+)\)", operands_list[1])
            if not m:
                raise ValueError("Line {}: Invalid format for lw operand '{}'".format(line_num, operands_list[1]))
            imm_str, rs1_str = m.groups()
            if imm_str in labels:
                immediate = labels[imm_str] - current_address
            else:
                immediate = parse_immediate(imm_str, 12, line_num)
            rs1 = parse_register(rs1_str, line_num)
            return encode_I_type(mnemonic, rd, rs1, immediate, line_num)
        elif mnemonic == "jalr":
            # Format: jalr rd, rs1, immediate
            if len(operands_list) != 3:
                raise ValueError("Line {}: jalr instruction requires 3 operands".format(line_num))
            rd  = parse_register(operands_list[0], line_num)
            rs1 = parse_register(operands_list[1], line_num)
            if operands_list[2] in labels:
                immediate = labels[operands_list[2]] - current_address
            else:
                immediate = parse_immediate(operands_list[2], 12, line_num)
            return encode_I_type(mnemonic, rd, rs1, immediate, line_num)
        else:  # addi
            # Format: addi rd, rs1, immediate
            if len(operands_list) != 3:
                raise ValueError("Line {}: addi instruction requires 3 operands".format(line_num))
            rd  = parse_register(operands_list[0], line_num)
            rs1 = parse_register(operands_list[1], line_num)
            if operands_list[2] in labels:
                immediate = labels[operands_list[2]] - current_address
            else:
                immediate = parse_immediate(operands_list[2], 12, line_num)
            return encode_I_type(mnemonic, rd, rs1, immediate, line_num)
    elif mnemonic in S_instructions:
        # Format: sw rs2, offset(rs1)
        if len(operands_list) != 2:
            raise ValueError("Line {}: sw instruction requires 2 operands".format(line_num))
        rs2 = parse_register(operands_list[0], line_num)
        m = re.match(r"(-?\w+)\((\w+)\)", operands_list[1])
        if not m:
            raise ValueError("Line {}: Invalid format for sw operand '{}'".format(line_num, operands_list[1]))
        imm_str, rs1_str = m.groups()
        if imm_str in labels:
            immediate = labels[imm_str] - current_address
        else:
            immediate = parse_immediate(imm_str, 12, line_num)
        rs1 = parse_register(rs1_str, line_num)
        return encode_S_type(mnemonic, rs1, rs2, immediate, line_num)
    elif mnemonic in B_instructions:
        # Format: beq/bne/blt rs1, rs2, immediate/label
        if len(operands_list) != 3:
            raise ValueError("Line {}: Branch instruction '{}' requires 3 operands".format(line_num, mnemonic))
        rs1 = parse_register(operands_list[0], line_num)
        rs2 = parse_register(operands_list[1], line_num)
        if operands_list[2] in labels:
            immediate = labels[operands_list[2]] - current_address
        else:
            immediate = parse_immediate(operands_list[2], 12, line_num)
        return encode_B_type(mnemonic, rs1, rs2, immediate, line_num)
    elif mnemonic in J_instructions:
        # Format: jal rd, immediate/label
        if len(operands_list) != 2:
            raise ValueError("Line {}: jal instruction requires 2 operands".format(line_num))
        rd = parse_register(operands_list[0], line_num)
        if operands_list[1] in labels:
            immediate = labels[operands_list[1]] - current_address
        else:
            immediate = parse_immediate(operands_list[1], 20, line_num)
        return encode_J_type(mnemonic, rd, immediate, line_num)
    else:
        raise ValueError("Line {}: Unknown instruction '{}'".format(line_num, mnemonic))

def main():
    if len(sys.argv) != 3:
        print("Usage: assembler.py <input_file> <output_file>")
        sys.exit(1)
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    try:
        with open(input_file, "r") as f:
            lines = f.readlines()
    except Exception as e:
        print("Error reading input file:", e)
        sys.exit(1)
    # First pass: collect labels and assign addresses (each instruction is 4 bytes)
    labels = {}
    instructions = []  # Each entry is a tuple: (instruction_text, line_number, address)
    current_address = 0
    for idx, line in enumerate(lines):
        line_stripped = line.strip()
        if line_stripped == "":
            continue
        if ":" in line_stripped:
            # A label line (or label plus instruction) e.g., "loop: beq ra,sp,end"
            parts = line_stripped.split(":", 1)
            label_name = parts[0].strip()
            if not label_name or not label_name[0].isalpha():
                print("Line {}: Invalid label '{}'".format(idx+1, label_name))
                sys.exit(1)
            labels[label_name] = current_address
            rest = parts[1].strip()
            if rest != "":
                instructions.append((rest, idx+1, current_address))
                current_address += 4
        else:
            instructions.append((line_stripped, idx+1, current_address))
            current_address += 4

    if len(instructions) == 0:
        print("Error: No instructions found.")
        sys.exit(1)
    # Ensure that the last instruction is the Virtual Halt: "beq zero,zero,0"
    last_instr_text, last_line, _ = instructions[-1]
    if not last_instr_text.startswith("beq"):
        print("Line {}: Last instruction must be Virtual Halt (beq zero,zero,0)".format(last_line))
        sys.exit(1)
    parts = last_instr_text.split(None, 1)
    if len(parts) < 2 or parts[1].replace(" ", "") != "zero,zero,0":
        print("Line {}: Last instruction must be Virtual Halt (beq zero,zero,0)".format(last_line))
        sys.exit(1)
    
    # Second pass: process each instruction and encode.
    binary_instructions = []
    for instr_text, line_num, addr in instructions:
        try:
            encoded = process_instruction(instr_text, addr, labels, line_num)
            if encoded is not None:
                binary_instructions.append(encoded)
        except Exception as e:
            print(e)
            sys.exit(1)
    
    # Write the binary code to the output file (each line is a 32-bit binary number)
    try:
        with open(output_file, "w") as f:
            for bin_instr in binary_instructions:
                f.write(bin_instr + "\n")
    except Exception as e:
        print("Error writing output file:", e)
        sys.exit(1)

if __name__ == "__main__":
    main()