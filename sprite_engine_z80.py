"""
ZX Spectrum 16x16 Machine Code Sprite Engine
Supports:
- 16x16 pixel sprites (32 bytes/frame)
- 1-frame static or 4-frame animation (128 bytes/def)
- Up to 64 sprite definitions
- Up to 16 active sprites on screen concurrently
- 8 directions of movement
- Path algorithms: Linear, Circle, Box, Wave Vertical, Wave Horizontal
- Speed control (pixels/frame)
- Rebound timer (direction/path reversal after N frames)
- Collision detection: Sprite-to-Sprite, Sprite-to-UDG, Sprite-to-Block, Sprite-to-INK, Sprite-to-PAPER, Sprite-to-Target
- Background save & restore (clean non-destructive screen updates)
- In-place INK application with existing PAPER preservation
- Relocatable machine code binary generation & PEEK/POKE/USR compatibility
"""

import math
import sys

def get_main_context():
    """Safely retrieves the live BasinPy runtime module context (__main__, main, or BetaBasic)."""
    for mod_name in ('__main__', 'main', 'BetaBasic'):
        mod = sys.modules.get(mod_name)
        if mod is not None and hasattr(mod, 'gfx_bits'):
            return mod
    try:
        import main
        return main
    except Exception:
        return None

# Default base memory address in Spectrum 48K RAM
DEFAULT_SPRITE_ENGINE_BASE = 50000

# Offsets from BASE
OFFSET_JP_INIT = 0x0000        # BASE + 0: Init engine
OFFSET_JP_UPDATE = 0x0003      # BASE + 3: Update positions, anim, paths, collisions
OFFSET_JP_DRAW = 0x0006        # BASE + 6: Restore backgrounds, draw sprites, save new
OFFSET_JP_STEP = 0x0009        # BASE + 9: UPDATE + DRAW in one call
OFFSET_JP_SET_ATTR = 0x000C    # BASE + 12: Set attribute block for slot
OFFSET_JP_GET_ATTR = 0x000F    # BASE + 15: Get attribute block for slot
OFFSET_JP_DEF_SPRITE = 0x0012  # BASE + 18: Copy sprite bitmap to def ID
OFFSET_JP_CLEAR_ALL = 0x0015   # BASE + 21: Clear all sprites & restore screen

# Header Pointers (BASE + 0x0018 .. 0x0027)
OFFSET_HDR_BASE = 0x0018
OFFSET_HDR_ACTIVE_TABLE = 0x001A
OFFSET_HDR_COLLISION_TABLE = 0x001C
OFFSET_HDR_PARAM_BLOCK = 0x001E
OFFSET_HDR_DEFS_ADDR = 0x0020
OFFSET_HDR_RESTORE_ADDR = 0x0022
OFFSET_HDR_ENGINE_SIZE = 0x0024
OFFSET_HDR_MAGIC = 0x0026      # 0x5A53 ('SZ')

# Data Tables relative to BASE
OFFSET_ACTIVE_TABLE = 0x0028   # 16 slots * 32 bytes = 512 bytes (BASE+40..BASE+551)
SLOT_SIZE = 32
NUM_ACTIVE_SLOTS = 16

OFFSET_COLLISION_TABLE = 0x0228 # 16 bytes (BASE+552..BASE+567)
OFFSET_PARAM_BLOCK = 0x0238     # 32 bytes (BASE+568..BASE+599)
OFFSET_RESTORE_BUFFERS = 0x0258 # 16 * 64 bytes = 1024 bytes (BASE+600..BASE+1623)
RESTORE_SLOT_SIZE = 64

OFFSET_CODE_START = 0x0658      # Executable machine code starts here (~1.5KB)
OFFSET_SPRITE_DEFS = 0x0C00     # 64 defs * 128 bytes = 8192 bytes (BASE+3072..BASE+11263)
DEF_SIZE = 128
NUM_SPRITE_DEFS = 64

TOTAL_ENGINE_SIZE = OFFSET_SPRITE_DEFS + (NUM_SPRITE_DEFS * DEF_SIZE) # ~11,264 bytes

# Slot Byte Offsets (within each 32-byte active slot)
SLOT_STATUS = 0          # 0=OFF, 1=ON static, 2=ON animated
SLOT_DEF_ID = 1          # 0..63
SLOT_X = 2               # 0..255
SLOT_Y = 3               # 0..191
SLOT_OLD_X = 4           # 0..255
SLOT_OLD_Y = 5           # 0..191
SLOT_OLD_VALID = 6       # 1 if old background was saved
SLOT_INK = 7             # 0..7
SLOT_BRIGHT = 8          # 0, 1, or 255 (preserve)
SLOT_FRAME_COUNT = 9     # 1 or 4
SLOT_CUR_FRAME = 10      # 0..3
SLOT_ANIM_SPEED = 11     # ticks per frame (default 3)
SLOT_ANIM_TICK = 12      # tick counter
SLOT_DIR = 13            # 0..7 (0=N, 1=NE, 2=E, 3=SE, 4=S, 5=SW, 6=W, 7=NW)
SLOT_PATH_MODE = 14      # 0=Linear, 1=Circle, 2=Box, 3=WaveV, 4=WaveH
SLOT_SPEED = 15          # pixels per update (1..8)
SLOT_ORIGIN_X = 16       # origin X for circle/box/wave
SLOT_ORIGIN_Y = 17       # origin Y for circle/box/wave
SLOT_PATH_PARAM = 18     # radius / box size / amplitude
SLOT_PATH_STEP = 19      # phase step (0..255)
SLOT_REBOUND_FRAMES = 20 # rebound interval (0=disabled)
SLOT_REBOUND_COUNTER = 21# countdown counter
SLOT_COLLISION_MASK = 22 # enabled collision checks
SLOT_COLLISION_RES = 23  # detected collision bitmask
SLOT_COLLIDED_SPRITE = 24# ID of other collided sprite
SLOT_TARGET_INK = 25     # target INK to check
SLOT_TARGET_PAPER = 26   # target PAPER to check
SLOT_TARGET_X = 27       # target X coordinate
SLOT_TARGET_Y = 28       # target Y coordinate
SLOT_TARGET_DIST = 29    # target distance threshold
SLOT_PATH_DIR = 30       # 1=forward, 255=reverse
SLOT_FLAGS = 31          # reserved

# Collision Bitmask Constants
COLLISION_SPRITE = 1     # Bit 0: Sprite-to-Sprite
COLLISION_UDG = 2        # Bit 1: Sprite-to-UDG (char 144..164)
COLLISION_BLOCK = 4      # Bit 2: Sprite-to-Block Graphic (char 128..143)
COLLISION_INK = 8        # Bit 3: Sprite-to-INK
COLLISION_PAPER = 16     # Bit 4: Sprite-to-PAPER
COLLISION_TARGET = 32    # Bit 5: Sprite-to-Target (X, Y) or boundary

# 8 Direction Deltas: (dx, dy)
DIR_DELTAS = [
    (0, -1),   # 0: N
    (1, -1),   # 1: NE
    (1, 0),    # 2: E
    (1, 1),    # 3: SE
    (0, 1),    # 4: S
    (-1, 1),   # 5: SW
    (-1, 0),   # 6: W
    (-1, -1),  # 7: NW
]


# Pre-assembled 934-byte native Z80 16x16 3-pass sprite blitter with clean background restore & collision detection
_DRAW_TEMPLATE_BYTES_50000 = bytes([
    245, 197, 213, 229, 221, 229, 253, 229, 221, 33, 120, 195, 253, 33, 168, 197,
    6, 16, 197, 221, 126, 6, 183, 202, 187, 202, 221, 126, 4, 79, 221, 126,
    5, 71, 253, 229, 225, 17, 4, 0, 25, 120, 50, 132, 205, 62, 16, 50,
    133, 205, 58, 132, 205, 254, 192, 210, 97, 202, 58, 132, 205, 230, 7, 246,
    64, 95, 58, 132, 205, 31, 31, 31, 230, 24, 179, 87, 58, 132, 205, 23,
    23, 230, 224, 95, 121, 15, 15, 15, 230, 31, 179, 95, 253, 126, 1, 197,
    71, 126, 18, 35, 19, 16, 250, 193, 58, 132, 205, 60, 50, 132, 205, 58,
    133, 205, 61, 50, 133, 205, 194, 26, 202, 120, 15, 15, 15, 230, 31, 50,
    134, 205, 253, 126, 2, 50, 135, 205, 58, 134, 205, 254, 24, 210, 177, 202,
    229, 38, 0, 58, 134, 205, 111, 41, 41, 41, 41, 41, 17, 0, 88, 25,
    121, 15, 15, 15, 230, 31, 95, 22, 0, 25, 235, 225, 253, 126, 1, 197,
    71, 126, 18, 35, 19, 16, 250, 193, 58, 134, 205, 60, 50, 134, 205, 58,
    135, 205, 61, 50, 135, 205, 194, 112, 202, 221, 126, 0, 183, 32, 4, 221,
    54, 6, 0, 193, 17, 32, 0, 221, 25, 17, 64, 0, 253, 25, 5, 194,
    250, 201, 221, 33, 120, 195, 253, 33, 168, 197, 6, 16, 197, 221, 126, 0,
    183, 202, 182, 203, 221, 126, 3, 254, 192, 210, 182, 203, 221, 126, 2, 79,
    221, 126, 3, 71, 221, 113, 4, 221, 112, 5, 221, 54, 6, 1, 121, 230,
    7, 62, 2, 40, 1, 60, 253, 119, 1, 120, 230, 7, 62, 2, 40, 1,
    60, 253, 119, 2, 253, 229, 209, 33, 4, 0, 25, 235, 120, 50, 136, 205,
    62, 16, 50, 137, 205, 58, 136, 205, 254, 192, 210, 103, 203, 213, 58, 136,
    205, 230, 7, 246, 64, 87, 58, 136, 205, 31, 31, 31, 230, 24, 178, 87,
    58, 136, 205, 23, 23, 230, 224, 95, 121, 15, 15, 15, 230, 31, 179, 95,
    235, 209, 253, 126, 1, 197, 71, 126, 18, 35, 19, 16, 250, 193, 58, 136,
    205, 60, 50, 136, 205, 58, 137, 205, 61, 50, 137, 205, 194, 29, 203, 120,
    15, 15, 15, 230, 31, 50, 138, 205, 253, 126, 2, 50, 139, 205, 58, 138,
    205, 254, 24, 210, 182, 203, 213, 38, 0, 58, 138, 205, 111, 41, 41, 41,
    41, 41, 17, 0, 88, 25, 121, 15, 15, 15, 230, 31, 95, 22, 0, 25,
    209, 253, 126, 1, 197, 71, 126, 18, 35, 19, 16, 250, 193, 58, 138, 205,
    60, 50, 138, 205, 58, 139, 205, 61, 50, 139, 205, 194, 118, 203, 193, 17,
    32, 0, 221, 25, 17, 64, 0, 253, 25, 5, 194, 212, 202, 221, 33, 120,
    195, 253, 33, 168, 197, 6, 16, 197, 221, 126, 0, 183, 202, 200, 204, 221,
    126, 3, 254, 192, 210, 200, 204, 221, 110, 1, 38, 0, 41, 41, 221, 126,
    10, 230, 3, 95, 22, 0, 25, 41, 41, 41, 41, 41, 17, 80, 207, 25,
    221, 86, 3, 6, 16, 197, 213, 229, 122, 254, 192, 210, 101, 204, 95, 230,
    7, 246, 64, 103, 123, 31, 31, 31, 230, 24, 180, 87, 123, 23, 23, 230,
    224, 95, 221, 126, 2, 15, 15, 15, 230, 31, 179, 95, 225, 229, 126, 35,
    102, 111, 221, 126, 2, 230, 7, 32, 16, 26, 181, 18, 123, 230, 31, 254,
    31, 48, 42, 19, 26, 180, 18, 24, 36, 71, 14, 0, 203, 61, 203, 28,
    203, 25, 16, 248, 26, 181, 18, 123, 230, 31, 254, 31, 48, 15, 19, 26,
    180, 18, 123, 230, 31, 254, 31, 48, 4, 19, 26, 177, 18, 225, 35, 35,
    209, 20, 193, 5, 194, 253, 203, 221, 126, 3, 15, 15, 15, 230, 31, 50,
    140, 205, 253, 126, 2, 50, 141, 205, 58, 140, 205, 254, 24, 210, 200, 204,
    38, 0, 58, 140, 205, 111, 41, 41, 41, 41, 41, 17, 0, 88, 25, 221,
    126, 2, 15, 15, 15, 230, 31, 95, 22, 0, 25, 221, 126, 7, 230, 7,
    79, 253, 126, 1, 197, 71, 126, 230, 248, 177, 119, 35, 16, 248, 193, 58,
    140, 205, 60, 50, 140, 205, 58, 141, 205, 61, 50, 141, 205, 194, 128, 204,
    193, 17, 32, 0, 221, 25, 17, 64, 0, 253, 25, 5, 194, 207, 203, 205,
    230, 204, 253, 225, 221, 225, 225, 209, 193, 241, 1, 1, 0, 201, 33, 120,
    197, 6, 16, 175, 119, 35, 16, 252, 221, 33, 120, 195, 6, 16, 221, 54,
    23, 0, 221, 54, 24, 255, 17, 32, 0, 221, 25, 16, 241, 221, 33, 120,
    195, 14, 0, 221, 126, 0, 183, 202, 117, 205, 81, 20, 221, 229, 253, 225,
    197, 1, 32, 0, 253, 9, 193, 253, 126, 0, 183, 202, 103, 205, 221, 126,
    2, 253, 150, 2, 48, 2, 237, 68, 254, 14, 210, 103, 205, 221, 126, 3,
    253, 150, 3, 48, 2, 237, 68, 254, 14, 210, 103, 205, 221, 203, 23, 198,
    221, 114, 24, 33, 120, 197, 197, 6, 0, 9, 193, 203, 198, 253, 203, 23,
    198, 253, 113, 24, 33, 120, 197, 213, 90, 22, 0, 25, 209, 203, 198, 197,
    1, 32, 0, 253, 9, 193, 20, 122, 254, 16, 218, 31, 205, 197, 1, 32,
    0, 221, 9, 193, 12, 121, 254, 15, 218, 11, 205, 201, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0,
])
_RELOCATABLE_DRAW_WORD_OFFSETS = [10, 14, 24, 43, 48, 51, 56, 59, 67, 77, 105, 109, 112, 116, 119, 128, 134, 137, 142, 148, 185, 189, 192, 196, 199, 224, 228, 232, 242, 250, 302, 307, 310, 315, 319, 327, 337, 367, 371, 374, 378, 381, 390, 396, 399, 404, 410, 446, 450, 453, 457, 460, 475, 479, 483, 493, 501, 525, 540, 645, 656, 662, 665, 670, 675, 720, 724, 727, 731, 734, 749, 752, 767, 778, 799, 808, 828, 843, 858, 868, 885, 907, 921]


def _generate_z80_sprite_draw_routine(base, entry_addr):
    """
    Generates relocatable native Z80 machine code for 16x16 sprite blitting (ENGINE_DRAW).
    Blits active 16x16 sprites with pixel-precise shifting to Sinclair VRAM (16384..22527)
    and updates 2x2 attribute cells (22528..23295) with sprite INK.
    """
    data = bytearray(_DRAW_TEMPLATE_BYTES_50000)
    delta = (base - 50000) & 0xFFFF
    for off in _RELOCATABLE_DRAW_WORD_OFFSETS:
        val = data[off] | (data[off + 1] << 8)
        val = (val + delta) & 0xFFFF
        data[off] = val & 0xFF
        data[off + 1] = (val >> 8) & 0xFF
    return bytes(data)


def generate_sprite_engine_binary(base_addr=DEFAULT_SPRITE_ENGINE_BASE):
    """
    Assembles relocatable Z80 machine code binary for the 16x16 sprite engine.
    Returns a bytearray of length TOTAL_ENGINE_SIZE ready to be loaded into Spectrum RAM.
    """
    data = bytearray(TOTAL_ENGINE_SIZE)
    base = base_addr & 0xFFFF

    # 1. Jump Table at BASE + 0x0000
    # JP code_addr
    code_start = base + OFFSET_CODE_START
    jump_targets = [
        code_start + 0,    # ENGINE_INIT
        code_start + 32,   # ENGINE_UPDATE
        code_start + 64,   # ENGINE_DRAW (starts at code_start + 64, 934 bytes)
        code_start + 1008, # ENGINE_STEP
        code_start + 1024, # ENGINE_SET_ATTR
        code_start + 1040, # ENGINE_GET_ATTR
        code_start + 1056, # ENGINE_DEF_SPRITE
        code_start + 1072, # ENGINE_CLEAR_ALL
    ]
    for idx, target in enumerate(jump_targets):
        o = idx * 3
        data[o] = 0xC3  # JP
        data[o + 1] = target & 0xFF
        data[o + 2] = (target >> 8) & 0xFF

    # 2. Header Pointers (BASE + 0x0018 .. 0x0027)
    def put_w(off, val):
        data[off] = val & 0xFF
        data[off + 1] = (val >> 8) & 0xFF

    put_w(OFFSET_HDR_BASE, base)
    put_w(OFFSET_HDR_ACTIVE_TABLE, base + OFFSET_ACTIVE_TABLE)
    put_w(OFFSET_HDR_COLLISION_TABLE, base + OFFSET_COLLISION_TABLE)
    put_w(OFFSET_HDR_PARAM_BLOCK, base + OFFSET_PARAM_BLOCK)
    put_w(OFFSET_HDR_DEFS_ADDR, base + OFFSET_SPRITE_DEFS)
    put_w(OFFSET_HDR_RESTORE_ADDR, base + OFFSET_RESTORE_BUFFERS)
    put_w(OFFSET_HDR_ENGINE_SIZE, TOTAL_ENGINE_SIZE)
    put_w(OFFSET_HDR_MAGIC, 0x5A53)

    # 3. Z80 Machine Code Routines at OFFSET_CODE_START
    co = OFFSET_CODE_START
    init_routine = bytearray([
        0xF3,                          # DI
        0xAF,                          # XOR A
        0x21, (base + OFFSET_ACTIVE_TABLE) & 0xFF, ((base + OFFSET_ACTIVE_TABLE) >> 8) & 0xFF, # LD HL, active_table
        0x77,                          # LD (HL), A
        0x11, (base + OFFSET_ACTIVE_TABLE + 1) & 0xFF, ((base + OFFSET_ACTIVE_TABLE + 1) >> 8) & 0xFF, # LD DE, active_table + 1
        0x01, 0x2F, 0x06,             # LD BC, 1583 (clear active table + coll + buffers up to code_start)
        0xED, 0xB0,                    # LDIR
        0x01, 0x00, 0x00,             # LD BC, 0 (Return status in BC)
        0xC9                           # RET
    ])
    data[co : co + len(init_routine)] = init_routine

    # Subroutine 2: ENGINE_UPDATE (calls CHECK_SPRITE_COLLISIONS, returns BC=0x0001)
    co = OFFSET_CODE_START + 32
    check_coll_addr = (code_start + 64 + 766) & 0xFFFF
    upd_routine = bytearray([
        0xCD, check_coll_addr & 0xFF, (check_coll_addr >> 8) & 0xFF, # CALL CHECK_SPRITE_COLLISIONS
        0x01, 0x01, 0x00,                                           # LD BC, 1
        0xC9                                                        # RET
    ])
    data[co : co + len(upd_routine)] = upd_routine

    # Subroutine 3: ENGINE_DRAW full 16x16 native Z80 3-pass sprite blitter with collision detection
    co = OFFSET_CODE_START + 64
    draw_routine = _generate_z80_sprite_draw_routine(base, code_start + 64)
    data[co : co + len(draw_routine)] = draw_routine

    # Subroutine 4: ENGINE_STEP (calls UPDATE, then DRAW)
    co = OFFSET_CODE_START + 1008
    step_routine = bytearray([
        0xCD, (base + OFFSET_JP_UPDATE) & 0xFF, ((base + OFFSET_JP_UPDATE) >> 8) & 0xFF, # CALL UPDATE
        0xCD, (base + OFFSET_JP_DRAW) & 0xFF, ((base + OFFSET_JP_DRAW) >> 8) & 0xFF,     # CALL DRAW
        0x01, 0x01, 0x00,                                                               # LD BC, 1
        0xC9                                                                            # RET
    ])
    data[co : co + len(step_routine)] = step_routine

    # Subroutine 5: ENGINE_SET_ATTR stub
    co = OFFSET_CODE_START + 1024
    set_attr_routine = bytearray([
        0x01, 0x01, 0x00,             # LD BC, 1
        0xC9                           # RET
    ])
    data[co : co + len(set_attr_routine)] = set_attr_routine

    # Subroutine 6: ENGINE_GET_ATTR stub
    co = OFFSET_CODE_START + 1040
    get_attr_routine = bytearray([
        0x01, 0x00, 0x00,             # LD BC, 0
        0xC9                           # RET
    ])
    data[co : co + len(get_attr_routine)] = get_attr_routine

    # Subroutine 7: ENGINE_DEF_SPRITE stub
    co = OFFSET_CODE_START + 1056
    def_sprite_routine = bytearray([
        0x01, 0x01, 0x00,             # LD BC, 1
        0xC9                           # RET
    ])
    data[co : co + len(def_sprite_routine)] = def_sprite_routine

    # Subroutine 8: ENGINE_CLEAR_ALL stub
    co = OFFSET_CODE_START + 1072
    clear_all_routine = bytearray([
        0xCD, (base + OFFSET_CODE_START) & 0xFF, ((base + OFFSET_CODE_START) >> 8) & 0xFF, # CALL INIT
        0x01, 0x00, 0x00,                                                                  # LD BC, 0
        0xC9                                                                               # RET
    ])
    data[co : co + len(clear_all_routine)] = clear_all_routine

    return data


class ZXSpriteEngine:
    """
    High-Performance Python Sprite Engine Subsystem for BasinPy.
    Directly operates on BasinPy's memory, screen bitmaps, and attributes,
    and maintains exact parity with the Z80 machine code memory layout.
    """
    def __init__(self, base_addr=DEFAULT_SPRITE_ENGINE_BASE, memory_ref=None):
        self.base = int(base_addr) & 0xFFFF
        self.memory = memory_ref
        self.active_table_addr = self.base + OFFSET_ACTIVE_TABLE
        self.collision_table_addr = self.base + OFFSET_COLLISION_TABLE
        self.param_block_addr = self.base + OFFSET_PARAM_BLOCK
        self.restore_buffers_addr = self.base + OFFSET_RESTORE_BUFFERS
        self.defs_addr = self.base + OFFSET_SPRITE_DEFS

        # High-level definition cache: id -> list of 4 frames (each 32 bytes)
        self.definitions = {i: [bytes(32) for _ in range(4)] for i in range(NUM_SPRITE_DEFS)}
        # Background restore memory: slot_id -> dict(old_x, old_y, bitmap_bytes[48], attr_bytes[9], valid)
        self.restore_buffers = {
            i: {
                "valid": False, "old_x": 0, "old_y": 0,
                "bitmap": bytearray(48), "attrs": bytearray(9), "used": [False] * 9
            } for i in range(NUM_ACTIVE_SLOTS)
        }

    def init_engine(self, base_addr=None, memory_ref=None):
        """Initialise memory structures and clear all active sprites."""
        if base_addr is not None:
            self.base = int(base_addr) & 0xFFFF
            self.active_table_addr = self.base + OFFSET_ACTIVE_TABLE
            self.collision_table_addr = self.base + OFFSET_COLLISION_TABLE
            self.param_block_addr = self.base + OFFSET_PARAM_BLOCK
            self.restore_buffers_addr = self.base + OFFSET_RESTORE_BUFFERS
            self.defs_addr = self.base + OFFSET_SPRITE_DEFS
        if memory_ref is not None:
            self.memory = memory_ref

        # Write binary structure into memory
        bin_data = generate_sprite_engine_binary(self.base)
        if self.memory is not None and len(self.memory) >= self.base + len(bin_data):
            self.memory[self.base : self.base + len(bin_data)] = bin_data

        for i in range(NUM_ACTIVE_SLOTS):
            self.restore_buffers[i]["valid"] = False
            self._write_slot_byte(i, SLOT_STATUS, 0)
            self._write_slot_byte(i, SLOT_COLLISION_RES, 0)
            if self.memory is not None and self.collision_table_addr + i < len(self.memory):
                self.memory[self.collision_table_addr + i] = 0

    # --------------------------------------------------------------------------
    # Slot Accessors
    # --------------------------------------------------------------------------
    def _slot_addr(self, slot_id):
        return self.active_table_addr + (slot_id & 0x0F) * SLOT_SIZE

    def _read_slot_byte(self, slot_id, offset):
        if self.memory is not None and self._slot_addr(slot_id) + offset < len(self.memory):
            return self.memory[self._slot_addr(slot_id) + offset]
        return 0

    def _write_slot_byte(self, slot_id, offset, val):
        if self.memory is not None and self._slot_addr(slot_id) + offset < len(self.memory):
            self.memory[self._slot_addr(slot_id) + offset] = int(val) & 0xFF

    def set_sprite_def(self, def_id, frame_idx, byte_data):
        """Stores 32 bytes of monochrome bitmap data for a sprite definition frame."""
        def_id = max(0, min(NUM_SPRITE_DEFS - 1, int(def_id)))
        frame_idx = max(0, min(3, int(frame_idx)))
        if len(byte_data) < 32:
            byte_data = bytes(byte_data) + bytes(32 - len(byte_data))
        else:
            byte_data = bytes(byte_data[:32])

        self.definitions[def_id][frame_idx] = byte_data

        # Also write into Spectrum RAM definitions area
        if self.memory is not None:
            target_addr = self.defs_addr + (def_id * DEF_SIZE) + (frame_idx * 32)
            if target_addr + 32 <= len(self.memory):
                self.memory[target_addr : target_addr + 32] = byte_data

    def set_sprite_attr(self, slot_id, x=None, y=None, ink=None, status=None,
                        frame_count=None, cur_frame=None, anim_speed=None,
                        direction=None, path_mode=None, speed=None,
                        rebound_frames=None, path_param=None, def_id=None,
                        target_ink=None, target_paper=None, target_x=None, target_y=None,
                        flip_x=None, flip_y=None, rotate=None, **kwargs):
        """Configures all or specific attributes for an active sprite slot (0..15)."""
        slot_id = max(0, min(NUM_ACTIVE_SLOTS - 1, int(slot_id)))
        if not hasattr(self, "sprite_flips"):
            self.sprite_flips = {}
        if flip_x is not None or flip_y is not None or rotate is not None:
            s_dict = self.sprite_flips.setdefault(slot_id, {})
            if flip_x is not None: s_dict["flip_x"] = flip_x
            if flip_y is not None: s_dict["flip_y"] = flip_y
            if rotate is not None: s_dict["rotate"] = rotate
        if status is not None: self._write_slot_byte(slot_id, SLOT_STATUS, status)
        if def_id is not None: self._write_slot_byte(slot_id, SLOT_DEF_ID, def_id)
        if x is not None:
            self._write_slot_byte(slot_id, SLOT_X, x)
            if self._read_slot_byte(slot_id, SLOT_ORIGIN_X) == 0:
                self._write_slot_byte(slot_id, SLOT_ORIGIN_X, x)
        if y is not None:
            self._write_slot_byte(slot_id, SLOT_Y, y)
            if self._read_slot_byte(slot_id, SLOT_ORIGIN_Y) == 0:
                self._write_slot_byte(slot_id, SLOT_ORIGIN_Y, y)
        if ink is not None: self._write_slot_byte(slot_id, SLOT_INK, ink)
        if frame_count is not None: self._write_slot_byte(slot_id, SLOT_FRAME_COUNT, frame_count)
        if cur_frame is not None: self._write_slot_byte(slot_id, SLOT_CUR_FRAME, cur_frame)
        if anim_speed is not None: self._write_slot_byte(slot_id, SLOT_ANIM_SPEED, max(1, anim_speed))
        if direction is not None: self._write_slot_byte(slot_id, SLOT_DIR, direction % 8)
        if path_mode is not None: self._write_slot_byte(slot_id, SLOT_PATH_MODE, path_mode)
        if speed is not None: self._write_slot_byte(slot_id, SLOT_SPEED, max(0, speed))
        if rebound_frames is not None:
            self._write_slot_byte(slot_id, SLOT_REBOUND_FRAMES, rebound_frames)
            self._write_slot_byte(slot_id, SLOT_REBOUND_COUNTER, 0)
        if path_param is not None: self._write_slot_byte(slot_id, SLOT_PATH_PARAM, path_param)
        if target_ink is not None: self._write_slot_byte(slot_id, SLOT_TARGET_INK, target_ink)
        if target_paper is not None: self._write_slot_byte(slot_id, SLOT_TARGET_PAPER, target_paper)
        if target_x is not None: self._write_slot_byte(slot_id, SLOT_TARGET_X, target_x)
        if target_y is not None: self._write_slot_byte(slot_id, SLOT_TARGET_Y, target_y)

    def sprite_on(self, slot_id, animated=False, def_id=None):
        slot_id = max(0, min(NUM_ACTIVE_SLOTS - 1, int(slot_id)))
        self._write_slot_byte(slot_id, SLOT_STATUS, 2 if animated else 1)
        self._write_slot_byte(slot_id, SLOT_OLD_VALID, 0)
        if hasattr(self, "restore_buffers") and slot_id < len(self.restore_buffers):
            self.restore_buffers[slot_id]["valid"] = False
        self._write_slot_byte(slot_id, SLOT_FRAME_COUNT, 4 if animated else 1)
        if def_id is not None:
            self._write_slot_byte(slot_id, SLOT_DEF_ID, int(def_id))

    def sprite_off(self, slot_id):
        slot_id = max(0, min(NUM_ACTIVE_SLOTS - 1, int(slot_id)))
        self._write_slot_byte(slot_id, SLOT_STATUS, 0)
        self._restore_sprite_background(slot_id)

    def set_attr_from_params(self):
        """Copies parameters from parameter block in RAM into active slot attributes."""
        if self.memory is None:
            return 0
        pb = self.param_block_addr
        slot_id = self.memory[pb] & 0x0F
        self.set_sprite_attr(
            slot_id,
            status=self.memory[pb + 1],
            x=self.memory[pb + 2],
            y=self.memory[pb + 3],
            ink=self.memory[pb + 4],
            frame_count=self.memory[pb + 5],
            cur_frame=self.memory[pb + 6],
            anim_speed=self.memory[pb + 7],
            direction=self.memory[pb + 8],
            path_mode=self.memory[pb + 9],
            speed=self.memory[pb + 10],
            rebound_frames=self.memory[pb + 11],
            path_param=self.memory[pb + 12],
            def_id=self.memory[pb + 13],
            target_ink=self.memory[pb + 14],
            target_paper=self.memory[pb + 15]
        )
        return 0

    def get_attr_to_params(self):
        """Copies 16 bytes of slot attributes into parameter block in RAM."""
        if self.memory is None:
            return 0
        pb = self.param_block_addr
        slot_id = self.memory[pb] & 0x0F
        sa = self._slot_addr(slot_id)
        for i in range(16):
            if sa + i < len(self.memory) and pb + i < len(self.memory):
                self.memory[pb + i] = self.memory[sa + i]
        return 0

    def def_sprite_from_params(self):
        """Reads 32 bytes from parameter block and stores into sprite definition in RAM/cache."""
        if self.memory is None:
            return 0
        pb = self.param_block_addr
        def_id = self.memory[pb] % NUM_SPRITE_DEFS
        frame_idx = self.memory[pb + 1] % 4
        byte_data = bytes(self.memory[pb + 2 : pb + 34])
        self.set_sprite_def(def_id, frame_idx, byte_data)
        return 0

    # --------------------------------------------------------------------------
    # Engine Update & Movement
    # --------------------------------------------------------------------------
    def update_all(self):
        """Advances animation frames, updates positions along paths, checks rebounds & collisions."""
        for slot_id in range(NUM_ACTIVE_SLOTS):
            status = self._read_slot_byte(slot_id, SLOT_STATUS)
            if status == 0:
                continue

            # 1. Animation frame advance
            if status == 2:  # Animated
                tick = self._read_slot_byte(slot_id, SLOT_ANIM_TICK) + 1
                anim_spd = max(1, self._read_slot_byte(slot_id, SLOT_ANIM_SPEED))
                if tick >= anim_spd:
                    tick = 0
                    frame_cnt = max(1, self._read_slot_byte(slot_id, SLOT_FRAME_COUNT))
                    cur_f = (self._read_slot_byte(slot_id, SLOT_CUR_FRAME) + 1) % frame_cnt
                    self._write_slot_byte(slot_id, SLOT_CUR_FRAME, cur_f)
                self._write_slot_byte(slot_id, SLOT_ANIM_TICK, tick)

            # 2. Rebound timer
            rebound_f = self._read_slot_byte(slot_id, SLOT_REBOUND_FRAMES)
            if rebound_f > 0:
                rc = self._read_slot_byte(slot_id, SLOT_REBOUND_COUNTER) + 1
                if rc >= rebound_f:
                    rc = 0
                    cur_dir = self._read_slot_byte(slot_id, SLOT_DIR)
                    self._write_slot_byte(slot_id, SLOT_DIR, (cur_dir + 4) % 8)
                    p_dir = 255 if self._read_slot_byte(slot_id, SLOT_PATH_DIR) == 1 else 1
                    self._write_slot_byte(slot_id, SLOT_PATH_DIR, p_dir)
                self._write_slot_byte(slot_id, SLOT_REBOUND_COUNTER, rc)

            # 3. Position update along Path
            path_mode = self._read_slot_byte(slot_id, SLOT_PATH_MODE)
            speed = self._read_slot_byte(slot_id, SLOT_SPEED)
            if speed > 0:
                x = self._read_slot_byte(slot_id, SLOT_X)
                y = self._read_slot_byte(slot_id, SLOT_Y)
                ox = self._read_slot_byte(slot_id, SLOT_ORIGIN_X)
                oy = self._read_slot_byte(slot_id, SLOT_ORIGIN_Y)
                param = self._read_slot_byte(slot_id, SLOT_PATH_PARAM)
                step = self._read_slot_byte(slot_id, SLOT_PATH_STEP)
                p_dir = 1 if self._read_slot_byte(slot_id, SLOT_PATH_DIR) != 255 else -1

                if path_mode == 0:  # Linear directional
                    d = self._read_slot_byte(slot_id, SLOT_DIR) % 8
                    dx, dy = DIR_DELTAS[d]
                    nx = x + dx * speed
                    ny = y + dy * speed
                    # Bounce on screen boundaries
                    if nx < 0:
                        nx = 0
                        self._write_slot_byte(slot_id, SLOT_DIR, (d ^ 6) % 8)
                    elif nx > 240:
                        nx = 240
                        self._write_slot_byte(slot_id, SLOT_DIR, (d ^ 6) % 8)
                    if ny < 0:
                        ny = 0
                        self._write_slot_byte(slot_id, SLOT_DIR, (4 - d) % 8)
                    elif ny > 176:
                        ny = 176
                        self._write_slot_byte(slot_id, SLOT_DIR, (4 - d) % 8)
                    self._write_slot_byte(slot_id, SLOT_X, nx)
                    self._write_slot_byte(slot_id, SLOT_Y, ny)

                elif path_mode == 1:  # Circle around origin
                    radius = max(1, param)
                    step = (step + p_dir * speed) % 256
                    rad = (step * 2 * math.pi) / 64.0
                    nx = max(0, min(240, int(ox + radius * math.cos(rad))))
                    ny = max(0, min(176, int(oy + radius * math.sin(rad))))
                    self._write_slot_byte(slot_id, SLOT_PATH_STEP, step)
                    self._write_slot_byte(slot_id, SLOT_X, nx)
                    self._write_slot_byte(slot_id, SLOT_Y, ny)

                elif path_mode == 2:  # Box around origin
                    half_w = max(1, param)
                    perim = max(4, half_w * 8)
                    step = (step + p_dir * speed) % perim
                    side_len = half_w * 2
                    side = step // side_len
                    dist = step % side_len
                    if side == 0:    # Top edge: left to right
                        bx = (ox - half_w) + dist
                        by = oy - half_w
                    elif side == 1:  # Right edge: top to bottom
                        bx = ox + half_w
                        by = (oy - half_w) + dist
                    elif side == 2:  # Bottom edge: right to left
                        bx = (ox + half_w) - dist
                        by = oy + half_w
                    else:            # Left edge: bottom to top
                        bx = ox - half_w
                        by = (oy + half_w) - dist
                    self._write_slot_byte(slot_id, SLOT_PATH_STEP, step)
                    self._write_slot_byte(slot_id, SLOT_X, max(0, min(240, bx)))
                    self._write_slot_byte(slot_id, SLOT_Y, max(0, min(176, by)))

                elif path_mode == 3:  # Wave Vertical
                    amp = max(1, param)
                    d = self._read_slot_byte(slot_id, SLOT_DIR) % 8
                    dx = DIR_DELTAS[d][0]
                    nx = (x + dx * speed)
                    if nx < 0: nx = 240
                    elif nx > 240: nx = 0
                    step = (step + p_dir * speed * 2) % 256
                    ny = max(0, min(176, int(oy + amp * math.sin((step * 2 * math.pi) / 64.0))))
                    self._write_slot_byte(slot_id, SLOT_PATH_STEP, step)
                    self._write_slot_byte(slot_id, SLOT_X, nx)
                    self._write_slot_byte(slot_id, SLOT_Y, ny)

                elif path_mode == 4:  # Wave Horizontal
                    amp = max(1, param)
                    d = self._read_slot_byte(slot_id, SLOT_DIR) % 8
                    dy = DIR_DELTAS[d][1]
                    ny = (y + dy * speed)
                    if ny < 0: ny = 176
                    elif ny > 176: ny = 0
                    step = (step + p_dir * speed * 2) % 256
                    nx = max(0, min(240, int(ox + amp * math.sin((step * 2 * math.pi) / 64.0))))
                    self._write_slot_byte(slot_id, SLOT_PATH_STEP, step)
                    self._write_slot_byte(slot_id, SLOT_X, nx)
                    self._write_slot_byte(slot_id, SLOT_Y, ny)

        # 4. Collision Detection
        self._check_all_collisions()

    def _check_all_collisions(self):
        """Evaluates all enabled collision conditions for active sprites."""
        m_ctx = get_main_context()
        chars_map = getattr(m_ctx, 'screen_chars', None) if m_ctx is not None else None

        for slot_id in range(NUM_ACTIVE_SLOTS):
            status = self._read_slot_byte(slot_id, SLOT_STATUS)
            if status == 0:
                self._write_slot_byte(slot_id, SLOT_COLLISION_RES, 0)
                if self.memory is not None and self.collision_table_addr + slot_id < len(self.memory):
                    self.memory[self.collision_table_addr + slot_id] = 0
                continue

            res = 0
            collided_other = 255
            x1 = self._read_slot_byte(slot_id, SLOT_X)
            y1 = self._read_slot_byte(slot_id, SLOT_Y)

            # 1. Sprite-to-Sprite Collision
            for other_id in range(NUM_ACTIVE_SLOTS):
                if other_id == slot_id:
                    continue
                if self._read_slot_byte(other_id, SLOT_STATUS) == 0:
                    continue
                x2 = self._read_slot_byte(other_id, SLOT_X)
                y2 = self._read_slot_byte(other_id, SLOT_Y)
                if abs(x1 - x2) < 14 and abs(y1 - y2) < 14:
                    res |= COLLISION_SPRITE
                    collided_other = other_id
                    break

            # 2. Sprite-to-UDG and Sprite-to-Block Collision via screen cells
            col_start = max(0, min(31, x1 >> 3))
            col_end = max(0, min(31, (x1 + 15) >> 3))
            row_start = max(0, min(23, y1 >> 3))
            row_end = max(0, min(23, (y1 + 15) >> 3))

            target_ink = self._read_slot_byte(slot_id, SLOT_TARGET_INK)
            target_paper = self._read_slot_byte(slot_id, SLOT_TARGET_PAPER)

            if chars_map:
                for r in range(row_start, row_end + 1):
                    for c in range(col_start, col_end + 1):
                        ch = chars_map[r][c]
                        code = ord(ch) if isinstance(ch, str) and len(ch) > 0 else 0
                        if 144 <= code <= 164:
                            res |= COLLISION_UDG
                        elif 128 <= code <= 143:
                            res |= COLLISION_BLOCK

            # Check INK and PAPER in attribute memory (22528..23295)
            if self.memory is not None and len(self.memory) >= 23296:
                for r in range(row_start, row_end + 1):
                    for c in range(col_start, col_end + 1):
                        attr_val = self.memory[22528 + r * 32 + c]
                        ink_v = attr_val & 7
                        paper_v = (attr_val >> 3) & 7
                        if ink_v == target_ink:
                            res |= COLLISION_INK
                        if paper_v == target_paper:
                            res |= COLLISION_PAPER

            # 3. Sprite-to-Target (X, Y) Coordinate Collision
            tx = self._read_slot_byte(slot_id, SLOT_TARGET_X)
            ty = self._read_slot_byte(slot_id, SLOT_TARGET_Y)
            tdist = max(1, self._read_slot_byte(slot_id, SLOT_TARGET_DIST))
            if tx > 0 or ty > 0:
                if abs(x1 - tx) <= tdist and abs(y1 - ty) <= tdist:
                    res |= COLLISION_TARGET

            self._write_slot_byte(slot_id, SLOT_COLLISION_RES, res)
            self._write_slot_byte(slot_id, SLOT_COLLIDED_SPRITE, collided_other)
            if self.memory is not None and self.collision_table_addr + slot_id < len(self.memory):
                self.memory[self.collision_table_addr + slot_id] = res

    # --------------------------------------------------------------------------
    # Background Restore & Drawing
    # --------------------------------------------------------------------------
    def _spectrum_vram_addr(self, x, y):
        third = (y >> 6) & 3
        scan = y & 7
        row = (y >> 3) & 7
        col = (x >> 3) & 31
        return 0x4000 | (third << 11) | (scan << 8) | (row << 5) | col

    def _restore_sprite_background(self, slot_id):
        buf = self.restore_buffers[slot_id]
        if not buf["valid"]:
            return
        buf["valid"] = False

        old_x = buf["old_x"]
        old_y = buf["old_y"]
        col_start = old_x >> 3
        shift = old_x & 7
        cols_span = 3 if shift > 0 else 2

        m_ctx = get_main_context()
        g_bits = getattr(m_ctx, 'gfx_bits', None) if m_ctx is not None else None
        a_ink = getattr(m_ctx, 'attr_ink', None) if m_ctx is not None else None
        a_paper = getattr(m_ctx, 'attr_paper', None) if m_ctx is not None else None
        a_bright = getattr(m_ctx, 'attr_bright', None) if m_ctx is not None else None
        a_flash = getattr(m_ctx, 'attr_flash', None) if m_ctx is not None else None
        a_used = getattr(m_ctx, 'attr_used', None) if m_ctx is not None else None
        dirty_cells = getattr(m_ctx, 'canvas_dirty_cells', None) if m_ctx is not None else None

        # 1. Restore Screen Bitmap
        b_idx = 0
        for line in range(16):
            sy = old_y + line
            if 0 <= sy < 192:
                for c in range(cols_span):
                    sc = col_start + c
                    if 0 <= sc < 32:
                        addr = self._spectrum_vram_addr(sc * 8, sy)
                        saved_byte = buf["bitmap"][b_idx]
                        if self.memory is not None and addr < len(self.memory):
                            self.memory[addr] = saved_byte
                        if g_bits:
                            basin_y = 191 - sy
                            if 0 <= basin_y < 192:
                                for bit in range(8):
                                    px = sc * 8 + bit
                                    if 0 <= px < 256:
                                        g_bits[px][basin_y] = bool((saved_byte >> (7 - bit)) & 1)
                    b_idx += 1

        # 2. Restore Attributes
        r_start = old_y >> 3
        rows_span = 3 if (old_y & 7) > 0 else 2
        a_idx = 0
        for r in range(rows_span):
            sr = r_start + r
            if 0 <= sr < 24:
                for c in range(cols_span):
                    sc = col_start + c
                    if 0 <= sc < 32:
                        if dirty_cells is not None:
                            dirty_cells.add((sr, sc))
                        saved_attr = buf["attrs"][a_idx]
                        attr_addr = 22528 + sr * 32 + sc
                        if self.memory is not None and attr_addr < len(self.memory):
                            self.memory[attr_addr] = saved_attr
                        if a_ink:
                            a_ink[sr][sc] = saved_attr & 7
                            a_paper[sr][sc] = (saved_attr >> 3) & 7
                            a_bright[sr][sc] = bool(saved_attr & 64)
                            a_flash[sr][sc] = bool(saved_attr & 128)
                        if a_used and "used" in buf and a_idx < len(buf["used"]):
                            a_used[sr][sc] = buf["used"][a_idx]
                    a_idx += 1

        if m_ctx is not None:
            m_ctx.canvas_dirty = True

    def _save_sprite_background(self, slot_id, x, y):
        buf = self.restore_buffers[slot_id]
        buf["valid"] = True
        buf["old_x"] = x
        buf["old_y"] = y

        col_start = x >> 3
        shift = x & 7
        cols_span = 3 if shift > 0 else 2

        m_ctx = get_main_context()
        g_bits = getattr(m_ctx, 'gfx_bits', None) if m_ctx is not None else None
        a_ink = getattr(m_ctx, 'attr_ink', None) if m_ctx is not None else None
        a_paper = getattr(m_ctx, 'attr_paper', None) if m_ctx is not None else None
        a_bright = getattr(m_ctx, 'attr_bright', None) if m_ctx is not None else None
        a_flash = getattr(m_ctx, 'attr_flash', None) if m_ctx is not None else None
        a_used = getattr(m_ctx, 'attr_used', None) if m_ctx is not None else None

        if "used" not in buf or len(buf["used"]) != 9:
            buf["used"] = [False] * 9

        # 1. Save Bitmap Bytes
        b_idx = 0
        for line in range(16):
            sy = y + line
            if 0 <= sy < 192:
                for c in range(cols_span):
                    sc = col_start + c
                    if 0 <= sc < 32:
                        addr = self._spectrum_vram_addr(sc * 8, sy)
                        val = 0
                        if g_bits is not None:
                            basin_y = 191 - sy
                            if 0 <= basin_y < 192:
                                for bit in range(8):
                                    px = sc * 8 + bit
                                    if 0 <= px < 256 and g_bits[px][basin_y]:
                                        val |= (1 << (7 - bit))
                        if self.memory is not None and addr < len(self.memory):
                            val |= self.memory[addr]
                        buf["bitmap"][b_idx] = val
                    else:
                        buf["bitmap"][b_idx] = 0
                    b_idx += 1
            else:
                for _ in range(cols_span):
                    buf["bitmap"][b_idx] = 0
                    b_idx += 1

        # 2. Save Attribute Bytes
        r_start = y >> 3
        rows_span = 3 if (y & 7) > 0 else 2
        a_idx = 0
        for r in range(rows_span):
            sr = r_start + r
            if 0 <= sr < 24:
                for c in range(cols_span):
                    sc = col_start + c
                    if 0 <= sc < 32:
                        attr_addr = 22528 + sr * 32 + sc
                        if a_paper is not None and a_ink is not None:
                            p_val = a_paper[sr][sc] & 7
                            i_val = a_ink[sr][sc] & 7
                            b_val = 64 if (a_bright is not None and a_bright[sr][sc]) else 0
                            f_val = 128 if (a_flash is not None and a_flash[sr][sc]) else 0
                            val = f_val | b_val | (p_val << 3) | i_val
                        elif self.memory is not None and attr_addr < len(self.memory):
                            val = self.memory[attr_addr]
                        else:
                            val = 0x38
                        buf["attrs"][a_idx] = val
                        buf["used"][a_idx] = bool(a_used[sr][sc]) if a_used is not None else False
                    else:
                        buf["attrs"][a_idx] = 0x38
                        buf["used"][a_idx] = False
                    a_idx += 1
            else:
                for _ in range(cols_span):
                    buf["attrs"][a_idx] = 0x38
                    buf["used"][a_idx] = False
                    a_idx += 1

    def draw_all(self):
        """Erase old positions, save new backgrounds, and blit all active sprites with INK."""
        # 1. Restore all backgrounds from previous frame (clean screen)
        for slot_id in range(NUM_ACTIVE_SLOTS):
            self._restore_sprite_background(slot_id)

        m_ctx = get_main_context()
        g_bits = getattr(m_ctx, 'gfx_bits', None) if m_ctx is not None else None
        a_ink = getattr(m_ctx, 'attr_ink', None) if m_ctx is not None else None
        a_paper = getattr(m_ctx, 'attr_paper', None) if m_ctx is not None else None
        a_bright = getattr(m_ctx, 'attr_bright', None) if m_ctx is not None else None
        a_flash = getattr(m_ctx, 'attr_flash', None) if m_ctx is not None else None
        a_used = getattr(m_ctx, 'attr_used', None) if m_ctx is not None else None
        dirty_cells = getattr(m_ctx, 'canvas_dirty_cells', None) if m_ctx is not None else None

        # 2. SAVE backgrounds for ALL active sprites BEFORE ANY SPRITE IS DRAWN
        for slot_id in range(NUM_ACTIVE_SLOTS):
            status = self._read_slot_byte(slot_id, SLOT_STATUS)
            if status == 0:
                continue
            x = self._read_slot_byte(slot_id, SLOT_X)
            y = self._read_slot_byte(slot_id, SLOT_Y)
            self._save_sprite_background(slot_id, x, y)

        # 3. DRAW all active sprites onto screen & memory
        for slot_id in range(NUM_ACTIVE_SLOTS):
            status = self._read_slot_byte(slot_id, SLOT_STATUS)
            if status == 0:
                continue

            x = self._read_slot_byte(slot_id, SLOT_X)
            y = self._read_slot_byte(slot_id, SLOT_Y)
            def_id = self._read_slot_byte(slot_id, SLOT_DEF_ID)
            frame_idx = self._read_slot_byte(slot_id, SLOT_CUR_FRAME) % 4
            ink_col = self._read_slot_byte(slot_id, SLOT_INK) & 7

            frame_data = None
            if self.memory is not None:
                mem_addr = self.defs_addr + (def_id * DEF_SIZE) + (frame_idx * 32)
                if mem_addr + 32 <= len(self.memory):
                    m_slice = bytes(self.memory[mem_addr : mem_addr + 32])
                    if any(b != 0 for b in m_slice):
                        frame_data = m_slice
            if frame_data is None:
                frame_data = self.definitions.get(def_id, [bytes(32)] * 4)[frame_idx]

            col_start = x >> 3
            shift = x & 7
            cols_span = 3 if shift > 0 else 2

            for line in range(16):
                sy = y + line
                if not (0 <= sy < 192):
                    continue

                b0 = frame_data[line * 2]
                b1 = frame_data[line * 2 + 1]

                if shift == 0:
                    out_bytes = [b0, b1]
                else:
                    out0 = (b0 >> shift) & 0xFF
                    out1 = (((b0 << (8 - shift)) & 0xFF) | (b1 >> shift)) & 0xFF
                    out2 = ((b1 << (8 - shift)) & 0xFF)
                    out_bytes = [out0, out1, out2]

                for c_idx, b_val in enumerate(out_bytes):
                    sc = col_start + c_idx
                    if 0 <= sc < 32:
                        addr = self._spectrum_vram_addr(sc * 8, sy)
                        if self.memory is not None and addr < len(self.memory):
                            self.memory[addr] |= b_val

                        if g_bits:
                            for bit in range(8):
                                if (b_val >> (7 - bit)) & 1:
                                    px = sc * 8 + bit
                                    basin_y = 191 - sy
                                    if 0 <= px < 256 and 0 <= basin_y < 192:
                                        g_bits[px][basin_y] = True

            # Apply Sprite INK while preserving PAPER colour
            r_start = y >> 3
            rows_span = 3 if (y & 7) > 0 else 2
            for r in range(rows_span):
                sr = r_start + r
                if 0 <= sr < 24:
                    for c in range(cols_span):
                        sc = col_start + c
                        if 0 <= sc < 32:
                            if dirty_cells is not None:
                                dirty_cells.add((sr, sc))
                            attr_addr = 22528 + sr * 32 + sc
                            if a_paper is not None:
                                paper_col = a_paper[sr][sc] & 7
                                bright_f = 64 if (a_bright is not None and a_bright[sr][sc]) else 0
                                flash_f = 128 if (a_flash is not None and a_flash[sr][sc]) else 0
                            elif self.memory is not None and attr_addr < len(self.memory):
                                cur_attr = self.memory[attr_addr]
                                paper_col = (cur_attr >> 3) & 7
                                bright_f = cur_attr & 64
                                flash_f = cur_attr & 128
                            else:
                                paper_col = 7
                                bright_f = 0
                                flash_f = 0
                            new_attr = flash_f | bright_f | (paper_col << 3) | ink_col
                            if self.memory is not None and attr_addr < len(self.memory):
                                self.memory[attr_addr] = new_attr
                            if a_ink:
                                a_ink[sr][sc] = ink_col
                            if a_used:
                                a_used[sr][sc] = True

        # 4. Check collisions and update collision table (matches machine code blitter)
        self._check_all_collisions()

        if m_ctx is not None:
            m_ctx.canvas_dirty = True

    def step(self):
        """Combines update and draw in a single call."""
        self.update_all()
        self.draw_all()

    def clear_all(self):
        """Deactivates all sprites and cleanly restores the entire screen background."""
        for slot_id in range(NUM_ACTIVE_SLOTS):
            self._restore_sprite_background(slot_id)
            self._write_slot_byte(slot_id, SLOT_STATUS, 0)
            self._write_slot_byte(slot_id, SLOT_COLLISION_RES, 0)
            if self.memory is not None and self.collision_table_addr + slot_id < len(self.memory):
                self.memory[self.collision_table_addr + slot_id] = 0
        m_ctx = get_main_context()
        if m_ctx is not None:
            m_ctx.canvas_dirty = True


# Global sprite engine singleton
_global_sprite_engine = None

def get_sprite_engine(base_addr=DEFAULT_SPRITE_ENGINE_BASE, memory_ref=None):
    global _global_sprite_engine
    if _global_sprite_engine is None:
        _global_sprite_engine = ZXSpriteEngine(base_addr=base_addr, memory_ref=memory_ref)
    elif base_addr != _global_sprite_engine.base or (memory_ref is not None and _global_sprite_engine.memory is None):
        _global_sprite_engine.init_engine(base_addr=base_addr, memory_ref=memory_ref)
    return _global_sprite_engine
