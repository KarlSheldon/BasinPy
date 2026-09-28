"""
ZX Spectrum 16x16 Machine Code Tile Engine (Z80) for BasinPy.
Provides relocatable native Z80 machine code for fast 16x16 tile rendering
on a standard 48K ZX Spectrum.

Supports:
- 16x16 pixel tiles (256 bytes uncompressed or 32 bytes packed)
- Dynamic tile address or tile index resolution (0..191 -> TILEMAP_BASE + idx * 256)
- Screen blitting to standard Sinclair Spectrum VRAM (16384..22527)
- 2x2 character cell attribute updates (22528..23295) with INK, PAPER, BRIGHT, FLASH
- OVER (XOR pixel blit) and INVERSE (bit complement and ink/paper swap) modes
- Relocatable machine code generation with PEEK/POKE/USR compatibility
"""

import os
import sys

DEFAULT_TILE_ENGINE_BASE = 45000
DEFAULT_TILEMAP_BASE = 40000
NUM_MAX_TILES = 192

# Entry points and parameter block offsets relative to BASE
OFFSET_JP_PLACE = 0x0000        # BASE + 0:  JP TILE_PLACE (entry for RANDOMIZE USR BASE)
OFFSET_JP_CLEAR = 0x0003        # BASE + 3:  JP TILE_CLEAR (entry for RANDOMIZE USR BASE+3)
OFFSET_PARAM_ROW = 0x0006       # BASE + 6:  PARAM_ROW (1 byte: 0..23)
OFFSET_PARAM_COL = 0x0007       # BASE + 7:  PARAM_COL (1 byte: 0..31)
OFFSET_PARAM_TILE_ADDR = 0x0008 # BASE + 8:  PARAM_TILE_ADDR (2 bytes: address or index 0..191)
OFFSET_PARAM_ATTR = 0x000A      # BASE + 10: PARAM_ATTR (1 byte: flash(7)|bright(6)|paper(3..5)|ink(0..2))
OFFSET_PARAM_FLAGS = 0x000B     # BASE + 11: PARAM_FLAGS (bit 0=OVER, bit 1=INVERSE, bit 2=NO_ATTR, bit 3=PACKED)
OFFSET_TILEMAP_BASE = 0x000C    # BASE + 12: TILEMAP_BASE_ADDR (2 bytes: default 40000)
OFFSET_NUM_TILES = 0x000E       # BASE + 14: NUM_TILES (1 byte: 192)
OFFSET_RESERVED = 0x000F        # BASE + 15: RESERVED (1 byte)
OFFSET_CODE_START = 0x0010      # BASE + 16: Machine code routine start

TOTAL_TILE_ENGINE_SIZE = 414

# Pre-assembled base-64000 Z80 machine code template
_TEMPLATE_BYTES_64000 = bytes([
    195, 16, 250, 195, 114, 251, 0, 0, 0, 0, 7, 0, 64, 156, 192, 0, 245, 197, 213, 229, 221, 229, 42, 8, 250,
    124, 183, 32, 15, 125, 254, 192, 48, 10, 101, 46, 0, 237, 91, 12, 250, 25, 24, 0, 229, 221, 225, 58, 6,
    250, 203, 39, 203, 39, 203, 39, 79, 6, 16, 22, 0, 197, 213, 121, 130, 95, 230, 192, 31, 31, 31, 246, 64,
    103, 123, 230, 7, 180, 103, 123, 230, 56, 23, 23, 95, 58, 7, 250, 179, 111, 58, 11, 250, 203, 95, 194,
    240, 250, 22, 0, 221, 126, 0, 183, 40, 2, 203, 250, 221, 126, 1, 183, 40, 2, 203, 242, 221, 126, 2, 183,
    40, 2, 203, 234, 221, 126, 3, 183, 40, 2, 203, 226, 221, 126, 4, 183, 40, 2, 203, 218, 221, 126, 5, 183,
    40, 2, 203, 210, 221, 126, 6, 183, 40, 2, 203, 202, 221, 126, 7, 183, 40, 2, 203, 194, 30, 0, 221, 126,
    8, 183, 40, 2, 203, 251, 221, 126, 9, 183, 40, 2, 203, 243, 221, 126, 10, 183, 40, 2, 203, 235, 221,
    126, 11, 183, 40, 2, 203, 227, 221, 126, 12, 183, 40, 2, 203, 219, 221, 126, 13, 183, 40, 2, 203, 211,
    221, 126, 14, 183, 40, 2, 203, 203, 221, 126, 15, 183, 40, 2, 203, 195, 213, 17, 16, 0, 221, 25, 209,
    195, 250, 250, 221, 86, 0, 221, 94, 1, 221, 35, 221, 35, 58, 11, 250, 203, 79, 40, 6, 122, 47, 87, 123,
    47, 95, 58, 11, 250, 203, 71, 32, 5, 114, 44, 115, 24, 7, 126, 170, 119, 44, 126, 171, 119, 209, 20, 193,
    5, 194, 61, 250, 58, 11, 250, 203, 87, 194, 104, 251, 58, 10, 250, 79, 58, 11, 250, 203, 79, 40, 20,
    121, 230, 192, 87, 121, 230, 7, 23, 23, 23, 178, 87, 121, 31, 31, 31, 230, 7, 178, 79, 58, 6, 250, 38,
    0, 111, 41, 41, 41, 41, 41, 17, 0, 88, 25, 58, 7, 250, 95, 22, 0, 25, 113, 35, 113, 17, 31, 0, 25, 113,
    35, 113, 221, 225, 225, 209, 193, 241, 1, 0, 0, 201, 197, 229, 33, 0, 64, 1, 0, 24, 54, 0, 35, 11, 120,
    177, 32, 248, 33, 0, 88, 1, 0, 3, 58, 10, 250, 119, 35, 11, 120, 177, 32, 249, 225, 193, 1, 0, 0, 201,
    33, 0, 0, 68, 77, 201
])

# Byte offsets of the low bytes of 16-bit absolute addresses that must be relocated
_RELOCATABLE_WORD_OFFSETS = [
    1, 4, 23, 39, 48, 86, 91, 96, 238, 251, 264, 287, 290, 295, 298, 302, 329, 344, 393
]


def generate_tile_engine_binary(base=DEFAULT_TILE_ENGINE_BASE, tilemap_base=DEFAULT_TILEMAP_BASE):
    """
    Generates a 414-byte relocatable Z80 machine code binary for the 16x16 Tile Engine.
    
    Args:
        base: Starting RAM address for the tile engine routine (default: 45000).
        tilemap_base: Base RAM address where 16x16 tile data lives (default: 40000).
    
    Returns:
        bytearray containing the ready-to-execute Z80 machine code.
    """
    base = int(base) & 0xFFFF
    tilemap_base = int(tilemap_base) & 0xFFFF

    data = bytearray(_TEMPLATE_BYTES_64000)
    delta = (base - 64000) & 0xFFFF

    # Relocate all internal absolute memory pointers to target base
    for off in _RELOCATABLE_WORD_OFFSETS:
        val = data[off] | (data[off + 1] << 8)
        val = (val + delta) & 0xFFFF
        data[off] = val & 0xFF
        data[off + 1] = (val >> 8) & 0xFF

    # Write target tilemap base address into the parameter block at offset 12
    data[OFFSET_TILEMAP_BASE] = tilemap_base & 0xFF
    data[OFFSET_TILEMAP_BASE + 1] = (tilemap_base >> 8) & 0xFF

    return data
