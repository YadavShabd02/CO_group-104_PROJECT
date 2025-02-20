import re
import sys
import pandas as pd

instructions_dict = {
    # J-type
    "jal": ("1101111", None, None),
    # U-type
    "lui": ("0110111", None, None),
    "auipc": ("0010111", None, None),
    # B-type
    "beq": ("1100011", "000", None),
    "bne": ("1100011", "001", None),
    "blt": ("1100011", "100", None),
    "bge": ("1100011", "101", None),
    "bltu": ("1100011", "110", None),
    "bgeu": ("1100011", "111", None),
    # S-type
    "sw": ("0100011", "010", None),
    # I-type
    "lw": ("0000011", "010", None),
    "addi": ("0010011", "000", None),
    "sltiu": ("0010011", "011", None),
    "jalr": ("1100111", "000", None),
    # R-type
    "add": ("0110011", "000", "0000000"),
    "sub": ("0110011", "000", "0100000"),
    "sll": ("0110011", "001", "0000000"),
    "slt": ("0110011", "010", "0000000"),
    "sltu": ("0110011", "011", "0000000"),
    "xor": ("0110011", "100", "0000000"),
    "srl": ("0110011", "101", "0000000"),
    "or": ("0110011", "110", "0000000"),
    "and": ("0110011", "111", "0000000")
}

registers = {
    "zero": "00000", "ra": "00001", "sp": "00010", "gp": "00011", "tp": "00100",
    "t0": "00101", "t1": "00110", "t2": "00111", "s0": "01000", "s1": "01001",
    "a0": "01010", "a1": "01011", "a2": "01100", "a3": "01101", "a4": "01110",
    "a5": "01111", "a6": "10000", "a7": "10001", "s2": "10010", "s3": "10011",
    "s4": "10100", "s5": "10101", "s6": "10110", "s7": "10111", "s8": "11000",
    "s9": "11001", "s10": "11010", "s11": "11011", "t3": "11100", "t4": "11101",
    "t5": "11110", "t6": "11111"
}


class Assembler:
    def __init__(self, filename):
        # Read and strip non-empty lines
        with open(filename, "r") as f:
            self.lines = [line.strip() for line in f if line.strip()]
        
        # Process labels and instructions
        self.labels = {}  # maps label name to address
        self.instructions = []
        current_address = 0
        for line in self.lines:
            if ':' in line:
                # Split into label and (optional) instruction
                parts = line.split(":", 1)
                label = parts[0].strip()
                if parts[0] != label:
                    print(f"Invalid label format at address {current_address}")
                    sys.exit(1)
                self.labels[label] = current_address
                if parts[1].strip():
                    self.instructions.append(parts[1].strip())
                    current_address += 4
            else:
                self.instructions.append(line)
                current_address += 4

        # Parse each instruction into [opcode, args]
        self.asm1 = []
        for instr in self.instructions:
            parts = instr.split(None, 1)
            if len(parts) < 2:
                print("Invalid instruction format:", instr)
                sys.exit(1)
            self.asm1.append(parts)
        
        # Optional: show a DataFrame of instructions for debugging
        asmdf = pd.DataFrame(self.asm1, columns=["opcode", "args"])
        print(asmdf)
        
        # Check for the virtual halt instruction "beq zero,zero,0"
        try:
            halt_index = self.asm1.index(["beq", "zero,zero,0"])
            print("Index of virtual halt instruction:", halt_index)
        except ValueError:
            print("Virtual halt instruction not found")
            sys.exit(1)

    def assemble_instruction(self, instruction, current_address):
        opcode_str = instruction[0]
        if opcode_str not in instructions_dict:
            print("Invalid instruction at address", current_address)
            sys.exit(1)
        opcode, funct3, funct7 = instructions_dict[opcode_str]
        # Split arguments using comma and parentheses as delimiters
        arguments = [arg.strip() for arg in re.split(r'[,\(\)]', instruction[1]) if arg.strip()]

        # J-type instruction: jal
        if opcode_str == "jal":
            if len(arguments) != 2:
                print(f"Invalid number of arguments for jal at address {current_address}")
                sys.exit(1)
            rd = registers.get(arguments[0])
            if rd is None:
                print(f"Invalid register {arguments[0]} at address {current_address}")
                sys.exit(1)
            # Immediate can be a number or a label
            try:
                imm_val = int(arguments[1])
            except ValueError:
                if arguments[1] in self.labels:
                    target = self.labels[arguments[1]]
                    imm_val = target - current_address
                else:
                    print(f"Invalid label {arguments[1]} at address {current_address}")
                    sys.exit(1)
            if imm_val >= 2**20 or imm_val < -2**20:
                print(f"Immediate value out of range for jal at address {current_address}")
                sys.exit(1)
            imm = '{:021b}'.format(imm_val if imm_val >= 0 else (2**21 + imm_val))
            # Reorder bits as per RISC-V jal instruction: imm[20] | imm[10:1] | imm[11] | imm[19:12]
            return imm[0] + imm[10:20] + imm[9] + imm[1:9] + rd + opcode

        # I-type: jalr, addi, sltiu, lw
        elif opcode_str == "jalr":
            if len(arguments) != 3:
                print(f"Invalid number of arguments for jalr at address {current_address}")
                sys.exit(1)
            rd = registers.get(arguments[0])
            rs1 = registers.get(arguments[1])
            if rd is None or rs1 is None:
                print(f"Invalid register in jalr at address {current_address}")
                sys.exit(1)
            try:
                imm_val = int(arguments[2])
            except ValueError:
                if arguments[2] in self.labels:
                    target = self.labels[arguments[2]]
                    imm_val = target - current_address
                else:
                    print(f"Invalid label {arguments[2]} at address {current_address}")
                    sys.exit(1)
            if imm_val >= 2**11 or imm_val < -2**11:
                print(f"Immediate value out of range for jalr at address {current_address}")
                sys.exit(1)
            imm = '{:012b}'.format(imm_val if imm_val >= 0 else (2**12 + imm_val))
            return imm + rs1 + funct3 + rd + opcode

        # B-type: branch instructions (beq, bne, etc.)
        elif opcode_str in ["beq", "bne", "blt", "bge", "bltu", "bgeu"]:
            if len(arguments) != 3:
                print(f"Invalid number of arguments for {opcode_str} at address {current_address}")
                sys.exit(1)
            rs1 = registers.get(arguments[0])
            rs2 = registers.get(arguments[1])
            if rs1 is None or rs2 is None:
                print(f"Invalid register in {opcode_str} at address {current_address}")
                sys.exit(1)
            try:
                imm_val = int(arguments[2])
            except ValueError:
                if arguments[2] in self.labels:
                    target = self.labels[arguments[2]]
                    imm_val = target - current_address
                else:
                    print(f"Invalid label {arguments[2]} at address {current_address}")
                    sys.exit(1)
            if imm_val >= 2**12 or imm_val < -2**12:
                print(f"Immediate value out of range for {opcode_str} at address {current_address}")
                sys.exit(1)
            imm = '{:013b}'.format(imm_val if imm_val >= 0 else (2**13 + imm_val))
            # Branch encoding: imm[12] | imm[10:5] | rs2 | rs1 | funct3 | imm[4:1] | imm[11] | opcode
            return imm[0] + imm[2:8] + rs2 + rs1 + funct3 + imm[8:12] + imm[1] + opcode

        # I-type load: lw
        elif opcode_str == "lw":
            if len(arguments) != 3:
                print(f"Invalid number of arguments for lw at address {current_address}")
                sys.exit(1)
            rd = registers.get(arguments[0])
            if rd is None:
                print(f"Invalid register {arguments[0]} at address {current_address}")
                sys.exit(1)
            try:
                imm_val = int(arguments[1])
            except ValueError:
                print(f"Invalid immediate value {arguments[1]} at address {current_address}")
                sys.exit(1)
            rs1 = registers.get(arguments[2])
            if rs1 is None:
                print(f"Invalid register {arguments[2]} at address {current_address}")
                sys.exit(1)
            if imm_val >= 2**11 or imm_val < -2**11:
                print(f"Immediate value out of range for lw at address {current_address}")
                sys.exit(1)
            imm = '{:012b}'.format(imm_val if imm_val >= 0 else (2**12 + imm_val))
            return imm + rs1 + funct3 + rd + opcode

        # S-type: sw
        elif opcode_str == "sw":
            if len(arguments) != 3:
                print(f"Invalid number of arguments for sw at address {current_address}")
                sys.exit(1)
            rs2 = registers.get(arguments[0])
            if rs2 is None:
                print(f"Invalid register {arguments[0]} at address {current_address}")
                sys.exit(1)
            try:
                imm_val = int(arguments[1])
            except ValueError:
                print(f"Invalid immediate value {arguments[1]} at address {current_address}")
                sys.exit(1)
            rs1 = registers.get(arguments[2])
            if rs1 is None:
                print(f"Invalid register {arguments[2]} at address {current_address}")
                sys.exit(1)
            if imm_val >= 2**11 or imm_val < -2**11:
                print(f"Immediate value out of range for sw at address {current_address}")
                sys.exit(1)
            imm = '{:012b}'.format(imm_val if imm_val >= 0 else (2**12 + imm_val))
            return imm[:7] + rs2 + rs1 + funct3 + imm[7:] + opcode

        # I-type arithmetic: addi, sltiu
        elif opcode_str in ["addi", "sltiu"]:
            if len(arguments) != 3:
                print(f"Invalid number of arguments for {opcode_str} at address {current_address}")
                sys.exit(1)
            rd = registers.get(arguments[0])
            rs1 = registers.get(arguments[1])
            if rd is None or rs1 is None:
                print(f"Invalid register in {opcode_str} at address {current_address}")
                sys.exit(1)
            try:
                imm_val = int(arguments[2])
            except ValueError:
                print(f"Invalid immediate value {arguments[2]} at address {current_address}")
                sys.exit(1)
            if imm_val >= 2**11 or imm_val < -2**11:
                print(f"Immediate value out of range for {opcode_str} at address {current_address}")
                sys.exit(1)
            imm = '{:012b}'.format(imm_val if imm_val >= 0 else (2**12 + imm_val))
            return imm + rs1 + funct3 + rd + opcode

        # R-type instructions: add, sub, sll, etc.
        elif opcode_str in ["add", "sub", "sll", "slt", "sltu", "xor", "srl", "or", "and"]:
            if len(arguments) != 3:
                print(f"Invalid number of arguments for {opcode_str} at address {current_address}")
                sys.exit(1)
            rd = registers.get(arguments[0])
            rs1 = registers.get(arguments[1])
            rs2 = registers.get(arguments[2])
            if rd is None or rs1 is None or rs2 is None:
                print(f"Invalid register in {opcode_str} at address {current_address}")
                sys.exit(1)
            return funct7 + rs2 + rs1 + funct3 + rd + opcode

        else:
            print(f"Unknown instruction {opcode_str} at address {current_address}")
            sys.exit(1)

    def assemble(self):
        self.machine_code = []
        for i, instr in enumerate(self.asm1):
            current_address = 4 * i
            assembled_instruction = self.assemble_instruction(instr, current_address)
            self.machine_code.append(assembled_instruction)
            print(f"Assembled at address {current_address}: {assembled_instruction}")
        print("Final machine code:", self.machine_code)

    def write_to_file(self, filename):
        with open(filename, "w") as f:
            for code in self.machine_code:
                f.write(code + "\n")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: assembler.py <input_filename> <output_filename>")
        sys.exit(1)
    assembler = Assembler(sys.argv[1])
    assembler.assemble()
    assembler.write_to_file(sys.argv[2])
