#!/usr/bin/env python3
# I type and J type done by 2024149 
# R and B type done by 2024442
# S type and outputting code done by 2024516
# dictionaries and class done by 2024244

import re
import sys
import pandas as pd

# Instruction set dictionary 
instr_set = {
    "jal":   ("1101111", None, None),
    "lui":   ("0110111", None, None),
    "auipc": ("0010111", None, None),
    "beq":   ("1100011", "000", None),
    "bne":   ("1100011", "001", None),
    "blt":   ("1100011", "100", None),
    "bge":   ("1100011", "101", None),
    "bltu":  ("1100011", "110", None),
    "bgeu":  ("1100011", "111", None),
    "sw":    ("0100011", "010", None),
    "lw":    ("0000011", "010", None),
    "addi":  ("0010011", "000", None),
    "sltiu": ("0010011", "011", None),
    "jalr":  ("1100111", "000", None),
    "add":   ("0110011", "000", "0000000"),
    "sub":   ("0110011", "000", "0100000"),
    "sll":   ("0110011", "001", "0000000"),
    "slt":   ("0110011", "010", "0000000"),
    "sltu":  ("0110011", "011", "0000000"),
    "xor":   ("0110011", "100", "0000000"),
    "srl":   ("0110011", "101", "0000000"),
    "or":    ("0110011", "110", "0000000"),
    "and":   ("0110011", "111", "0000000")
}

# Register mapping (using binary string representations)
reg_bin = {
    "zero": "00000", "ra": "00001", "sp": "00010", "gp": "00011", "tp": "00100",
    "t0": "00101", "t1": "00110", "t2": "00111", "s0": "01000", "s1": "01001",
    "a0": "01010", "a1": "01011", "a2": "01100", "a3": "01101", "a4": "01110",
    "a5": "01111", "a6": "10000", "a7": "10001", "s2": "10010", "s3": "10011",
    "s4": "10100", "s5": "10101", "s6": "10110", "s7": "10111", "s8": "11000",
    "s9": "11001", "s10": "11010", "s11": "11011", "t3": "11100", "t4": "11101",
    "t5": "11110", "t6": "11111"
}

class RVAssembler:
    def __init__(self, filename):
        # Read all non-empty lines from the input file
        try:
            with open(filename, "r") as f:
                self.raw_lines = [line.strip() for line in f if line.strip()]
        except Exception as e:
            sys.exit(f"Error reading file: {e}")
        
        # Process labels and instructions 
        self.labels = {}
        self.instr_lines = []  # Instructions after label removal
        current_addr = 0
        for idx, line in enumerate(self.raw_lines):
            if ':' in line:
                # Split into label and (optional) instruction part
                label_part, remainder = line.split(":", 1)
                label = label_part.strip()
                if not label or not label[0].isalpha():
                    sys.exit(f"Invalid label format at line {idx+1}")
                self.labels[label] = current_addr
                if remainder.strip():
                    self.instr_lines.append(remainder.strip())
                    current_addr += 4
            else:
                self.instr_lines.append(line)
                current_addr += 4
        
        if not self.instr_lines:
            sys.exit("No instructions found in the source file.")
        
        # Break instructions into opcode and argument parts
        self.asm_parts = []
        for line in self.instr_lines:
            parts = line.split(None, 1)
            if len(parts) < 2:
                sys.exit(f"Invalid instruction format: {line}")
            self.asm_parts.append(parts)
        
        # Debug: Display instructions using a DataFrame 
        df = pd.DataFrame(self.asm_parts, columns=["opcode", "args"])
        print(df)
        
        # Enforce that the last instruction is the virtual halt: "beq zero,zero,0"
        last_op, last_args = self.asm_parts[-1]
        if last_op != "beq":
            sys.exit("Error: Last instruction must be 'beq zero,zero,0'")
        # Remove all spaces and check
        if "".join(last_args.split()) != "zero,zero,0":
            sys.exit("Error: Last instruction must be 'beq zero,zero,0'")

    def to_binary(self, n, bits):
        # Return two's complement binary representation of n with the given number of bits.
        if n < 0:
            n = (1 << bits) + n
        if n < 0 or n >= (1 << bits):
            sys.exit(f"Immediate {n} out of range for {bits} bits")
        return format(n, f'0{bits}b')

    def assemble_instruction(self, parts, curr_addr):
        opcode = parts[0]
        if opcode not in instr_set:
            sys.exit(f"Unknown instruction '{opcode}' at address {curr_addr}")
        op_info = instr_set[opcode]
        # Split the argument string using commas and parentheses
        args = [arg.strip() for arg in re.split(r'[,\(\)]', parts[1]) if arg.strip()]
        
        # J-type: jal
        if opcode == "jal":
            if len(args) != 2:
                sys.exit(f"Invalid number of arguments for jal at address {curr_addr}")
            rd = reg_bin.get(args[0])
            if rd is None:
                sys.exit(f"Invalid register {args[0]} at address {curr_addr}")
            try:
                imm_val = int(args[1])
            except ValueError:
                if args[1] in self.labels:
                    imm_val = self.labels[args[1]] - curr_addr
                else:
                    sys.exit(f"Invalid immediate/label '{args[1]}' at address {curr_addr}")
            if imm_val >= 2**20 or imm_val < -2**20:
                sys.exit(f"Immediate value out of range for jal at address {curr_addr}")
            imm = '{:021b}'.format(imm_val if imm_val >= 0 else (2**21 + imm_val))
            # Rearrangement: imm[20] | imm[10:1] | imm[11] | imm[19:12]
            return imm[0] + imm[10:20] + imm[9] + imm[1:9] + rd + op_info[0]
        
        # I-type instructions: lw, jalr, addi
        elif opcode in ["lw", "jalr", "addi"]:
            if opcode == "lw":
                if len(args) != 2:
                    sys.exit(f"Invalid number of arguments for lw at address {curr_addr}")
                rd = reg_bin.get(args[0])
                # Expect format like offset(reg)
                match = re.match(r"(-?\w+)\((\w+)\)", parts[1].split(",")[1].strip())
                if not match:
                    sys.exit(f"Invalid lw format at address {curr_addr}")
                imm_str, rs1_str = match.groups()
                try:
                    imm_val = int(imm_str)
                except ValueError:
                    if imm_str in self.labels:
                        imm_val = self.labels[imm_str] - curr_addr
                    else:
                        sys.exit(f"Invalid immediate/label '{imm_str}' at address {curr_addr}")
                rs1 = reg_bin.get(rs1_str)
                if rd is None or rs1 is None:
                    sys.exit(f"Invalid register in lw at address {curr_addr}")
                return self.to_binary(imm_val, 12) + rs1 + op_info[1] + rd + op_info[0]
            elif opcode == "jalr":
                if len(args) != 3:
                    sys.exit(f"Invalid number of arguments for jalr at address {curr_addr}")
                rd = reg_bin.get(args[0])
                rs1 = reg_bin.get(args[1])
                try:
                    imm_val = int(args[2])
                except ValueError:
                    if args[2] in self.labels:
                        imm_val = self.labels[args[2]] - curr_addr
                    else:
                        sys.exit(f"Invalid immediate/label '{args[2]}' at address {curr_addr}")
                if rd is None or rs1 is None:
                    sys.exit(f"Invalid register in jalr at address {curr_addr}")
                return self.to_binary(imm_val, 12) + rs1 + op_info[1] + rd + op_info[0]
            else:  # addi
                if len(args) != 3:
                    sys.exit(f"Invalid number of arguments for addi at address {curr_addr}")
                rd = reg_bin.get(args[0])
                rs1 = reg_bin.get(args[1])
                try:
                    imm_val = int(args[2])
                except ValueError:
                    if args[2] in self.labels:
                        imm_val = self.labels[args[2]] - curr_addr
                    else:
                        sys.exit(f"Invalid immediate/label '{args[2]}' at address {curr_addr}")
                if rd is None or rs1 is None:
                    sys.exit(f"Invalid register in addi at address {curr_addr}")
                return self.to_binary(imm_val, 12) + rs1 + op_info[1] + rd + op_info[0]
        
        # B-type instructions: beq, bne, blt, etc.
        elif opcode in ["beq", "bne", "blt", "bge", "bltu", "bgeu"]:
            if len(args) != 3:
                sys.exit(f"Invalid number of arguments for {opcode} at address {curr_addr}")
            rs1 = reg_bin.get(args[0])
            rs2 = reg_bin.get(args[1])
            try:
                imm_val = int(args[2])
            except ValueError:
                if args[2] in self.labels:
                    imm_val = self.labels[args[2]] - curr_addr
                else:
                    sys.exit(f"Invalid immediate/label '{args[2]}' at address {curr_addr}")
            if rs1 is None or rs2 is None:
                sys.exit(f"Invalid register in {opcode} at address {curr_addr}")
            if imm_val >= 2**12 or imm_val < -2**12:
                sys.exit(f"Immediate out of range for {opcode} at address {curr_addr}")
            imm = '{:013b}'.format(imm_val if imm_val >= 0 else (2**13 + imm_val))
            # Branch format: imm[12] | imm[10:5] | rs2 | rs1 | funct3 | imm[4:1] | imm[11] | opcode
            return imm[0] + imm[2:8] + rs2 + rs1 + op_info[1] + imm[8:12] + imm[1] + op_info[0]
        
        # S-type: sw
        elif opcode == "sw":
            if len(args) != 2:
                sys.exit(f"Invalid number of arguments for sw at address {curr_addr}")
            rs2 = reg_bin.get(args[0])
            match = re.match(r"(-?\w+)\((\w+)\)", parts[1].split(",")[1].strip())
            if not match:
                sys.exit(f"Invalid sw format at address {curr_addr}")
            imm_str, rs1_str = match.groups()
            try:
                imm_val = int(imm_str)
            except ValueError:
                if imm_str in self.labels:
                    imm_val = self.labels[imm_str] - curr_addr
                else:
                    sys.exit(f"Invalid immediate/label '{imm_str}' at address {curr_addr}")
            rs1 = reg_bin.get(rs1_str)
            if rs1 is None or rs2 is None:
                sys.exit(f"Invalid register in sw at address {curr_addr}")
            imm_bin = '{:012b}'.format(imm_val if imm_val >= 0 else (2**12 + imm_val))
            return imm_bin[:7] + rs2 + rs1 + op_info[1] + imm_bin[7:] + op_info[0]
        
        # R-type instructions: add, sub, sll, etc.
        elif opcode in ["add", "sub", "sll", "slt", "sltu", "xor", "srl", "or", "and"]:
            if len(args) != 3:
                sys.exit(f"Invalid number of arguments for {opcode} at address {curr_addr}")
            rd = reg_bin.get(args[0])
            rs1 = reg_bin.get(args[1])
            rs2 = reg_bin.get(args[2])
            if rd is None or rs1 is None or rs2 is None:
                sys.exit(f"Invalid register in {opcode} at address {curr_addr}")
            return op_info[2] + rs2 + rs1 + op_info[1] + rd + op_info[0]
        else:
            sys.exit(f"Unknown instruction '{opcode}' at address {curr_addr}")

    def assemble(self):
        machine_codes = []
        curr_addr = 0
        for part in self.asm_parts:
            code = self.assemble_instruction(part, curr_addr)
            machine_codes.append(code)
            curr_addr += 4
        return machine_codes

    def write_output(self, out_filename):
        codes = self.assemble()
        try:
            with open(out_filename, "w") as f:
                for code in codes:
                    f.write(code + "\n")
        except Exception as e:
            sys.exit(f"Error writing output file: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Usage: rv_assembler.py <input_file> <output_file>")
    assembler = RVAssembler(sys.argv[1])
    assembler.write_output(sys.argv[2])
