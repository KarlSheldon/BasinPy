"""
ZX Spectrum 16x16 Tilemap Editor for BasinPy & BetaBasic
Command: EDTILES [tile_id]

Features:
- Edits 16x16 pixel tiles matching BasinPy's Tilemap Engine.
- Manages 192 tiles total (a full 256x192 ZX Spectrum screen: 16 cols x 12 rows).
- Top area: 16x16 pixel editor with drawing grid, palette, and tools.
- Lower area: 8x4 tile selector (32 tiles visible per page across 6 pages = 192 tiles).
- Selectable tile thumbnails in the lower 8x4 display.
- Save as .map bitmap file (16x16 tiles) and as .scn / .scr (standard Spectrum SCREEN$ 6912 bytes).
- Grab tiles from .scr screen files directly into the editor.
- Full mouse click/drag and keyboard controls.
"""

import os
import sys
import pygame

try:
    from tilemap_engine import (
        NUM_TILES, TILE_WIDTH, TILE_HEIGHT, TILE_SIZE_BYTES,
        DEFAULT_TILEMAP_BASE, get_tilemap_engine
    )
except Exception:
    NUM_TILES, TILE_WIDTH, TILE_HEIGHT, TILE_SIZE_BYTES = 192, 16, 16, 256
    DEFAULT_TILEMAP_BASE = 32768
    get_tilemap_engine = None

def get_main_context():
    """Safely retrieves the live BasinPy runtime module context."""
    for mod_name in ('__main__', 'main', 'BetaBasic'):
        mod = sys.modules.get(mod_name)
        if mod is not None and hasattr(mod, 'program'):
            return mod
    try:
        import main
        return main
    except Exception:
        return None

# Sinclair Spectrum 8 Standard Colors & Brights
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

SPECTRUM_BRIGHT_COLORS = [
    (0, 0, 0),        # 0: Black
    (0, 0, 255),      # 1: Bright Blue
    (255, 0, 0),      # 2: Bright Red
    (255, 0, 255),    # 3: Bright Magenta
    (0, 255, 0),      # 4: Bright Green
    (0, 255, 255),    # 5: Bright Cyan
    (255, 255, 0),    # 6: Bright Yellow
    (255, 255, 255)   # 7: Bright White
]

COLOR_NAMES = ["BLK", "BLU", "RED", "MAG", "GRN", "CYN", "YEL", "WHT"]


class ZXTileEditor:
    """
    16x16 Tilemap Editor for ZX Spectrum / BasinPy.
    """
    def __init__(self, start_tile_id=0):
        self.num_tiles = NUM_TILES
        self.active_tile = max(0, min(self.num_tiles - 1, int(start_tile_id)))
        self.cursor_row = 0       # 0 to 15
        self.cursor_col = 0       # 0 to 15
        self.page = self.active_tile // 32  # 0 to 5 (32 tiles per page)

        # Editor UI state
        self.running = True
        self.status_msg = f"Tile Editor Ready - Tile #{self.active_tile}"
        self.mouse_down = False
        self.mouse_paint_val = None

        # Connect with TilemapEngine
        self.engine = get_tilemap_engine() if get_tilemap_engine else None
        if self.engine:
            self.engine.sync_from_memory()

    def get_tile_pixel(self, t_id, r, c):
        if not self.engine:
            return 0
        t_data = self.engine.get_tile_data(t_id)
        if 0 <= r < 16 and 0 <= c < 16:
            return t_data[r * 16 + c]
        return 0

    def set_tile_pixel(self, t_id, r, c, val):
        if not self.engine:
            return
        t_data = self.engine.get_tile_data(t_id)
        if 0 <= r < 16 and 0 <= c < 16:
            t_data[r * 16 + c] = 1 if val else 0
            self.engine._sync_tile_to_memory(t_id)

    def get_tile_colors(self, t_id):
        if not self.engine:
            return 7, 0, False
        attrs = self.engine.get_tile_attrs(t_id)
        raw = attrs[0]
        ink = raw & 7
        paper = (raw >> 3) & 7
        bright = bool(raw & 64)
        return ink, paper, bright

    def set_tile_colors(self, t_id, ink=None, paper=None, bright=None):
        if not self.engine:
            return
        attrs = self.engine.get_tile_attrs(t_id)
        for i in range(4):
            raw = attrs[i]
            cur_ink = raw & 7
            cur_paper = (raw >> 3) & 7
            cur_bright = bool(raw & 64)
            cur_flash = raw & 128

            new_ink = (ink & 7) if ink is not None else cur_ink
            new_paper = (paper & 7) if paper is not None else cur_paper
            new_bright = 64 if (bright if bright is not None else cur_bright) else 0

            attrs[i] = cur_flash | new_bright | (new_paper << 3) | new_ink

    # --------------------------------------------------------------------------
    # Editing Operations
    # --------------------------------------------------------------------------
    def clear_tile(self, t_id):
        if not self.engine: return
        t_data = self.engine.get_tile_data(t_id)
        for i in range(256):
            t_data[i] = 0
        self.engine._sync_tile_to_memory(t_id)
        self.status_msg = f"Tile #{t_id} Cleared"

    def invert_tile(self, t_id):
        if not self.engine: return
        t_data = self.engine.get_tile_data(t_id)
        for i in range(256):
            t_data[i] = 0 if t_data[i] else 1
        self.engine._sync_tile_to_memory(t_id)
        self.status_msg = f"Tile #{t_id} Inverted"

    def flip_h(self, t_id):
        if not self.engine: return
        t_data = self.engine.get_tile_data(t_id)
        new_data = bytearray(256)
        for r in range(16):
            for c in range(16):
                new_data[r * 16 + c] = t_data[r * 16 + (15 - c)]
        self.engine.set_tile_data(t_id, new_data)
        self.status_msg = f"Tile #{t_id} Flipped H"

    def flip_v(self, t_id):
        if not self.engine: return
        t_data = self.engine.get_tile_data(t_id)
        new_data = bytearray(256)
        for r in range(16):
            for c in range(16):
                new_data[r * 16 + c] = t_data[(15 - r) * 16 + c]
        self.engine.set_tile_data(t_id, new_data)
        self.status_msg = f"Tile #{t_id} Flipped V"

    def rotate_90(self, t_id):
        if not self.engine: return
        t_data = self.engine.get_tile_data(t_id)
        new_data = bytearray(256)
        for r in range(16):
            for c in range(16):
                new_data[c * 16 + (15 - r)] = t_data[r * 16 + c]
        self.engine.set_tile_data(t_id, new_data)
        self.status_msg = f"Tile #{t_id} Rotated 90 deg"

    # --------------------------------------------------------------------------
    # Rendering & BASIC Line Generation
    # --------------------------------------------------------------------------
    def generate_basic_lines(self):
        """Generates Sinclair BASIC lines in resident program to load and setup tilemap."""
        ctx = get_main_context()
        base_addr = 40000
        if self.engine and hasattr(self.engine, "tilemap_base"):
            base_addr = self.engine.tilemap_base

        lines_to_add = {
            5000: 'REM *** TILEMAP CONFIGURATION ***',
            5010: f'TILEMAP {base_addr}',
            5020: 'REM 192 TILES DEFINED (16x16 PIXELS)',
            5030: 'REM USE "PLACE tile_id, col, row" TO DRAW'
        }
        if ctx is not None and hasattr(ctx, "program"):
            for ln, text in lines_to_add.items():
                ctx.program[ln] = text
                if hasattr(ctx, "program_line_order") and ln not in ctx.program_line_order:
                    ctx.program_line_order.append(ln)
            if hasattr(ctx, "canvas_dirty"):
                ctx.canvas_dirty = True
        self.status_msg = "Lines 5000-5030 Generated in BASIC!"

    def draw_text(self, surf, text, x, y, fg=(255, 255, 255), bg=None):
        """Draws authentic 8x8 Sinclair font bitmap text onto surface."""
        ctx = get_main_context()
        for ch in text:
            bmp = None
            if ctx is not None and hasattr(ctx, "get_char_bitmap"):
                try:
                    bmp = ctx.get_char_bitmap(ch)
                except Exception:
                    bmp = None
            if bmp is None:
                bmp = bytearray(8)
            for r in range(8):
                byte_val = bmp[r] if r < len(bmp) else 0
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
        """
        Renders authentic ZX Spectrum Tilemap Editor UI onto 256x192 canvas:
        - Header Bar: y = 0..11
        - Top Area: 16x16 Pixel Drawing Grid (x=4..100, y=14..110)
                    Palette, Tools, Preview (x=106..254, y=14..104)
        - Lower Area: 8x4 Tile Selector (32 tiles visible) (x=4..164, y=108..176)
                      Page navigation & Bank info (x=170..254, y=108..176)
        - Status Bar: y = 181..191
        """
        t_id = self.active_tile
        ink, paper, bright = self.get_tile_colors(t_id)
        pal = SPECTRUM_BRIGHT_COLORS if bright else SPECTRUM_COLORS
        ink_color = pal[ink]
        paper_color = pal[paper]

        c_black = (0, 0, 0)
        c_white = (255, 255, 255)
        c_gray = (128, 128, 128)
        c_dark_gray = (40, 40, 40)
        c_yellow = (255, 255, 0)
        c_cyan = (0, 192, 192)
        c_green = (0, 192, 0)
        c_red = (192, 0, 0)
        c_blue = (0, 0, 192)

        # 1. Background
        target_surf.fill(c_black)

        # 2. Header Bar (y = 0..11)
        pygame.draw.rect(target_surf, c_blue, (0, 0, 256, 11))
        self.draw_text(target_surf, "EDTILES", 2, 2, c_yellow, c_blue)
        self.draw_text(target_surf, f"T#{t_id:03d}", 62, 2, c_white, c_blue)
        self.draw_text(target_surf, f"P{self.page + 1}/6", 106, 2, c_cyan, c_blue)

        # Quick Tile Prev/Next buttons [<] [>]
        pygame.draw.rect(target_surf, c_cyan, (142, 1, 14, 9))
        self.draw_text(target_surf, "<", 145, 2, c_black, c_cyan)
        pygame.draw.rect(target_surf, c_cyan, (160, 1, 14, 9))
        self.draw_text(target_surf, ">", 163, 2, c_black, c_cyan)

        # GEN and EXT buttons
        pygame.draw.rect(target_surf, c_yellow, (178, 1, 36, 9))
        self.draw_text(target_surf, "GEN", 184, 2, c_black, c_yellow)
        pygame.draw.rect(target_surf, c_red, (218, 1, 36, 9))
        self.draw_text(target_surf, "EXT", 224, 2, c_white, c_red)

        # ----------------------------------------------------------------------
        # TOP AREA: 16x16 Pixel Grid & Tools (y = 14..104)
        # ----------------------------------------------------------------------
        # A. 16x16 Pixel Grid (x=4..100, y=14..110)
        grid_x = 4
        grid_y = 14
        cell_size = 6

        pygame.draw.rect(target_surf, c_gray, (grid_x - 1, grid_y - 1, 98, 98), 1)
        for r in range(16):
            for c in range(16):
                px = grid_x + c * cell_size
                py = grid_y + r * cell_size
                p_val = self.get_tile_pixel(t_id, r, c)
                p_col = ink_color if p_val else paper_color
                pygame.draw.rect(target_surf, p_col, (px, py, cell_size, cell_size))
                pygame.draw.rect(target_surf, c_dark_gray, (px, py, cell_size, cell_size), 1)

        # Guidelines across 16x16 grid
        pygame.draw.line(target_surf, c_blue, (grid_x + 48, grid_y), (grid_x + 48, grid_y + 95))
        pygame.draw.line(target_surf, c_blue, (grid_x, grid_y + 48), (grid_x + 95, grid_y + 48))

        # Cursor outline
        cur_px = grid_x + self.cursor_col * cell_size
        cur_py = grid_y + self.cursor_row * cell_size
        pygame.draw.rect(target_surf, c_yellow, (cur_px, cur_py, cell_size, cell_size), 1)

        # B. Right Side of Top Area (x=106..254, y=14..104)
        # 1. Preview Boxes (1:1 and 2:1)
        self.draw_text(target_surf, "1:1", 102, 13, c_gray)
        pygame.draw.rect(target_surf, c_gray, (105, 23, 18, 18), 1)
        pygame.draw.rect(target_surf, paper_color, (106, 24, 16, 16))
        for r in range(16):
            for c in range(16):
                if self.get_tile_pixel(t_id, r, c):
                    target_surf.set_at((106 + c, 24 + r), ink_color)

        self.draw_text(target_surf, "2:1", 135, 13, c_gray)
        pygame.draw.rect(target_surf, c_gray, (129, 23, 34, 34), 1)
        pygame.draw.rect(target_surf, paper_color, (130, 24, 32, 32))
        for r in range(16):
            for c in range(16):
                if self.get_tile_pixel(t_id, r, c):
                    pygame.draw.rect(target_surf, ink_color, (130 + c * 2, 24 + r * 2, 2, 2))

        # 2. Colors: INK & PAPER Pickers
        self.draw_text(target_surf, "INK", 170, 14, c_white)
        for i in range(8):
            bx = 170 + (i % 4) * 10
            by = 24 + (i // 4) * 10
            pcol = pal[i]
            pygame.draw.rect(target_surf, pcol, (bx, by, 9, 9))
            if i == ink:
                pygame.draw.rect(target_surf, c_white, (bx - 1, by - 1, 11, 11), 1)

        self.draw_text(target_surf, "PAP", 214, 14, c_white)
        for i in range(8):
            bx = 214 + (i % 4) * 10
            by = 24 + (i // 4) * 10
            pcol = pal[i]
            pygame.draw.rect(target_surf, pcol, (bx, by, 9, 9))
            if i == paper:
                pygame.draw.rect(target_surf, c_white, (bx - 1, by - 1, 11, 11), 1)

        # BRIGHT toggle button
        b_str = "BRT:1" if bright else "BRT:0"
        pygame.draw.rect(target_surf, c_gray, (106, 46, 44, 11), 1)
        pygame.draw.rect(target_surf, (20, 20, 40), (107, 47, 42, 9))
        self.draw_text(target_surf, b_str, 108, 48, c_yellow if bright else c_gray)

        # 3. Action Tools: CLR, INV, FLH, FLV, ROT (y = 61..72)
        tools = [
            ("CLR", 106),
            ("INV", 136),
            ("FLH", 166),
            ("FLV", 196),
            ("ROT", 226)
        ]
        for t_name, tx in tools:
            pygame.draw.rect(target_surf, c_gray, (tx, 61, 28, 11), 1)
            pygame.draw.rect(target_surf, (30, 30, 60), (tx + 1, 62, 26, 9))
            self.draw_text(target_surf, t_name, tx + 2, 63, c_cyan)

        # 4. Action Buttons: [SAVE MAP] [SAVE SCN] [GRAB SCR] [LOAD MAP]
        # Row 1 (y = 75..87)
        pygame.draw.rect(target_surf, c_green, (106, 75, 72, 12), 1)
        pygame.draw.rect(target_surf, (20, 50, 20), (107, 76, 70, 10))
        self.draw_text(target_surf, "SAVE MAP", 110, 77, c_white)

        pygame.draw.rect(target_surf, c_red, (182, 75, 72, 12), 1)
        pygame.draw.rect(target_surf, (50, 20, 20), (183, 76, 70, 10))
        self.draw_text(target_surf, "SAVE SCN", 186, 77, c_white)

        # Row 2 (y = 90..102)
        pygame.draw.rect(target_surf, c_cyan, (106, 90, 72, 12), 1)
        pygame.draw.rect(target_surf, (20, 30, 60), (107, 91, 70, 10))
        self.draw_text(target_surf, "GRAB SCR", 110, 92, c_white)

        pygame.draw.rect(target_surf, c_yellow, (182, 90, 72, 12), 1)
        pygame.draw.rect(target_surf, (40, 40, 20), (183, 91, 70, 10))
        self.draw_text(target_surf, "LOAD MAP", 186, 92, c_white)

        # ----------------------------------------------------------------------
        # LOWER AREA: 8x4 Tile Selector (y = 106..180)
        # ----------------------------------------------------------------------
        pygame.draw.line(target_surf, c_blue, (0, 105), (255, 105))

        start_idx = self.page * 32
        base_grid_x = 4
        base_grid_y = 108

        for row in range(4):
            for col in range(8):
                idx = start_idx + (row * 8 + col)
                if idx >= self.num_tiles:
                    continue
                tx = base_grid_x + col * 20
                ty = base_grid_y + row * 17

                t_ink, t_pap, t_brt = self.get_tile_colors(idx)
                t_pal = SPECTRUM_BRIGHT_COLORS if t_brt else SPECTRUM_COLORS
                t_ink_c = t_pal[t_ink]
                t_pap_c = t_pal[t_pap]

                # Border around thumbnail
                is_selected = (idx == self.active_tile)
                b_color = c_yellow if is_selected else c_dark_gray
                pygame.draw.rect(target_surf, b_color, (tx - 1, ty - 1, 18, 16), 1 if not is_selected else 2)
                pygame.draw.rect(target_surf, t_pap_c, (tx, ty, 16, 14))

                # Render thumbnail pixels (sampled 16x14)
                for py in range(14):
                    for px in range(16):
                        if self.get_tile_pixel(idx, py, px):
                            target_surf.set_at((tx + px, ty + py), t_ink_c)

        # Page Controls & Info (x = 170..254, y = 108..178)
        p_num = self.page + 1
        self.draw_text(target_surf, f"PAGE {p_num}/6", 170, 108, c_yellow)
        self.draw_text(target_surf, f"{start_idx:03d}..{start_idx+31:03d}", 170, 118, c_gray)

        # [< PREV] [NEXT >] buttons
        pygame.draw.rect(target_surf, c_cyan, (170, 129, 38, 11), 1)
        pygame.draw.rect(target_surf, (10, 30, 50), (171, 130, 36, 9))
        self.draw_text(target_surf, "PREV", 173, 131, c_cyan)

        pygame.draw.rect(target_surf, c_cyan, (214, 129, 38, 11), 1)
        pygame.draw.rect(target_surf, (10, 30, 50), (215, 130, 36, 9))
        self.draw_text(target_surf, "NEXT", 217, 131, c_cyan)

        # Address indicator
        if self.engine:
            cur_addr = self.engine.get_tile_address(self.active_tile)
            self.draw_text(target_surf, f"A:{cur_addr}", 170, 144, c_gray)

        self.draw_text(target_surf, "192 TILES", 170, 156, c_green)
        self.draw_text(target_surf, "SPACE:Plot", 170, 168, c_cyan)

        # ----------------------------------------------------------------------
        # STATUS BAR (y = 181..191)
        # ----------------------------------------------------------------------
        pygame.draw.rect(target_surf, c_blue, (0, 181, 256, 11))
        self.draw_text(target_surf, self.status_msg[:32], 2, 182, c_yellow, c_blue)

    # --------------------------------------------------------------------------
    # Event Handling
    # --------------------------------------------------------------------------
    def handle_mouse_click(self, cx, cy, button):
        """Processes mouse clicks in 256x192 canvas coordinates."""
        t_id = self.active_tile

        # 1. Header Buttons (y = 0..11)
        if 0 <= cy <= 11:
            if 142 <= cx <= 156:  # Prev tile <
                self.active_tile = (self.active_tile - 1) % self.num_tiles
                self.page = self.active_tile // 32
                self.status_msg = f"Tile #{self.active_tile} Selected"
                return
            elif 160 <= cx <= 174:  # Next tile >
                self.active_tile = (self.active_tile + 1) % self.num_tiles
                self.page = self.active_tile // 32
                self.status_msg = f"Tile #{self.active_tile} Selected"
                return
            elif 178 <= cx <= 214:  # [GEN]
                self.generate_basic_lines()
                return
            elif 218 <= cx <= 254:  # [EXT]
                self.running = False
                return

        # 2. 16x16 Pixel Grid Click (x=4..100, y=14..110)
        grid_x, grid_y, cell_size = 4, 14, 6
        if grid_x <= cx < grid_x + 96 and grid_y <= cy < grid_y + 96:
            c = (cx - grid_x) // cell_size
            r = (cy - grid_y) // cell_size
            self.cursor_row = r
            self.cursor_col = c
            if button == 1:  # Left click: toggle or paint ink
                cur_val = self.get_tile_pixel(t_id, r, c)
                new_val = 0 if cur_val else 1
                self.set_tile_pixel(t_id, r, c, new_val)
                self.mouse_paint_val = new_val
            elif button == 3:  # Right click: erase
                self.set_tile_pixel(t_id, r, c, 0)
                self.mouse_paint_val = 0
            self.mouse_down = True
            return

        # 3. Top Area Right Side Controls (y = 14..104)
        # INK Picker (x=170..210, y=24..44)
        if 24 <= cy <= 44 and 170 <= cx <= 210:
            i_col = (cx - 170) // 10
            i_row = (cy - 24) // 10
            sel_ink = i_row * 4 + i_col
            if 0 <= sel_ink < 8:
                self.set_tile_colors(t_id, ink=sel_ink)
                self.status_msg = f"INK set to {sel_ink} ({COLOR_NAMES[sel_ink]})"
                return

        # PAPER Picker (x=214..254, y=24..44)
        if 24 <= cy <= 44 and 214 <= cx <= 254:
            p_col = (cx - 214) // 10
            p_row = (cy - 24) // 10
            sel_paper = p_row * 4 + p_col
            if 0 <= sel_paper < 8:
                self.set_tile_colors(t_id, paper=sel_paper)
                self.status_msg = f"PAPER set to {sel_paper} ({COLOR_NAMES[sel_paper]})"
                return

        # BRIGHT Toggle (x=106..150, y=46..58)
        if 46 <= cy <= 58 and 106 <= cx <= 150:
            _, _, brt = self.get_tile_colors(t_id)
            self.set_tile_colors(t_id, bright=not brt)
            self.status_msg = f"BRIGHT set to {0 if brt else 1}"
            return

        # Tools Row: CLR, INV, FLH, FLV, ROT (y = 61..72)
        if 61 <= cy <= 72:
            if 106 <= cx <= 134: self.clear_tile(t_id); return
            if 136 <= cx <= 164: self.invert_tile(t_id); return
            if 166 <= cx <= 194: self.flip_h(t_id); return
            if 196 <= cx <= 224: self.flip_v(t_id); return
            if 226 <= cx <= 254: self.rotate_90(t_id); return

        # Action Buttons (Save/Load)
        # Row 1 (y = 75..87)
        if 75 <= cy <= 87:
            if 106 <= cx <= 178: self.save_map_dialog(); return
            if 182 <= cx <= 254: self.save_scn_dialog(); return
        # Row 2 (y = 90..102)
        if 90 <= cy <= 102:
            if 106 <= cx <= 178: self.grab_scr_dialog(); return
            if 182 <= cx <= 254: self.load_map_dialog(); return

        # 4. Lower Area 8x4 Tile Selector (x=4..164, y=108..176)
        base_grid_x, base_grid_y = 4, 108
        if base_grid_x <= cx < base_grid_x + 160 and base_grid_y <= cy < base_grid_y + 68:
            col = (cx - base_grid_x) // 20
            row = (cy - base_grid_y) // 17
            clicked_idx = self.page * 32 + (row * 8 + col)
            if 0 <= clicked_idx < self.num_tiles:
                self.active_tile = clicked_idx
                self.status_msg = f"Selected Tile #{self.active_tile}"
                return

        # Page Navigation Buttons (PREV / NEXT) (y = 129..140)
        if 129 <= cy <= 140:
            if 170 <= cx <= 208:  # PREV
                self.page = (self.page - 1) % 6
                self.status_msg = f"Page {self.page + 1}/6"
                return
            elif 214 <= cx <= 252:  # NEXT
                self.page = (self.page + 1) % 6
                self.status_msg = f"Page {self.page + 1}/6"
                return

    def handle_mouse_drag(self, cx, cy):
        """Allows drag-painting in the 16x16 grid."""
        if not self.mouse_down or self.mouse_paint_val is None:
            return
        grid_x, grid_y, cell_size = 4, 14, 6
        if grid_x <= cx < grid_x + 96 and grid_y <= cy < grid_y + 96:
            c = (cx - grid_x) // cell_size
            r = (cy - grid_y) // cell_size
            self.cursor_row = r
            self.cursor_col = c
            self.set_tile_pixel(self.active_tile, r, c, self.mouse_paint_val)

    def handle_key(self, event):
        """Processes keyboard shortcuts."""
        t_id = self.active_tile
        key = event.key
        mod = event.mod

        if key in (pygame.K_ESCAPE, pygame.K_q):
            self.running = False
            return

        # Cursor movement in 16x16 grid
        if key == pygame.K_UP:
            self.cursor_row = (self.cursor_row - 1) % 16
        elif key == pygame.K_DOWN:
            self.cursor_row = (self.cursor_row + 1) % 16
        elif key == pygame.K_LEFT:
            self.cursor_col = (self.cursor_col - 1) % 16
        elif key == pygame.K_RIGHT:
            self.cursor_col = (self.cursor_col + 1) % 16
        elif key in (pygame.K_SPACE, pygame.K_RETURN):
            cur = self.get_tile_pixel(t_id, self.cursor_row, self.cursor_col)
            self.set_tile_pixel(t_id, self.cursor_row, self.cursor_col, 0 if cur else 1)

        # Tile switching
        elif key in (pygame.K_LEFTBRACKET, pygame.K_MINUS):
            self.active_tile = (self.active_tile - 1) % self.num_tiles
            self.page = self.active_tile // 32
            self.status_msg = f"Tile #{self.active_tile}"
        elif key in (pygame.K_RIGHTBRACKET, pygame.K_EQUALS):
            self.active_tile = (self.active_tile + 1) % self.num_tiles
            self.page = self.active_tile // 32
            self.status_msg = f"Tile #{self.active_tile}"
        elif key == pygame.K_PAGEUP:
            self.page = (self.page - 1) % 6
            self.status_msg = f"Page {self.page + 1}/6"
        elif key == pygame.K_PAGEDOWN:
            self.page = (self.page + 1) % 6
            self.status_msg = f"Page {self.page + 1}/6"

        # Hotkeys: C=Clr, V=Inv, H=FlpH, F=FlpV, R=Rot, G=Generate
        elif key == pygame.K_c and not (mod & pygame.KMOD_CTRL):
            self.clear_tile(t_id)
        elif key == pygame.K_v and not (mod & pygame.KMOD_CTRL):
            self.invert_tile(t_id)
        elif key == pygame.K_h:
            self.flip_h(t_id)
        elif key == pygame.K_f:
            self.flip_v(t_id)
        elif key == pygame.K_r:
            self.rotate_90(t_id)
        elif key == pygame.K_g and not (mod & pygame.KMOD_CTRL):
            self.generate_basic_lines()

        # Color shortcuts (1..8 sets INK)
        elif pygame.K_1 <= key <= pygame.K_8:
            new_ink = key - pygame.K_1
            self.set_tile_colors(t_id, ink=new_ink)
            self.status_msg = f"INK set to {new_ink}"

        # File actions
        elif key == pygame.K_s:
            if mod & pygame.KMOD_SHIFT:
                self.save_scn_dialog()
            else:
                self.save_map_dialog()
        elif key == pygame.K_l:
            self.load_map_dialog()

    # --------------------------------------------------------------------------
    # Dialogs & File Operations
    # --------------------------------------------------------------------------
    def save_map_dialog(self):
        if not self.engine: return
        target = "tilemap.map"
        try:
            ctx = get_main_context()
            if ctx and hasattr(ctx, 'ask_save_filename'):
                fn = ctx.ask_save_filename(defaultextension=".map", filetypes=[("Tilemap files", "*.map"), ("All files", "*.*")])
                if fn: target = fn
        except Exception:
            pass
        try:
            self.engine.save_map_file(target)
            self.status_msg = f"Saved {os.path.basename(target)} (49KB .map)"
        except Exception as e:
            self.status_msg = f"Save error: {e}"

    def save_scn_dialog(self):
        if not self.engine: return
        target = "tilemap.scn"
        try:
            ctx = get_main_context()
            if ctx and hasattr(ctx, 'ask_save_filename'):
                fn = ctx.ask_save_filename(defaultextension=".scn", filetypes=[("Spectrum SCREEN$ files", "*.scn;*.scr"), ("All files", "*.*")])
                if fn: target = fn
        except Exception:
            pass
        try:
            self.engine.save_scn_file(target)
            self.status_msg = f"Saved {os.path.basename(target)} (6912B SCREEN$)"
        except Exception as e:
            self.status_msg = f"Save error: {e}"

    def grab_scr_dialog(self):
        if not self.engine: return
        target = None
        try:
            ctx = get_main_context()
            if ctx and hasattr(ctx, 'ask_open_filename'):
                fn = ctx.ask_open_filename(filetypes=[("Spectrum SCREEN$ files", "*.scr;*.scn"), ("All files", "*.*")])
                if fn: target = fn
        except Exception:
            pass
        if not target:
            candidates = [f for f in os.listdir(".") if f.lower().endswith((".scr", ".scn"))]
            if candidates:
                target = candidates[0]
        if target and os.path.exists(target):
            try:
                self.engine.load_map_file(target)
                self.status_msg = f"Grabbed tiles from {os.path.basename(target)}"
            except Exception as e:
                self.status_msg = f"Grab error: {e}"
        else:
            self.status_msg = "No .scr/.scn files found"

    def load_map_dialog(self):
        if not self.engine: return
        target = None
        try:
            ctx = get_main_context()
            if ctx and hasattr(ctx, 'ask_open_filename'):
                fn = ctx.ask_open_filename(filetypes=[("Tilemap & Screen files", "*.map;*.scn;*.scr"), ("All files", "*.*")])
                if fn: target = fn
        except Exception:
            pass
        if not target:
            target = "tilemap.map"
        if os.path.exists(target):
            try:
                self.engine.load_map_file(target)
                self.status_msg = f"Loaded {os.path.basename(target)}"
            except Exception as e:
                self.status_msg = f"Load error: {e}"
        else:
            self.status_msg = f"{os.path.basename(target)} not found"


def launch_tile_editor(args=""):
    """
    Launches the interactive EDTILES tilemap editor.
    Can be run from BasinPy command prompt (e.g. EDTILES or EDTILES 5).
    Opens directly on the Spectrum output screen in authentic ZX Spectrum style.
    """
    start_tile = 0
    s_clean = args.strip()
    if s_clean.isdigit():
        start_tile = int(s_clean)

    editor = ZXTileEditor(start_tile_id=start_tile)

    # If running headless (test mode), return immediately after setup
    if os.environ.get("SDL_VIDEODRIVER") == "dummy" or os.environ.get("BASINPY_HEADLESS") == "1":
        return editor

    ctx = get_main_context()
    screen = getattr(ctx, "screen", None) if ctx else None
    if screen is None:
        screen = pygame.display.get_surface()

    canvas = getattr(ctx, "canvas", None) if ctx else None
    if canvas is None:
        canvas = pygame.Surface((256, 192))

    render_frame = getattr(ctx, "render_frame", None) if ctx else None

    clock = pygame.time.Clock()
    editor.running = True

    try:
        while editor.running:
            clock.tick(60)

            scale_x = getattr(ctx, "scale_x", 1.0) if ctx else 1.0
            scale_y = getattr(ctx, "scale_y", 1.0) if ctx else 1.0
            canvas_blit_x = getattr(ctx, "canvas_blit_x", 0) if ctx else 0
            canvas_blit_y = getattr(ctx, "canvas_blit_y", 0) if ctx else 0

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
                    editor.mouse_down = False
                    editor.mouse_paint_val = None
                elif event.type == pygame.MOUSEMOTION:
                    if editor.mouse_down and editor.mouse_paint_val is not None:
                        if scale_x > 0 and scale_y > 0:
                            cx = int((event.pos[0] - canvas_blit_x) / scale_x)
                            cy = int((event.pos[1] - canvas_blit_y) / scale_y)
                            editor.handle_mouse_drag(cx, cy)
                elif event.type == pygame.KEYDOWN:
                    editor.handle_key(event)

            editor.render(canvas)
            if render_frame is not None:
                render_frame()
            elif screen is not None:
                cur_w, cur_h = screen.get_size()
                scaled = pygame.transform.scale(canvas, (cur_w, cur_h))
                screen.blit(scaled, (0, 0))

            try:
                pygame.display.flip()
            except Exception:
                pass
    finally:
        # Sync back to BasinPy memory upon exit
        if editor.engine:
            editor.engine.sync_to_memory()
        if ctx is not None:
            if hasattr(ctx, "canvas_dirty"):
                ctx.canvas_dirty = True
            if hasattr(ctx, "redraw_canvas"):
                ctx.redraw_canvas()
            if hasattr(ctx, "update_display"):
                ctx.update_display()

    return editor
