"""
GEM / Mac OS 6 WIMP Graphical User Interface for Sinclair ZX Spectrum & BasinPy
Runs directly on the 256x192 ZX Spectrum display in crisp monochrome (black ink on white paper).
Controls: AMX Mouse (with Kempston fallback) & Keyboard.

Features:
- Mac OS System 6 / GEM style desktop with alternating stipple background (0xAA, 0x55).
- Top Menu Bar: FILE (New Basic, New Text, Cut, Copy, Paste), SYSTEM (Refresh, Tidy, Empty Bin, Quit),
  plus custom menus via BASIC MENU command. Dynamic context matching for active applications (e.g. Text Editor).
- Desktop Icons:
  * Floppy Drives (Drives 1..4)
  * Microdrives (Drives 1..8, with Microdrive 8 dedicated to temp storage 'wimp.mdr')
  * Attached Tape
  * Trash Bin (drag/drop delete and Empty Bin)
  * Desk Accessories: Text Editor, Clock (with alarm), Calculator, Calendar (simple diary),
    Card Index, 15/8 Slide Puzzle.
- Sizable Framed Windows:
  * 1px border, Mac OS horizontal striped title bar.
  * Top-left Grab Handle: only the wireframe outline moves during drag; window redraws on mouse release.
  * Top-right Close Box [X].
  * Bottom-right Resize Drag Icon: only resize outline moves during drag; window redraws on release.
  * Client canvas strictly clipped to window interior.
- Drive Directory Windows:
  * Opens on double-click of drive icon.
  * Double-click on .zxb or .bas loads program into BasinPy and executes RUN.
  * Right-click on .zxb or .bas brings up context popup: Edit (load & list for editing), Delete, Cut, Copy, Paste.
- BASIC Extensions:
  * GUI, GUI ON, GUI OFF
  * WINDOW (OPEN, CLOSE, MOVE, SIZE, SELECT, CLS, PRINT)
  * MENU (ADD, ITEM, CLEAR, ON, OFF)
  * MOUSE (query x, y, buttons, context code)
  * ICON (DEF, DRAW, CLEAR)
  * ICONED (interactive 16x16 icon designer styled like tile_editor.py)
"""

import os
import sys
import time
import math
import re
import pygame

# ------------------------------------------------------------------------------
# Screen & Graphic Constants (Timex Sinclair 2068 Hi-Res 512x192 Mode 6)
# ------------------------------------------------------------------------------
SCREEN_W = 512
SCREEN_H = 192
MENU_BAR_H = 10
CHAR_W = 8
CHAR_H = 8
COLS = 64
ROWS = 24

C_BLACK = (0, 0, 0)
C_WHITE = (255, 255, 255)
C_GRAY = (128, 128, 128)
C_DARK_GRAY = (64, 64, 64)
C_LIGHT_GRAY = (192, 192, 192)
C_CYAN = (0, 192, 192)

# Context Codes for MOUSE command
CTX_DESKTOP = 0
CTX_CLIENT = 1
CTX_TITLE = 2
CTX_CLOSE = 3
CTX_RESIZE = 4
CTX_MENU_BAR = 5
CTX_MENU_ITEM = 6
CTX_ICON = 7
CTX_SCROLL = 8

def get_main_context():
    """Safely retrieves live BasinPy / BetaBasic runtime module context."""
    for mod_name in ('__main__', 'main', 'BetaBasic'):
        mod = sys.modules.get(mod_name)
        if mod is not None and hasattr(mod, 'program'):
            return mod
    try:
        import BetaBasic
        return BetaBasic
    except Exception:
        try:
            import main
            return main
        except Exception:
            return None


# ------------------------------------------------------------------------------
# 8x8 Monochrome Font Data (ZX Spectrum ROM fallback)
# ------------------------------------------------------------------------------
# Embedded standard 8x8 font bitmaps for printable ASCII (32..127)
# 8 bytes per character.
FONT_8X8 = {
    ' ': [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
    '!': [0x18, 0x18, 0x18, 0x18, 0x18, 0x00, 0x18, 0x00],
    '"': [0x66, 0x66, 0x66, 0x00, 0x00, 0x00, 0x00, 0x00],
    '#': [0x66, 0x66, 0xFF, 0x66, 0xFF, 0x66, 0x66, 0x00],
    '$': [0x18, 0x3E, 0x60, 0x3C, 0x06, 0x7C, 0x18, 0x00],
    '%': [0x62, 0x66, 0x0C, 0x18, 0x30, 0x66, 0x46, 0x00],
    '&': [0x38, 0x6C, 0x38, 0x76, 0xDC, 0xCC, 0x76, 0x00],
    "'": [0x18, 0x18, 0x30, 0x00, 0x00, 0x00, 0x00, 0x00],
    '(': [0x0C, 0x18, 0x30, 0x30, 0x30, 0x18, 0x0C, 0x00],
    ')': [0x30, 0x18, 0x0C, 0x0C, 0x0C, 0x18, 0x30, 0x00],
    '*': [0x00, 0x66, 0x3C, 0xFF, 0x3C, 0x66, 0x00, 0x00],
    '+': [0x00, 0x18, 0x18, 0x7E, 0x18, 0x18, 0x00, 0x00],
    ',': [0x00, 0x00, 0x00, 0x00, 0x18, 0x18, 0x30, 0x00],
    '-': [0x00, 0x00, 0x00, 0x7E, 0x00, 0x00, 0x00, 0x00],
    '.': [0x00, 0x00, 0x00, 0x00, 0x00, 0x18, 0x18, 0x00],
    '/': [0x06, 0x0C, 0x18, 0x30, 0x60, 0xC0, 0x80, 0x00],
    '0': [0x3C, 0x66, 0x6E, 0x76, 0x66, 0x66, 0x3C, 0x00],
    '1': [0x18, 0x38, 0x18, 0x18, 0x18, 0x18, 0x7E, 0x00],
    '2': [0x3C, 0x66, 0x06, 0x0C, 0x18, 0x30, 0x7E, 0x00],
    '3': [0x3C, 0x66, 0x06, 0x1C, 0x06, 0x66, 0x3C, 0x00],
    '4': [0x0C, 0x1C, 0x3C, 0x6C, 0xFE, 0x0C, 0x0C, 0x00],
    '5': [0x7E, 0x60, 0x7C, 0x06, 0x06, 0x66, 0x3C, 0x00],
    '6': [0x1C, 0x30, 0x60, 0x7C, 0x66, 0x66, 0x3C, 0x00],
    '7': [0x7E, 0x06, 0x0C, 0x18, 0x30, 0x30, 0x30, 0x00],
    '8': [0x3C, 0x66, 0x66, 0x3C, 0x66, 0x66, 0x3C, 0x00],
    '9': [0x3C, 0x66, 0x66, 0x3E, 0x06, 0x0C, 0x38, 0x00],
    ':': [0x00, 0x18, 0x18, 0x00, 0x18, 0x18, 0x00, 0x00],
    ';': [0x00, 0x18, 0x18, 0x00, 0x18, 0x18, 0x30, 0x00],
    '<': [0x0C, 0x18, 0x30, 0x60, 0x30, 0x18, 0x0C, 0x00],
    '=': [0x00, 0x7E, 0x00, 0x7E, 0x00, 0x00, 0x00, 0x00],
    '>': [0x30, 0x18, 0x0C, 0x06, 0x0C, 0x18, 0x30, 0x00],
    '?': [0x3C, 0x66, 0x06, 0x0C, 0x18, 0x00, 0x18, 0x00],
    '@': [0x3C, 0x66, 0x6E, 0x6E, 0x60, 0x62, 0x3C, 0x00],
    'A': [0x18, 0x3C, 0x66, 0x66, 0x7E, 0x66, 0x66, 0x00],
    'B': [0x7C, 0x66, 0x66, 0x7C, 0x66, 0x66, 0x7C, 0x00],
    'C': [0x3C, 0x66, 0x60, 0x60, 0x60, 0x66, 0x3C, 0x00],
    'D': [0x78, 0x6C, 0x66, 0x66, 0x66, 0x6C, 0x78, 0x00],
    'E': [0x7E, 0x60, 0x60, 0x7C, 0x60, 0x60, 0x7E, 0x00],
    'F': [0x7E, 0x60, 0x60, 0x7C, 0x60, 0x60, 0x60, 0x00],
    'G': [0x3C, 0x66, 0x60, 0x6E, 0x66, 0x66, 0x3E, 0x00],
    'H': [0x66, 0x66, 0x66, 0x7E, 0x66, 0x66, 0x66, 0x00],
    'I': [0x3C, 0x18, 0x18, 0x18, 0x18, 0x18, 0x3C, 0x00],
    'J': [0x1E, 0x06, 0x06, 0x06, 0x06, 0x66, 0x3C, 0x00],
    'K': [0x66, 0x6C, 0x78, 0x70, 0x78, 0x6C, 0x66, 0x00],
    'L': [0x60, 0x60, 0x60, 0x60, 0x60, 0x60, 0x7E, 0x00],
    'M': [0x63, 0x77, 0x7F, 0x6B, 0x63, 0x63, 0x63, 0x00],
    'N': [0x66, 0x76, 0x7E, 0x7E, 0x6E, 0x66, 0x66, 0x00],
    'O': [0x3C, 0x66, 0x66, 0x66, 0x66, 0x66, 0x3C, 0x00],
    'P': [0x7C, 0x66, 0x66, 0x7C, 0x60, 0x60, 0x60, 0x00],
    'Q': [0x3C, 0x66, 0x66, 0x66, 0x6A, 0x6C, 0x36, 0x00],
    'R': [0x7C, 0x66, 0x66, 0x7C, 0x6C, 0x66, 0x66, 0x00],
    'S': [0x3C, 0x66, 0x60, 0x3C, 0x06, 0x66, 0x3C, 0x00],
    'T': [0x7E, 0x18, 0x18, 0x18, 0x18, 0x18, 0x18, 0x00],
    'U': [0x66, 0x66, 0x66, 0x66, 0x66, 0x66, 0x3C, 0x00],
    'V': [0x66, 0x66, 0x66, 0x66, 0x66, 0x3C, 0x18, 0x00],
    'W': [0x63, 0x63, 0x63, 0x6B, 0x7F, 0x77, 0x63, 0x00],
    'X': [0x66, 0x66, 0x3C, 0x18, 0x3C, 0x66, 0x66, 0x00],
    'Y': [0x66, 0x66, 0x66, 0x3C, 0x18, 0x18, 0x18, 0x00],
    'Z': [0x7E, 0x06, 0x0C, 0x18, 0x30, 0x60, 0x7E, 0x00],
    '[': [0x3C, 0x30, 0x30, 0x30, 0x30, 0x30, 0x3C, 0x00],
    '\\': [0xC0, 0x60, 0x30, 0x18, 0x0C, 0x06, 0x02, 0x00],
    ']': [0x3C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x3C, 0x00],
    '^': [0x18, 0x3C, 0x66, 0x00, 0x00, 0x00, 0x00, 0x00],
    '_': [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xFF, 0x00],
    '`': [0x30, 0x18, 0x0C, 0x00, 0x00, 0x00, 0x00, 0x00],
    'a': [0x00, 0x00, 0x3C, 0x06, 0x3E, 0x66, 0x3E, 0x00],
    'b': [0x60, 0x60, 0x7C, 0x66, 0x66, 0x66, 0x7C, 0x00],
    'c': [0x00, 0x00, 0x3C, 0x66, 0x60, 0x66, 0x3C, 0x00],
    'd': [0x06, 0x06, 0x3E, 0x66, 0x66, 0x66, 0x3E, 0x00],
    'e': [0x00, 0x00, 0x3C, 0x66, 0x7E, 0x60, 0x3C, 0x00],
    'f': [0x0E, 0x18, 0x7E, 0x18, 0x18, 0x18, 0x18, 0x00],
    'g': [0x00, 0x00, 0x3E, 0x66, 0x66, 0x3E, 0x06, 0x3C],
    'h': [0x60, 0x60, 0x7C, 0x66, 0x66, 0x66, 0x66, 0x00],
    'i': [0x18, 0x00, 0x38, 0x18, 0x18, 0x18, 0x3C, 0x00],
    'j': [0x06, 0x00, 0x0E, 0x06, 0x06, 0x66, 0x3C, 0x00],
    'k': [0x60, 0x60, 0x66, 0x6C, 0x78, 0x6C, 0x66, 0x00],
    'l': [0x38, 0x18, 0x18, 0x18, 0x18, 0x18, 0x3C, 0x00],
    'm': [0x00, 0x00, 0x66, 0x7F, 0x6B, 0x63, 0x63, 0x00],
    'n': [0x00, 0x00, 0x7C, 0x66, 0x66, 0x66, 0x66, 0x00],
    'o': [0x00, 0x00, 0x3C, 0x66, 0x66, 0x66, 0x3C, 0x00],
    'p': [0x00, 0x00, 0x7C, 0x66, 0x66, 0x7C, 0x60, 0x60],
    'q': [0x00, 0x00, 0x3E, 0x66, 0x66, 0x3E, 0x06, 0x06],
    'r': [0x00, 0x00, 0x7C, 0x66, 0x60, 0x60, 0x60, 0x00],
    's': [0x00, 0x00, 0x3E, 0x60, 0x3C, 0x06, 0x7C, 0x00],
    't': [0x18, 0x18, 0x7E, 0x18, 0x18, 0x18, 0x0E, 0x00],
    'u': [0x00, 0x00, 0x66, 0x66, 0x66, 0x66, 0x3E, 0x00],
    'v': [0x00, 0x00, 0x66, 0x66, 0x66, 0x3C, 0x18, 0x00],
    'w': [0x00, 0x00, 0x63, 0x6B, 0x7F, 0x36, 0x36, 0x00],
    'x': [0x00, 0x00, 0x66, 0x3C, 0x18, 0x3C, 0x66, 0x00],
    'y': [0x00, 0x00, 0x66, 0x66, 0x66, 0x3E, 0x06, 0x3C],
    'z': [0x00, 0x00, 0x7E, 0x0C, 0x18, 0x30, 0x7E, 0x00],
    '{': [0x0E, 0x18, 0x18, 0x70, 0x18, 0x18, 0x0E, 0x00],
    '|': [0x18, 0x18, 0x18, 0x00, 0x18, 0x18, 0x18, 0x00],
    '}': [0x70, 0x18, 0x18, 0x0E, 0x18, 0x18, 0x70, 0x00],
    '~': [0x76, 0xDC, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
    '±': [0x18, 0x18, 0x7E, 0x18, 0x18, 0x00, 0x7E, 0x00],
}


CPM_5X8_FONT = {
    ' ': (0, 0, 0, 0, 0, 0, 0, 0),
    '!': (4, 4, 4, 4, 4, 0, 4, 0),
    '"': (10, 10, 10, 0, 0, 0, 0, 0),
    '#': (10, 10, 31, 10, 31, 10, 10, 0),
    '$': (4, 15, 20, 14, 5, 30, 4, 0),
    '%': (18, 19, 8, 4, 2, 25, 9, 0),
    '&': (12, 18, 18, 12, 21, 18, 13, 0),
    "'": (12, 4, 8, 0, 0, 0, 0, 0),
    '(': (2, 4, 8, 8, 8, 4, 2, 0),
    ')': (8, 4, 2, 2, 2, 4, 8, 0),
    '*': (0, 10, 4, 31, 4, 10, 0, 0),
    '+': (0, 4, 4, 31, 4, 4, 0, 0),
    ',': (0, 0, 0, 0, 0, 6, 4, 8),
    '-': (0, 0, 0, 31, 0, 0, 0, 0),
    '.': (0, 0, 0, 0, 0, 6, 6, 0),
    '/': (0, 1, 2, 4, 8, 16, 0, 0),
    '0': (14, 17, 19, 21, 25, 17, 14, 0),
    '1': (4, 12, 4, 4, 4, 4, 14, 0),
    '2': (14, 17, 1, 6, 8, 16, 31, 0),
    '3': (31, 2, 4, 6, 1, 17, 14, 0),
    '4': (2, 6, 10, 18, 31, 2, 2, 0),
    '5': (31, 16, 30, 1, 1, 17, 14, 0),
    '6': (6, 8, 16, 30, 17, 17, 14, 0),
    '7': (31, 1, 2, 4, 8, 8, 8, 0),
    '8': (14, 17, 17, 14, 17, 17, 14, 0),
    '9': (14, 17, 17, 15, 1, 2, 12, 0),
    ':': (0, 6, 6, 0, 6, 6, 0, 0),
    ';': (0, 6, 6, 0, 6, 4, 8, 0),
    '<': (1, 2, 4, 8, 4, 2, 1, 0),
    '=': (0, 31, 0, 0, 31, 0, 0, 0),
    '>': (16, 8, 4, 2, 4, 8, 16, 0),
    '?': (14, 17, 1, 2, 4, 0, 4, 0),
    '@': (14, 17, 1, 13, 21, 21, 14, 0),
    'A': (14, 17, 17, 31, 17, 17, 17, 0),
    'B': (30, 17, 17, 30, 17, 17, 30, 0),
    'C': (14, 17, 16, 16, 16, 17, 14, 0),
    'D': (28, 18, 17, 17, 17, 18, 28, 0),
    'E': (31, 16, 16, 30, 16, 16, 31, 0),
    'F': (31, 16, 16, 30, 16, 16, 16, 0),
    'G': (14, 17, 16, 23, 17, 17, 14, 0),
    'H': (17, 17, 17, 31, 17, 17, 17, 0),
    'I': (14, 4, 4, 4, 4, 4, 14, 0),
    'J': (1, 1, 1, 1, 1, 17, 14, 0),
    'K': (17, 18, 20, 24, 20, 18, 17, 0),
    'L': (16, 16, 16, 16, 16, 16, 31, 0),
    'M': (17, 27, 21, 21, 17, 17, 17, 0),
    'N': (17, 25, 21, 19, 17, 17, 17, 0),
    'O': (14, 17, 17, 17, 17, 17, 14, 0),
    'P': (30, 17, 17, 30, 16, 16, 16, 0),
    'Q': (14, 17, 17, 17, 21, 18, 13, 0),
    'R': (30, 17, 17, 30, 20, 18, 17, 0),
    'S': (14, 17, 16, 14, 1, 17, 14, 0),
    'T': (31, 4, 4, 4, 4, 4, 4, 0),
    'U': (17, 17, 17, 17, 17, 17, 14, 0),
    'V': (17, 17, 17, 17, 17, 10, 4, 0),
    'W': (17, 17, 17, 21, 21, 27, 17, 0),
    'X': (17, 17, 10, 4, 10, 17, 17, 0),
    'Y': (17, 17, 10, 4, 4, 4, 4, 0),
    'Z': (31, 1, 2, 4, 8, 16, 31, 0),
    '[': (14, 8, 8, 8, 8, 8, 14, 0),
    '\\': (0, 16, 8, 4, 2, 1, 0, 0),
    ']': (14, 2, 2, 2, 2, 2, 14, 0),
    '^': (4, 10, 17, 0, 0, 0, 0, 0),
    '_': (0, 0, 0, 0, 0, 0, 31, 0),
    '`': (8, 4, 2, 0, 0, 0, 0, 0),
    'a': (0, 0, 14, 1, 15, 17, 15, 0),
    'b': (16, 16, 22, 25, 17, 17, 30, 0),
    'c': (0, 0, 14, 16, 16, 17, 14, 0),
    'd': (1, 1, 13, 19, 17, 17, 15, 0),
    'e': (0, 0, 14, 17, 31, 16, 14, 0),
    'f': (6, 9, 8, 28, 8, 8, 8, 0),
    'g': (0, 0, 15, 17, 17, 15, 1, 14),
    'h': (16, 16, 22, 25, 17, 17, 17, 0),
    'i': (4, 0, 12, 4, 4, 4, 14, 0),
    'j': (2, 0, 6, 2, 2, 2, 18, 12),
    'k': (16, 16, 18, 20, 24, 20, 18, 0),
    'l': (12, 4, 4, 4, 4, 4, 14, 0),
    'm': (0, 0, 26, 21, 21, 17, 17, 0),
    'n': (0, 0, 22, 25, 17, 17, 17, 0),
    'o': (0, 0, 14, 17, 17, 17, 14, 0),
    'p': (0, 0, 30, 17, 17, 30, 16, 16),
    'q': (0, 0, 15, 17, 17, 15, 1, 1),
    'r': (0, 0, 22, 25, 16, 16, 16, 0),
    's': (0, 0, 15, 16, 14, 1, 30, 0),
    't': (8, 8, 28, 8, 8, 9, 6, 0),
    'u': (0, 0, 17, 17, 17, 19, 13, 0),
    'v': (0, 0, 17, 17, 17, 10, 4, 0),
    'w': (0, 0, 17, 17, 21, 21, 10, 0),
    'x': (0, 0, 17, 10, 4, 10, 17, 0),
    'y': (0, 0, 17, 17, 17, 15, 1, 14),
    'z': (0, 0, 31, 2, 4, 8, 31, 0),
    '{': (2, 4, 4, 8, 4, 4, 2, 0),
    '|': (4, 4, 4, 4, 4, 4, 4, 0),
    '}': (8, 4, 4, 2, 4, 4, 8, 0),
    '~': (0, 13, 22, 0, 0, 0, 0, 0),
    '±': (8, 28, 8, 0, 28, 0, 0, 0),
}



_FONT_CACHE = {}

def draw_mono_text(surf, text, x, y, fg=C_BLACK, bg=None):
    """Draws 8x8 64-column bitmap text onto surface with caching."""
    cur_x = x
    for ch in str(text):
        cache_key = (ch, fg, bg)
        if cache_key not in _FONT_CACHE:
            bmp8 = FONT_8X8.get(ch, FONT_8X8.get(' ', [0] * 8))
            ch_surf = pygame.Surface((8, 8), pygame.SRCALPHA)
            if bg is not None:
                ch_surf.fill(bg)
            for r in range(8):
                row_bits = bmp8[r] if r < len(bmp8) else 0
                for c in range(8):
                    if (row_bits >> (7 - c)) & 1:
                        ch_surf.set_at((c, r), fg)
            _FONT_CACHE[cache_key] = ch_surf
            
        surf.blit(_FONT_CACHE[cache_key], (cur_x, y))
        cur_x += CHAR_W


def draw_mini_text(surf, text, x, y, fg=C_BLACK, bg=None):
    """Draws 8x8 64-column bitmap text."""
    return draw_mono_text(surf, text, x, y, fg=fg, bg=bg)


# ------------------------------------------------------------------------------
# 16x16 Monochrome Icon Bitmaps (32 bytes per icon)
# ------------------------------------------------------------------------------
DEFAULT_ICONS = {
    "floppy": [
        0x7F, 0xFE,  # ##############.
        0x80, 0x01,  # #............#
        0x9F, 0xF9,  # #.##########.# (Metal shutter)
        0x9F, 0xF9,  # #.##########.#
        0x90, 0x09,  # #.#........#.# (Shutter hole)
        0x90, 0x09,  # #.#........#.#
        0x9F, 0xF9,  # #.##########.#
        0x80, 0x01,  # #............#
        0xBF, 0xFD,  # #.############
        0xA0, 0x05,  # #.#..........# (Label area)
        0xA0, 0x05,  # #.#..........#
        0xA0, 0x05,  # #.#..........#
        0xBF, 0xFD,  # #.############
        0x80, 0x01,  # #............#
        0x7F, 0xFE,  # ##############.
        0x00, 0x00,
    ],
    "microdrive": [
        0x3F, 0xFC,  # ..############..
        0x40, 0x02,  # .#............#.
        0x4F, 0xF2,  # .#.##########.#. (Label)
        0x49, 0x92,  # .#.#..##..##..#.
        0x4F, 0xF2,  # .#.##########.#.
        0x40, 0x02,  # .#............#.
        0x43, 0xC2,  # .#...####.....#. (Drive head slot)
        0x42, 0x42,  # .#...#..#.....#.
        0x42, 0x42,  # .#...#..#.....#.
        0x43, 0xC2,  # .#...####.....#.
        0x40, 0x02,  # .#............#.
        0x41, 0x82,  # .#....##......#. (Spool window)
        0x41, 0x82,  # .#....##......#.
        0x40, 0x02,  # .#............#.
        0x3F, 0xFC,  # ..############..
        0x00, 0x00,
    ],
    "tape": [
        0x7F, 0xFE,  # ##############.
        0x80, 0x01,  # #............#
        0x9F, 0xF9,  # #.##########.#
        0x90, 0x09,  # #.#........#.#
        0x92, 0x49,  # #.#.#....#.#.# (Two reels)
        0x97, 0xE9,  # #.#.######.#.#
        0x92, 0x49,  # #.#.#....#.#.#
        0x90, 0x09,  # #.#........#.#
        0x9F, 0xF9,  # #.##########.#
        0x80, 0x01,  # #............#
        0x83, 0xC1,  # #...######...# (Trapezoid head base)
        0x82, 0x41,  # #...#....#...#
        0x7C, 0x3E,  # .####....####.
        0x00, 0x00,
        0x00, 0x00,
        0x00, 0x00,
    ],
    "trash": [
        0x0F, 0xF0,  # ....########.... (Handle)
        0x03, 0xC0,  # ......####......
        0x7F, 0xFE,  # ################ (Rim)
        0x40, 0x02,  # .#............#.
        0x20, 0x04,  # ..#..........#..
        0x24, 0x24,  # ..#.#..#..#..#.. (Ribs)
        0x24, 0x24,  # ..#.#..#..#..#..
        0x24, 0x24,  # ..#.#..#..#..#..
        0x24, 0x24,  # ..#.#..#..#..#..
        0x24, 0x24,  # ..#.#..#..#..#..
        0x24, 0x24,  # ..#.#..#..#..#..
        0x24, 0x24,  # ..#.#..#..#..#..
        0x20, 0x04,  # ..#..........#..
        0x1F, 0xF8,  # ...##########... (Base)
        0x00, 0x00,
        0x00, 0x00,
    ],
    "text_editor": [
        0x3F, 0xF0,  # ..##########....
        0x20, 0x18,  # ..#........##... (Dog-ear)
        0x20, 0x1C,  # ..#........###..
        0x2F, 0xFC,  # ..#.......####..
        0x20, 0x04,  # ..#..........#..
        0x27, 0xE4,  # ..#.######...#.. (Lines of text)
        0x20, 0x04,  # ..#..........#..
        0x27, 0xE4,  # ..#.######...#..
        0x20, 0x04,  # ..#..........#..
        0x27, 0xC4,  # ..#.#####....#..
        0x20, 0x04,  # ..#..........#..
        0x23, 0x84,  # ..#.###......#..
        0x20, 0x04,  # ..#..........#..
        0x3F, 0xFC,  # ..############..
        0x00, 0x00,
        0x00, 0x00,
    ],
    "clock": [
        0x07, 0xE0,  # .....######.....
        0x18, 0x18,  # ...##......##... (Bell / top)
        0x30, 0x0C,  # ..#..........#..
        0x60, 0xC6,  # .#....##......#.
        0x41, 0x82,  # #.....##.......#
        0x41, 0x82,  # #.....##.......#
        0x41, 0xFE,  # #.....########.# (Hands)
        0x40, 0x02,  # #..............#
        0x40, 0x02,  # #..............#
        0x60, 0x06,  # .#............#.
        0x30, 0x0C,  # ..#..........#..
        0x18, 0x18,  # ...##......##...
        0x07, 0xE0,  # .....######.....
        0x0C, 0x30,  # ....##....##.... (Legs)
        0x00, 0x00,
        0x00, 0x00,
    ],
    "calculator": [
        0x3F, 0xFC,  # ..############..
        0x40, 0x02,  # .#............#.
        0x5F, 0xFA,  # .#.##########.#. (LCD display)
        0x50, 0x0A,  # .#.#..123456#.#.
        0x5F, 0xFA,  # .#.##########.#.
        0x40, 0x02,  # .#............#.
        0x49, 0x92,  # .#.#..#..#..#. (Buttons)
        0x40, 0x02,  # .#............#.
        0x49, 0x92,  # .#.#..#..#..#.
        0x40, 0x02,  # .#............#.
        0x49, 0x92,  # .#.#..#..#..#.
        0x40, 0x02,  # .#............#.
        0x49, 0x92,  # .#.#..#..#..#.
        0x40, 0x02,  # .#............#.
        0x3F, 0xFC,  # ..############..
        0x00, 0x00,
    ],
    "calendar": [
        0x24, 0x24,  # ..#..#..#..#.. (Binder rings)
        0x7F, 0xFE,  # ################
        0x40, 0x02,  # #..............#
        0x7F, 0xFE,  # ################ (Header bar)
        0x40, 0x02,  # #..............#
        0x49, 0x92,  # #..#..#..#..#..# (Date grid)
        0x40, 0x02,  # #..............#
        0x49, 0x92,  # #..#..#..#..#..#
        0x40, 0x02,  # #..............#
        0x49, 0x92,  # #..#..#..#..#..#
        0x40, 0x02,  # #..............#
        0x49, 0x92,  # #..#..#..#..#..#
        0x40, 0x02,  # #..............#
        0x7F, 0xFE,  # ################
        0x00, 0x00,
        0x00, 0x00,
    ],
    "card_index": [
        0x0F, 0xF0,  # ....########.... (Card tab)
        0x08, 0x10,  # ....#......#....
        0x7F, 0xFE,  # ################ (Card box)
        0x40, 0x02,  # #..............#
        0x5F, 0xFA,  # #.############.# (Top card)
        0x50, 0x0A,  # #.#..........#.#
        0x57, 0xEA,  # #.#.########.#.# (Card lines)
        0x50, 0x0A,  # #.#..........#.#
        0x57, 0xEA,  # #.#.########.#.#
        0x50, 0x0A,  # #.#..........#.#
        0x5F, 0xFA,  # #.############.#
        0x43, 0xC2,  # #...######...# (Drawer pull)
        0x43, 0xC2,  # #...######...#
        0x7F, 0xFE,  # ################
        0x00, 0x00,
        0x00, 0x00,
    ],
    "puzzle": [
        0x7F, 0xFE,  # ################
        0x40, 0x02,  # #..............#
        0x47, 0xE2,  # #.###..###...#.# (15 Puzzle grid)
        0x44, 0x22,  # #.#.1..#.2...#.#
        0x47, 0xE2,  # #.###..###...#.#
        0x40, 0x02,  # #..............#
        0x47, 0xE2,  # #.###........#.#
        0x44, 0x22,  # #.#.3..[   ].#.#
        0x47, 0xE2,  # #.###........#.#
        0x40, 0x02,  # #..............#
        0x7F, 0xFE,  # ################
        0x00, 0x00,
        0x00, 0x00,
        0x00, 0x00,
        0x00, 0x00,
        0x00, 0x00,
    ],
    "basic_prog": [
        0x3F, 0xF0,  # ..##########....
        0x20, 0x18,  # ..#........##...
        0x20, 0x1C,  # ..#........###..
        0x2F, 0xFC,  # ..#.......####..
        0x20, 0x04,  # ..#..........#..
        0x23, 0x84,  # ..#..BAS.....#..
        0x22, 0x84,  # ..#..B.S.....#..
        0x23, 0x84,  # ..#..BAS.....#..
        0x20, 0x04,  # ..#..........#..
        0x27, 0xE4,  # ..#.######...#..
        0x20, 0x04,  # ..#..........#..
        0x27, 0xE4,  # ..#.######...#..
        0x20, 0x04,  # ..#..........#..
        0x3F, 0xFC,  # ..############..
        0x00, 0x00,
        0x00, 0x00,
    ],
    "data_file": [
        0x3F, 0xF0,  # ..##########....
        0x20, 0x18,  # ..#........##...
        0x20, 0x1C,  # ..#........###..
        0x2F, 0xFC,  # ..#.......####..
        0x20, 0x04,  # ..#..........#..
        0x21, 0x04,  # ..#...0101...#..
        0x22, 0x84,  # ..#..10101...#..
        0x21, 0x04,  # ..#...0101...#..
        0x20, 0x04,  # ..#..........#..
        0x27, 0xE4,  # ..#.######...#..
        0x20, 0x04,  # ..#..........#..
        0x27, 0xE4,  # ..#.######...#..
        0x20, 0x04,  # ..#..........#..
        0x3F, 0xFC,  # ..############..
        0x00, 0x00,
        0x00, 0x00,
    ]
}


def draw_icon_16x16(surf, icon_data, x, y, invert=False, bg=C_CYAN, fg=C_BLACK):
    """Draws 16x16 monochrome icon bitmap onto surface with cyan paper and black ink."""
    for r in range(16):
        if r * 2 + 1 < len(icon_data):
            w = (icon_data[r * 2] << 8) | icon_data[r * 2 + 1]
        elif r < len(icon_data):
            w = icon_data[r]
        else:
            w = 0
        for c in range(16):
            px = x + c
            py = y + r
            if 0 <= px < surf.get_width() and 0 <= py < surf.get_height():
                is_set = bool(w & (1 << (15 - c)))
                if invert:
                    col = fg if not is_set else bg
                else:
                    col = fg if is_set else bg
                if col is not None:
                    surf.set_at((px, py), col)


# ------------------------------------------------------------------------------
# WIMPIcon Representation
# ------------------------------------------------------------------------------
class WIMPIcon:
    def __init__(self, icon_id, title, icon_type, x, y, on_open=None, metadata=None):
        self.icon_id = icon_id
        self.title = title
        self.icon_type = icon_type  # key in DEFAULT_ICONS or custom bitmap
        self.x = x
        self.y = y
        self.w = 32
        self.h = 28
        self.selected = False
        self.on_open = on_open
        self.metadata = metadata or {}

    @property
    def label(self):
        return self.title

    @label.setter
    def label(self, val):
        self.title = val

    def get_rect(self):
        return pygame.Rect(self.x, self.y, self.w, self.h)

    def draw(self, surf):
        # 16x16 icon centered horizontally at top
        icon_x = self.x + (self.w - 16) // 2
        icon_y = self.y
        bmp = DEFAULT_ICONS.get(self.icon_type, DEFAULT_ICONS["data_file"])
        if isinstance(self.icon_type, (list, bytearray)):
            bmp = self.icon_type
        draw_icon_16x16(surf, bmp, icon_x, icon_y, invert=self.selected)

        # Label underneath (8x8 font, 64-column mode)
        lbl = self.title[:12]
        lbl_w = len(lbl) * CHAR_W
        lbl_x = max(0, min(SCREEN_W - lbl_w - 2, self.x + (self.w - lbl_w) // 2))
        lbl_y = min(SCREEN_H - 10, self.y + 18)
        if self.selected:
            pygame.draw.rect(surf, C_BLACK, (lbl_x - 1, lbl_y - 1, lbl_w + 2, 9))
            draw_mono_text(surf, lbl, lbl_x, lbl_y, fg=C_CYAN, bg=C_BLACK)
        else:
            draw_mono_text(surf, lbl, lbl_x, lbl_y, fg=C_BLACK, bg=None)


# ------------------------------------------------------------------------------
# WIMPWindow: Resizable Framed Window with Clipped Canvas
# ------------------------------------------------------------------------------
class WIMPWindow:
    def __init__(self, win_id, title, x, y, w, h, desktop=None):
        self.win_id = win_id
        self.title = title
        self.x = max(0, min(SCREEN_W - 40, x))
        self.y = max(MENU_BAR_H, min(SCREEN_H - 30, y))
        self.w = max(48, min(SCREEN_W, w))
        self.h = max(32, min(SCREEN_H - MENU_BAR_H, h))
        self.desktop = desktop
        self.min_w = 48
        self.min_h = 32
        self.visible = True
        self.active = False
        self.dirty = True

        # Window interior client canvas
        self.client_surf = None
        self._realloc_client()

        # Text line buffer for standard WINDOW PRINT output
        self.text_lines = []
        self.scroll_y = 0

        # Custom app instance if this window belongs to a desk accessory
        self.app = None

    def _realloc_client(self):
        cw = max(1, self.w - 2)
        ch = max(1, self.h - 11)
        self.client_surf = pygame.Surface((cw, ch))
        self.client_surf.fill(C_CYAN)
        self.dirty = True

    def set_size(self, w, h):
        self.w = max(self.min_w, min(SCREEN_W - self.x, w))
        self.h = max(self.min_h, min(SCREEN_H - self.y, h))
        self._realloc_client()

    def set_pos(self, x, y):
        self.x = max(0, min(SCREEN_W - 32, x))
        self.y = max(MENU_BAR_H, min(SCREEN_H - 24, y))
        self.dirty = True

    def get_outer_rect(self):
        return pygame.Rect(self.x, self.y, self.w, self.h)

    def get_title_rect(self):
        return pygame.Rect(self.x, self.y, self.w, 10)

    def get_close_rect(self):
        return pygame.Rect(self.x + self.w - 9, self.y + 1, 8, 8)

    def get_grab_rect(self):
        return pygame.Rect(self.x + 1, self.y + 1, 9, 8)

    def get_resize_rect(self):
        return pygame.Rect(self.x + self.w - 9, self.y + self.h - 9, 8, 8)

    def get_content_height(self):
        if self.app and hasattr(self.app, 'get_content_height'):
            return self.app.get_content_height()
        elif self.app and hasattr(self.app, 'files'):
            return len(self.app.files) * 10 + 2
        elif self.app and hasattr(self.app, 'lines'):
            return len(self.app.lines) * 8 + 4
        elif self.app:
            return self.client_surf.get_height() if self.client_surf else 0
        else:
            return len(self.text_lines) * 8 + 2

    def can_scroll(self):
        if not self.client_surf:
            return False
        return self.get_content_height() > self.client_surf.get_height()

    def get_scroll_up_rect(self):
        return pygame.Rect(self.x + self.w - 10, self.y + 10, 9, 9)

    def get_scroll_down_rect(self):
        return pygame.Rect(self.x + self.w - 10, self.y + self.h - 18, 9, 9)

    def get_scroll_track_rect(self):
        track_y = self.y + 19
        track_h = max(0, (self.y + self.h - 18) - track_y)
        return pygame.Rect(self.x + self.w - 10, track_y, 9, track_h)

    def get_thumb_rect_y_h(self):
        track_rect = self.get_scroll_track_rect()
        if track_rect.height <= 0:
            return track_rect.y, 0
        content_h = self.get_content_height()
        visible_h = self.client_surf.get_height() if self.client_surf else max(1, self.h - 11)
        thumb_h = max(6, min(track_rect.height - 2, int(track_rect.height * (visible_h / float(content_h))))) if content_h > 0 else 6
        travel = track_rect.height - thumb_h
        max_s = self.get_max_scroll()
        ratio = (self.scroll_y / float(max_s)) if max_s > 0 else 0.0
        thumb_y = track_rect.y + int(ratio * travel)
        return thumb_y, thumb_h

    def get_max_scroll(self):
        content_h = self.get_content_height()
        visible_h = self.client_surf.get_height() if self.client_surf else max(1, self.h - 11)
        return max(0, content_h - visible_h)

    def get_scroll_step(self):
        if self.app and hasattr(self.app, 'scroll_step'):
            return self.app.scroll_step
        if self.app and hasattr(self.app, 'files'):
            return 10
        return 8

    def get_page_step(self):
        visible_h = self.client_surf.get_height() if self.client_surf else max(1, self.h - 11)
        step = self.get_scroll_step()
        return max(1, visible_h // step)

    def scroll_up(self, steps=1):
        step_sz = self.get_scroll_step()
        self.scroll_y = max(0, self.scroll_y - step_sz * steps)
        self.dirty = True
        if self.app and hasattr(self.app, 'dirty'):
            self.app.dirty = True

    def scroll_down(self, steps=1):
        step_sz = self.get_scroll_step()
        max_s = self.get_max_scroll()
        self.scroll_y = min(max_s, self.scroll_y + step_sz * steps)
        self.dirty = True
        if self.app and hasattr(self.app, 'dirty'):
            self.app.dirty = True

    def handle_track_click(self, mx, my):
        track_rect = self.get_scroll_track_rect()
        if track_rect.height <= 0:
            return
        thumb_y, thumb_h = self.get_thumb_rect_y_h()
        if my < thumb_y:
            self.scroll_up(steps=self.get_page_step())
        elif my > thumb_y + thumb_h:
            self.scroll_down(steps=self.get_page_step())
        elif self.desktop:
            self.desktop.drag_mode = "SCROLL_THUMB"
            self.desktop.drag_target = self
            self.desktop.drag_offset_y = my - thumb_y

    def get_client_rect(self):
        if self.can_scroll():
            return pygame.Rect(self.x + 1, self.y + 10, self.w - 11, self.h - 11)
        return pygame.Rect(self.x + 1, self.y + 10, self.w - 2, self.h - 11)

    def cls(self):
        if self.client_surf:
            self.client_surf.fill(C_CYAN)
        self.text_lines.clear()
        self.scroll_y = 0
        self.dirty = True

    def print_text(self, text):
        lines = str(text).split('\n')
        self.text_lines.extend(lines)
        # Cap lines
        if len(self.text_lines) > 200:
            self.text_lines = self.text_lines[-200:]
        self.dirty = True

    def render_content(self):
        """Renders client output (either app-specific or standard text lines)."""
        if self.app and hasattr(self.app, 'render'):
            self.app.render(self.client_surf)
        else:
            self.client_surf.fill(C_CYAN)
            line_h = 8
            y_offset = 1 - self.scroll_y
            for line in self.text_lines:
                if y_offset + line_h > 0 and y_offset < self.client_surf.get_height():
                    draw_mono_text(self.client_surf, line, 2, y_offset, C_BLACK, C_CYAN)
                y_offset += line_h

    def draw(self, surf):
        if not self.visible:
            return

        # 1. 1px black window frame with cyan background
        pygame.draw.rect(surf, C_CYAN, (self.x, self.y, self.w, self.h))
        pygame.draw.rect(surf, C_BLACK, (self.x, self.y, self.w, self.h), 1)

        # 2. Title bar (10 px high)
        pygame.draw.line(surf, C_BLACK, (self.x, self.y + 9), (self.x + self.w - 1, self.y + 9))

        # Mac OS Horizontal Stripes in title bar when window is active
        if self.active:
            for sy in (self.y + 2, self.y + 4, self.y + 6, self.y + 8):
                pygame.draw.line(surf, C_BLACK, (self.x + 11, sy), (self.x + self.w - 11, sy))

        # 3. Top-left Grab Handle [=]
        pygame.draw.rect(surf, C_BLACK, self.get_grab_rect(), 1)
        pygame.draw.line(surf, C_BLACK, (self.x + 3, self.y + 3), (self.x + 7, self.y + 3))
        pygame.draw.line(surf, C_BLACK, (self.x + 3, self.y + 5), (self.x + 7, self.y + 5))
        pygame.draw.line(surf, C_BLACK, (self.x + 3, self.y + 7), (self.x + 7, self.y + 7))

        # 4. Top-right Close Box [X]
        pygame.draw.rect(surf, C_BLACK, self.get_close_rect(), 1)
        # Small 'X' inside close box
        cx = self.x + self.w - 8
        cy = self.y + 2
        pygame.draw.line(surf, C_BLACK, (cx + 1, cy + 1), (cx + 5, cy + 5))
        pygame.draw.line(surf, C_BLACK, (cx + 5, cy + 1), (cx + 1, cy + 5))

        # 5. Window Title centered in title bar (cyan backing, 8x8 font)
        max_title_w = max(8, self.w - 24)
        max_chars = max(1, max_title_w // CHAR_W)
        t_str = self.title[:max_chars]
        t_w = len(t_str) * CHAR_W
        tx = self.x + (self.w - t_w) // 2
        ty = self.y + 1
        # Cyan rect under title so stripes don't interfere
        pygame.draw.rect(surf, C_CYAN, (tx - 3, self.y + 1, t_w + 6, 8))
        draw_mono_text(surf, t_str, tx, ty, C_BLACK, C_CYAN)

        # 6. Client Area (Clipped)
        if self.dirty or (self.app and getattr(self.app, 'dirty', True)):
            self.render_content()
            self.dirty = False

        cw = (self.w - 11) if self.can_scroll() else (self.w - 2)
        ch = self.client_surf.get_height()
        surf.blit(self.client_surf, (self.x + 1, self.y + 10), area=pygame.Rect(0, 0, cw, ch))

        # 7. Vertical Scrollbar (Up/Down arrows, track & thumb) when whole contents cannot be shown
        if self.can_scroll():
            sb_x = self.x + self.w - 10
            # Vertical divider line
            pygame.draw.line(surf, C_BLACK, (sb_x, self.y + 10), (sb_x, self.y + self.h - 2))

            # Up Arrow button (top right)
            up_rect = self.get_scroll_up_rect()
            pygame.draw.rect(surf, C_CYAN, up_rect)
            pygame.draw.line(surf, C_BLACK, (sb_x, up_rect.bottom - 1), (sb_x + 8, up_rect.bottom - 1))
            pygame.draw.polygon(surf, C_BLACK, [
                (sb_x + 4, up_rect.y + 2),
                (sb_x + 2, up_rect.y + 6),
                (sb_x + 6, up_rect.y + 6)
            ])

            # Down Arrow button (bottom right, above resize box)
            down_rect = self.get_scroll_down_rect()
            pygame.draw.rect(surf, C_CYAN, down_rect)
            pygame.draw.line(surf, C_BLACK, (sb_x, down_rect.y), (sb_x + 8, down_rect.y))
            pygame.draw.line(surf, C_BLACK, (sb_x, down_rect.bottom - 1), (sb_x + 8, down_rect.bottom - 1))
            pygame.draw.polygon(surf, C_BLACK, [
                (sb_x + 2, down_rect.y + 2),
                (sb_x + 6, down_rect.y + 2),
                (sb_x + 4, down_rect.y + 6)
            ])

            # Scroll Track & Elevator Thumb
            track_rect = self.get_scroll_track_rect()
            if track_rect.height > 0:
                pygame.draw.rect(surf, C_CYAN, track_rect)
                for ty in range(track_rect.y, track_rect.bottom):
                    stip_offset = (ty % 2)
                    for tx in range(sb_x + 1 + stip_offset, sb_x + 9, 2):
                        surf.set_at((tx, ty), C_BLACK)

                thumb_y, thumb_h = self.get_thumb_rect_y_h()
                if thumb_h > 0:
                    pygame.draw.rect(surf, C_CYAN, (sb_x + 1, thumb_y, 7, thumb_h))
                    pygame.draw.rect(surf, C_BLACK, (sb_x + 1, thumb_y, 7, thumb_h), 1)

        # 8. Bottom-right Resize Drag Icon (Mac/GEM corner glyph)
        rx = self.x + self.w - 8
        ry = self.y + self.h - 8
        pygame.draw.rect(surf, C_CYAN, (rx, ry, 7, 7))
        pygame.draw.line(surf, C_BLACK, (rx + 6, ry), (rx, ry + 6))
        pygame.draw.line(surf, C_BLACK, (rx + 6, ry + 3), (rx + 3, ry + 6))
        pygame.draw.line(surf, C_BLACK, (rx + 6, ry + 5), (rx + 5, ry + 6))


# ------------------------------------------------------------------------------
# WIMPMenu: Top Menu Bar & Pull-down Menus
# ------------------------------------------------------------------------------
class WIMPMenu:
    def __init__(self, desktop):
        self.desktop = desktop
        self.visible = True
        self.active_menu_idx = -1
        self.hover_item_idx = -1

        # Menu structure: list of dicts: {'title': str, 'items': [str, ...], 'handlers': [fn, ...]}
        self.menus = []
        self.reset_default_menus()

    def reset_default_menus(self):
        self.menus = [
            {
                "title": "FILE",
                "items": ["New Basic", "New Text", "Cut", "Copy", "Paste"],
                "handlers": [
                    self._on_new_basic,
                    self._on_new_text,
                    self._on_cut,
                    self._on_copy,
                    self._on_paste
                ]
            },
            {
                "title": "SYSTEM",
                "items": ["Refresh", "Tidy", "Empty Bin", "Quit to BASIC"],
                "handlers": [
                    self._on_refresh,
                    self._on_tidy,
                    self._on_empty_bin,
                    self._on_quit
                ]
            }
        ]

    def get_active_file_items(self):
        """Returns dynamic File menu options depending on active window."""
        act_win = self.desktop.active_window
        if act_win and act_win.app and isinstance(act_win.app, TextEditorApp):
            return ["New Text", "Open File", "Save File", "Close Editor", "Cut", "Copy", "Paste"]
        return ["New Basic", "New Text", "Cut", "Copy", "Paste"]

    def get_current_items(self, menu_idx):
        """Returns currently available items for menu index taking dynamic context into account."""
        if 0 <= menu_idx < len(self.menus):
            m = self.menus[menu_idx]
            if m["title"] == "FILE":
                return self.get_active_file_items()
            return list(m["items"])
        return []

    def _on_new_basic(self):
        ctx = get_main_context()
        if ctx is not None and hasattr(ctx, "perform_new"):
            ctx.perform_new()
        elif ctx is not None and hasattr(ctx, "program"):
            ctx.program.clear()
            if hasattr(ctx, "variables"): ctx.variables.clear()

    def _on_new_text(self):
        self.desktop.open_text_editor()

    def _on_cut(self):
        act = self.desktop.active_window
        if act and act.app and hasattr(act.app, 'cut'):
            act.app.cut()

    def _on_copy(self):
        act = self.desktop.active_window
        if act and act.app and hasattr(act.app, 'copy'):
            act.app.copy()

    def _on_paste(self):
        act = self.desktop.active_window
        if act and act.app and hasattr(act.app, 'paste'):
            act.app.paste()

    def _on_refresh(self):
        self.desktop.redraw_all()

    def _on_tidy(self):
        self.desktop.tidy_icons()

    def _on_empty_bin(self):
        self.desktop.empty_trash()

    def _on_quit(self):
        self.desktop.running = False
        for mod_name in ('BetaBasic', 'main', '__main__'):
            mod = sys.modules.get(mod_name)
            if mod is not None:
                if hasattr(mod, "gui_mode"):
                    mod.gui_mode = False
                if hasattr(mod, "set_timex_mode"):
                    try: mod.set_timex_mode(0)
                    except Exception: pass
                if hasattr(mod, "set_zx48_mode"):
                    try: mod.set_zx48_mode()
                    except Exception: pass
                elif hasattr(mod, "execute_statement"):
                    try: mod.execute_statement("ZX48")
                    except Exception: pass
        ctx = get_main_context()
        if ctx is not None:
            if hasattr(ctx, "gui_mode"):
                ctx.gui_mode = False
            if hasattr(ctx, "set_timex_mode"):
                try: ctx.set_timex_mode(0)
                except Exception: pass
            if hasattr(ctx, "set_zx48_mode"):
                try: ctx.set_zx48_mode()
                except Exception: pass
            elif hasattr(ctx, "execute_statement"):
                try: ctx.execute_statement("ZX48")
                except Exception: pass

    def add_menu(self, title):
        """Adds custom main menu title (up to 5 extra)."""
        if len(self.menus) >= 7:  # 2 default + 5 user
            return -1
        m_dict = {"title": title.upper()[:10], "items": [], "handlers": []}
        self.menus.append(m_dict)
        return len(self.menus) - 1

    def add_item(self, menu_idx, item_title, handler=None):
        """Adds child item to menu (up to 10 items)."""
        if 0 <= menu_idx < len(self.menus):
            m = self.menus[menu_idx]
            if len(m["items"]) < 10:
                m["items"].append(item_title[:16])
                m["handlers"].append(handler)
                return len(m["items"]) - 1
        return -1

    def draw(self, surf):
        if not self.visible:
            return

        # 1. Top cyan bar with 1px black line underneath
        pygame.draw.rect(surf, C_CYAN, (0, 0, SCREEN_W, MENU_BAR_H))
        pygame.draw.line(surf, C_BLACK, (0, MENU_BAR_H - 1), (SCREEN_W, MENU_BAR_H - 1))

        # 2. Draw Menu Headers (8x8 font, 64-column mode)
        x_pos = 4
        for idx, m in enumerate(self.menus):
            t = m["title"]
            w = len(t) * CHAR_W + 8
            is_active = (idx == self.active_menu_idx)
            if is_active:
                pygame.draw.rect(surf, C_BLACK, (x_pos, 0, w, MENU_BAR_H - 1))
                draw_mono_text(surf, t, x_pos + 4, 1, C_CYAN, C_BLACK)
            else:
                draw_mono_text(surf, t, x_pos + 4, 1, C_BLACK, C_CYAN)
            m["_x"] = x_pos
            m["_w"] = w
            x_pos += w + 4

        # 3. Draw active drop-down popup box with drop shadow
        if 0 <= self.active_menu_idx < len(self.menus):
            m = self.menus[self.active_menu_idx]
            mx = m["_x"]
            my = MENU_BAR_H
            # Check dynamic items for FILE menu
            items = self.get_active_file_items() if m["title"] == "FILE" else m["items"]
            if not items:
                items = ["(Empty)"]
            
            mw = max(len(it) for it in items) * CHAR_W + 12
            mh = len(items) * 10 + 4

            # Drop shadow
            pygame.draw.rect(surf, C_BLACK, (mx + 2, my + 2, mw, mh))

            # Menu Box (Cyan background, black border)
            pygame.draw.rect(surf, C_CYAN, (mx, my, mw, mh))
            pygame.draw.rect(surf, C_BLACK, (mx, my, mw, mh), 1)

            # Menu Items
            iy = my + 2
            for i_idx, item_str in enumerate(items):
                is_hover = (i_idx == self.hover_item_idx)
                if is_hover:
                    pygame.draw.rect(surf, C_BLACK, (mx + 1, iy, mw - 2, 10))
                    draw_mono_text(surf, item_str, mx + 5, iy + 1, C_CYAN, C_BLACK)
                else:
                    draw_mono_text(surf, item_str, mx + 5, iy + 1, C_BLACK, C_CYAN)
                iy += 10


# ------------------------------------------------------------------------------
# Desk Accessories & Built-in Applications
# ------------------------------------------------------------------------------
class TextEditorApp:
    """Built-in Mac/GEM style Notepad Text Editor with multi-line buffer and file I/O."""
    def __init__(self, window):
        self.window = window
        self.lines = ["Hello ZX Spectrum!", "BasinPy WIMP GUI Active."]
        self.cursor_r = 0
        self.cursor_c = 0
        self.filename = "NOTES.TXT"
        self.dirty = True
        self.scroll_step = 8

    def get_content_height(self):
        return len(self.lines) * 8 + 4

    def _ensure_cursor_visible(self):
        if self.window:
            line_h = 8
            cur_y = self.cursor_r * line_h
            vis_h = self.window.client_surf.get_height() if self.window.client_surf else 1
            if cur_y < self.window.scroll_y:
                self.window.scroll_y = cur_y
            elif cur_y + line_h > self.window.scroll_y + vis_h:
                self.window.scroll_y = cur_y + line_h - vis_h
            self.window.scroll_y = max(0, min(self.window.get_max_scroll(), self.window.scroll_y))
            self.window.dirty = True

    def load_content(self, content):
        if isinstance(content, list):
            self.lines = list(content)
        else:
            self.lines = str(content).split('\n')
        self.cursor_r = 0
        self.cursor_c = 0
        self.dirty = True

    def handle_key(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                if self.cursor_c > 0:
                    line = self.lines[self.cursor_r]
                    self.lines[self.cursor_r] = line[:self.cursor_c - 1] + line[self.cursor_c:]
                    self.cursor_c -= 1
                elif self.cursor_r > 0:
                    prev_len = len(self.lines[self.cursor_r - 1])
                    self.lines[self.cursor_r - 1] += self.lines.pop(self.cursor_r)
                    self.cursor_r -= 1
                    self.cursor_c = prev_len
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                line = self.lines[self.cursor_r]
                new_l = line[self.cursor_c:]
                self.lines[self.cursor_r] = line[:self.cursor_c]
                self.lines.insert(self.cursor_r + 1, new_l)
                self.cursor_r += 1
                self.cursor_c = 0
            elif event.key == pygame.K_LEFT:
                if self.cursor_c > 0: self.cursor_c -= 1
            elif event.key == pygame.K_RIGHT:
                if self.cursor_c < len(self.lines[self.cursor_r]): self.cursor_c += 1
            elif event.key == pygame.K_UP:
                if self.cursor_r > 0:
                    self.cursor_r -= 1
                    self.cursor_c = min(self.cursor_c, len(self.lines[self.cursor_r]))
            elif event.key == pygame.K_DOWN:
                if self.cursor_r < len(self.lines) - 1:
                    self.cursor_r += 1
                    self.cursor_c = min(self.cursor_c, len(self.lines[self.cursor_r]))
            elif event.unicode and ord(event.unicode) >= 32:
                line = self.lines[self.cursor_r]
                self.lines[self.cursor_r] = line[:self.cursor_c] + event.unicode + line[self.cursor_c:]
                self.cursor_c += 1
            self.dirty = True
            self._ensure_cursor_visible()

    def cut(self):
        self.copy()
        if 0 <= self.cursor_r < len(self.lines):
            self.lines[self.cursor_r] = ""
            self.cursor_c = 0
            self.dirty = True
            self._ensure_cursor_visible()

    def copy(self):
        if 0 <= self.cursor_r < len(self.lines):
            if self.window and self.window.desktop:
                self.window.desktop.clipboard_text = self.lines[self.cursor_r]

    def paste(self):
        if self.window and self.window.desktop and self.window.desktop.clipboard_text:
            cb = self.window.desktop.clipboard_text
            line = self.lines[self.cursor_r]
            self.lines[self.cursor_r] = line[:self.cursor_c] + cb + line[self.cursor_c:]
            self.cursor_c += len(cb)
            self.dirty = True
            self._ensure_cursor_visible()

    def save_file(self):
        # Save to wimp.mdr or local file
        try:
            content = "\n".join(self.lines).encode('latin-1', errors='replace')
            ctx = get_main_context()
            if ctx is not None and hasattr(ctx, 'mdr_write_file_bytes'):
                ctx.mdr_write_file_bytes(8, self.filename, content, "PRINT")
            with open(self.filename, "w", encoding="latin-1") as f:
                f.write("\n".join(self.lines))
        except Exception:
            pass

    def load_file(self):
        try:
            ctx = get_main_context()
            if ctx is not None and hasattr(ctx, 'mdr_read_file_bytes'):
                raw = ctx.mdr_read_file_bytes(8, self.filename)
                if raw:
                    self.lines = raw.decode('latin-1', errors='replace').splitlines()
                    self.dirty = True
                    self._ensure_cursor_visible()
                    return
            if os.path.exists(self.filename):
                with open(self.filename, "r", encoding="latin-1") as f:
                    self.lines = f.read().splitlines()
                self.dirty = True
                self._ensure_cursor_visible()
        except Exception:
            pass

    def render(self, surf):
        surf.fill(C_CYAN)
        scroll_y = getattr(self.window, "scroll_y", 0) if self.window else 0
        line_h = 8
        for i, line in enumerate(self.lines):
            y = i * line_h - scroll_y
            if y + line_h > 0 and y < surf.get_height():
                draw_mono_text(surf, line, 2, y, C_BLACK, C_CYAN)
        # Cursor
        cx = 2 + self.cursor_c * CHAR_W
        cy = self.cursor_r * line_h - scroll_y
        if 0 <= cx < surf.get_width() - 2 and 0 <= cy < surf.get_height() - 7:
            pygame.draw.line(surf, C_BLACK, (cx, cy), (cx, cy + 7))


class ClockApp:
    """Desk Accessory: Real-time clock with alarm and audio alert."""
    def __init__(self, window):
        self.window = window
        self.alarm_h = 8
        self.alarm_m = 0
        self.alarm_enabled = False
        self.alarm_triggered = False
        self.flash_state = False
        self.last_sec = -1
        self.dirty = True

    def set_alarm(self, time_str="12:00", enabled=True):
        self.alarm_enabled = enabled
        if ":" in str(time_str):
            parts = str(time_str).split(":")
            self.alarm_h = int(parts[0]) % 24
            self.alarm_m = int(parts[1]) % 60
        self.dirty = True

    @property
    def alarm_time(self):
        return f"{self.alarm_h:02d}:{self.alarm_m:02d}"

    def update(self):
        t = time.localtime()
        if t.tm_sec != self.last_sec:
            self.last_sec = t.tm_sec
            self.dirty = True
            if self.alarm_enabled and t.tm_hour == self.alarm_h and t.tm_min == self.alarm_m:
                self.alarm_triggered = True
                self.flash_state = not self.flash_state
                # Sound beep
                try:
                    ctx = get_main_context()
                    if ctx is not None and hasattr(ctx, 'play_beep'):
                        ctx.play_beep(0.1, 20)
                except Exception:
                    pass

    def handle_click(self, cx, cy):
        # Toggle alarm or adjust alarm time
        # [ALARM: ON/OFF] button at y=32..40
        if 32 <= cy <= 42:
            if 4 <= cx <= 48:
                self.alarm_enabled = not self.alarm_enabled
                self.alarm_triggered = False
                self.dirty = True
            elif 52 <= cx <= 64:  # Hour +
                self.alarm_h = (self.alarm_h + 1) % 24
                self.dirty = True
            elif 68 <= cx <= 80:  # Min +
                self.alarm_m = (self.alarm_m + 5) % 60
                self.dirty = True

    def render(self, surf):
        surf.fill(C_CYAN)
        t = time.localtime()
        time_str = f"{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d}"
        date_str = f"{t.tm_mday:02d}/{t.tm_mon:02d}/{t.tm_year}"

        # Draw time
        draw_mono_text(surf, time_str, 8, 4, C_BLACK, C_CYAN)
        draw_mini_text(surf, date_str, 12, 16, C_BLACK, C_CYAN)

        # Alarm control line
        al_status = "ON " if self.alarm_enabled else "OFF"
        al_str = f"ALM:{al_status} {self.alarm_h:02d}:{self.alarm_m:02d}"
        draw_mini_text(surf, al_str, 4, 32, C_BLACK, C_CYAN)
        draw_mini_text(surf, "[+H][+M]", 52, 42, C_BLACK, C_CYAN)

        if self.alarm_triggered and self.flash_state:
            pygame.draw.rect(surf, C_BLACK, (2, 24, surf.get_width() - 4, 7))
            draw_mini_text(surf, "*** ALARM! ***", 14, 25, C_CYAN, C_BLACK)


class CalcApp:
    """Desk Accessory: Handheld 4-function pocket calculator."""
    def __init__(self, window):
        self.window = window
        self.display_str = "0"
        self.curr_val = 0.0
        self.pending_op = None
        self.new_entry = True
        self.dirty = True

        self.buttons = [
            ("C", 10, 18),  ("±", 34, 18), ("%", 58, 18), ("/", 82, 18),
            ("7", 10, 30),  ("8", 34, 30), ("9", 58, 30), ("*", 82, 30),
            ("4", 10, 42),  ("5", 34, 42), ("6", 58, 42), ("-", 82, 42),
            ("1", 10, 54),  ("2", 34, 54), ("3", 58, 54), ("+", 82, 54),
            ("0", 10, 66),  (".", 34, 66), ("=", 58, 66)
        ]

    def input_digit(self, d):
        if self.new_entry:
            self.display_str = d
            self.new_entry = False
        else:
            if len(self.display_str) < 9:
                self.display_str += d
        self.dirty = True

    def input_op(self, op):
        try:
            val = float(self.display_str)
        except Exception:
            val = 0.0

        if self.pending_op and not self.new_entry:
            self.calculate()
        else:
            self.curr_val = val

        self.pending_op = op
        self.new_entry = True
        self.dirty = True

    def calculate(self):
        try:
            val = float(self.display_str)
            if self.pending_op == "+": res = self.curr_val + val
            elif self.pending_op == "-": res = self.curr_val - val
            elif self.pending_op == "*": res = self.curr_val * val
            elif self.pending_op == "/": res = self.curr_val / val if val != 0 else 0
            else: res = val
            # Format nicely
            if res.is_integer():
                self.display_str = str(int(res))
            else:
                self.display_str = f"{res:.4g}"
            self.curr_val = res
            self.pending_op = None
            self.new_entry = True
        except Exception:
            self.display_str = "ERR"
        self.dirty = True

    def handle_click(self, cx, cy):
        for label, bx, by in self.buttons:
            bw = 44 if label == "=" else 20
            bh = 10
            if bx <= cx <= bx + bw and by <= cy <= by + bh:
                if label in "0123456789":
                    self.input_digit(label)
                elif label == ".":
                    if "." not in self.display_str:
                        if self.new_entry:
                            self.display_str = "0."
                            self.new_entry = False
                        else:
                            self.display_str += "."
                    self.dirty = True
                elif label == "C":
                    self.display_str = "0"
                    self.curr_val = 0.0
                    self.pending_op = None
                    self.new_entry = True
                    self.dirty = True
                elif label == "±":
                    if self.display_str.startswith("-"):
                        self.display_str = self.display_str[1:]
                    elif self.display_str != "0":
                        self.display_str = "-" + self.display_str
                    self.dirty = True
                elif label in ("+", "-", "*", "/"):
                    self.input_op(label)
                elif label == "=":
                    self.calculate()
                break

    def handle_key(self, event):
        if event.type == pygame.KEYDOWN:
            if event.unicode in "0123456789":
                self.input_digit(event.unicode)
            elif event.unicode in "+-*/":
                self.input_op(event.unicode)
            elif event.key in (pygame.K_RETURN, pygame.K_EQUALS):
                self.calculate()
            elif event.key in (pygame.K_c, pygame.K_ESCAPE):
                self.display_str = "0"
                self.pending_op = None
                self.new_entry = True
                self.dirty = True

    def press_key(self, k):
        k_str = str(k)
        if k_str in "0123456789":
            self.input_digit(k_str)
        elif k_str in "+-*/":
            self.input_op(k_str)
        elif k_str in ("=", "\r", "\n"):
            self.calculate()
        elif k_str.upper() == "C":
            self.display_str = "0"
            self.curr_val = 0.0
            self.pending_op = None
            self.new_entry = True
            self.dirty = True

    def render(self, surf):
        surf.fill(C_CYAN)
        # LCD Display box
        pygame.draw.rect(surf, C_BLACK, (4, 3, surf.get_width() - 8, 12), 1)
        draw_mono_text(surf, f"{self.display_str:>10}", 6, 5, C_BLACK, C_CYAN)

        # Buttons
        for label, bx, by in self.buttons:
            bw = 44 if label == "=" else 20
            bh = 10
            pygame.draw.rect(surf, C_BLACK, (bx, by, bw, bh), 1)
            tx = bx + (bw - len(label) * CHAR_W) // 2
            draw_mono_text(surf, label, tx, by + 1, C_BLACK, C_CYAN)


class CalendarApp:
    """Desk Accessory: Monthly calendar with day selector and diary notes."""
    def __init__(self, window):
        self.window = window
        now = time.localtime()
        self.year = now.tm_year
        self.month = now.tm_mon
        self.selected_day = now.tm_mday
        self.diary_entries = {
            self.selected_day: "BasinPy WIMP GUI Launch!"
        }
        self.editing_note = False
        self.dirty = True

    def get_days_in_month(self):
        if self.month in (1, 3, 5, 7, 8, 10, 12): return 31
        if self.month in (4, 6, 9, 11): return 30
        # Feb leap check
        if (self.year % 4 == 0 and self.year % 100 != 0) or (self.year % 400 == 0): return 29
        return 28

    def set_note(self, year, month, day, text):
        self.year = year
        self.month = month
        self.selected_day = day
        self.diary_entries[day] = str(text)
        self.dirty = True

    def get_note(self, year, month, day):
        if self.year == year and self.month == month:
            return self.diary_entries.get(day, "")
        return ""

    def handle_click(self, cx, cy):
        # Header navigation [<] [>]
        if 2 <= cy <= 11:
            if 4 <= cx <= 16:  # [<]
                self.month -= 1
                if self.month < 1: self.month = 12; self.year -= 1
                self.dirty = True
            elif 110 <= cx <= 122:  # [>]
                self.month += 1
                if self.month > 12: self.month = 1; self.year += 1
                self.dirty = True
        # Days grid: y=18..60, cols 7
        elif 18 <= cy <= 60:
            row = (cy - 18) // 8
            col = (cx - 4) // 18
            day = row * 7 + col + 1
            if 1 <= day <= self.get_days_in_month():
                self.selected_day = day
                self.dirty = True
        # Diary note click: y=68..80
        elif 68 <= cy <= 85:
            self.editing_note = True

    def handle_key(self, event):
        if event.type == pygame.KEYDOWN and self.editing_note:
            note = self.diary_entries.get(self.selected_day, "")
            if event.key == pygame.K_BACKSPACE:
                self.diary_entries[self.selected_day] = note[:-1]
            elif event.key == pygame.K_RETURN:
                self.editing_note = False
            elif event.unicode and ord(event.unicode) >= 32:
                self.diary_entries[self.selected_day] = (note + event.unicode)[:26]
            self.dirty = True

    def render(self, surf):
        surf.fill(C_CYAN)
        months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
        hdr = f"< {months[self.month - 1]} {self.year} >"
        draw_mono_text(surf, hdr, 14, 2, C_BLACK, C_CYAN)

        # Day grid
        days = self.get_days_in_month()
        for d in range(1, days + 1):
            idx = d - 1
            r = idx // 7
            c = idx % 7
            dx = 4 + c * 18
            dy = 16 + r * 8
            if d == self.selected_day:
                pygame.draw.rect(surf, C_BLACK, (dx - 1, dy - 1, 16, 8))
                draw_mini_text(surf, f"{d:02d}", dx, dy, C_CYAN, C_BLACK)
            else:
                draw_mini_text(surf, f"{d:02d}", dx, dy, C_BLACK, C_CYAN)

        # Diary line for selected day
        pygame.draw.line(surf, C_BLACK, (2, 64), (surf.get_width() - 2, 64))
        note = self.diary_entries.get(self.selected_day, "")
        draw_mini_text(surf, f"NOTE {self.selected_day:02d}: {note}", 4, 68, C_BLACK, C_CYAN)


class CardIndexApp:
    """Desk Accessory: Rolodex Card Index database."""
    def __init__(self, window):
        self.window = window
        self.cards = [
            {"title": "Contacts", "body": "John Smith\nTel: 01-555-1234"},
            {"title": "BasinPy", "body": "Sinclair Spectrum WIMP\nGEM/Mac OS 6 UI"},
            {"title": "Notes", "body": "Temp storage in MDR 8\nwimp.mdr mounted"}
        ]
        self.card_idx = 0
        self.dirty = True

    def add_card(self, title, body):
        self.cards.append({"title": str(title), "body": str(body)})
        self.card_idx = len(self.cards) - 1
        self.dirty = True

    def find_cards(self, keyword):
        kw = str(keyword).lower()
        return [c for c in self.cards if kw in c["title"].lower() or kw in c["body"].lower()]

    def handle_click(self, cx, cy):
        # Navigation buttons at bottom y=52..62
        if 50 <= cy <= 64:
            if 4 <= cx <= 24:  # [<]
                if self.card_idx > 0: self.card_idx -= 1
                self.dirty = True
            elif 28 <= cx <= 48:  # [>]
                if self.card_idx < len(self.cards) - 1: self.card_idx += 1
                self.dirty = True
            elif 52 <= cx <= 84:  # [+New]
                self.cards.append({"title": f"Card {len(self.cards)+1}", "body": "New card note"})
                self.card_idx = len(self.cards) - 1
                self.dirty = True
            elif 88 <= cx <= 118:  # [Del]
                if len(self.cards) > 1:
                    self.cards.pop(self.card_idx)
                    self.card_idx = max(0, self.card_idx - 1)
                    self.dirty = True

    def render(self, surf):
        surf.fill(C_CYAN)
        if not self.cards:
            return
        card = self.cards[self.card_idx]

        # Tab and card frame
        pygame.draw.rect(surf, C_BLACK, (4, 4, 60, 9), 1)
        draw_mini_text(surf, card["title"][:10], 6, 6, C_BLACK, C_CYAN)
        pygame.draw.rect(surf, C_BLACK, (4, 12, surf.get_width() - 8, 36), 1)

        # Body lines
        lines = card["body"].split("\n")
        by = 15
        for l in lines[:3]:
            draw_mini_text(surf, l[:24], 8, by, C_BLACK, C_CYAN)
            by += 8

        # Buttons
        draw_mini_text(surf, "[<] [>] [+NEW] [DEL]", 4, 52, C_BLACK, C_CYAN)
        draw_mini_text(surf, f"{self.card_idx + 1}/{len(self.cards)}", surf.get_width() - 28, 52, C_BLACK, C_CYAN)


class SlidePuzzleApp:
    """Desk Accessory: Classic 8-Slide Puzzle game (3x3 tiles)."""
    def __init__(self, window):
        self.window = window
        self.grid = [1, 2, 3, 4, 5, 6, 7, 8, 0]  # 0 is blank
        self.solved = True
        self.shuffle()
        self.dirty = True

    def shuffle(self, moves=60):
        import random
        # Random valid moves to guarantee solvable puzzle
        for _ in range(moves):
            idx = self.grid.index(0)
            r, c = idx // 3, idx % 3
            moves = []
            if r > 0: moves.append(idx - 3)
            if r < 2: moves.append(idx + 3)
            if c > 0: moves.append(idx - 1)
            if c < 2: moves.append(idx + 1)
            pick = random.choice(moves)
            self.grid[idx], self.grid[pick] = self.grid[pick], self.grid[idx]
        self.check_solved()

    def check_solved(self):
        self.solved = (self.grid == [1, 2, 3, 4, 5, 6, 7, 8, 0])

    def handle_click(self, cx, cy):
        # Grid area: x=8..74, y=4..70 (22x22 cells)
        if 4 <= cy <= 70 and 8 <= cx <= 74:
            r = (cy - 4) // 22
            c = (cx - 8) // 22
            tile_idx = r * 3 + c
            blank_idx = self.grid.index(0)
            br, bc = blank_idx // 3, blank_idx % 3
            if abs(r - br) + abs(c - bc) == 1:
                # Slide
                self.grid[blank_idx], self.grid[tile_idx] = self.grid[tile_idx], self.grid[blank_idx]
                self.check_solved()
                self.dirty = True
        # [Shuffle] button at y=76..86
        elif 74 <= cy <= 86 and 8 <= cx <= 64:
            self.shuffle()
            self.dirty = True

    def render(self, surf):
        surf.fill(C_CYAN)
        for r in range(3):
            for c in range(3):
                val = self.grid[r * 3 + c]
                tx = 8 + c * 22
                ty = 4 + r * 22
                if val != 0:
                    pygame.draw.rect(surf, C_BLACK, (tx, ty, 20, 20), 1)
                    draw_mono_text(surf, str(val), tx + 6, ty + 6, C_BLACK, C_CYAN)
                else:
                    pygame.draw.rect(surf, C_CYAN, (tx, ty, 20, 20))

        # Shuffle button
        draw_mini_text(surf, "[SHUFFLE]", 12, 74, C_BLACK, C_CYAN)
        if self.solved:
            draw_mini_text(surf, "SOLVED!", 62, 74, C_BLACK, C_CYAN)


# ------------------------------------------------------------------------------
# WIMPDesktop Manager
# ------------------------------------------------------------------------------
class WIMPDesktop:
    """Complete GEM / Mac OS 6 Desktop Environment."""
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = WIMPDesktop()
        return cls._instance

    def __init__(self):
        self.windows = []
        self.active_window = None
        self.icons = []
        self.menu = WIMPMenu(self)
        self.canvas = pygame.Surface((SCREEN_W, SCREEN_H))
        self.running = True

        # Stipple pattern surface (alternating 0xAA / 0x55 System 6 desktop)
        self.stipple_surf = pygame.Surface((SCREEN_W, SCREEN_H))
        self._init_stipple()

        # AMX Mouse & Interaction State
        self.mouse_x = 128
        self.mouse_y = 96
        self.mouse_btn = 0
        self.drag_mode = None  # None, "WINDOW_DRAG", "WINDOW_RESIZE", "ICON_DRAG"
        self.drag_target = None
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        self.drag_rect = None

        # Double-click tracking
        self.last_click_time = 0
        self.last_click_pos = (0, 0)
        self.double_click_threshold = 0.5  # seconds
        self.in_modal_loop = False
        self.pending_run_file = None

        # Context Popup Menu (Right-click on files)
        self.popup_menu = None  # {'x': int, 'y': int, 'items': [...], 'target': obj}

        # Clipboard buffer
        self.clipboard_file = None
        self.clipboard_text = ""

        # Microdrive 8 Temp File storage initialization
        self.init_temp_microdrive()

        # Desktop Icons Initialization
        self.init_desktop_icons()

    def _init_stipple(self):
        """Creates solid cyan desktop background (not stippled)."""
        self.stipple_surf.fill(C_CYAN)

    def init_temp_microdrive(self):
        """Ensures Microdrive 8 is configured as 'wimp.mdr' for temp storage."""
        ctx = get_main_context()
        if ctx is not None:
            if hasattr(ctx, "microdrive_attachments"):
                ctx.microdrive_attachments[8] = "wimp.mdr"
            # If wimp.mdr does not exist, create a blank image
            if not os.path.exists("wimp.mdr") and hasattr(ctx, "create_blank_mdr"):
                try:
                    ctx.create_blank_mdr("wimp.mdr", "WIMP_TEMP")
                except Exception:
                    pass

    def init_desktop_icons(self):
        """Populates standard Mac OS / GEM desktop icons for 512x192 64-column desktop."""
        self.icons.clear()
        # Right column: Floppy and Microdrive drives
        col_r_x = SCREEN_W - 48
        y_pos = 14

        # Floppy 1
        self.icons.append(WIMPIcon("drv_flop1", "Floppy 1", "floppy", col_r_x, y_pos,
                                   on_open=lambda: self.open_drive_window("Floppy 1", 1)))
        y_pos += 32

        # Microdrive 1
        self.icons.append(WIMPIcon("drv_mdr1", "MDR 1", "microdrive", col_r_x, y_pos,
                                   on_open=lambda: self.open_drive_window("MDR 1", 1, is_mdr=True)))
        y_pos += 32

        # Microdrive 8 (Temp Storage)
        self.icons.append(WIMPIcon("drv_mdr8", "MDR 8", "microdrive", col_r_x, y_pos,
                                   on_open=lambda: self.open_drive_window("MDR 8 (Temp)", 8, is_mdr=True)))
        y_pos += 32

        # Tape
        self.icons.append(WIMPIcon("drv_tape", "Tape", "tape", col_r_x, y_pos,
                                   on_open=lambda: self.open_tape_window()))
        y_pos += 32

        # Trash Bin at bottom right
        self.icons.append(WIMPIcon("trash", "Trash", "trash", col_r_x, SCREEN_H - 32,
                                   on_open=lambda: self.empty_trash()))

        # Left column: Applications & Desk Accessories
        col_l_x = 16
        ay_pos = 14

        # Text Editor
        self.icons.append(WIMPIcon("app_text", "Text Ed", "text_editor", col_l_x, ay_pos,
                                   on_open=lambda: self.open_text_editor()))
        ay_pos += 32

        # Clock
        self.icons.append(WIMPIcon("app_clock", "Clock", "clock", col_l_x, ay_pos,
                                   on_open=lambda: self.open_clock_app()))
        ay_pos += 32

        # Calculator
        self.icons.append(WIMPIcon("app_calc", "Calc", "calculator", col_l_x, ay_pos,
                                   on_open=lambda: self.open_calc_app()))
        ay_pos += 32

        # Calendar
        self.icons.append(WIMPIcon("app_cal", "Calendar", "calendar", col_l_x, ay_pos,
                                   on_open=lambda: self.open_calendar_app()))
        ay_pos += 32

        # Card Index
        self.icons.append(WIMPIcon("app_card", "Cards", "card_index", col_l_x, ay_pos,
                                   on_open=lambda: self.open_card_index_app()))

        # Slide Puzzle (placed next column)
        self.icons.append(WIMPIcon("app_puzzle", "Puzzle", "puzzle", col_l_x + 64, 14,
                                   on_open=lambda: self.open_puzzle_app()))

    def tidy_icons(self):
        """Realigns desktop icons to neat grid positions."""
        self.init_desktop_icons()
        self.redraw_all()

    def empty_trash(self):
        # Empty trash action
        pass

    def add_window(self, win):
        self.windows.append(win)
        self.select_window(win)
        return win

    def select_window(self, win):
        if win in self.windows:
            self.windows.remove(win)
            self.windows.append(win)
        for w in self.windows:
            w.active = (w == win)
            w.dirty = True
        self.active_window = win

    def close_window(self, win):
        if win in self.windows:
            self.windows.remove(win)
        if self.active_window == win:
            self.active_window = self.windows[-1] if self.windows else None
            if self.active_window:
                self.active_window.active = True
                self.active_window.dirty = True

    # --------------------------------------------------------------------------
    # Desk Accessory Launcher Windows
    # --------------------------------------------------------------------------
    def open_text_editor(self, filename="", content="", x=90, y=20, w=240, h=116):
        win = WIMPWindow("text_ed", f"Text Editor - {filename}" if filename else "Text Editor", x, y, w, h, self)
        win.app = TextEditorApp(win)
        if filename:
            win.app.filename = filename
        if content:
            win.app.load_content(content)
        self.add_window(win)
        return win

    def open_clock_app(self, x=140, y=30, w=110, h=68):
        win = WIMPWindow("clock", "Clock", x, y, w, h, self)
        win.app = ClockApp(win)
        self.add_window(win)
        return win

    def open_calc_app(self, x=110, y=24, w=108, h=96):
        win = WIMPWindow("calc", "Calculator", x, y, w, h, self)
        win.app = CalcApp(win)
        self.add_window(win)
        return win

    def open_calendar_app(self, x=90, y=24, w=156, h=100):
        win = WIMPWindow("calendar", "Calendar", x, y, w, h, self)
        win.app = CalendarApp(win)
        self.add_window(win)
        return win

    def open_card_index_app(self, x=90, y=30, w=168, h=86):
        win = WIMPWindow("cards", "Card Index", x, y, w, h, self)
        win.app = CardIndexApp(win)
        self.add_window(win)
        return win

    def open_puzzle_app(self, x=120, y=24, w=100, h=106):
        win = WIMPWindow("puzzle", "15 Puzzle", x, y, w, h, self)
        win.app = SlidePuzzleApp(win)
        self.add_window(win)
        return win

    # --------------------------------------------------------------------------
    # Drive Directory Windows
    # --------------------------------------------------------------------------
    def open_drive_window(self, title, drive_num=1, is_mdr=False):
        """Opens directory window for floppy or microdrive."""
        win = WIMPWindow(f"dir_{title}", f"Dir: {title}", 70, 24, 220, 120, self)
        files = []
        ctx = get_main_context()

        if is_mdr:
            # Read Microdrive directory
            if ctx is not None and hasattr(ctx, "get_mdr_path"):
                path = ctx.get_mdr_path(drive_num)
                if os.path.exists(path):
                    try:
                        with open(path, "rb") as f:
                            data = f.read()
                        found = set()
                        for i in range(254):
                            rec_offset = i * 543 + 15
                            recflg = data[rec_offset]
                            reclen = data[rec_offset + 2] + (data[rec_offset + 3] * 256)
                            name = data[rec_offset + 4:rec_offset + 14].decode('latin-1', errors='ignore').strip()
                            if recflg != 0xFF and reclen > 0 and name and name not in found:
                                found.add(name)
                                ftype = "bas" if (recflg & 2) == 0 else "txt"
                                files.append({"name": name, "ext": ftype, "path": path, "is_mdr": True, "drive": drive_num})
                    except Exception:
                        pass
        else:
            # Floppy drive / directory files
            for fn in os.listdir("."):
                low = fn.lower()
                if low.endswith((".zxb", ".bas", ".tap", ".tzx", ".scr")):
                    ext = low.split(".")[-1]
                    files.append({"name": fn, "ext": ext, "path": os.path.abspath(fn), "is_mdr": False, "drive": drive_num})

        if not files:
            files.append({"name": "Empty Drive", "ext": "dat", "path": "", "is_mdr": False})

        # Directory App embedded in window
        win.app = DirectoryViewApp(win, files)
        self.add_window(win)

    def open_tape_window(self):
        """Opens directory window for attached tape."""
        win = WIMPWindow("dir_tape", "Tape Directory", 40, 30, 160, 110, self)
        files = []
        ctx = get_main_context()
        tape_p = getattr(ctx, "attached_tape_path", None) if ctx else None
        if tape_p and os.path.exists(tape_p):
            files.append({"name": os.path.basename(tape_p), "ext": "tap", "path": tape_p, "is_tape": True})
        else:
            for fn in os.listdir("."):
                if fn.lower().endswith((".tap", ".tzx")):
                    files.append({"name": fn, "ext": "tap", "path": os.path.abspath(fn), "is_tape": True})
        if not files:
            files.append({"name": "No Tape Attached", "ext": "dat", "path": ""})
        win.app = DirectoryViewApp(win, files)
        self.add_window(win)

    # --------------------------------------------------------------------------
    # Event Handling & Wireframe Outlines
    # --------------------------------------------------------------------------
    def handle_mouse_down(self, mx, my, button):
        self.mouse_x = mx
        self.mouse_y = my
        self.mouse_btn = button
        now = time.time()
        is_double = (now - self.last_click_time < self.double_click_threshold and
                     abs(mx - self.last_click_pos[0]) <= 8 and abs(my - self.last_click_pos[1]) <= 8)
        if is_double:
            self.last_click_time = 0
        else:
            self.last_click_time = now
        self.last_click_pos = (mx, my)

        # 1. Close popup menu if open
        if self.popup_menu:
            pm = self.popup_menu
            px, py, pw, ph = pm["x"], pm["y"], pm["w"], pm["h"]
            if px <= mx <= px + pw and py <= my <= py + ph:
                idx = (my - py - 2) // 10
                if 0 <= idx < len(pm["items"]):
                    pm["handlers"][idx]()
            self.popup_menu = None
            self.redraw_all()
            return

        # 2. Check Menu Bar (y = 0..9)
        if my < MENU_BAR_H:
            for idx, m in enumerate(self.menu.menus):
                if m["_x"] <= mx <= m["_x"] + m["_w"]:
                    if self.menu.active_menu_idx == idx:
                        self.menu.active_menu_idx = -1
                    else:
                        self.menu.active_menu_idx = idx
                        self.menu.hover_item_idx = -1
                    return
            self.menu.active_menu_idx = -1
            return

        # 3. Check active drop-down menu popup
        if self.menu.active_menu_idx >= 0:
            m = self.menu.menus[self.menu.active_menu_idx]
            mx_start = m["_x"]
            items = self.menu.get_active_file_items() if m["title"] == "FILE" else m["items"]
            mw = max(len(it) for it in items) * 8 + 12
            mh = len(items) * 10 + 4
            if mx_start <= mx <= mx_start + mw and MENU_BAR_H <= my <= MENU_BAR_H + mh:
                item_idx = (my - MENU_BAR_H - 2) // 10
                if 0 <= item_idx < len(items):
                    if m["title"] == "FILE":
                        # Execute dynamic file action
                        act_text = items[item_idx]
                        if act_text == "New Basic": self.menu._on_new_basic()
                        elif act_text == "New Text": self.menu._on_new_text()
                        elif act_text == "Open File":
                            if self.active_window and self.active_window.app and hasattr(self.active_window.app, 'load_file'):
                                self.active_window.app.load_file()
                        elif act_text == "Save File":
                            if self.active_window and self.active_window.app and hasattr(self.active_window.app, 'save_file'):
                                self.active_window.app.save_file()
                        elif act_text == "Close Editor":
                            if self.active_window: self.close_window(self.active_window)
                        elif act_text == "Cut": self.menu._on_cut()
                        elif act_text == "Copy": self.menu._on_copy()
                        elif act_text == "Paste": self.menu._on_paste()
                    elif item_idx < len(m["handlers"]) and m["handlers"][item_idx]:
                        m["handlers"][item_idx]()
                self.menu.active_menu_idx = -1
                return
            else:
                self.menu.active_menu_idx = -1

        # 4. Check Windows (in reverse z-order: topmost first)
        for win in reversed(self.windows):
            if not win.visible:
                continue

            # Check Close Box
            if win.get_close_rect().collidepoint(mx, my):
                self.close_window(win)
                return

            # Check Top-left Grab Handle or Title Bar
            if win.get_title_rect().collidepoint(mx, my):
                self.select_window(win)
                # Enter wireframe drag mode!
                self.drag_mode = "WINDOW_DRAG"
                self.drag_target = win
                self.drag_offset_x = mx - win.x
                self.drag_offset_y = my - win.y
                self.drag_rect = [win.x, win.y, win.w, win.h]
                return

            # Check Bottom-right Resize Handle
            if win.get_resize_rect().collidepoint(mx, my):
                self.select_window(win)
                # Enter wireframe resize mode!
                self.drag_mode = "WINDOW_RESIZE"
                self.drag_target = win
                self.drag_rect = [win.x, win.y, win.w, win.h]
                return

            # Check Scroll Controls (Up/Down arrows, track, mouse wheel)
            if win.can_scroll():
                if button == 4:
                    self.select_window(win)
                    win.scroll_up(steps=2)
                    return
                elif button == 5:
                    self.select_window(win)
                    win.scroll_down(steps=2)
                    return
                if win.get_scroll_up_rect().collidepoint(mx, my):
                    self.select_window(win)
                    win.scroll_up(steps=1)
                    return
                if win.get_scroll_down_rect().collidepoint(mx, my):
                    self.select_window(win)
                    win.scroll_down(steps=1)
                    return
                if win.get_scroll_track_rect().collidepoint(mx, my):
                    self.select_window(win)
                    win.handle_track_click(mx, my)
                    return

            # Check Client Area
            if win.get_client_rect().collidepoint(mx, my):
                self.select_window(win)
                if button == 4 and win.can_scroll():
                    win.scroll_up(steps=2)
                    return
                elif button == 5 and win.can_scroll():
                    win.scroll_down(steps=2)
                    return
                cx = mx - (win.x + 1)
                cy = my - (win.y + 10)
                if win.app and hasattr(win.app, 'handle_click'):
                    if button == 3:  # Right click
                        if hasattr(win.app, 'handle_right_click'):
                            win.app.handle_right_click(cx, cy, mx, my)
                    else:
                        if is_double and hasattr(win.app, 'handle_double_click'):
                            win.app.handle_double_click(cx, cy)
                        else:
                            win.app.handle_click(cx, cy)
                return

        # 5. Check Desktop Icons
        for icon in self.icons:
            if icon.get_rect().collidepoint(mx, my):
                for ic in self.icons:
                    ic.selected = (ic == icon)
                if is_double:
                    if icon.on_open:
                        icon.on_open()
                    elif icon.metadata and isinstance(icon.metadata, dict):
                        f_item = icon.metadata
                        ext = f_item.get("ext", "").lower()
                        if ext in ("bas", "zxb"):
                            self.launch_basic_program(f_item, action="RUN")
                    elif icon.title and (icon.title.lower().endswith(".bas") or icon.title.lower().endswith(".zxb")):
                        self.launch_basic_program({"path": os.path.abspath(icon.title), "name": icon.title, "ext": icon.title.split(".")[-1].lower()}, action="RUN")
                elif button == 1:
                    # Drag icon
                    self.drag_mode = "ICON_DRAG"
                    self.drag_target = icon
                    self.drag_offset_x = mx - icon.x
                    self.drag_offset_y = my - icon.y
                return

        # Clicked background desktop: deselect icons
        for ic in self.icons:
            ic.selected = False

    def handle_mouse_move(self, mx, my):
        self.mouse_x = mx
        self.mouse_y = my

        # Dropdown menu hover
        if self.menu.active_menu_idx >= 0:
            m = self.menu.menus[self.menu.active_menu_idx]
            items = self.menu.get_active_file_items() if m["title"] == "FILE" else m["items"]
            mw = max(len(it) for it in items) * 8 + 12
            mh = len(items) * 10 + 4
            if m["_x"] <= mx <= m["_x"] + mw and MENU_BAR_H <= my <= MENU_BAR_H + mh:
                self.menu.hover_item_idx = (my - MENU_BAR_H - 2) // 10
            else:
                self.menu.hover_item_idx = -1

        # Wireframe drag
        if self.drag_mode == "WINDOW_DRAG" and self.drag_target:
            nx = mx - self.drag_offset_x
            ny = my - self.drag_offset_y
            nx = max(0, min(SCREEN_W - 32, nx))
            ny = max(MENU_BAR_H, min(SCREEN_H - 24, ny))
            self.drag_rect = [nx, ny, self.drag_target.w, self.drag_target.h]

        # Wireframe resize
        elif self.drag_mode == "WINDOW_RESIZE" and self.drag_target:
            nw = max(self.drag_target.min_w, mx - self.drag_target.x)
            nh = max(self.drag_target.min_h, my - self.drag_target.y)
            nw = min(SCREEN_W - self.drag_target.x, nw)
            nh = min(SCREEN_H - self.drag_target.y, nh)
            self.drag_rect = [self.drag_target.x, self.drag_target.y, nw, nh]

        # Icon drag
        elif self.drag_mode == "ICON_DRAG" and self.drag_target:
            self.drag_target.x = max(0, min(SCREEN_W - 32, mx - self.drag_offset_x))
            self.drag_target.y = max(MENU_BAR_H, min(SCREEN_H - 28, my - self.drag_offset_y))

        # Scroll thumb drag
        elif self.drag_mode == "SCROLL_THUMB" and self.drag_target:
            win = self.drag_target
            track_rect = win.get_scroll_track_rect()
            thumb_y, thumb_h = win.get_thumb_rect_y_h()
            travel = track_rect.height - thumb_h
            if travel > 0:
                rel_y = my - self.drag_offset_y - track_rect.y
                ratio = max(0.0, min(1.0, rel_y / float(travel)))
                win.scroll_y = int(ratio * win.get_max_scroll())
                win.dirty = True
                if win.app and hasattr(win.app, 'dirty'):
                    win.app.dirty = True

    def handle_mouse_up(self, mx, my, button):
        self.mouse_x = mx
        self.mouse_y = my
        self.mouse_btn = 0

        # Release Window Drag -> Apply new position and redraw
        if self.drag_mode == "WINDOW_DRAG" and self.drag_target:
            if self.drag_rect:
                self.drag_target.set_pos(self.drag_rect[0], self.drag_rect[1])
            self.drag_mode = None
            self.drag_target = None
            self.drag_rect = None
            self.redraw_all()

        # Release Window Resize -> Apply new size and redraw
        elif self.drag_mode == "WINDOW_RESIZE" and self.drag_target:
            if self.drag_rect:
                self.drag_target.set_size(self.drag_rect[2], self.drag_rect[3])
            self.drag_mode = None
            self.drag_target = None
            self.drag_rect = None
            self.redraw_all()

        # Release Icon Drag -> Check if dropped onto Trash Bin
        elif self.drag_mode == "ICON_DRAG" and self.drag_target:
            trash_icon = next((ic for ic in self.icons if ic.icon_id == "trash"), None)
            if trash_icon and trash_icon.get_rect().collidepoint(mx, my) and self.drag_target != trash_icon:
                # Remove or delete item
                if self.drag_target in self.icons:
                    self.icons.remove(self.drag_target)
            self.drag_mode = None
            self.drag_target = None

        # Release Scroll Thumb Drag
        elif self.drag_mode == "SCROLL_THUMB":
            self.drag_mode = None
            self.drag_target = None
            self.drag_offset_y = 0

    def handle_key(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                # Close active window or exit GUI
                if self.active_window:
                    self.close_window(self.active_window)
                else:
                    self.running = False
                return

        # Forward keys to active window application
        if self.active_window and self.active_window.app and hasattr(self.active_window.app, 'handle_key'):
            self.active_window.app.handle_key(event)

    def query_mouse_state(self):
        """Returns (x, y, btn_mask, context_code) for BASIC MOUSE command."""
        ctx_code = CTX_DESKTOP
        mx, my = self.mouse_x, self.mouse_y

        if my < MENU_BAR_H:
            ctx_code = CTX_MENU_BAR
        elif self.menu.active_menu_idx >= 0:
            ctx_code = CTX_MENU_ITEM
        else:
            for win in reversed(self.windows):
                if not win.visible: continue
                if win.get_close_rect().collidepoint(mx, my): ctx_code = CTX_CLOSE; break
                if win.get_grab_rect().collidepoint(mx, my): ctx_code = CTX_TITLE; break
                if win.get_title_rect().collidepoint(mx, my): ctx_code = CTX_TITLE; break
                if win.get_resize_rect().collidepoint(mx, my): ctx_code = CTX_RESIZE; break
                if win.can_scroll():
                    if win.get_scroll_up_rect().collidepoint(mx, my): ctx_code = CTX_SCROLL; break
                    if win.get_scroll_down_rect().collidepoint(mx, my): ctx_code = CTX_SCROLL; break
                    if win.get_scroll_track_rect().collidepoint(mx, my): ctx_code = CTX_SCROLL; break
                if win.get_client_rect().collidepoint(mx, my): ctx_code = CTX_CLIENT; break

            if ctx_code == CTX_DESKTOP:
                for icon in self.icons:
                    if icon.get_rect().collidepoint(mx, my):
                        ctx_code = CTX_ICON
                        break

        # Invert y for Spectrum (0 at bottom, 191 at top)
        spec_y = max(0, min(191, 191 - my))
        return self.mouse_x, spec_y, self.mouse_btn, ctx_code

    def render(self, target_surf):
        """Renders entire WIMP desktop to 256x192 surface."""
        # 1. Background Stipple
        target_surf.blit(self.stipple_surf, (0, 0))

        # 2. Desktop Icons
        for icon in self.icons:
            icon.draw(target_surf)

        # 3. Windows (in z-order)
        for win in self.windows:
            win.draw(target_surf)

        # 4. Wireframe Drag / Resize Outline (Fast Spectrum Speed)
        if self.drag_rect:
            rx, ry, rw, rh = self.drag_rect
            # Draw 1px black wireframe outline
            pygame.draw.rect(target_surf, C_BLACK, (rx, ry, rw, rh), 1)

        # 5. Top Menu Bar & Pull-down Menus
        self.menu.draw(target_surf)

        # 6. Context Popup Menu (if open)
        if self.popup_menu:
            pm = self.popup_menu
            px, py, pw, ph = pm["x"], pm["y"], pm["w"], pm["h"]
            pygame.draw.rect(target_surf, C_BLACK, (px + 2, py + 2, pw, ph))
            pygame.draw.rect(target_surf, C_CYAN, (px, py, pw, ph))
            pygame.draw.rect(target_surf, C_BLACK, (px, py, pw, ph), 1)
            iy = py + 2
            for it in pm["items"]:
                draw_mono_text(target_surf, it, px + 4, iy, C_BLACK, C_CYAN)
                iy += 10

        # 7. AMX Mouse Pointer
        self.draw_pointer(target_surf)

    def draw_pointer(self, surf):
        """Renders classic Mac OS / GEM arrow pointer at (mouse_x, mouse_y)."""
        px, py = self.mouse_x, self.mouse_y
        pts = [
            (px, py),
            (px, py + 12),
            (px + 3, py + 9),
            (px + 6, py + 14),
            (px + 8, py + 13),
            (px + 5, py + 8),
            (px + 10, py + 8)
        ]
        pygame.draw.polygon(surf, C_BLACK, pts)
        inner_pts = [
            (px + 1, py + 1),
            (px + 1, py + 10),
            (px + 3, py + 8),
            (px + 6, py + 12),
            (px + 7, py + 11),
            (px + 4, py + 7),
            (px + 8, py + 7)
        ]
        pygame.draw.polygon(surf, C_WHITE, inner_pts)

    def redraw_all(self):
        for w in self.windows:
            w.dirty = True

    def launch_basic_program(self, file_item, action="RUN"):
        """Exits GUI, resets to 48K mode, loads the BASIC program, and executes or lists it."""
        self.pending_run_file = {"item": file_item, "action": action}
        self.running = False
        if not getattr(self, "in_modal_loop", False):
            self.execute_pending_run()

    def execute_pending_run(self, pending=None):
        """Switches to ZX Spectrum 48K mode, loads the selected file, and runs or lists it."""
        if pending is None:
            pending = self.pending_run_file
        self.pending_run_file = None
        if not pending:
            return

        f = pending.get("item", {})
        action = pending.get("action", "RUN")
        ctx = get_main_context()

        # 1. Switch out of GUI mode and restore Sinclair ZX Spectrum 48K mode
        for mod_name in ('BetaBasic', 'main', '__main__'):
            mod = sys.modules.get(mod_name)
            if mod is not None:
                if hasattr(mod, "gui_mode"):
                    mod.gui_mode = False
                if hasattr(mod, "set_timex_mode"):
                    try: mod.set_timex_mode(0)
                    except Exception: pass
                if hasattr(mod, "set_zx48_mode"):
                    try: mod.set_zx48_mode(reset_vars=True, attach_defaults=True)
                    except Exception:
                        try: mod.set_zx48_mode()
                        except Exception: pass
                elif hasattr(mod, "execute_statement"):
                    try: mod.execute_statement("ZX48")
                    except Exception: pass

        if ctx is not None:
            if hasattr(ctx, "gui_mode"):
                ctx.gui_mode = False
            if hasattr(ctx, "set_timex_mode"):
                try: ctx.set_timex_mode(0)
                except Exception: pass
            if hasattr(ctx, "set_zx48_mode"):
                try: ctx.set_zx48_mode(reset_vars=True, attach_defaults=True)
                except Exception:
                    try: ctx.set_zx48_mode()
                    except Exception: pass
            elif hasattr(ctx, "execute_statement"):
                try: ctx.execute_statement("ZX48")
                except Exception: pass

        # 2. Load program into memory
        is_mdr = f.get("is_mdr", False)
        path = f.get("path", "")
        name = f.get("name", "")
        drive = f.get("drive", 1)

        loaded = False
        if is_mdr:
            for mod_name in ('BetaBasic', 'main', '__main__'):
                mod = sys.modules.get(mod_name)
                if mod is not None and hasattr(mod, "mdr_load_program"):
                    try:
                        mod.mdr_load_program(drive, name)
                        loaded = True
                        break
                    except Exception: pass
            if not loaded and ctx is not None and hasattr(ctx, "mdr_load_program"):
                try:
                    ctx.mdr_load_program(drive, name)
                    loaded = True
                except Exception: pass
        else:
            if not path and name:
                path = os.path.abspath(name)
            if path and os.path.exists(path):
                for mod_name in ('BetaBasic', 'main', '__main__'):
                    mod = sys.modules.get(mod_name)
                    if mod is not None and hasattr(mod, "load_program_file"):
                        try:
                            mod.load_program_file(path, mode="")
                            loaded = True
                            break
                        except Exception: pass
                if not loaded and ctx is not None and hasattr(ctx, "load_program_file"):
                    try:
                        ctx.load_program_file(path, mode="")
                        loaded = True
                    except Exception: pass

        # 3. Refresh canvas and display for 48K display
        if ctx is not None:
            if hasattr(ctx, "canvas_dirty"): ctx.canvas_dirty = True
            if hasattr(ctx, "redraw_canvas"):
                try: ctx.redraw_canvas(force=True)
                except Exception: pass
            if hasattr(ctx, "update_display"):
                try: ctx.update_display()
                except Exception: pass

        # 4. Execute or list
        if action == "RUN":
            for mod_name in ('BetaBasic', 'main', '__main__'):
                mod = sys.modules.get(mod_name)
                if mod is not None and hasattr(mod, "run_program"):
                    try:
                        mod.run_program(0)
                        return
                    except Exception: pass
            if ctx is not None and hasattr(ctx, "run_program"):
                try: ctx.run_program(0)
                except Exception: pass
        elif action == "EDIT":
            for mod_name in ('BetaBasic', 'main', '__main__'):
                mod = sys.modules.get(mod_name)
                if mod is not None and hasattr(mod, "execute_statement"):
                    try:
                        mod.execute_statement("LIST")
                        return
                    except Exception: pass
            if ctx is not None and hasattr(ctx, "execute_statement"):
                try: ctx.execute_statement("LIST")
                except Exception: pass


# ------------------------------------------------------------------------------
# Directory View App for Drive Windows
# ------------------------------------------------------------------------------
class DirectoryViewApp:
    """Lists files inside a drive or tape window with double-click and right-click context."""
    def __init__(self, window, files):
        self.window = window
        self.files = files
        self.selected_idx = 0 if files else -1
        self.dirty = True
        self.scroll_step = 10

    def get_content_height(self):
        return len(self.files) * 10 + 2

    def handle_click(self, cx, cy):
        scroll_y = getattr(self.window, "scroll_y", 0) if self.window else 0
        row = (cy + scroll_y) // 10
        if 0 <= row < len(self.files):
            self.selected_idx = row
            self.dirty = True

    def handle_double_click(self, cx, cy):
        scroll_y = getattr(self.window, "scroll_y", 0) if self.window else 0
        row = (cy + scroll_y) // 10
        if 0 <= row < len(self.files):
            f = self.files[row]
            # If program file (.zxb or .bas), load and RUN!
            ext = f.get("ext", "").lower()
            if ext in ("bas", "zxb"):
                self.run_file(f)

    def handle_right_click(self, cx, cy, screen_mx, screen_my):
        scroll_y = getattr(self.window, "scroll_y", 0) if self.window else 0
        row = (cy + scroll_y) // 10
        if 0 <= row < len(self.files):
            self.selected_idx = row
            f = self.files[row]
            # Open Context Popup Menu
            items = ["Edit", "Delete", "Cut", "Copy", "Paste"]
            handlers = [
                lambda: self.edit_file(f),
                lambda: self.delete_file(f),
                lambda: self.cut_file(f),
                lambda: self.copy_file(f),
                lambda: self.paste_file()
            ]
            self.window.desktop.popup_menu = {
                "x": min(SCREEN_W - 54, screen_mx),
                "y": min(SCREEN_H - 56, screen_my),
                "w": 52,
                "h": len(items) * 10 + 4,
                "items": items,
                "handlers": handlers,
                "target": f
            }

    def run_file(self, f):
        if self.window and self.window.desktop:
            self.window.desktop.launch_basic_program(f, action="RUN")

    def edit_file(self, f):
        if self.window and self.window.desktop:
            self.window.desktop.launch_basic_program(f, action="EDIT")

    def delete_file(self, f):
        path = f.get("path", "")
        if path and os.path.exists(path):
            try:
                os.remove(path)
                self.files.remove(f)
                self.dirty = True
            except Exception:
                pass

    def cut_file(self, f):
        self.copy_file(f)
        self.delete_file(f)

    def copy_file(self, f):
        if self.window and self.window.desktop:
            self.window.desktop.clipboard_file = f

    def paste_file(self):
        # Pastes clipboard file to this drive, using wimp.mdr as temp cache
        cb = self.window.desktop.clipboard_file
        if cb and cb.get("path") and os.path.exists(cb["path"]):
            import shutil
            dest = os.path.join(".", cb["name"])
            shutil.copyfile(cb["path"], dest)
            self.files.append({"name": cb["name"], "ext": cb.get("ext", "bas"), "path": os.path.abspath(dest)})
            self.dirty = True

    def render(self, surf):
        surf.fill(C_CYAN)
        scroll_y = getattr(self.window, "scroll_y", 0) if self.window else 0
        y = 1 - scroll_y
        for idx, f in enumerate(self.files):
            is_sel = (idx == self.selected_idx)
            fn = f["name"][:24]
            ext = f.get("ext", "").upper()
            if y + 10 > 0 and y < surf.get_height():
                if is_sel:
                    pygame.draw.rect(surf, C_BLACK, (0, y - 1, surf.get_width(), 9))
                    draw_mini_text(surf, f"[{ext:<3}] {fn}", 2, y, C_CYAN, C_BLACK)
                else:
                    draw_mini_text(surf, f"[{ext:<3}] {fn}", 2, y, C_BLACK, C_CYAN)
            y += 10


# ------------------------------------------------------------------------------
# Interactive 16x16 Icon Editor (ICONED)
# ------------------------------------------------------------------------------
class IconEditor:
    """
    Interactive 16x16 monochrome icon editor styled similarly to tile_editor.py.
    Provides pixel drawing, 1:1 preview, tools (invert, clear, flip, rotate),
    and BASIC statement line generation (ICON DEF id, "...").
    """
    def __init__(self, icon_id=0):
        self.icon_id = max(0, min(63, int(icon_id)))
        self.pixels = bytearray(256)  # 16x16 (0 or 1)
        self.running = True
        self.status_msg = f"ICONED Ready - Icon #{self.icon_id}"
        self.mouse_down = False
        self.mouse_paint_val = None

        # Load existing icon if available
        custom_icons = getattr(get_main_context(), "CUSTOM_ICONS", {}) if get_main_context() else {}
        if self.icon_id in custom_icons:
            self.load_from_bytes(custom_icons[self.icon_id])

    def load_from_bytes(self, data_bytes):
        for r in range(16):
            if r * 2 + 1 < len(data_bytes):
                w = (data_bytes[r * 2] << 8) | data_bytes[r * 2 + 1]
                for c in range(16):
                    self.pixels[r * 16 + c] = 1 if (w & (1 << (15 - c))) else 0

    def to_bytes(self):
        data = bytearray(32)
        for r in range(16):
            w = 0
            for c in range(16):
                if self.pixels[r * 16 + c]:
                    w |= (1 << (15 - c))
            data[r * 2] = (w >> 8) & 0xFF
            data[r * 2 + 1] = w & 0xFF
        return data

    def set_pixel(self, x, y, val=1):
        if 0 <= x < 16 and 0 <= y < 16:
            self.pixels[y * 16 + x] = 1 if val else 0

    def get_pixel(self, x, y):
        if 0 <= x < 16 and 0 <= y < 16:
            return self.pixels[y * 16 + x]
        return 0

    def clear(self):
        self.pixels = bytearray(256)
        self.status_msg = "Icon Cleared"

    def invert(self):
        for i in range(256):
            self.pixels[i] = 0 if self.pixels[i] else 1
        self.status_msg = "Icon Inverted"

    def invert_pixels(self):
        self.invert()

    def flip_h(self):
        new_px = bytearray(256)
        for r in range(16):
            for c in range(16):
                new_px[r * 16 + c] = self.pixels[r * 16 + (15 - c)]
        self.pixels = new_px
        self.status_msg = "Flipped Horizontal"

    def flip_horizontal(self):
        self.flip_h()

    def flip_v(self):
        new_px = bytearray(256)
        for r in range(16):
            for c in range(16):
                new_px[r * 16 + c] = self.pixels[(15 - r) * 16 + c]
        self.pixels = new_px
        self.status_msg = "Flipped Vertical"

    def flip_vertical(self):
        self.flip_v()

    def rotate_90(self):
        new_px = bytearray(256)
        for r in range(16):
            for c in range(16):
                new_px[c * 16 + (15 - r)] = self.pixels[r * 16 + c]
        self.pixels = new_px
        self.status_msg = "Rotated 90 deg"

    def generate_basic_line(self, line_num=None):
        """Generates Sinclair BASIC line 'ICON DEF id, ...' into resident program."""
        ctx = get_main_context()
        hex_str = self.to_bytes().hex().upper()
        line_no = line_num if line_num is not None else (8000 + self.icon_id * 10)
        cmd_text = f'{line_no} ICON DEF {self.icon_id}, "{hex_str}"'

        if ctx is not None and hasattr(ctx, "program"):
            ctx.program[line_no] = f'ICON DEF {self.icon_id}, "{hex_str}"'
            if hasattr(ctx, "program_line_order") and line_no not in ctx.program_line_order:
                ctx.program_line_order.append(line_no)
                ctx.program_line_order.sort()
            self.status_msg = f"Generated Line {line_no}!"
        else:
            self.status_msg = f"DEF {self.icon_id}: {hex_str[:16]}..."
        return cmd_text

    def handle_click(self, cx, cy, button):
        # 16x16 Grid: x=10..106, y=18..114 (6x6 pixels per cell)
        if 10 <= cx < 106 and 18 <= cy < 114:
            col = (cx - 10) // 6
            row = (cy - 18) // 6
            if 0 <= row < 16 and 0 <= col < 16:
                val = 0 if button == 3 else 1
                self.pixels[row * 16 + col] = val
                self.mouse_down = True
                self.mouse_paint_val = val

        # Tools on right side: x=120..240
        elif 120 <= cx <= 240:
            if 40 <= cy <= 50: self.invert()
            elif 54 <= cy <= 64: self.clear()
            elif 68 <= cy <= 78: self.flip_h()
            elif 82 <= cy <= 92: self.flip_v()
            elif 96 <= cy <= 106: self.rotate_90()
            elif 110 <= cy <= 120: self.generate_basic_line()
            elif 124 <= cy <= 134: self.running = False  # Exit

    def handle_drag(self, cx, cy):
        if 10 <= cx < 106 and 18 <= cy < 114:
            col = (cx - 10) // 6
            row = (cy - 18) // 6
            if 0 <= row < 16 and 0 <= col < 16 and self.mouse_paint_val is not None:
                self.pixels[row * 16 + col] = self.mouse_paint_val

    def handle_key(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_q, pygame.K_ESCAPE): self.running = False
            elif event.key == pygame.K_i: self.invert()
            elif event.key == pygame.K_c: self.clear()
            elif event.key == pygame.K_h: self.flip_h()
            elif event.key == pygame.K_v: self.flip_v()
            elif event.key == pygame.K_r: self.rotate_90()
            elif event.key == pygame.K_g: self.generate_basic_line()

    def render(self, surf):
        surf.fill(C_CYAN)
        # Header bar
        pygame.draw.rect(surf, C_BLACK, (0, 0, SCREEN_W, 11))
        draw_mono_text(surf, f"ICONED - ICON #{self.icon_id:02d}", 4, 1, C_CYAN, C_BLACK)

        # 16x16 Pixel Grid (x=10, y=18, cell=6)
        gx, gy = 10, 18
        pygame.draw.rect(surf, C_BLACK, (gx - 1, gy - 1, 98, 98), 1)
        for r in range(16):
            for c in range(16):
                px = gx + c * 6
                py = gy + r * 6
                val = self.pixels[r * 16 + c]
                pygame.draw.rect(surf, C_BLACK if val else C_CYAN, (px, py, 6, 6))
                pygame.draw.rect(surf, C_DARK_GRAY, (px, py, 6, 6), 1)

        # 1:1 Preview Box on right (x=120, y=18)
        draw_mini_text(surf, "PREVIEW:", 120, 18, C_BLACK, C_CYAN)
        pygame.draw.rect(surf, C_BLACK, (170, 16, 18, 18), 1)
        draw_icon_16x16(surf, self.to_bytes(), 171, 17)

        # Tool buttons
        buttons = [
            ("[INV] INVERT", 40),
            ("[CLR] CLEAR", 54),
            ("[FLIP H]", 68),
            ("[FLIP V]", 82),
            ("[ROT] 90 DEG", 96),
            ("[GEN] BASIC", 110),
            ("[EXT] EXIT", 124)
        ]
        for lbl, by in buttons:
            pygame.draw.rect(surf, C_BLACK, (120, by, 120, 11), 1)
            draw_mini_text(surf, lbl, 124, by + 2, C_BLACK, C_CYAN)

        # Status Bar
        pygame.draw.line(surf, C_BLACK, (0, SCREEN_H - 12), (SCREEN_W, SCREEN_H - 12))
        draw_mini_text(surf, self.status_msg, 4, SCREEN_H - 10, C_BLACK, C_CYAN)


# ------------------------------------------------------------------------------
# Launchers and BASIC Command Dispatchers
# ------------------------------------------------------------------------------
def launch_wimp_desktop():
    """Launches interactive WIMP Desktop event loop inside the ZX Spectrum output window."""
    desktop = WIMPDesktop.get_instance()
    desktop.running = True
    ctx = get_main_context()

    # Enter Timex 512x192 Mode 6 for WIMP GUI
    for mod_name in ('BetaBasic', 'main', '__main__'):
        mod = sys.modules.get(mod_name)
        if mod is not None:
            if hasattr(mod, "gui_mode"):
                mod.gui_mode = True
            if hasattr(mod, "set_timex_mode"):
                try: mod.set_timex_mode(6)
                except Exception: pass

    if ctx is not None:
        ctx.gui_mode = True
        if hasattr(ctx, "set_timex_mode"):
            try: ctx.set_timex_mode(6)
            except Exception: pass
        elif hasattr(ctx, "execute_statement"):
            try: ctx.execute_statement("MODE 6")
            except Exception: pass
        screen = getattr(ctx, "screen", None)
        scale_x = getattr(ctx, "scale_x", 1.0)
        scale_y = getattr(ctx, "scale_y", 1.0)
        canvas_blit_x = getattr(ctx, "canvas_blit_x", 0)
        canvas_blit_y = getattr(ctx, "canvas_blit_y", 0)
    else:
        screen = None
        scale_x, scale_y, canvas_blit_x, canvas_blit_y = 1.0, 1.0, 0, 0

    clock = pygame.time.Clock()
    canvas = desktop.canvas
    desktop.in_modal_loop = True
    desktop.pending_run_file = None

    try:
        while desktop.running:
            clock.tick(50)

            if ctx is not None:
                screen = getattr(ctx, "screen", screen)
                scale_x = getattr(ctx, "scale_x", scale_x)
                scale_y = getattr(ctx, "scale_y", scale_y)
                canvas_blit_x = getattr(ctx, "canvas_blit_x", canvas_blit_x)
                canvas_blit_y = getattr(ctx, "canvas_blit_y", canvas_blit_y)

            # Update clock app if active
            for w in desktop.windows:
                if w.app and hasattr(w.app, 'update'):
                    w.app.update()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    desktop.running = False
                    pygame.quit()
                    sys.exit(0)
                elif event.type == pygame.VIDEORESIZE and ctx is not None:
                    ctx.screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
                    screen = ctx.screen
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if scale_x > 0 and scale_y > 0:
                        scaled_w = getattr(ctx, "scaled_canvas_w", None) if ctx else None
                        scaled_h = getattr(ctx, "scaled_canvas_h", None) if ctx else None
                        if scaled_w and scaled_w > 0 and scaled_h and scaled_h > 0:
                            cx = int((event.pos[0] - canvas_blit_x) / float(scaled_w) * SCREEN_W)
                            cy = int((event.pos[1] - canvas_blit_y) / float(scaled_h) * SCREEN_H)
                        else:
                            cx = int((event.pos[0] - canvas_blit_x) / scale_x)
                            cy = int((event.pos[1] - canvas_blit_y) / scale_y)
                        if 0 <= cx < SCREEN_W and 0 <= cy < SCREEN_H:
                            desktop.handle_mouse_down(cx, cy, event.button)
                elif event.type == pygame.MOUSEBUTTONUP:
                    if scale_x > 0 and scale_y > 0:
                        scaled_w = getattr(ctx, "scaled_canvas_w", None) if ctx else None
                        scaled_h = getattr(ctx, "scaled_canvas_h", None) if ctx else None
                        if scaled_w and scaled_w > 0 and scaled_h and scaled_h > 0:
                            cx = int((event.pos[0] - canvas_blit_x) / float(scaled_w) * SCREEN_W)
                            cy = int((event.pos[1] - canvas_blit_y) / float(scaled_h) * SCREEN_H)
                        else:
                            cx = int((event.pos[0] - canvas_blit_x) / scale_x)
                            cy = int((event.pos[1] - canvas_blit_y) / scale_y)
                        desktop.handle_mouse_up(cx, cy, event.button)
                elif event.type == pygame.MOUSEMOTION:
                    if scale_x > 0 and scale_y > 0:
                        scaled_w = getattr(ctx, "scaled_canvas_w", None) if ctx else None
                        scaled_h = getattr(ctx, "scaled_canvas_h", None) if ctx else None
                        if scaled_w and scaled_w > 0 and scaled_h and scaled_h > 0:
                            cx = int((event.pos[0] - canvas_blit_x) / float(scaled_w) * SCREEN_W)
                            cy = int((event.pos[1] - canvas_blit_y) / float(scaled_h) * SCREEN_H)
                        else:
                            cx = int((event.pos[0] - canvas_blit_x) / scale_x)
                            cy = int((event.pos[1] - canvas_blit_y) / scale_y)
                        desktop.handle_mouse_move(cx, cy)
                elif event.type == pygame.KEYDOWN:
                    desktop.handle_key(event)

            desktop.render(canvas)

            if ctx is not None and hasattr(ctx, "render_frame") and callable(ctx.render_frame):
                if hasattr(ctx, "canvas") and ctx.canvas is not None and ctx.canvas != canvas:
                    ctx.canvas.blit(canvas, (0, 0))
                ctx.render_frame()
                try:
                    pygame.display.flip()
                except Exception:
                    pass
            elif screen is not None:
                cur_w, cur_h = screen.get_size()
                aspect = SCREEN_W / float(SCREEN_H)
                if cur_w / float(cur_h) > aspect:
                    sh = cur_h
                    sw = int(sh * aspect)
                    sx = (cur_w - sw) // 2
                    sy = 0
                else:
                    sw = cur_w
                    sh = int(sw / aspect)
                    sx = 0
                    sy = (cur_h - sh) // 2
                screen.fill(C_BLACK)
                scaled = pygame.transform.scale(canvas, (sw, sh))
                screen.blit(scaled, (sx, sy))
                try:
                    pygame.display.flip()
                except Exception:
                    pass
    finally:
        desktop.in_modal_loop = False
        desktop.running = False

        # Cleanup upon exit: restore Timex mode 0 and ZX48 normal screen
        for mod_name in ('BetaBasic', 'main', '__main__'):
            mod = sys.modules.get(mod_name)
            if mod is not None:
                if hasattr(mod, "gui_mode"):
                    mod.gui_mode = False
                if hasattr(mod, "set_timex_mode"):
                    try: mod.set_timex_mode(0)
                    except Exception: pass
                if hasattr(mod, "set_zx48_mode"):
                    try: mod.set_zx48_mode(reset_vars=True, attach_defaults=True)
                    except Exception:
                        try: mod.set_zx48_mode()
                        except Exception: pass
                elif hasattr(mod, "execute_statement"):
                    try: mod.execute_statement("ZX48")
                    except Exception: pass
        if ctx is not None:
            if hasattr(ctx, "gui_mode"):
                ctx.gui_mode = False
            if hasattr(ctx, "set_timex_mode"):
                try: ctx.set_timex_mode(0)
                except Exception: pass
            if hasattr(ctx, "set_zx48_mode"):
                try: ctx.set_zx48_mode(reset_vars=True, attach_defaults=True)
                except Exception:
                    try: ctx.set_zx48_mode()
                    except Exception: pass
            elif hasattr(ctx, "execute_statement"):
                try: ctx.execute_statement("ZX48")
                except Exception: pass
            if hasattr(ctx, "canvas_dirty"): ctx.canvas_dirty = True
            if hasattr(ctx, "redraw_canvas"): ctx.redraw_canvas(force=True)
            if hasattr(ctx, "update_display"): ctx.update_display()

        if getattr(desktop, "pending_run_file", None):
            desktop.execute_pending_run()


def launch_icon_editor(args=""):
    """Launches interactive 16x16 icon editor within the ZX Spectrum output window."""
    icon_id = 0
    if args:
        try:
            icon_id = int(args.split()[0].strip(":"))
        except Exception:
            icon_id = 0

    editor = IconEditor(icon_id)
    ctx = get_main_context()

    if ctx is not None:
        ctx.gui_mode = True
        screen = getattr(ctx, "screen", None)
        scale_x = getattr(ctx, "scale_x", 1.0)
        scale_y = getattr(ctx, "scale_y", 1.0)
        canvas_blit_x = getattr(ctx, "canvas_blit_x", 0)
        canvas_blit_y = getattr(ctx, "canvas_blit_y", 0)
    else:
        screen = None
        scale_x, scale_y, canvas_blit_x, canvas_blit_y = 1.0, 1.0, 0, 0

    clock = pygame.time.Clock()
    surf = pygame.Surface((SCREEN_W, SCREEN_H))

    while editor.running:
        clock.tick(50)

        if ctx is not None:
            screen = getattr(ctx, "screen", screen)
            scale_x = getattr(ctx, "scale_x", scale_x)
            scale_y = getattr(ctx, "scale_y", scale_y)
            canvas_blit_x = getattr(ctx, "canvas_blit_x", canvas_blit_x)
            canvas_blit_y = getattr(ctx, "canvas_blit_y", canvas_blit_y)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                editor.running = False
                pygame.quit()
                sys.exit(0)
            elif event.type == pygame.VIDEORESIZE and ctx is not None:
                ctx.screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
                screen = ctx.screen
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if scale_x > 0 and scale_y > 0:
                    scaled_w = getattr(ctx, "scaled_canvas_w", None) if ctx else None
                    scaled_h = getattr(ctx, "scaled_canvas_h", None) if ctx else None
                    if scaled_w and scaled_w > 0 and scaled_h and scaled_h > 0:
                        cx = int((event.pos[0] - canvas_blit_x) / float(scaled_w) * SCREEN_W)
                        cy = int((event.pos[1] - canvas_blit_y) / float(scaled_h) * SCREEN_H)
                    else:
                        cx = int((event.pos[0] - canvas_blit_x) / scale_x)
                        cy = int((event.pos[1] - canvas_blit_y) / scale_y)
                    if 0 <= cx < SCREEN_W and 0 <= cy < SCREEN_H:
                        editor.handle_click(cx, cy, event.button)
            elif event.type == pygame.MOUSEBUTTONUP:
                editor.mouse_down = False
                editor.mouse_paint_val = None
            elif event.type == pygame.MOUSEMOTION:
                if editor.mouse_down and scale_x > 0 and scale_y > 0:
                    scaled_w = getattr(ctx, "scaled_canvas_w", None) if ctx else None
                    scaled_h = getattr(ctx, "scaled_canvas_h", None) if ctx else None
                    if scaled_w and scaled_w > 0 and scaled_h and scaled_h > 0:
                        cx = int((event.pos[0] - canvas_blit_x) / float(scaled_w) * SCREEN_W)
                        cy = int((event.pos[1] - canvas_blit_y) / float(scaled_h) * SCREEN_H)
                    else:
                        cx = int((event.pos[0] - canvas_blit_x) / scale_x)
                        cy = int((event.pos[1] - canvas_blit_y) / scale_y)
                    if 0 <= cx < SCREEN_W and 0 <= cy < SCREEN_H:
                        editor.handle_drag(cx, cy)
            elif event.type == pygame.KEYDOWN:
                editor.handle_key(event)

        editor.render(surf)

        if ctx is not None and hasattr(ctx, "render_frame") and callable(ctx.render_frame):
            if hasattr(ctx, "canvas") and ctx.canvas is not None and ctx.canvas != surf:
                ctx.canvas.blit(surf, (0, 0))
            ctx.render_frame()
            try:
                pygame.display.flip()
            except Exception:
                pass
        elif screen is not None:
            cur_w, cur_h = screen.get_size()
            aspect = SCREEN_W / float(SCREEN_H)
            if cur_w / float(cur_h) > aspect:
                sh = cur_h
                sw = int(sh * aspect)
                sx = (cur_w - sw) // 2
                sy = 0
            else:
                sw = cur_w
                sh = int(sw / aspect)
                sx = 0
                sy = (cur_h - sh) // 2
            screen.fill(C_BLACK)
            scaled = pygame.transform.scale(surf, (sw, sh))
            screen.blit(scaled, (sx, sy))
            try:
                pygame.display.flip()
            except Exception:
                pass

    # Save defined icon into runtime CUSTOM_ICONS
    if ctx is not None:
        if hasattr(ctx, "gui_mode"):
            ctx.gui_mode = False
        if not hasattr(ctx, "CUSTOM_ICONS"):
            ctx.CUSTOM_ICONS = {}
        ctx.CUSTOM_ICONS[editor.icon_id] = editor.to_bytes()
        if hasattr(ctx, "canvas_dirty"): ctx.canvas_dirty = True
        if hasattr(ctx, "redraw_canvas"): ctx.redraw_canvas(force=True)
        if hasattr(ctx, "update_display"): ctx.update_display()

    return editor


# ------------------------------------------------------------------------------
# BASIC Command Statement Handlers
# ------------------------------------------------------------------------------
def _split_args(s):
    """Splits string by comma outside quotes and parentheses."""
    res = []
    curr = []
    in_quote = False
    paren_depth = 0
    for ch in s:
        if ch == '"':
            in_quote = not in_quote
            curr.append(ch)
        elif ch == '(' and not in_quote:
            paren_depth += 1
            curr.append(ch)
        elif ch == ')' and not in_quote:
            paren_depth = max(0, paren_depth - 1)
            curr.append(ch)
        elif ch == ',' and not in_quote and paren_depth == 0:
            res.append(''.join(curr).strip())
            curr = []
        else:
            curr.append(ch)
    if curr:
        res.append(''.join(curr).strip())
    return res


def handle_gui_command(stmt_str="", ctx=None):
    """Handles GUI, GUI ON, GUI OFF commands."""
    if ctx is None:
        ctx = get_main_context()
    s = (stmt_str or "").strip()
    if s.upper().startswith("GUI"):
        s = s[3:].strip()
    if s.startswith(":"):
        s = s[1:].strip()
    s_upper = s.upper()

    is_on = None
    if s_upper in ("", "RUN", "START"):
        is_on = True
    elif s_upper in ("ON", "/ON"):
        is_on = True
    elif s_upper in ("OFF", "/OFF"):
        is_on = False

    for mod_name in ('BetaBasic', 'main', '__main__'):
        mod = sys.modules.get(mod_name)
        if mod is not None and hasattr(mod, "gui_mode") and is_on is not None:
            mod.gui_mode = is_on

    if ctx is not None and hasattr(ctx, "gui_mode") and is_on is not None:
        ctx.gui_mode = is_on

    desktop = WIMPDesktop.get_instance()
    if is_on is True:
        desktop.running = True
        for mod_name in ('BetaBasic', 'main', '__main__'):
            mod = sys.modules.get(mod_name)
            if mod is not None and hasattr(mod, "set_timex_mode"):
                try: mod.set_timex_mode(6)
                except Exception: pass
        if ctx is not None and hasattr(ctx, "set_timex_mode"):
            try: ctx.set_timex_mode(6)
            except Exception: pass
        if s_upper in ("", "RUN", "START"):
            launch_wimp_desktop()
        else:
            if ctx is not None and hasattr(ctx, "redraw_canvas"):
                try: ctx.redraw_canvas(force=True)
                except Exception: pass
            if ctx is not None and hasattr(ctx, "update_display"):
                try: ctx.update_display()
                except Exception: pass
    elif is_on is False:
        desktop.running = False
        for mod_name in ('BetaBasic', 'main', '__main__'):
            mod = sys.modules.get(mod_name)
            if mod is not None:
                if hasattr(mod, "gui_mode"):
                    mod.gui_mode = False
                if hasattr(mod, "set_timex_mode"):
                    try: mod.set_timex_mode(0)
                    except Exception: pass
                if hasattr(mod, "set_zx48_mode"):
                    try: mod.set_zx48_mode()
                    except Exception: pass
                elif hasattr(mod, "execute_statement"):
                    try: mod.execute_statement("ZX48")
                    except Exception: pass
        if ctx is not None:
            if hasattr(ctx, "gui_mode"):
                ctx.gui_mode = False
            if hasattr(ctx, "set_timex_mode"):
                try: ctx.set_timex_mode(0)
                except Exception: pass
            if hasattr(ctx, "set_zx48_mode"):
                try: ctx.set_zx48_mode()
                except Exception: pass
            elif hasattr(ctx, "execute_statement"):
                try: ctx.execute_statement("ZX48")
                except Exception: pass
            if hasattr(ctx, "canvas_dirty"): ctx.canvas_dirty = True
            if hasattr(ctx, "redraw_canvas"): ctx.redraw_canvas(force=True)
            if hasattr(ctx, "update_display"):
                try: ctx.update_display()
                except Exception: pass


def handle_wimp_window_command(stmt_str=""):
    """
    Handles WIMP window management from BASIC:
    WINDOW OPEN id, x, y, w, h [, "title"]
    WINDOW CLOSE [id]
    WINDOW MOVE id, x, y
    WINDOW SIZE id, w, h
    WINDOW SELECT id
    WINDOW CLS [id]
    WINDOW PRINT id, "text"
    """
    desktop = WIMPDesktop.get_instance()
    s = (stmt_str or "").strip()
    if s.upper().startswith("WINDOW"):
        s = s[6:].strip()
    if s.startswith(":"):
        s = s[1:].strip()
    s_upper = s.upper()

    if s_upper.startswith("OPEN "):
        parts = _split_args(s[5:].strip())
        if len(parts) >= 5:
            win_id = parts[0].strip('"\';')
            try:
                x = int(float(parts[1]))
                y = int(float(parts[2]))
                w = int(float(parts[3]))
                h = int(float(parts[4]))
                title = parts[5].strip('"\';') if len(parts) > 5 else f"Window {win_id}"
            except ValueError:
                title = parts[1].strip('"\';')
                x = int(float(parts[2])) if len(parts) > 2 else 20
                y = int(float(parts[3])) if len(parts) > 3 else 20
                w = int(float(parts[4])) if len(parts) > 4 else 120
                h = int(float(parts[5])) if len(parts) > 5 else 80
            win = WIMPWindow(win_id, title, x, y, w, h, desktop)
            desktop.add_window(win)
            return win

    elif s_upper.startswith("CLOSE"):
        rem = s[5:].strip()
        if rem:
            win_id = rem.strip('"\';')
            target = next((w for w in desktop.windows if str(w.win_id) == win_id), None)
            if target:
                desktop.close_window(target)
        elif desktop.active_window:
            desktop.close_window(desktop.active_window)

    elif s_upper.startswith("MOVE "):
        parts = _split_args(s[5:].strip())
        if len(parts) >= 3:
            win_id = parts[0].strip('"\';')
            x = int(float(parts[1]))
            y = int(float(parts[2]))
            target = next((w for w in desktop.windows if str(w.win_id) == win_id), None)
            if target:
                target.set_pos(x, y)

    elif s_upper.startswith("SIZE "):
        parts = _split_args(s[5:].strip())
        if len(parts) >= 3:
            win_id = parts[0].strip('"\';')
            w = int(float(parts[1]))
            h = int(float(parts[2]))
            target = next((w for w in desktop.windows if str(w.win_id) == win_id), None)
            if target:
                target.set_size(w, h)

    elif s_upper.startswith("SELECT "):
        win_id = s[7:].strip().strip('"\';')
        target = next((w for w in desktop.windows if str(w.win_id) == win_id), None)
        if target:
            desktop.select_window(target)

    elif s_upper.startswith("CLS"):
        rem = s[3:].strip()
        target = desktop.active_window
        if rem:
            win_id = rem.strip('"\';')
            target = next((w for w in desktop.windows if str(w.win_id) == win_id), desktop.active_window)
        if target:
            target.cls()

    elif s_upper.startswith("PRINT "):
        parts = _split_args(s[6:].strip())
        if len(parts) >= 2:
            win_id = parts[0].strip('"\';')
            text = parts[1].strip('"\';')
            target = next((w for w in desktop.windows if str(w.win_id) == win_id), None)
            if target:
                target.print_text(text)


def handle_wimp_menu_command(stmt_str=""):
    """
    Handles MENU command extensions from BASIC:
    MENU ADD "Title"
    MENU ITEM menu_idx, "ItemName"
    MENU CLEAR
    MENU ON / MENU OFF
    """
    desktop = WIMPDesktop.get_instance()
    s = (stmt_str or "").strip()
    if s.upper().startswith("MENU"):
        s = s[4:].strip()
    if s.startswith(":"):
        s = s[1:].strip()
    s_upper = s.upper()

    if s_upper.startswith("ADD "):
        title = s[4:].strip().strip('"\';')
        desktop.menu.add_menu(title)

    elif s_upper.startswith("ITEM "):
        parts = _split_args(s[5:].strip())
        if len(parts) >= 2:
            m_idx = int(float(parts[0]))
            it_name = parts[1].strip('"\';')
            desktop.menu.add_item(m_idx, it_name)

    elif s_upper.startswith("CLEAR"):
        desktop.menu.reset_default_menus()

    elif s_upper in ("ON", "/ON"):
        desktop.menu.visible = True

    elif s_upper in ("OFF", "/OFF"):
        desktop.menu.visible = False

    elif "," in s:
        parts = _split_args(s)
        if len(parts) >= 2:
            title = parts[0].strip('"\';')
            m_idx = desktop.menu.add_menu(title)
            items = parts[1].strip('"\';').split("|")
            for it in items:
                it = it.strip()
                if it:
                    desktop.menu.add_item(m_idx, it)


def handle_wimp_mouse_command(stmt_str="", ctx=None):
    """
    Handles MOUSE command from BASIC:
    MOUSE x_var, y_var, btn_var [, ctx_var]
    Also backward-compatible with MOUSE /AMX and MOUSE /KEMP.
    """
    if ctx is None:
        ctx = get_main_context()
    s = (stmt_str or "").strip()
    if s.upper().startswith("MOUSE"):
        s = s[5:].strip()
    if s.startswith(":"):
        s = s[1:].strip()

    # Hardware switch check (/AMX, /KEMP)
    s_upper = s.upper()
    if s_upper.startswith("/") or s_upper in ("AMX", "KEMP", "KEMPSTON", "?", "HELP", "STATUS"):
        if ctx is not None and hasattr(ctx, "handle_mousey_command"):
            ctx.handle_mousey_command(stmt_str)
            return

    # Variable assignment: MOUSE x, y, b [, c]
    parts = _split_args(s)
    if len(parts) >= 3:
        desktop = WIMPDesktop.get_instance()
        mx, my, mb, mc = desktop.query_mouse_state()
        vx = parts[0].strip().upper()
        vy = parts[1].strip().upper()
        vb = parts[2].strip().upper()
        vc = parts[3].strip().upper() if len(parts) >= 4 else None

        if ctx is not None and hasattr(ctx, "variables"):
            ctx.variables[vx] = float(mx)
            ctx.variables[vy] = float(my)
            ctx.variables[vb] = float(mb)
            if vc:
                ctx.variables[vc] = float(mc)

        for mod_name in ('BetaBasic', 'main', '__main__'):
            mod = sys.modules.get(mod_name)
            if mod is not None and hasattr(mod, "variables"):
                mod.variables[vx] = float(mx)
                mod.variables[vy] = float(my)
                mod.variables[vb] = float(mb)
                if vc:
                    mod.variables[vc] = float(mc)


def handle_wimp_icon_command(stmt_str=""):
    """
    Handles ICON command from BASIC:
    ICON DEF id, "hex_string"
    ICON DRAW id, x, y
    ICON CLEAR [id]
    """
    ctx = get_main_context()
    s = (stmt_str or "").strip()
    if s.upper().startswith("ICON"):
        s = s[4:].strip()
    if s.startswith(":"):
        s = s[1:].strip()
    s_upper = s.upper()

    if not hasattr(ctx, "CUSTOM_ICONS"):
        ctx.CUSTOM_ICONS = {}

    if s_upper.startswith("DEF "):
        parts = _split_args(s[4:].strip())
        if len(parts) >= 2:
            icon_id = int(float(parts[0]))
            hex_data = parts[1].strip('"\';')
            # Decode hex or comma bytes
            try:
                clean_hex = re.sub(r'[^0-9A-Fa-f]', '', hex_data)
                raw = bytes.fromhex(clean_hex)
                ctx.CUSTOM_ICONS[icon_id] = raw
            except Exception:
                pass

    elif s_upper.startswith("DRAW "):
        parts = _split_args(s[5:].strip())
        if len(parts) >= 3:
            icon_id = int(float(parts[0]))
            x = int(float(parts[1]))
            y = int(float(parts[2]))
            bmp = ctx.CUSTOM_ICONS.get(icon_id)
            if bmp and ctx is not None:
                screen_surf = getattr(ctx, "screen", None)
                if screen_surf is not None:
                    # Invert y for Spectrum coords if needed
                    draw_icon_16x16(screen_surf, bmp, x, y)
                    if hasattr(ctx, "update_display"): ctx.update_display()

    elif s_upper.startswith("CLEAR"):
        rem = s[5:].strip()
        if rem:
            try:
                icon_id = int(float(rem))
                ctx.CUSTOM_ICONS.pop(icon_id, None)
            except Exception:
                pass
        else:
            ctx.CUSTOM_ICONS.clear()

    elif "," in s:
        parts = _split_args(s)
        if len(parts) >= 3:
            desktop = WIMPDesktop.get_instance()
            try:
                if len(parts) >= 4:
                    icon_id = parts[0].strip('"\';')
                    x = int(float(parts[1]))
                    y = int(float(parts[2]))
                    lbl = parts[3].strip('"\';')
                else:
                    icon_id = str(len(desktop.icons) + 1)
                    x = int(float(parts[0]))
                    y = int(float(parts[1]))
                    lbl = parts[2].strip('"\';')
                desktop.icons.append(WIMPIcon(f"custom_{icon_id}", lbl, "data_file", x, y))
            except Exception:
                pass

