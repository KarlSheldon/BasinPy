"""
ZX Spectrum 16x16 Sprite Editor for BasinPy & BetaBasic
Command: EDSPRITES [sprite_id | "ZX" | "NEXT"]

Features:
- Dual-Engine Support:
  1. ZX Engine: Monochrome 16x16 1-bit sprites matching machine code ZXSpriteEngine (Boriel compiler compatible).
     Saves into standard Sinclair 48K BASIC (lines 5000+).
  2. NEXT Engine: ZX Spectrum Next hardware color sprites supporting 16, 32, 64, 128, and 256 colors.
     Saves into native NextBASIC definitions (lines 5000+).
- ZX Mode:
  - 16 sprite slots with 4 frames per sprite (32 bytes/frame, 128 bytes/def).
  - INK attribute (0..7) and machine code motion parameters (direction, speed, path, rebound).
  - 4 frames in a row with 5th animated preview sequence.
- NEXT Mode:
  - 64 hardware sprite patterns (256 bytes each / 16x16 pixels with 8-bit palette indices).
  - 5 selectable color depths: 16, 32, 64, 128, 256 colors.
  - Interactive palette swatches with Next 9-bit RGB rendering.
  - Transparency support (Next standard 0xE3 / 227).
  - Full drawing controls: Draw, Erase/Transparent, Invert, Flip H/V, Rotate 90.
"""

import os
import re
import sys
import pygame

try:
    from sprite_engine_z80 import (
        SLOT_STATUS, SLOT_DEF_ID, SLOT_X, SLOT_Y, SLOT_INK, SLOT_FRAME_COUNT,
        SLOT_DIR, SLOT_PATH_MODE, SLOT_SPEED, SLOT_PATH_PARAM, SLOT_REBOUND_FRAMES
    )
except Exception:
    SLOT_STATUS, SLOT_DEF_ID, SLOT_X, SLOT_Y, SLOT_INK, SLOT_FRAME_COUNT = 0, 1, 2, 3, 7, 9
    SLOT_DIR, SLOT_PATH_MODE, SLOT_SPEED, SLOT_PATH_PARAM, SLOT_REBOUND_FRAMES = 13, 14, 15, 18, 20

def get_main_context():
    """Safely retrieves the live BasinPy runtime module context (__main__, main, or BetaBasic)."""
    for mod_name in ('__main__', 'main', 'BetaBasic'):
        mod = sys.modules.get(mod_name)
        if mod is not None and hasattr(mod, 'program'):
            return mod
    try:
        import main
        return main
    except Exception:
        return None

# Sinclair Spectrum 8 Standard Colors
SPECTRUM_COLORS = [
    (0, 0, 0),        # 0: Black
    (0, 0, 192),      # 1: Blue
    (192, 0, 0),      # 2: Red
    (192, 0, 192),    # 3: Magenta
    (0, 192, 0),      # 4: Green
    (0, 192, 192),    # 5: Cyan
    (255, 255, 0),    # 6: Yellow
    (255, 255, 255)   # 7: White
]

SPECTRUM_COLOR_NAMES = ["BLK", "BLU", "RED", "MAG", "GRN", "CYN", "YEL", "WHT"]
PATH_NAMES = ["NONE", "LINEAR", "CIRCLE", "BOX", "WAVE-V", "WAVE-H"]
DIR_NAMES = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
COLOR_DEPTHS = [16, 32, 64, 128, 256]
NEXT_TRANSPARENCY_COLOR = 0xE3  # 227 (Magenta)


def next_rgb_to_888(col):
    """Converts 8-bit Next palette byte or RGB tuple to 24-bit RGB."""
    if isinstance(col, (tuple, list)):
        return (int(col[0]), int(col[1]), int(col[2]))
    c = int(col) & 0xFF
    r = ((c >> 5) & 7) * 255 // 7
    g = ((c >> 2) & 7) * 255 // 7
    b = (c & 3) * 255 // 3
    return (r, g, b)


class ZXSpriteEditor:
    """
    16x16 Dual-Engine Sprite Editor for ZX Spectrum / BasinPy.
    Supports both ZX Monochrome (48K) and ZX Spectrum Next (Hardware Color).
    """
    def __init__(self, start_sprite_id=0, mode=None, sprite_id=None):
        if sprite_id is not None:
            start_sprite_id = sprite_id
        ctx = get_main_context()

        # Engine Mode: "ZX" or "NEXT"
        if mode in ("ZX", "NEXT"):
            self.engine_mode = mode
        elif ctx is not None and hasattr(ctx, "current_sprite_mode"):
            self.engine_mode = ctx.current_sprite_mode
        elif ctx is not None and getattr(ctx, "spectrum_mode", "48K") == "NEXT":
            self.engine_mode = "NEXT"
        else:
            self.engine_mode = "ZX"

        self.cursor_row = 0
        self.cursor_col = 0
        self.mouse_down = False
        self.mouse_paint_val = None
        self.running = True

        # ==========================================
        # 1. ZX Monochrome Engine State (16 Sprites)
        # ==========================================
        self.num_sprites = 16
        self.active_sprite = max(0, min(15, int(start_sprite_id)))
        self.active_frame = 0    # 0 to 3

        self.sprites = []
        for s in range(self.num_sprites):
            self.sprites.append({
                "frames": [bytearray(32) for _ in range(4)],
                "ink": 2 if s == 0 else (1 if s == 1 else (6 if s == 2 else 4)),
                "animated": True,
                "x": 30 + (s % 4) * 50,
                "y": 40 + (s // 4) * 35,
                "direction": 2,      # East
                "speed": 2,          # 2 px/frame
                "path_mode": 0,      # 0=None
                "path_param": 20,
                "rebound": 30
            })

        # Real-time animated preview state for ZX mode
        self.anim_frame = 0
        self.anim_timer = 0
        self.anim_speed = 150    # ms per frame (~6.6 fps)
        self.anim_paused = False

        # ==========================================
        # 2. NEXT Color Engine State (64 Patterns)
        # ==========================================
        self.num_next_patterns = 64
        self.active_next_pattern = max(0, min(63, int(start_sprite_id)))
        self.color_depth = 256   # 16, 32, 64, 128, 256
        self.selected_color = 3  # Active drawing color index (0..255)
        self.palette_page = 0    # Current 16-color page in palette (0..15)

        # 64 patterns of 256 bytes (16x16 pixels with 8-bit palette index)
        self.next_patterns = [bytearray(256) for _ in range(self.num_next_patterns)]
        for p in range(self.num_next_patterns):
            for i in range(256):
                self.next_patterns[p][i] = NEXT_TRANSPARENCY_COLOR

        # 64 Next sprite instances
        self.next_sprites = []
        for s in range(self.num_next_patterns):
            self.next_sprites.append({
                "x": 32 + (s % 8) * 24,
                "y": 32 + (s // 8) * 20,
                "pattern": s,
                "palette_offset": 0,
                "scale_x": 1,
                "scale_y": 1,
                "flip_x": False,
                "flip_y": False,
                "rotate": 0,
                "visible": True
            })

        # Build / cache 256 Next RGB colors
        self.next_palette = [next_rgb_to_888(c) for c in range(256)]

        # Synchronize from running engines if available
        self.load_from_sprite_engine()

        self.status_msg = f"Sprite Editor [{self.engine_mode}] Ready - S{self.get_active_id():02d}"

    def get_active_id(self):
        return self.active_next_pattern if self.engine_mode == "NEXT" else self.active_sprite

    def set_active_id(self, new_id):
        if self.engine_mode == "NEXT":
            self.active_next_pattern = max(0, min(self.num_next_patterns - 1, int(new_id)))
        else:
            self.active_sprite = max(0, min(self.num_sprites - 1, int(new_id)))
        self.status_msg = f"{self.engine_mode} S{self.get_active_id():02d} Selected"

    @property
    def next_color_depth(self):
        return self.color_depth

    @next_color_depth.setter
    def next_color_depth(self, v):
        self.set_color_depth(v)

    @property
    def current_frame(self):
        return self.active_frame

    @current_frame.setter
    def current_frame(self, v):
        self.active_frame = int(v) % 4

    @property
    def current_pattern(self):
        return self.active_next_pattern

    @current_pattern.setter
    def current_pattern(self, v):
        self.active_next_pattern = int(v) % self.num_next_patterns

    @property
    def zx_frames(self):
        return self.sprites[self.active_sprite]["frames"]

    def next_frame(self):
        self.active_frame = (self.active_frame + 1) % 4

    def prev_frame(self):
        self.active_frame = (self.active_frame - 1) % 4

    def copy_frame(self, frame_idx=None):
        if frame_idx is None:
            frame_idx = self.active_frame
        if self.engine_mode == "ZX":
            self.clipboard_frame = bytearray(self.sprites[self.active_sprite]["frames"][frame_idx])
            self.status_msg = f"Copied Frame {frame_idx + 1}"
        else:
            self.clipboard_pattern = bytearray(self.next_patterns[self.active_next_pattern])
            self.status_msg = f"Copied Pattern {self.active_next_pattern}"

    def paste_frame(self, frame_idx=None):
        if frame_idx is None:
            frame_idx = self.active_frame
        if self.engine_mode == "ZX" and hasattr(self, 'clipboard_frame'):
            self.sprites[self.active_sprite]["frames"][frame_idx] = bytearray(self.clipboard_frame)
            self.status_msg = f"Pasted to Frame {frame_idx + 1}"
        elif self.engine_mode == "NEXT" and hasattr(self, 'clipboard_pattern'):
            self.next_patterns[self.active_next_pattern] = bytearray(self.clipboard_pattern)
            self.status_msg = f"Pasted to Pattern {self.active_next_pattern}"

    def toggle_engine_mode(self):
        """Switches between ZX monochrome engine and NEXT hardware color engine."""
        self.engine_mode = "NEXT" if self.engine_mode == "ZX" else "ZX"
        ctx = get_main_context()
        if ctx is not None:
            ctx.current_sprite_mode = self.engine_mode
        self.status_msg = f"Engine switched to: {self.engine_mode}"

    def cycle_color_depth(self):
        """Cycles color depth among [16, 32, 64, 128, 256]."""
        idx = COLOR_DEPTHS.index(self.color_depth) if self.color_depth in COLOR_DEPTHS else 4
        self.color_depth = COLOR_DEPTHS[(idx + 1) % len(COLOR_DEPTHS)]
        self.palette_page = 0
        if self.selected_color != NEXT_TRANSPARENCY_COLOR:
            self.selected_color = self.selected_color % self.color_depth
        self.status_msg = f"Next Color Depth: {self.color_depth} Colours"

    def set_color_depth(self, depth):
        if depth in COLOR_DEPTHS:
            self.color_depth = depth
            self.palette_page = 0
            if self.selected_color != NEXT_TRANSPARENCY_COLOR:
                self.selected_color = self.selected_color % self.color_depth
            self.status_msg = f"Next Color Depth: {self.color_depth} Colours"

    def load_from_sprite_engine(self):
        """Loads definitions and attributes from the running sprite engines."""
        ctx = get_main_context()
        if ctx is None:
            return

        # 1. Load ZX monochrome machine code engine
        if hasattr(ctx, "get_sprite_engine"):
            eng = ctx.get_sprite_engine()
            if eng is not None:
                for s in range(self.num_sprites):
                    if hasattr(eng, "definitions") and s in eng.definitions:
                        for f in range(4):
                            b_data = eng.definitions[s][f]
                            if b_data and len(b_data) == 32 and any(b != 0 for b in b_data):
                                self.sprites[s]["frames"][f] = bytearray(b_data)

                    if hasattr(eng, "_read_slot_byte"):
                        st = eng._read_slot_byte(s, SLOT_STATUS)
                        if st != 0:
                            self.sprites[s]["animated"] = (st == 2)
                            self.sprites[s]["x"] = eng._read_slot_byte(s, SLOT_X)
                            self.sprites[s]["y"] = eng._read_slot_byte(s, SLOT_Y)
                            self.sprites[s]["ink"] = eng._read_slot_byte(s, SLOT_INK) & 7
                            self.sprites[s]["direction"] = eng._read_slot_byte(s, SLOT_DIR) & 7
                            self.sprites[s]["speed"] = eng._read_slot_byte(s, SLOT_SPEED)
                            self.sprites[s]["path_mode"] = eng._read_slot_byte(s, SLOT_PATH_MODE)
                            self.sprites[s]["path_param"] = eng._read_slot_byte(s, SLOT_PATH_PARAM)
                            self.sprites[s]["rebound"] = eng._read_slot_byte(s, SLOT_REBOUND_FRAMES)

        # 2. Load Next hardware color engine
        if hasattr(ctx, "next_sprite_manager") and ctx.next_sprite_manager is not None:
            nsm = ctx.next_sprite_manager
            for p in range(min(len(nsm.patterns), self.num_next_patterns)):
                pat_bytes = nsm.patterns[p]
                if pat_bytes and len(pat_bytes) == 256:
                    self.next_patterns[p] = bytearray(pat_bytes)

            for s in range(min(len(nsm.sprites), self.num_next_patterns)):
                sp = nsm.sprites[s]
                self.next_sprites[s]["x"] = getattr(sp, "x", 0)
                self.next_sprites[s]["y"] = getattr(sp, "y", 0)
                self.next_sprites[s]["pattern"] = getattr(sp, "pattern", s)
                self.next_sprites[s]["visible"] = getattr(sp, "visible", True)
                self.next_sprites[s]["palette_offset"] = getattr(sp, "palette_offset", 0)
                self.next_sprites[s]["flip_x"] = getattr(sp, "flip_x", False)
                self.next_sprites[s]["flip_y"] = getattr(sp, "flip_y", False)
                self.next_sprites[s]["rotate"] = getattr(sp, "rotate", 0)
                self.next_sprites[s]["scale_x"] = getattr(sp, "scale_x", 1)
                self.next_sprites[s]["scale_y"] = getattr(sp, "scale_y", 1)

    def sync_to_sprite_engine(self):
        """Synchronizes current sprite definitions and attributes to the live sprite engine."""
        ctx = get_main_context()
        if ctx is None:
            return

        if self.engine_mode == "ZX":
            if hasattr(ctx, "get_sprite_engine"):
                eng = ctx.get_sprite_engine()
                if eng is not None:
                    for s in range(self.num_sprites):
                        s_data = self.sprites[s]
                        for f in range(4):
                            eng.set_sprite_def(s, f, bytes(s_data["frames"][f]))
                        if hasattr(eng, "set_sprite_attr"):
                            status_val = 2 if s_data["animated"] else 1
                            eng.set_sprite_attr(
                                s,
                                status=status_val,
                                def_id=s,
                                x=s_data["x"],
                                y=s_data["y"],
                                ink=s_data["ink"],
                                direction=s_data["direction"],
                                path_mode=s_data["path_mode"],
                                speed=s_data["speed"],
                                path_param=s_data["path_param"],
                                rebound_frames=s_data["rebound"]
                            )
        else:
            if hasattr(ctx, "next_sprite_manager") and ctx.next_sprite_manager is not None:
                nsm = ctx.next_sprite_manager
                for p in range(self.num_next_patterns):
                    nsm.patterns[p][:] = self.next_patterns[p][:]
                if hasattr(nsm, "pattern_surfaces"):
                    nsm.pattern_surfaces.clear()

    def is_sprite_used(self, sprite_id):
        """Returns True if sprite/pattern has any non-blank pixels."""
        if self.engine_mode == "ZX":
            for f in range(4):
                if any(b != 0 for b in self.sprites[sprite_id]["frames"][f]):
                    return True
            return False
        else:
            # In Next, blank is all 0xE3 (transparent) or all 0
            pat = self.next_patterns[sprite_id]
            return any(b != NEXT_TRANSPARENCY_COLOR for b in pat)

    # ==========================================
    # Pixel Get / Set Methods
    # ==========================================
    def get_pixel(self, *args):
        if len(args) == 2:
            r, c = args
            sprite_id = self.active_sprite if self.engine_mode == "ZX" else self.active_next_pattern
            frame_idx = self.active_frame
        elif len(args) == 3:
            p_or_f, r, c = args
            if self.engine_mode == "ZX":
                sprite_id = self.active_sprite
                frame_idx = p_or_f
            else:
                sprite_id = p_or_f
                frame_idx = 0
        elif len(args) >= 4:
            sprite_id, frame_idx, r, c = args[:4]
        else:
            return False

        if not (0 <= r < 16 and 0 <= c < 16):
            return False
        if self.engine_mode == "ZX":
            b_idx = r * 2 + (c // 8)
            bit = 7 - (c % 8)
            return bool(self.sprites[sprite_id]["frames"][frame_idx][b_idx] & (1 << bit))
        else:
            # Returns color index in NEXT mode
            return self.next_patterns[sprite_id][r * 16 + c]

    def set_pixel(self, *args):
        if len(args) == 3:
            r, c, val = args
            sprite_id = self.active_sprite if self.engine_mode == "ZX" else self.active_next_pattern
            frame_idx = self.active_frame
        elif len(args) == 4:
            p_or_f, r, c, val = args
            if self.engine_mode == "ZX":
                sprite_id = self.active_sprite
                frame_idx = p_or_f
            else:
                sprite_id = p_or_f
                frame_idx = 0
        elif len(args) >= 5:
            sprite_id, frame_idx, r, c, val = args[:5]
        else:
            return

        if not (0 <= r < 16 and 0 <= c < 16):
            return
        if self.engine_mode == "ZX":
            b_idx = r * 2 + (c // 8)
            bit = 7 - (c % 8)
            if val:
                self.sprites[sprite_id]["frames"][frame_idx][b_idx] |= (1 << bit)
            else:
                self.sprites[sprite_id]["frames"][frame_idx][b_idx] &= ~(1 << bit)
        else:
            # Set color index in NEXT mode
            col = int(val)
            if col != NEXT_TRANSPARENCY_COLOR:
                col = col % self.color_depth
            self.next_patterns[sprite_id][r * 16 + c] = col

    def toggle_pixel(self, sprite_id, frame_idx, r, c):
        if not (0 <= r < 16 and 0 <= c < 16):
            return
        if self.engine_mode == "ZX":
            b_idx = r * 2 + (c // 8)
            bit = 7 - (c % 8)
            self.sprites[sprite_id]["frames"][frame_idx][b_idx] ^= (1 << bit)
        else:
            cur = self.next_patterns[sprite_id][r * 16 + c]
            if cur == self.selected_color:
                self.next_patterns[sprite_id][r * 16 + c] = NEXT_TRANSPARENCY_COLOR
            else:
                self.next_patterns[sprite_id][r * 16 + c] = self.selected_color

    def clear_frame(self, sprite_id, frame_idx):
        if self.engine_mode == "ZX":
            self.sprites[sprite_id]["frames"][frame_idx] = bytearray(32)
            self.status_msg = f"S{sprite_id} F{frame_idx+1} Cleared"
        else:
            for i in range(256):
                self.next_patterns[sprite_id][i] = NEXT_TRANSPARENCY_COLOR
            self.status_msg = f"Next Pattern {sprite_id} Cleared"

    def invert_frame(self, sprite_id, frame_idx):
        if self.engine_mode == "ZX":
            for i in range(32):
                self.sprites[sprite_id]["frames"][frame_idx][i] ^= 0xFF
            self.status_msg = f"S{sprite_id} F{frame_idx+1} Inverted"
        else:
            mask = self.color_depth - 1
            for i in range(256):
                val = self.next_patterns[sprite_id][i]
                if val != NEXT_TRANSPARENCY_COLOR:
                    self.next_patterns[sprite_id][i] = val ^ mask
            self.status_msg = f"Pattern {sprite_id} Inverted ({self.color_depth} cols)"

    def flip_h(self, sprite_id, frame_idx):
        if self.engine_mode == "ZX":
            frame = self.sprites[sprite_id]["frames"][frame_idx]
            new_frame = bytearray(32)
            for r in range(16):
                b0 = frame[r * 2]
                b1 = frame[r * 2 + 1]
                row_val = (b0 << 8) | b1
                rev_val = 0
                for bit in range(16):
                    if row_val & (1 << bit):
                        rev_val |= (1 << (15 - bit))
                new_frame[r * 2] = (rev_val >> 8) & 0xFF
                new_frame[r * 2 + 1] = rev_val & 0xFF
            self.sprites[sprite_id]["frames"][frame_idx] = new_frame
            self.status_msg = f"S{sprite_id} F{frame_idx+1} Flipped H"
        else:
            pat = self.next_patterns[sprite_id]
            new_pat = bytearray(256)
            for r in range(16):
                for c in range(16):
                    new_pat[r * 16 + c] = pat[r * 16 + (15 - c)]
            self.next_patterns[sprite_id] = new_pat
            self.status_msg = f"Pattern {sprite_id} Flipped H"

    def flip_v(self, sprite_id, frame_idx):
        if self.engine_mode == "ZX":
            frame = self.sprites[sprite_id]["frames"][frame_idx]
            new_frame = bytearray(32)
            for r in range(16):
                new_frame[r * 2] = frame[(15 - r) * 2]
                new_frame[r * 2 + 1] = frame[(15 - r) * 2 + 1]
            self.sprites[sprite_id]["frames"][frame_idx] = new_frame
            self.status_msg = f"S{sprite_id} F{frame_idx+1} Flipped V"
        else:
            pat = self.next_patterns[sprite_id]
            new_pat = bytearray(256)
            for r in range(16):
                for c in range(16):
                    new_pat[r * 16 + c] = pat[(15 - r) * 16 + c]
            self.next_patterns[sprite_id] = new_pat
            self.status_msg = f"Pattern {sprite_id} Flipped V"

    def rotate_90(self, sprite_id, frame_idx):
        if self.engine_mode == "ZX":
            new_frame = bytearray(32)
            for r in range(16):
                for c in range(16):
                    if self.get_pixel(sprite_id, frame_idx, r, c):
                        nr = c
                        nc = 15 - r
                        b_idx = nr * 2 + (nc // 8)
                        bit = 7 - (nc % 8)
                        new_frame[b_idx] |= (1 << bit)
            self.sprites[sprite_id]["frames"][frame_idx] = new_frame
            self.status_msg = f"S{sprite_id} F{frame_idx+1} Rotated 90"
        else:
            pat = self.next_patterns[sprite_id]
            new_pat = bytearray(256)
            for r in range(16):
                for c in range(16):
                    new_pat[c * 16 + (15 - r)] = pat[r * 16 + c]
            self.next_patterns[sprite_id] = new_pat
            self.status_msg = f"Pattern {sprite_id} Rotated 90"

    def copy_frame_to_next(self, sprite_id, frame_idx):
        if self.engine_mode == "ZX":
            dst_f = (frame_idx + 1) % 4
            self.sprites[sprite_id]["frames"][dst_f] = bytearray(self.sprites[sprite_id]["frames"][frame_idx])
            self.status_msg = f"Copied F{frame_idx+1} -> F{dst_f+1}"
        else:
            dst_p = (sprite_id + 1) % self.num_next_patterns
            self.next_patterns[dst_p] = bytearray(self.next_patterns[sprite_id])
            self.status_msg = f"Copied P{sprite_id} -> P{dst_p}"

    def step_animation(self, dt_ms):
        """Advances real-time animation for previewing 4-frame cycle."""
        if self.anim_paused:
            return
        self.anim_timer += dt_ms
        if self.anim_timer >= self.anim_speed:
            self.anim_timer %= self.anim_speed
            self.anim_frame = (self.anim_frame + 1) % 4

    def generate_basic_lines(self, target_prog=None):
        """
        Outputs clean executable BASIC listing at line 5000+:
        - In ZX Mode: Sinclair 48K BASIC loading machine code engine definitions (compiler compatible).
        - In NEXT Mode: Sinclair ZX Spectrum NextBASIC definitions.
        """
        ctx = get_main_context()
        if target_prog is not None:
            program = target_prog
        elif ctx is not None and hasattr(ctx, "program"):
            program = ctx.program
        else:
            program = {}

        if self.engine_mode == "ZX":
            # ========================================================
            # Normal 48K Sinclair BASIC for ZX Monochrome Engine
            # ========================================================
            program[5000] = 'REM === SPRITE ENGINE AUTO-LOADER ==='
            program[5005] = 'SPRITE INIT 50000: REM Init Engine at BASE 50000'

            active_sprites = [s for s in range(self.num_sprites) if self.is_sprite_used(s)]
            if not active_sprites:
                active_sprites = [self.active_sprite]

            cur_line = 5010
            for s in active_sprites:
                s_data = self.sprites[s]
                data_start = 5200 + s * 50

                program[cur_line] = f'SPRITE DEF {s} FROM {data_start}: REM Load Sprite {s} Def'
                cur_line += 5

                anim_val = 1 if s_data["animated"] else 0
                program[cur_line] = (
                    f'SPRITE POS {s}, {s_data["x"]}, {s_data["y"]}: '
                    f'SPRITE MOVE {s}, {s_data["direction"]}, {s_data["speed"]}: '
                    f'SPRITE INK {s}, {s_data["ink"]}: '
                    f'SPRITE PATH {s}, {s_data["path_mode"]}, {s_data["path_param"]}: '
                    f'SPRITE REBOUND {s}, {s_data["rebound"]}: '
                    f'SPRITE ON {s}, {anim_val}, {s}'
                )
                cur_line += 5

            program[cur_line] = 'RETURN: REM End of Sprite Loader Subroutine'

            for s in active_sprites:
                s_data = self.sprites[s]
                base_line = 5200 + s * 50
                program[base_line] = f'REM --- Sprite {s} Data (4 Frames x 32 Bytes) ---'
                for f in range(4):
                    f_line = base_line + 10 + f * 10
                    f_bytes = s_data["frames"][f]
                    b_str = ",".join(str(int(b)) for b in f_bytes)
                    program[f_line] = f'DATA {b_str}: REM S{s} F{f+1}'

            self.sync_to_sprite_engine()
            if ctx is not None and hasattr(ctx, "parse_data_lines"):
                ctx.parse_data_lines()

            self.status_msg = f"Lines 5000-{cur_line} & 5200+ (48K BASIC) OK!"

        else:
            # ========================================================
            # Native NextBASIC Definitions for Next Hardware Sprites
            # ========================================================
            program[5000] = 'REM === NEXT SPRITE DEFINITIONS ==='
            program[5005] = 'SPRITE CLEAR: REM Clear hardware sprites'

            active_patterns = [p for p in range(self.num_next_patterns) if self.is_sprite_used(p)]
            if not active_patterns:
                active_patterns = [self.active_next_pattern]

            cur_line = 5010
            for idx, p in enumerate(active_patterns):
                data_start = 5200 + idx * 100
                sp_data = self.next_sprites[p]

                # 1. Define pattern from DATA
                program[cur_line] = f'SPRITE DEF {p} FROM {data_start}: REM Pattern {p}'
                cur_line += 5

                # 2. Place and activate sprite instance
                pal_off = sp_data["palette_offset"]
                program[cur_line] = f'SPRITE {p}, {sp_data["x"]}, {sp_data["y"]}, {p}, {pal_off}: SPRITE ON {p}, {p}'
                cur_line += 5

            program[cur_line] = 'RETURN: REM End of Next Sprites Loader'

            # Generate 256 bytes of DATA per 16x16 pattern (16 rows of 16 values)
            for idx, p in enumerate(active_patterns):
                pat = self.next_patterns[p]
                base_line = 5200 + idx * 100
                program[base_line] = f'REM --- Next Pattern {p} (16x16, 256 Bytes, {self.color_depth} Col) ---'
                for row in range(16):
                    r_line = base_line + 5 + row * 5
                    r_bytes = pat[row * 16 : (row + 1) * 16]
                    b_str = ",".join(str(int(b)) for b in r_bytes)
                    program[r_line] = f'DATA {b_str}'

            self.sync_to_sprite_engine()
            if ctx is not None and hasattr(ctx, "parse_data_lines"):
                ctx.parse_data_lines()

            self.status_msg = f"Lines 5000-{cur_line} (NextBASIC) Generated!"

        return program

    def draw_text(self, surf, text, x, y, fg, bg=None):
        """Draws standard 8x8 bitmap text onto surface."""
        ctx = get_main_context()
        for ch in text:
            bmp = None
            if ctx is not None and hasattr(ctx, "get_char_bitmap"):
                bmp = ctx.get_char_bitmap(ch)
            if bmp is None:
                bmp = bytearray(8)
            for r in range(8):
                byte_val = bmp[r]
                for c in range(8):
                    px = x + c
                    py = y + r
                    if 0 <= px < 256 and 0 <= py < 192:
                        if byte_val & (1 << (7 - c)):
                            surf.set_at((px, py), fg)
                        elif bg is not None:
                            surf.set_at((px, py), bg)
            x += 8

    def render(self, target_surf):
        """Renders complete sprite editor UI onto the 256x192 canvas."""
        c_black = (0, 0, 0)
        c_blue = (0, 0, 192)
        c_red = (192, 0, 0)
        c_green = (0, 192, 0)
        c_cyan = (0, 192, 192)
        c_yellow = (255, 255, 0)
        c_white = (255, 255, 255)
        c_gray = (100, 100, 100)
        c_magenta = (192, 0, 192)
        c_grid_bg = (10, 10, 35)

        target_surf.fill(c_black)

        # 1. Top Header Bar (y = 0..10)
        pygame.draw.rect(target_surf, c_blue, (0, 0, 256, 11))
        self.draw_text(target_surf, "EDSPRITES", 2, 1, c_yellow, c_blue)

        # Engine Badge / Toggle Button [ZX] or [NEXT] (x = 80..120)
        engine_badge_col = c_cyan if self.engine_mode == "ZX" else c_magenta
        pygame.draw.rect(target_surf, engine_badge_col, (78, 1, 38, 9))
        self.draw_text(target_surf, f"[{self.engine_mode}]", 80, 1, c_black, engine_badge_col)

        # Quick Selector Tabs [<] [>] (x = 122..154)
        curr_id = self.get_active_id()
        max_id = (self.num_next_patterns - 1) if self.engine_mode == "NEXT" else (self.num_sprites - 1)
        self.draw_text(target_surf, f"S{curr_id:02d}", 118, 1, c_white, c_blue)
        pygame.draw.rect(target_surf, c_cyan, (144, 1, 12, 9))
        self.draw_text(target_surf, "<", 146, 1, c_black, c_cyan)
        pygame.draw.rect(target_surf, c_cyan, (158, 1, 12, 9))
        self.draw_text(target_surf, ">", 160, 1, c_black, c_cyan)

        # Generate Button & Exit Button at top right
        pygame.draw.rect(target_surf, c_yellow, (174, 1, 36, 9))
        self.draw_text(target_surf, "GEN", 182, 1, c_black, c_yellow)
        pygame.draw.rect(target_surf, c_red, (216, 1, 36, 9))
        self.draw_text(target_surf, "EXT", 224, 1, c_white, c_red)

        # 2. Main 16x16 Edit Grid (x = 4..100, y = 12..108, 96x96 pixels)
        grid_x = 4
        grid_y = 12
        pygame.draw.rect(target_surf, c_cyan, (grid_x - 1, grid_y - 1, 98, 98), 1)
        pygame.draw.rect(target_surf, c_grid_bg, (grid_x, grid_y, 96, 96))

        # Quadrant guide lines (row 8 and col 8)
        pygame.draw.line(target_surf, (20, 40, 80), (grid_x + 48, grid_y), (grid_x + 48, grid_y + 95))
        pygame.draw.line(target_surf, (20, 40, 80), (grid_x, grid_y + 48), (grid_x + 95, grid_y + 48))

        if self.engine_mode == "ZX":
            s_data = self.sprites[self.active_sprite]
            ink_color = SPECTRUM_COLORS[s_data["ink"]]
            f_id = self.active_frame

            for r in range(16):
                for c in range(16):
                    cell_x = grid_x + c * 6
                    cell_y = grid_y + r * 6
                    if self.get_pixel(self.active_sprite, f_id, r, c):
                        pygame.draw.rect(target_surf, ink_color, (cell_x + 1, cell_y + 1, 5, 5))
                    else:
                        target_surf.set_at((cell_x + 3, cell_y + 3), (25, 25, 60))

                    if r == self.cursor_row and c == self.cursor_col:
                        pygame.draw.rect(target_surf, c_white, (cell_x, cell_y, 6, 6), 1)

            # Control Panel for ZX Mode
            self.render_zx_controls(target_surf, s_data, f_id)
            self.render_zx_preview_strip(target_surf, s_data, f_id, ink_color)

        else:
            # NEXT Color Mode
            pat_id = self.active_next_pattern
            pat_data = self.next_patterns[pat_id]

            for r in range(16):
                for c in range(16):
                    cell_x = grid_x + c * 6
                    cell_y = grid_y + r * 6
                    col_idx = pat_data[r * 16 + c]
                    if col_idx == NEXT_TRANSPARENCY_COLOR:
                        # Draw checkerboard transparency
                        check_col = (40, 15, 40) if ((r + c) % 2 == 0) else (20, 10, 25)
                        pygame.draw.rect(target_surf, check_col, (cell_x + 1, cell_y + 1, 5, 5))
                    else:
                        rgb = self.next_palette[col_idx & 0xFF]
                        pygame.draw.rect(target_surf, rgb, (cell_x + 1, cell_y + 1, 5, 5))

                    if r == self.cursor_row and c == self.cursor_col:
                        pygame.draw.rect(target_surf, c_white, (cell_x, cell_y, 6, 6), 1)

            # Control Panel for NEXT Mode
            self.render_next_controls(target_surf, pat_id)
            self.render_next_preview_strip(target_surf, pat_id)

        # 5. Help / Shortcut Bar (y = 156..180)
        pygame.draw.line(target_surf, c_blue, (0, 155), (255, 155))
        if self.engine_mode == "ZX":
            self.draw_text(target_surf, "SPACE:Plot 1-4:Frame K:Ink A:Anim", 4, 157, c_white)
            self.draw_text(target_surf, "M:Switch->NEXT C:Clr G:GEN 48K", 4, 167, c_cyan)
        else:
            self.draw_text(target_surf, "SPACE:Plot D:Depth K:Pal T:Trans", 4, 157, c_white)
            self.draw_text(target_surf, "M:Switch->ZX  C:Clr G:GEN NEXT", 4, 167, c_cyan)

        # 6. Status Bar (y = 180..191)
        pygame.draw.rect(target_surf, c_blue, (0, 180, 256, 12))
        self.draw_text(target_surf, self.status_msg[:32], 2, 182, c_yellow, c_blue)

    def render_zx_controls(self, target_surf, s_data, f_id):
        c_cyan = (0, 192, 192)
        c_white = (255, 255, 255)
        c_yellow = (255, 255, 0)
        c_gray = (100, 100, 100)
        c_black = (0, 0, 0)
        c_green = (0, 192, 0)
        c_red = (192, 0, 0)

        # Frame selection buttons [F1] [F2] [F3] [F4]
        self.draw_text(target_surf, "FRM:", 106, 14, c_cyan)
        for f in range(4):
            fx = 142 + f * 26
            is_active_f = (f == f_id)
            btn_bg = c_yellow if is_active_f else c_black
            btn_fg = c_black if is_active_f else c_white
            border = c_yellow if is_active_f else c_gray
            pygame.draw.rect(target_surf, border, (fx - 1, 13, 24, 10), 1)
            pygame.draw.rect(target_surf, btn_bg, (fx, 14, 22, 8))
            self.draw_text(target_surf, f"F{f+1}", fx + 3, 14, btn_fg, btn_bg)

        # INK Palette Swatches (0..7)
        self.draw_text(target_surf, "INK:", 106, 27, c_cyan)
        for col_idx in range(8):
            cx = 142 + col_idx * 13
            is_sel = (col_idx == s_data["ink"])
            pygame.draw.rect(target_surf, SPECTRUM_COLORS[col_idx], (cx, 26, 11, 10))
            if is_sel:
                pygame.draw.rect(target_surf, c_white, (cx - 1, 25, 13, 12), 1)

        # Animate Toggle: [ANIM: ON] / [ANIM: OFF]
        self.draw_text(target_surf, "ANM:", 106, 40, c_cyan)
        anim_text = "ON " if s_data["animated"] else "OFF"
        anim_bg = c_green if s_data["animated"] else c_red
        pygame.draw.rect(target_surf, anim_bg, (142, 39, 32, 10))
        self.draw_text(target_surf, anim_text, 146, 40, c_black if s_data["animated"] else c_white, anim_bg)

        # Path Mode: NONE, LIN, CIRC, BOX, WAVEV, WAVEH
        p_mode = s_data["path_mode"]
        p_name = PATH_NAMES[p_mode] if 0 <= p_mode < len(PATH_NAMES) else "NONE"
        self.draw_text(target_surf, "PTH:", 182, 40, c_cyan)
        pygame.draw.rect(target_surf, (0, 0, 100), (212, 39, 42, 10))
        self.draw_text(target_surf, p_name[:5], 214, 40, c_yellow)

        # Direction & Speed
        dir_val = s_data["direction"]
        d_name = DIR_NAMES[dir_val] if 0 <= dir_val < len(DIR_NAMES) else "E"
        self.draw_text(target_surf, f"DIR:{d_name:<2}", 106, 53, c_white)
        self.draw_text(target_surf, f"SPD:{s_data['speed']}", 160, 53, c_white)
        self.draw_text(target_surf, f"REB:{s_data['rebound']}", 206, 53, c_white)

        # Tools Row [CLR] [INV] [FLPH] [FLPV] [ROT]
        tool_btns = [("CLR", 106), ("INV", 136), ("FLPH", 166), ("FLPV", 198), ("ROT", 230)]
        for t_name, tx in tool_btns:
            w = len(t_name) * 8 + 4
            pygame.draw.rect(target_surf, c_gray, (tx - 1, 65, w, 10), 1)
            pygame.draw.rect(target_surf, (30, 30, 60), (tx, 66, w - 2, 8))
            self.draw_text(target_surf, t_name, tx + 1, 66, c_cyan)

        # Copy to next frame button
        pygame.draw.rect(target_surf, c_gray, (105, 78, 144, 10), 1)
        pygame.draw.rect(target_surf, (20, 40, 60), (106, 79, 142, 8))
        self.draw_text(target_surf, "COPY F->F+1 (KEY Y)", 110, 79, c_yellow)

        # Engine Mode Indicator
        self.draw_text(target_surf, "ENGINE: 48K MONOCHROME", 106, 92, (140, 180, 255))

    def render_zx_preview_strip(self, target_surf, s_data, f_id, ink_color):
        c_blue = (0, 0, 192)
        c_yellow = (255, 255, 0)
        c_green = (0, 192, 0)
        c_gray = (100, 100, 100)
        c_black = (0, 0, 0)
        c_white = (255, 255, 255)
        c_cyan = (0, 192, 192)
        c_red = (192, 0, 0)

        pygame.draw.line(target_surf, c_blue, (0, 109), (255, 109))
        frame_box_xs = [6, 44, 82, 120]
        preview_y = 113

        for f in range(4):
            bx = frame_box_xs[f]
            is_active_edit = (f == f_id)
            is_anim_playhead = (f == self.anim_frame and s_data["animated"])
            b_col = c_yellow if is_active_edit else (c_green if is_anim_playhead else c_gray)
            pygame.draw.rect(target_surf, b_col, (bx - 1, preview_y - 1, 34, 34), 2 if is_active_edit else 1)
            pygame.draw.rect(target_surf, c_black, (bx, preview_y, 32, 32))

            for r in range(16):
                for c in range(16):
                    if self.get_pixel(self.active_sprite, f, r, c):
                        pygame.draw.rect(target_surf, ink_color, (bx + c * 2, preview_y + r * 2, 2, 2))

            lbl_col = c_yellow if is_active_edit else c_gray
            self.draw_text(target_surf, f"F{f+1}", bx + 8, preview_y + 35, lbl_col)

        self.draw_text(target_surf, "->", 158, preview_y + 12, c_yellow)

        anim_bx = 180
        pygame.draw.rect(target_surf, c_yellow, (anim_bx - 1, preview_y - 1, 34, 34), 1)
        pygame.draw.rect(target_surf, c_black, (anim_bx, preview_y, 32, 32))

        disp_f = self.anim_frame if s_data["animated"] else f_id
        for r in range(16):
            for c in range(16):
                if self.get_pixel(self.active_sprite, disp_f, r, c):
                    pygame.draw.rect(target_surf, ink_color, (anim_bx + c * 2, preview_y + r * 2, 2, 2))

        anim_lbl = "ANIM" if s_data["animated"] else "STAT"
        self.draw_text(target_surf, anim_lbl, anim_bx + 2, preview_y + 35, c_green if s_data["animated"] else c_red)

        fps = round(1000.0 / self.anim_speed, 1)
        self.draw_text(target_surf, f"{fps}FPS", 220, preview_y + 4, c_white)
        self.draw_text(target_surf, "[A]NIM", 218, preview_y + 16, c_cyan)

    def render_next_controls(self, target_surf, pat_id):
        c_cyan = (0, 192, 192)
        c_white = (255, 255, 255)
        c_yellow = (255, 255, 0)
        c_gray = (100, 100, 100)
        c_black = (0, 0, 0)
        c_magenta = (192, 0, 192)

        # 1. Color Depth Buttons [16] [32] [64] [128] [256] (y = 13..21)
        self.draw_text(target_surf, "COL:", 106, 13, c_cyan)
        depth_xs = [138, 160, 182, 204, 230]
        depth_ws = [20, 20, 20, 24, 24]
        for idx, d in enumerate(COLOR_DEPTHS):
            dx = depth_xs[idx]
            dw = depth_ws[idx]
            is_sel = (d == self.color_depth)
            b_bg = c_yellow if is_sel else c_black
            b_fg = c_black if is_sel else c_white
            pygame.draw.rect(target_surf, c_yellow if is_sel else c_gray, (dx - 1, 12, dw, 10), 1)
            pygame.draw.rect(target_surf, b_bg, (dx, 13, dw - 2, 8))
            self.draw_text(target_surf, str(d), dx + 1, 13, b_fg, b_bg)

        # 2. Palette Swatches Row (y = 25..36)
        # Show 16 swatches corresponding to current palette_page
        start_col = self.palette_page * 16
        for i in range(16):
            c_idx = start_col + i
            if c_idx >= self.color_depth:
                break
            sw_x = 106 + i * 8
            sw_col = self.next_palette[c_idx]
            pygame.draw.rect(target_surf, sw_col, (sw_x, 26, 7, 10))
            if c_idx == self.selected_color:
                pygame.draw.rect(target_surf, c_white, (sw_x - 1, 25, 9, 12), 1)

        # Page buttons [<] [>] for palette (x = 236..254)
        if self.color_depth > 16:
            pygame.draw.rect(target_surf, c_cyan, (236, 26, 8, 10))
            self.draw_text(target_surf, "<", 237, 27, c_black, c_cyan)
            pygame.draw.rect(target_surf, c_cyan, (246, 26, 8, 10))
            self.draw_text(target_surf, ">", 247, 27, c_black, c_cyan)

        # 3. Selected Color Preview & Transparent Quick-Select (y = 40..50)
        self.draw_text(target_surf, "SEL:", 106, 40, c_white)
        sel_box_x = 138
        if self.selected_color == NEXT_TRANSPARENCY_COLOR:
            pygame.draw.rect(target_surf, c_magenta, (sel_box_x, 39, 16, 11))
            self.draw_text(target_surf, "T", sel_box_x + 4, 40, c_white, c_magenta)
            self.draw_text(target_surf, "TRANS", 158, 40, c_magenta)
        else:
            sel_rgb = self.next_palette[self.selected_color & 0xFF]
            pygame.draw.rect(target_surf, sel_rgb, (sel_box_x, 39, 16, 11))
            pygame.draw.rect(target_surf, c_white, (sel_box_x - 1, 38, 18, 13), 1)
            self.draw_text(target_surf, f"#{self.selected_color:02X} ({self.selected_color})", 158, 40, c_yellow)

        # [TRANS] Button
        pygame.draw.rect(target_surf, c_magenta, (216, 39, 36, 11))
        self.draw_text(target_surf, "TRANS", 218, 40, c_white, c_magenta)

        # 4. Pattern / Instance Properties (y = 53..63)
        sp_inst = self.next_sprites[pat_id]
        self.draw_text(target_surf, f"POS:({sp_inst['x']},{sp_inst['y']})", 106, 53, c_white)
        self.draw_text(target_surf, f"PAL-OFF:{sp_inst['palette_offset']}", 192, 53, c_white)

        # 5. Tools Row [CLR] [INV] [FLPH] [FLPV] [ROT] (y = 66..76)
        tool_btns = [("CLR", 106), ("INV", 136), ("FLPH", 166), ("FLPV", 198), ("ROT", 230)]
        for t_name, tx in tool_btns:
            w = len(t_name) * 8 + 4
            pygame.draw.rect(target_surf, c_gray, (tx - 1, 65, w, 10), 1)
            pygame.draw.rect(target_surf, (30, 30, 60), (tx, 66, w - 2, 8))
            self.draw_text(target_surf, t_name, tx + 1, 66, c_cyan)

        # 6. Copy Pattern Button (y = 78..88)
        pygame.draw.rect(target_surf, c_gray, (105, 78, 144, 10), 1)
        pygame.draw.rect(target_surf, (20, 40, 60), (106, 79, 142, 8))
        self.draw_text(target_surf, "COPY P->P+1 (KEY Y)", 110, 79, c_yellow)

        # 7. Engine Mode Indicator
        self.draw_text(target_surf, f"ENGINE: NEXT ({self.color_depth} COLOURS)", 106, 92, (255, 180, 220))

    def render_next_preview_strip(self, target_surf, pat_id):
        c_blue = (0, 0, 192)
        c_yellow = (255, 255, 0)
        c_gray = (100, 100, 100)
        c_black = (0, 0, 0)
        c_green = (0, 192, 0)

        pygame.draw.line(target_surf, c_blue, (0, 109), (255, 109))
        frame_box_xs = [6, 44, 82, 120]
        preview_y = 113

        # Display 4 patterns starting from (pat_id // 4) * 4
        base_p = (pat_id // 4) * 4
        for idx in range(4):
            p = (base_p + idx) % self.num_next_patterns
            bx = frame_box_xs[idx]
            is_active = (p == pat_id)

            pygame.draw.rect(target_surf, c_yellow if is_active else c_gray, (bx - 1, preview_y - 1, 34, 34), 2 if is_active else 1)
            pygame.draw.rect(target_surf, c_black, (bx, preview_y, 32, 32))

            p_data = self.next_patterns[p]
            for r in range(16):
                for c in range(16):
                    col = p_data[r * 16 + c]
                    if col != NEXT_TRANSPARENCY_COLOR:
                        rgb = self.next_palette[col & 0xFF]
                        pygame.draw.rect(target_surf, rgb, (bx + c * 2, preview_y + r * 2, 2, 2))

            lbl_col = c_yellow if is_active else c_gray
            self.draw_text(target_surf, f"P{p:02d}", bx + 4, preview_y + 35, lbl_col)

        self.draw_text(target_surf, "->", 158, preview_y + 12, c_yellow)

        # 5th Box: Big Real-Time Preview over checkered background
        anim_bx = 180
        pygame.draw.rect(target_surf, c_yellow, (anim_bx - 1, preview_y - 1, 34, 34), 1)
        pygame.draw.rect(target_surf, c_black, (anim_bx, preview_y, 32, 32))

        # Checkered background in preview
        for r in range(16):
            for c in range(16):
                bg_col = (30, 30, 40) if ((r + c) % 2 == 0) else (15, 15, 20)
                pygame.draw.rect(target_surf, bg_col, (anim_bx + c * 2, preview_y + r * 2, 2, 2))

        cur_pat = self.next_patterns[pat_id]
        for r in range(16):
            for c in range(16):
                col = cur_pat[r * 16 + c]
                if col != NEXT_TRANSPARENCY_COLOR:
                    rgb = self.next_palette[col & 0xFF]
                    pygame.draw.rect(target_surf, rgb, (anim_bx + c * 2, preview_y + r * 2, 2, 2))

        self.draw_text(target_surf, "SPRITE", anim_bx + 2, preview_y + 35, c_green)
        self.draw_text(target_surf, f"{self.color_depth}C", 222, preview_y + 4, c_yellow)
        self.draw_text(target_surf, "NEXT", 222, preview_y + 16, c_green)

    def handle_mouse_click(self, cx, cy, button):
        """Processes mouse click events in canvas pixel coordinates."""
        # 1. Top Header Buttons
        if 0 <= cy <= 11:
            if 78 <= cx <= 116:   # Mode Toggle [ZX] <-> [NEXT]
                self.toggle_engine_mode()
                return
            elif 144 <= cx <= 156: # [<] Prev
                curr = self.get_active_id()
                max_cnt = self.num_next_patterns if self.engine_mode == "NEXT" else self.num_sprites
                self.set_active_id((curr - 1) % max_cnt)
                return
            elif 158 <= cx <= 170: # [>] Next
                curr = self.get_active_id()
                max_cnt = self.num_next_patterns if self.engine_mode == "NEXT" else self.num_sprites
                self.set_active_id((curr + 1) % max_cnt)
                return
            elif 174 <= cx <= 210: # [GEN]
                self.generate_basic_lines()
                return
            elif 216 <= cx <= 252: # [EXT]
                self.running = False
                return

        # 2. Main 16x16 Edit Grid (x = 4..100, y = 12..108)
        if 4 <= cx < 100 and 12 <= cy < 108:
            col = (cx - 4) // 6
            row = (cy - 12) // 6
            if 0 <= col < 16 and 0 <= row < 16:
                self.cursor_col = col
                self.cursor_row = row
                active_id = self.get_active_id()
                f_id = self.active_frame

                if self.engine_mode == "ZX":
                    if button == 1:
                        new_val = not self.get_pixel(active_id, f_id, row, col)
                        self.set_pixel(active_id, f_id, row, col, new_val)
                        self.mouse_paint_val = new_val
                    elif button == 3:
                        self.set_pixel(active_id, f_id, row, col, False)
                        self.mouse_paint_val = False
                else:
                    # NEXT mode
                    if button == 1:
                        self.set_pixel(active_id, 0, row, col, self.selected_color)
                        self.mouse_paint_val = self.selected_color
                    elif button == 3:
                        # Right click erases to transparent
                        self.set_pixel(active_id, 0, row, col, NEXT_TRANSPARENCY_COLOR)
                        self.mouse_paint_val = NEXT_TRANSPARENCY_COLOR
            return

        # 3. Control Panel Routing
        if self.engine_mode == "ZX":
            self.handle_zx_control_click(cx, cy, button)
        else:
            self.handle_next_control_click(cx, cy, button)

    def handle_zx_control_click(self, cx, cy, button):
        s_id = self.active_sprite
        f_id = self.active_frame

        # Frame Selector Buttons [F1] [F2] [F3] [F4] (y = 13..23)
        if 13 <= cy <= 23:
            for f in range(4):
                fx = 142 + f * 26
                if fx <= cx <= fx + 24:
                    self.active_frame = f
                    self.status_msg = f"Frame {f+1} Selected"
                    return

        # INK Palette Swatches (y = 25..36)
        if 25 <= cy <= 36:
            for col_idx in range(8):
                cx_swatch = 142 + col_idx * 13
                if cx_swatch <= cx <= cx_swatch + 12:
                    self.sprites[s_id]["ink"] = col_idx
                    self.status_msg = f"INK {col_idx} ({SPECTRUM_COLOR_NAMES[col_idx]}) Selected"
                    return

        # Animate Toggle & Path Mode (y = 39..49)
        if 39 <= cy <= 49:
            if 142 <= cx <= 174:
                self.sprites[s_id]["animated"] = not self.sprites[s_id]["animated"]
                st_str = "ANIMATED" if self.sprites[s_id]["animated"] else "STATIC"
                self.status_msg = f"Sprite {s_id} Mode: {st_str}"
                return
            elif 212 <= cx <= 254:
                self.sprites[s_id]["path_mode"] = (self.sprites[s_id]["path_mode"] + 1) % len(PATH_NAMES)
                self.status_msg = f"Path: {PATH_NAMES[self.sprites[s_id]['path_mode']]}"
                return

        # Direction & Speed Buttons (y = 52..62)
        if 52 <= cy <= 62:
            if 106 <= cx <= 145:
                self.sprites[s_id]["direction"] = (self.sprites[s_id]["direction"] + 1) % 8
                self.status_msg = f"Dir: {DIR_NAMES[self.sprites[s_id]['direction']]}"
                return
            elif 160 <= cx <= 195:
                self.sprites[s_id]["speed"] = (self.sprites[s_id]["speed"] + 1) % 8
                self.status_msg = f"Speed: {self.sprites[s_id]['speed']}"
                return

        # Tools Row [CLR] [INV] [FLPH] [FLPV] [ROT] (y = 65..75)
        if 65 <= cy <= 75:
            if 106 <= cx <= 132:
                self.clear_frame(s_id, f_id)
                return
            elif 136 <= cx <= 162:
                self.invert_frame(s_id, f_id)
                return
            elif 166 <= cx <= 194:
                self.flip_h(s_id, f_id)
                return
            elif 198 <= cx <= 226:
                self.flip_v(s_id, f_id)
                return
            elif 230 <= cx <= 254:
                self.rotate_90(s_id, f_id)
                return

        # Copy Frame (y = 78..88)
        if 78 <= cy <= 88 and 105 <= cx <= 250:
            self.copy_frame_to_next(s_id, f_id)
            return

        # Frames Strip Preview Selection (y = 113..147)
        if 113 <= cy <= 147:
            frame_box_xs = [6, 44, 82, 120]
            for f in range(4):
                bx = frame_box_xs[f]
                if bx <= cx <= bx + 34:
                    self.active_frame = f
                    self.status_msg = f"Frame {f+1} Selected"
                    return
            if 180 <= cx <= 214:
                self.sprites[s_id]["animated"] = not self.sprites[s_id]["animated"]
                st_str = "ANIMATED" if self.sprites[s_id]["animated"] else "STATIC"
                self.status_msg = f"Sprite {s_id} Mode: {st_str}"
                return

    def handle_next_control_click(self, cx, cy, button):
        pat_id = self.active_next_pattern

        # 1. Color Depth Buttons (y = 12..22)
        if 12 <= cy <= 22:
            depth_xs = [138, 160, 182, 204, 230]
            depth_ws = [20, 20, 20, 24, 24]
            for idx, d in enumerate(COLOR_DEPTHS):
                dx = depth_xs[idx]
                dw = depth_ws[idx]
                if dx <= cx <= dx + dw:
                    self.set_color_depth(d)
                    return

        # 2. Palette Swatches Row (y = 25..36)
        if 25 <= cy <= 36:
            start_col = self.palette_page * 16
            for i in range(16):
                sw_x = 106 + i * 8
                if sw_x <= cx <= sw_x + 7:
                    c_idx = start_col + i
                    if c_idx < self.color_depth:
                        self.selected_color = c_idx
                        self.status_msg = f"Color #{c_idx:02X} ({c_idx}) Selected"
                        return

            if self.color_depth > 16:
                max_pages = (self.color_depth + 15) // 16
                if 236 <= cx <= 244:  # [<] Prev Page
                    self.palette_page = (self.palette_page - 1) % max_pages
                    self.status_msg = f"Palette Page {self.palette_page + 1}/{max_pages}"
                    return
                elif 246 <= cx <= 254: # [>] Next Page
                    self.palette_page = (self.palette_page + 1) % max_pages
                    self.status_msg = f"Palette Page {self.palette_page + 1}/{max_pages}"
                    return

        # 3. [TRANS] Button (y = 39..50)
        if 39 <= cy <= 50 and 216 <= cx <= 252:
            self.selected_color = NEXT_TRANSPARENCY_COLOR
            self.status_msg = "Selected: TRANSPARENT (0xE3)"
            return

        # 4. Tools Row [CLR] [INV] [FLPH] [FLPV] [ROT] (y = 65..75)
        if 65 <= cy <= 75:
            if 106 <= cx <= 132:
                self.clear_frame(pat_id, 0)
                return
            elif 136 <= cx <= 162:
                self.invert_frame(pat_id, 0)
                return
            elif 166 <= cx <= 194:
                self.flip_h(pat_id, 0)
                return
            elif 198 <= cx <= 226:
                self.flip_v(pat_id, 0)
                return
            elif 230 <= cx <= 254:
                self.rotate_90(pat_id, 0)
                return

        # 5. Copy Pattern (y = 78..88)
        if 78 <= cy <= 88 and 105 <= cx <= 250:
            self.copy_frame_to_next(pat_id, 0)
            return

        # 6. Preview Strip Pattern Selection (y = 113..147)
        if 113 <= cy <= 147:
            frame_box_xs = [6, 44, 82, 120]
            base_p = (pat_id // 4) * 4
            for idx in range(4):
                bx = frame_box_xs[idx]
                if bx <= cx <= bx + 34:
                    self.active_next_pattern = (base_p + idx) % self.num_next_patterns
                    self.status_msg = f"Pattern {self.active_next_pattern:02d} Selected"
                    return

    def handle_mouse_motion(self, cx, cy):
        """Draws or erases while mouse is dragged on edit grid."""
        if self.mouse_paint_val is not None:
            if 4 <= cx < 100 and 12 <= cy < 108:
                col = (cx - 4) // 6
                row = (cy - 12) // 6
                if 0 <= col < 16 and 0 <= row < 16:
                    self.cursor_col = col
                    self.cursor_row = row
                    active_id = self.get_active_id()
                    f_id = self.active_frame if self.engine_mode == "ZX" else 0
                    self.set_pixel(active_id, f_id, row, col, self.mouse_paint_val)

    def handle_key(self, key_char, key_code, mod=0):
        """Processes keyboard shortcut commands."""
        active_id = self.get_active_id()
        f_id = self.active_frame if self.engine_mode == "ZX" else 0

        if key_code == pygame.K_UP:
            self.cursor_row = (self.cursor_row - 1) % 16
        elif key_code == pygame.K_DOWN:
            self.cursor_row = (self.cursor_row + 1) % 16
        elif key_code == pygame.K_LEFT:
            self.cursor_col = (self.cursor_col - 1) % 16
        elif key_code == pygame.K_RIGHT:
            self.cursor_col = (self.cursor_col + 1) % 16
        elif key_code in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
            self.toggle_pixel(active_id, f_id, self.cursor_row, self.cursor_col)
        elif key_char in ('m', 'M'):
            self.toggle_engine_mode()
        elif key_char in ('d', 'D'):
            if self.engine_mode == "NEXT":
                self.cycle_color_depth()
            else:
                self.sprites[active_id]["direction"] = (self.sprites[active_id]["direction"] + 1) % 8
                self.status_msg = f"Dir: {DIR_NAMES[self.sprites[active_id]['direction']]}"
        elif key_char in ('t', 'T'):
            if self.engine_mode == "NEXT":
                self.selected_color = NEXT_TRANSPARENCY_COLOR
                self.status_msg = "Selected: TRANSPARENT (0xE3)"
        elif key_char in ('1', '2', '3', '4'):
            if self.engine_mode == "ZX":
                self.active_frame = int(key_char) - 1
                self.status_msg = f"Frame {self.active_frame + 1} Selected"
            else:
                p_idx = int(key_char) - 1
                base_p = (self.active_next_pattern // 4) * 4
                self.active_next_pattern = (base_p + p_idx) % self.num_next_patterns
                self.status_msg = f"Pattern {self.active_next_pattern:02d} Selected"
        elif key_code == pygame.K_TAB:
            if self.engine_mode == "ZX":
                self.active_frame = (self.active_frame + 1) % 4
                self.status_msg = f"Frame {self.active_frame + 1} Selected"
            else:
                self.palette_page = (self.palette_page + 1) % max(1, (self.color_depth + 15) // 16)
                self.status_msg = f"Palette Page {self.palette_page + 1}"
        elif key_char in ('[', '<') or key_code == pygame.K_PAGEUP:
            max_cnt = self.num_next_patterns if self.engine_mode == "NEXT" else self.num_sprites
            self.set_active_id((active_id - 1) % max_cnt)
        elif key_char in (']', '>') or key_code == pygame.K_PAGEDOWN:
            max_cnt = self.num_next_patterns if self.engine_mode == "NEXT" else self.num_sprites
            self.set_active_id((active_id + 1) % max_cnt)
        elif key_char in ('k', 'K'):
            if self.engine_mode == "ZX":
                self.sprites[active_id]["ink"] = (self.sprites[active_id]["ink"] + 1) % 8
                self.status_msg = f"INK {self.sprites[active_id]['ink']} ({SPECTRUM_COLOR_NAMES[self.sprites[active_id]['ink']]})"
            else:
                self.selected_color = (self.selected_color + 1) % self.color_depth
                self.status_msg = f"Color #{self.selected_color:02X} ({self.selected_color})"
        elif key_char in ('a', 'A'):
            if self.engine_mode == "ZX":
                self.sprites[active_id]["animated"] = not self.sprites[active_id]["animated"]
                st_str = "ANIMATED" if self.sprites[active_id]["animated"] else "STATIC"
                self.status_msg = f"Sprite {active_id} Mode: {st_str}"
        elif key_char in ('s', 'S'):
            if self.engine_mode == "ZX":
                self.sprites[active_id]["speed"] = (self.sprites[active_id]["speed"] + 1) % 8
                self.status_msg = f"Speed: {self.sprites[active_id]['speed']}"
        elif key_char in ('+', '='):
            self.anim_speed = max(30, self.anim_speed - 20)
            self.status_msg = f"Anim Speed: {round(1000/self.anim_speed, 1)} FPS"
        elif key_char in ('-', '_'):
            self.anim_speed = min(500, self.anim_speed + 20)
            self.status_msg = f"Anim Speed: {round(1000/self.anim_speed, 1)} FPS"
        elif key_char in ('c', 'C'):
            self.clear_frame(active_id, f_id)
        elif key_char in ('i', 'I'):
            self.invert_frame(active_id, f_id)
        elif key_char in ('h', 'H', 'f', 'F'):
            self.flip_h(active_id, f_id)
        elif key_char in ('v', 'V'):
            self.flip_v(active_id, f_id)
        elif key_char in ('r', 'R', 'o', 'O'):
            self.rotate_90(active_id, f_id)
        elif key_char in ('y', 'Y'):
            self.copy_frame_to_next(active_id, f_id)
        elif key_char in ('g', 'G'):
            self.generate_basic_lines()
        elif key_char in ('q', 'Q', 'x', 'X') or key_code == pygame.K_ESCAPE:
            self.running = False


def launch_sprite_editor(args="", mode=None):
    """
    Launches the interactive 16x16 Dual-Engine Sprite Editor.
    Accepts starting sprite ID (0..63) or mode ("ZX" or "NEXT").
    """
    ctx = get_main_context()
    start_id = 0
    clean_args = (args or "").strip().strip('"').strip("'").strip()

    if clean_args.upper() in ("NEXT", "ZXNEXT", "SPECTRUMNEXT", "COLOR", "COLOUR"):
        mode = "NEXT"
    elif clean_args.upper() in ("ZX", "48K", "MONO", "MONOCHROME"):
        mode = "ZX"
    elif clean_args:
        try:
            start_id = int(clean_args)
        except Exception:
            start_id = 0

    editor = ZXSpriteEditor(start_sprite_id=start_id, mode=mode)

    if os.environ.get("SDL_VIDEODRIVER") == "dummy":
        editor.generate_basic_lines()
        if ctx is not None and hasattr(ctx, "canvas_dirty"):
            ctx.canvas_dirty = True
        return editor

    editor.running = True
    clock = pygame.time.Clock()

    scale_x = getattr(ctx, "scale_x", 1.0)
    scale_y = getattr(ctx, "scale_y", 1.0)
    canvas_blit_x = getattr(ctx, "canvas_blit_x", 0)
    canvas_blit_y = getattr(ctx, "canvas_blit_y", 0)
    canvas = getattr(ctx, "canvas", None)
    render_frame = getattr(ctx, "render_frame", None)

    try:
        while editor.running:
            dt = clock.tick(60)
            editor.step_animation(dt)

            scale_x = getattr(ctx, "scale_x", 1.0)
            scale_y = getattr(ctx, "scale_y", 1.0)
            canvas_blit_x = getattr(ctx, "canvas_blit_x", 0)
            canvas_blit_y = getattr(ctx, "canvas_blit_y", 0)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    editor.running = False
                    pygame.quit()
                    sys.exit(0)
                elif event.type == pygame.VIDEORESIZE:
                    if ctx is not None:
                        ctx.screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if scale_x > 0 and scale_y > 0:
                        cx = int((event.pos[0] - canvas_blit_x) / scale_x)
                        cy = int((event.pos[1] - canvas_blit_y) / scale_y)
                        editor.handle_mouse_click(cx, cy, event.button)
                elif event.type == pygame.MOUSEBUTTONUP:
                    editor.mouse_paint_val = None
                elif event.type == pygame.MOUSEMOTION:
                    if editor.mouse_paint_val is not None:
                        if scale_x > 0 and scale_y > 0:
                            cx = int((event.pos[0] - canvas_blit_x) / scale_x)
                            cy = int((event.pos[1] - canvas_blit_y) / scale_y)
                            editor.handle_mouse_motion(cx, cy)
                elif event.type == pygame.KEYDOWN:
                    editor.handle_key(event.unicode, event.key, event.mod)

            if canvas is not None:
                editor.render(canvas)
                if render_frame is not None:
                    render_frame()
                try:
                    pygame.display.flip()
                except Exception:
                    pass

    finally:
        if ctx is not None:
            if hasattr(ctx, "canvas_dirty"):
                ctx.canvas_dirty = True
            if hasattr(ctx, "redraw_canvas"):
                ctx.redraw_canvas()
            if hasattr(ctx, "update_display"):
                ctx.update_display()

    return editor


# Dual-Engine Sprite Editor class alias
SpriteEditor = ZXSpriteEditor
