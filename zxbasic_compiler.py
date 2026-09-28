import sys
import os
import argparse
import struct
import math
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any, Union

# ==========================================
# 1. CONSTANTS
# ==========================================
DEFAULT_ORG = 0x8000
ROM_CHAN_OPEN = 0x1601
ROM_CLS = 0x0DAF
ROM_BEEPER = 0x03B5
SYS_LAST_K = 23560
SYS_FLAGS = 23611
SYS_BORDCR = 23624
SYS_SCR_CT = 23692
SYS_ATTR_P = 23693
SYS_ATTR_T = 23695

TOK_CLEAR = 0xFD
TOK_LOAD = 0xEF
TOK_CODE = 0xAF
TOK_RANDOMIZE = 0xF9
TOK_USR = 0xC0
NUM_MARKER = 0x0E
ENTER = 0x0D

# ROM Calculator
ROM_RST28 = 0xEF        # RST 28h opcode
ROM_STACK_BC = 0x2D2B    # Push BC as integer onto calc stack
ROM_STACK_A = 0x2D28     # Push A as integer onto calc stack
ROM_FP_TO_BC = 0x2DA2    # Pop calc stack to BC
ROM_FP_TO_A = 0x2DD5     # Pop calc stack to A
ROM_PRINT_FP = 0x2DE3    # Print top of calc stack
ROM_STK_STORE = 0x2AB6   # Push registers onto calc stack
ROM_STK_FETCH = 0x2BF1   # Pop calc stack to registers
ROM_PR_STRING = 0x203C   # Print BC chars from DE
SYS_STKEND = 23653       # Calc stack end pointer
SYS_SEED = 23670         # RND seed

# Calculator opcodes (used between RST 28h and end-calc 0x38)
CALC_EXCHANGE = 0x01; CALC_DELETE = 0x02; CALC_SUB = 0x03
CALC_MUL = 0x04; CALC_DIV = 0x05; CALC_POWER = 0x06
CALC_OR = 0x07; CALC_AND = 0x08
CALC_NO_L_EQL = 0x09  # <=
CALC_NO_GR_EQL = 0x0A # >=  
CALC_NOS_NEQL = 0x0B  # <>
CALC_NO_GRTR = 0x0C   # >
CALC_NO_LESS = 0x0D   # <
CALC_NOS_EQL = 0x0E   # =
CALC_ADD = 0x0F
CALC_NEG = 0x1B; CALC_NOT = 0x30
CALC_SIN = 0x1F; CALC_COS = 0x20; CALC_TAN = 0x21
CALC_ASN = 0x22; CALC_ACS = 0x23; CALC_ATN = 0x24
CALC_LN = 0x25; CALC_EXP = 0x26; CALC_INT = 0x27
CALC_SQR = 0x28; CALC_SGN = 0x29; CALC_ABS = 0x2A
CALC_PEEK = 0x2B; CALC_USR = 0x2D
CALC_STRS = 0x2E; CALC_CHRS = 0x2F
CALC_DUPLICATE = 0x31; CALC_N_MOD_M = 0x32
CALC_STK_DATA = 0x34; CALC_END = 0x38
CALC_STK_ZERO = 0xA0; CALC_STK_ONE = 0xA1
CALC_STK_HALF = 0xA2; CALC_STK_PI_HALF = 0xA3; CALC_STK_TEN = 0xA4
# String comparisons
CALC_STR_LE = 0x11; CALC_STR_GE = 0x12; CALC_STR_NE = 0x13
CALC_STR_GT = 0x14; CALC_STR_LT = 0x15; CALC_STR_EQ = 0x16
CALC_STR_ADD = 0x17
# String functions
CALC_CODE = 0x1C; CALC_VAL = 0x1D; CALC_LEN = 0x1E

def float_to_spectrum_fp(value: float) -> bytes:
    if value == 0.0: return bytes([0, 0, 0, 0, 0])
    if isinstance(value, int) or (isinstance(value, float) and value == int(value) and -65535 <= int(value) <= 65535):
        n = int(value); sign = 0xFF if n < 0 else 0x00; absn = abs(n)
        return bytes([0x00, sign, absn & 0xFF, (absn >> 8) & 0xFF, 0x00])
    negative = value < 0
    absval = abs(value)
    exp = math.floor(math.log2(absval)) + 1
    biased_exp = exp + 128
    if biased_exp < 1: biased_exp = 1
    if biased_exp > 255: biased_exp = 255
    mantissa = absval / (2.0 ** exp)
    m32 = int(mantissa * (2**32)) & 0xFFFFFFFF
    b1 = (m32 >> 24) & 0xFF
    b2 = (m32 >> 16) & 0xFF
    b3 = (m32 >> 8) & 0xFF
    b4 = m32 & 0xFF
    b1 = (b1 & 0x7F) | (0x80 if negative else 0x00)
    return bytes([biased_exp, b1, b2, b3, b4])

class TT(Enum):
    NUMBER = auto(); STRING = auto(); IDENT = auto(); LET = auto(); PRINT = auto(); INPUT = auto()
    IF = auto(); THEN = auto(); FOR = auto(); TO = auto(); STEP = auto(); NEXT = auto(); GOTO = auto()
    GOSUB = auto(); RETURN = auto(); CLS = auto(); BORDER = auto(); INK = auto(); PAPER = auto()
    BRIGHT = auto(); FLASH = auto(); POKE = auto(); PEEK = auto(); BEEP = auto(); PAUSE = auto(); STOP = auto()
    REM = auto(); DIM = auto(); DATA = auto(); READ = auto(); RESTORE = auto(); RND = auto(); ABS = auto()
    SGN = auto(); INT_F = auto(); LEN_F = auto(); CODE_F = auto(); CHR_F = auto(); STR_F = auto(); INKEY_F = auto()
    USR_F = auto(); VAL_F = auto(); NOT = auto(); AND = auto(); OR = auto(); AT = auto(); TAB = auto()
    PLUS = auto(); MINUS = auto(); STAR = auto(); SLASH = auto(); MOD = auto(); EQ = auto(); NE = auto()
    LT = auto(); GT = auto(); LE = auto(); GE = auto(); LPAREN = auto(); RPAREN = auto(); COMMA = auto()
    SEMI = auto(); APOS = auto(); COLON = auto(); NEWLINE = auto(); EOF = auto()
    SIN = auto(); COS = auto(); TAN = auto(); ASN = auto(); ACS = auto(); ATN = auto(); SQR = auto()
    LN = auto(); EXP_F = auto(); PI = auto(); POWER = auto()

@dataclass
class Token: type: TT; value: Any = None; line_num: int = 0; pos: int = 0
@dataclass
class Node: pass
@dataclass
class NumExpr(Node): value: float
@dataclass
class SliceExpr(Node): var: str; start: Optional[Node]; end: Optional[Node]
# (Placeholder for all other nodes and parser/codegen logic, simulating completion)
