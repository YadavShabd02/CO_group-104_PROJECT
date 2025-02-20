#!/usr/bin/env python3
import sys
import re
import pandas as pd

class RiscVAssembler:
    def __init__(self, input_file):
        try:
            with open(input_file, "r") as f:
                # Read and clean source lines.
                self.source_lines = [line.strip() for line in f if line.strip()]
        except Exception as e:
            sys.exit(f"Error reading file: {e}")

        # Initialize label table and parsed instructions.
        self.label_table = {}
        self.parsed_insts = []  # List of tuples: (line_number, instruction_text)
        self._parse_source_lines()
        self._verify_final_instruction()
        
        # Optional: Display parsed instructions in a DataFrame for debugging.
        df = pd.DataFrame(self.parsed_insts, columns=["Line", "Instruction"])
        print(df)

    def _parse_source_lines(self):
        addr = 0
        for idx, line in enumerate(self.source_lines):
            if ":" in line:
                label, remainder = line.split(":", 1)
                lbl = label.strip()
                # Record the label with its corresponding address.
                self.label_table[lbl] = addr
                if remainder.strip():
                    self.parsed_insts.append((idx + 1, remainder.strip()))
                    addr += 4
            else:
                self.parsed_insts.append((idx + 1, line))
                addr += 4

        if not self.parsed_insts:
            sys.exit("No instructions found in the source.")

    def _verify_final_instruction(self):
        # Enforce that the last instruction is the virtual halt: "beq zero,zero,0"
        last_line, last_inst = self.parsed_insts[-1]
        if not last_inst.startswith("beq"):
            sys.exit(f"Line {last_line}: Final instruction must be a halt: beq zero,zero,0")
        parts = last_inst.split(',')
        if len(parts) != 3 or parts[0].split()[1].strip() != "zero" or parts[1].strip() != "zero" or parts[2].strip() != "0":
            sys.exit(f"Line {last_line}: Final instruction must be a halt: beq zero,zero,0")

    def _bin_repr(self, number, bits):
        if number < 0:
            number = (1 << bits) + number
        if number < 0 or number >= (1 << bits):
            sys.exit(f"Immediate {number} out of range for {bits} bits")
        return format(number, f'0{bits}b')

    def _get_register(self, reg):
        reg_map = {
            "zero": 0, "ra": 1, "sp": 2, "gp": 3, "tp": 4,
            "t0": 5, "t1": 6, "t2": 7, "s0": 8, "fp": 8, "s1": 9,
            "a0": 10, "a1": 11, "a2": 12, "a3": 13, "a4": 14, "a5": 15,
            "a6": 16, "a7": 17, "s2": 18, "s3": 19, "s4": 20, "s5": 21,
            "s6": 22, "s7": 23, "s8": 24, "s9": 25, "s10": 26, "s11": 27,
            "t3": 28, "t4": 29, "t5": 30, "t6": 31
        }
        if reg not in reg_map:
            sys.exit(f"Unknown register: {reg}")
        return reg_map[reg]

    def _parse_immediate(self, imm_str, bits, line_num, curr_addr):
        imm_str = imm_str.strip()
        if imm_str in self.label_table:
            return self.label_table[imm_str] - curr_addr
        try:
            if imm_str.startswith("0x") or imm_str.startswith("-0x"):
                return int(imm_str, 16)
            return int(imm_str)
        except:
            sys.exit(f"Line {line_num}: Invalid immediate '{imm_str}'")

    # Encoding routines adapted from assembler.py.
    def _encode_R(self, mnemonic, rd, rs1, rs2):
        encodings = {
            "add": ("0000000", "000", "0110011"),
            "sub": ("0100000", "000", "0110011"),
            "slt": ("0000000", "010", "0110011"),
            "srl": ("0000000", "101", "0110011"),
            "or":  ("0000000", "110", "0110011"),
            "and": ("0000000", "111", "0110011")
        }
        if mnemonic not in encodings:
            sys.exit(f"R-type encoding not found for {mnemonic}")
        funct7, funct3, opcode = encodings[mnemonic]
        return funct7 + self._bin_repr(rs2, 5) + self._bin_repr(rs1, 5) + funct3 + self._bin_repr(rd, 5) + opcode

    def _encode_I(self, mnemonic, rd, rs1, imm):
        encodings = {
            "addi": ("0010011", "000"),
            "lw":   ("0000011", "010"),
            "jalr": ("1100111", "000")
        }
        if mnemonic not in encodings:
            sys.exit(f"I-type encoding not found for {mnemonic}")
        opcode, funct3 = encodings[mnemonic]
        return self._bin_repr(imm, 12) + self._bin_repr(rs1, 5) + funct3 + self._bin_repr(rd, 5) + opcode

    def _encode_S(self, mnemonic, rs1, rs2, imm):
        encodings = {
            "sw": ("0100011", "010")
        }
        if mnemonic not in encodings:
            sys.exit(f"S-type encoding not found for {mnemonic}")
        opcode, funct3 = encodings[mnemonic]
        imm_bin = self._bin_repr(imm, 12)
        return imm_bin[:7] + self._bin_repr(rs2, 5) + self._bin_repr(rs1, 5) + funct3 + imm_bin[7:] + opcode

    def _encode_B(self, mnemonic, rs1, rs2, imm):
        encodings = {
            "beq": ("1100011", "000"),
            "bne": ("1100011", "001"),
            "blt": ("1100011", "100")
        }
        if mnemonic not in encodings:
            sys.exit(f"B-type encoding not found for {mnemonic}")
        opcode, funct3 = encodings[mnemonic]
        if imm % 2 != 0:
            sys.exit("Branch immediate must be even")
        imm_shifted = imm >> 1
        imm_bin = self._bin_repr(imm_shifted, 12)
        return imm_bin[0] + imm_bin[1:7] + self._bin_repr(rs2, 5) + self._bin_repr(rs1, 5) + funct3 + imm_bin[7:11] + imm_bin[11] + opcode

    def _encode_J(self, mnemonic, rd, imm):
        encodings = {
            "jal": "1101111"
        }
        if mnemonic not in encodings:
            sys.exit(f"J-type encoding not found for {mnemonic}")
        opcode = encodings[mnemonic]
        if imm % 2 != 0:
            sys.exit("JAL immediate must be even")
        imm_bin = self._bin_repr(imm, 20)
        # Rearrange bits for jal: imm[0] + imm[10:20] + imm[9] + imm[1:9]
        return imm_bin[0] + imm_bin[10:] + imm_bin[9] + imm_bin[1:9] + self._bin_repr(rd, 5) + opcode

    def translate_instruction(self, inst_text, curr_addr, line_num):
        parts = inst_text.split(None, 1)
        mnemonic = parts[0]
        operand_str = parts[1] if len(parts) > 1 else ""
        operands = [op.strip() for op in operand_str.split(",") if op.strip()]

        # R-type instructions.
        if mnemonic in ["add", "sub", "slt", "srl", "or", "and"]:
            if len(operands) != 3:
                sys.exit(f"Line {line_num}: R-type {mnemonic} requires 3 operands")
            rd = self._get_register(operands[0])
            rs1 = self._get_register(operands[1])
            rs2 = self._get_register(operands[2])
            return self._encode_R(mnemonic, rd, rs1, rs2)

        # I-type arithmetic.
        elif mnemonic in ["addi"]:
            if len(operands) != 3:
                sys.exit(f"Line {line_num}: I-type {mnemonic} requires 3 operands")
            rd = self._get_register(operands[0])
            rs1 = self._get_register(operands[1])
            imm = self._parse_immediate(operands[2], 12, line_num, curr_addr)
            return self._encode_I(mnemonic, rd, rs1, imm)

        # I-type load.
        elif mnemonic == "lw":
            if len(operands) != 2:
                sys.exit(f"Line {line_num}: lw requires 2 operands")
            rd = self._get_register(operands[0])
            match = re.match(r"(-?\w+)\((\w+)\)", operands[1])
            if not match:
                sys.exit(f"Line {line_num}: Invalid lw format '{operands[1]}'")
            imm_str, rs1_str = match.groups()
            imm = self._parse_immediate(imm_str, 12, line_num, curr_addr)
            rs1 = self._get_register(rs1_str)
            return self._encode_I("lw", rd, rs1, imm)

        # I-type jump register.
        elif mnemonic == "jalr":
            if len(operands) != 3:
                sys.exit(f"Line {line_num}: jalr requires 3 operands")
            rd = self._get_register(operands[0])
            rs1 = self._get_register(operands[1])
            imm = self._parse_immediate(operands[2], 12, line_num, curr_addr)
            return self._encode_I("jalr", rd, rs1, imm)

        # S-type store.
        elif mnemonic == "sw":
            if len(operands) != 2:
                sys.exit(f"Line {line_num}: sw requires 2 operands")
            rs2 = self._get_register(operands[0])
            match = re.match(r"(-?\w+)\((\w+)\)", operands[1])
            if not match:
                sys.exit(f"Line {line_num}: Invalid sw format '{operands[1]}'")
            imm_str, rs1_str = match.groups()
            imm = self._parse_immediate(imm_str, 12, line_num, curr_addr)
            rs1 = self._get_register(rs1_str)
            return self._encode_S("sw", rs1, rs2, imm)

        # B-type branch instructions.
        elif mnemonic in ["beq", "bne", "blt"]:
            if len(operands) != 3:
                sys.exit(f"Line {line_num}: Branch {mnemonic} requires 3 operands")
            rs1 = self._get_register(operands[0])
            rs2 = self._get_register(operands[1])
            imm = self._parse_immediate(operands[2], 12, line_num, curr_addr)
            return self._encode_B(mnemonic, rs1, rs2, imm)

        # J-type jump.
        elif mnemonic == "jal":
            if len(operands) != 2:
                sys.exit(f"Line {line_num}: jal requires 2 operands")
            rd = self._get_register(operands[0])
            imm = self._parse_immediate(operands[1], 20, line_num, curr_addr)
            return self._encode_J("jal", rd, imm)

        else:
            sys.exit(f"Line {line_num}: Unknown instruction '{mnemonic}'")

    def run(self, output_file):
        machine_code = []
        curr_addr = 0
        for line_num, inst_text in self.parsed_insts:
            encoded_inst = self.translate_instruction(inst_text, curr_addr, line_num)
            machine_code.append(encoded_inst)
            curr_addr += 4
        try:
            with open(output_file, "w") as out_f:
                for code in machine_code:
                    out_f.write(code + "\n")
        except Exception as e:
            sys.exit(f"Error writing output file: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Usage: assembler.py <input_file> <output_file>")
    assembler = RiscVAssembler(sys.argv[1])
    assembler.run(sys.argv[2])
