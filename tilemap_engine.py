"""
ZX Spectrum 16x16 Tilemap Engine for BasinPy & BetaBasic.
Manages up to 192 tiles (a full 256x192 screen arranged in 16 columns x 12 rows).
Each tile is 16x16 pixels (256 bytes uncompressed, 1 byte per pixel).
Supports memory mapping at configurable base address, SCREEN$ (.scr / .scn)
import/export, and inline PLACE rendering matching Sinclair PRINT syntax.
"""

import os
import sys
import struct

NUM_TILES = 192        # 16 columns * 12 rows = 192 tiles (full screen)
TILE_WIDTH = 16
TILE_HEIGHT = 16
TILE_SIZE_BYTES = 256  # 16 * 16 pixels = 256 bytes per tile
DEFAULT_TILEMAP_BASE = 32768

def get_main_context():
    """Safely retrieves the live BasinPy runtime module context (__main__, main, or BetaBasic)."""
    for mod_name in ('__main__', 'main', 'BetaBasic'):
        mod = sys.modules.get(mod_name)
        if mod is not None and hasattr(mod, 'memory'):
            return mod
    try:
        import main
        return main
    except Exception:
        return None


class TilemapEngine:
    """
    Manages the 192 16x16 tiles, memory synchronization, and screen rendering.
    """
    def __init__(self, base_address=DEFAULT_TILEMAP_BASE):
        self.base_address = int(base_address) & 0xFFFF
        # 192 tiles, each 256 bytes (16 rows of 16 pixel bytes: 0=paper, 1=ink/color)
        self.tiles = [bytearray(TILE_SIZE_BYTES) for _ in range(NUM_TILES)]
        # 192 tile attribute blocks (each tile covers 2x2 character cells: TL, TR, BL, BR)
        # Default: INK 7, PAPER 0, BRIGHT 0, FLASH 0 (0x07)
        self.attrs = [bytearray([7, 7, 7, 7]) for _ in range(NUM_TILES)]
        self._init_default_tiles()

    def _init_default_tiles(self):
        """Creates sample tile patterns (brick, stone, ground, hazard, etc.) for initial use."""
        # Tile 0: Blank / Space (all 0)
        # Tile 1: Brick block
        t1 = bytearray(256)
        for y in range(16):
            for x in range(16):
                # Brick pattern with mortar lines
                if y in (0, 7, 8, 15) or (y < 8 and x in (0, 8)) or (y >= 8 and x in (4, 12)):
                    t1[y * 16 + x] = 0
                else:
                    t1[y * 16 + x] = 1
        self.tiles[1] = t1
        self.attrs[1] = bytearray([2, 2, 2, 2])  # Red bricks

        # Tile 2: Stone / Cobblestone block
        t2 = bytearray(256)
        for y in range(16):
            for x in range(16):
                if (x % 4 == 0) or (y % 4 == 0) or ((x + y) % 6 == 0):
                    t2[y * 16 + x] = 1
        self.tiles[2] = t2
        self.attrs[2] = bytearray([6, 6, 6, 6])  # Yellow / Stone

        # Tile 3: Hazard / Striped block
        t3 = bytearray(256)
        for y in range(16):
            for x in range(16):
                if (x + y) % 4 in (0, 1):
                    t3[y * 16 + x] = 1
        self.tiles[3] = t3
        self.attrs[3] = bytearray([6, 6, 6, 6])  # Yellow/Black hazard

    def set_base_address(self, addr):
        """Configures the memory location for tile 0 (each tile is 256 bytes)."""
        self.base_address = int(addr) & 0xFFFF
        self.sync_to_memory()

    def get_tile_address(self, tile_idx):
        """Returns the memory address of the specified tile."""
        tile_idx = max(0, min(NUM_TILES - 1, int(tile_idx)))
        return (self.base_address + tile_idx * TILE_SIZE_BYTES) & 0xFFFF

    def get_tile_data(self, tile_idx):
        """Returns the 256-byte pixel bytearray for tile_idx (0..191)."""
        tile_idx = max(0, min(NUM_TILES - 1, int(tile_idx)))
        return self.tiles[tile_idx]

    def set_tile_data(self, tile_idx, byte_data):
        """Sets the 256-byte pixel data for tile_idx and updates RAM."""
        tile_idx = max(0, min(NUM_TILES - 1, int(tile_idx)))
        data = bytearray(byte_data[:TILE_SIZE_BYTES])
        if len(data) < TILE_SIZE_BYTES:
            data.extend(bytearray(TILE_SIZE_BYTES - len(data)))
        self.tiles[tile_idx] = data
        self._sync_tile_to_memory(tile_idx)

    def set_tile_attrs(self, tile_idx, tl=None, tr=None, bl=None, br=None):
        """Sets the 4 cell attributes for the tile (2x2 character cells)."""
        tile_idx = max(0, min(NUM_TILES - 1, int(tile_idx)))
        if tl is not None: self.attrs[tile_idx][0] = tl & 0xFF
        if tr is not None: self.attrs[tile_idx][1] = tr & 0xFF
        if bl is not None: self.attrs[tile_idx][2] = bl & 0xFF
        if br is not None: self.attrs[tile_idx][3] = br & 0xFF

    def get_tile_attrs(self, tile_idx):
        """Returns the 4 attribute bytes [TL, TR, BL, BR] for the tile."""
        tile_idx = max(0, min(NUM_TILES - 1, int(tile_idx)))
        return self.attrs[tile_idx]

    def sync_to_memory(self):
        """Writes all 192 tiles (192 * 256 bytes) into BasinPy's Spectrum memory array."""
        ctx = get_main_context()
        if not ctx or not hasattr(ctx, 'memory') or ctx.memory is None:
            return
        mem = ctx.memory
        mem_len = len(mem)
        for i in range(NUM_TILES):
            addr = (self.base_address + i * TILE_SIZE_BYTES) & 0xFFFF
            t_data = self.tiles[i]
            for b_idx in range(TILE_SIZE_BYTES):
                target = (addr + b_idx) & 0xFFFF
                if target < mem_len:
                    mem[target] = t_data[b_idx]

    def _sync_tile_to_memory(self, tile_idx):
        """Writes a single tile into BasinPy's Spectrum memory array."""
        ctx = get_main_context()
        if not ctx or not hasattr(ctx, 'memory') or ctx.memory is None:
            return
        mem = ctx.memory
        mem_len = len(mem)
        addr = (self.base_address + tile_idx * TILE_SIZE_BYTES) & 0xFFFF
        t_data = self.tiles[tile_idx]
        for b_idx in range(TILE_SIZE_BYTES):
            target = (addr + b_idx) & 0xFFFF
            if target < mem_len:
                mem[target] = t_data[b_idx]

    def sync_from_memory(self, tile_idx=None):
        """Reads tile data back from BasinPy's Spectrum memory array."""
        ctx = get_main_context()
        if not ctx or not hasattr(ctx, 'memory') or ctx.memory is None:
            return
        mem = ctx.memory
        mem_len = len(mem)
        indices = [tile_idx] if tile_idx is not None else range(NUM_TILES)
        for i in indices:
            if 0 <= i < NUM_TILES:
                addr = (self.base_address + i * TILE_SIZE_BYTES) & 0xFFFF
                t_data = bytearray(TILE_SIZE_BYTES)
                for b_idx in range(TILE_SIZE_BYTES):
                    target = (addr + b_idx) & 0xFFFF
                    if target < mem_len:
                        t_data[b_idx] = mem[target]
                self.tiles[i] = t_data

    # --------------------------------------------------------------------------
    # Screen Rendering & PLACE Command Execution
    # --------------------------------------------------------------------------
    def render_tile_to_screen(self, tile_idx, row, col, ink=None, paper=None,
                              bright=None, flash=None, inverse=False, over=False):
        """
        Renders a 16x16 tile onto the live screen at character position (row, col)
        or pixel position if row/col exceed character cell dimensions (24 rows, 32 cols).
        Updates both pixel bitmap (gfx_bits) and color attributes (attr_ink, attr_paper, etc.).
        """
        ctx = get_main_context()
        if not ctx:
            return

        tile_idx = max(0, min(NUM_TILES - 1, int(tile_idx)))
        tile = self.tiles[tile_idx]
        tile_attr = self.attrs[tile_idx]

        # Determine pixel top-left coordinates:
        # If row <= 23 and col <= 31, coordinates are character rows/cols matching PRINT AT
        if row <= 23 and col <= 31:
            base_px = int(col) * 8
            base_py = int(row) * 8
        else:
            base_px = int(col)
            base_py = int(row)

        gfx_bits = ctx.gfx_bits if hasattr(ctx, 'gfx_bits') else None
        attr_ink = ctx.attr_ink if hasattr(ctx, 'attr_ink') else None
        attr_paper = ctx.attr_paper if hasattr(ctx, 'attr_paper') else None
        attr_bright = ctx.attr_bright if hasattr(ctx, 'attr_bright') else None
        attr_flash = ctx.attr_flash if hasattr(ctx, 'attr_flash') else None
        attr_used = ctx.attr_used if hasattr(ctx, 'attr_used') else None

        # 1. Plot 16x16 Pixels
        if gfx_bits is not None:
            for py in range(16):
                sy = base_py + py
                if 0 <= sy < 192:
                    y_idx = 191 - sy  # Sinclair Y coordinate is bottom-up in gfx_bits
                    for px in range(16):
                        sx = base_px + px
                        if 0 <= sx < 256:
                            pixel_val = bool(tile[py * 16 + px])
                            if inverse:
                                pixel_val = not pixel_val
                            if over:
                                gfx_bits[sx][y_idx] ^= pixel_val
                            else:
                                gfx_bits[sx][y_idx] = pixel_val

        # 2. Update Attributes (covers 2x2 character cells)
        if attr_ink is not None and attr_paper is not None:
            char_r0 = base_py // 8
            char_c0 = base_px // 8
            # 4 cell positions: (0,0)->TL, (0,1)->TR, (1,0)->BL, (1,1)->BR
            cell_offsets = [
                (0, 0, 0),  # TL
                (0, 1, 1),  # TR
                (1, 0, 2),  # BL
                (1, 1, 3),  # BR
            ]
            for dr, dc, attr_idx in cell_offsets:
                cr = char_r0 + dr
                cc = char_c0 + dc
                if 0 <= cr < 24 and 0 <= cc < 32:
                    raw_attr = tile_attr[attr_idx]
                    def_ink = raw_attr & 7
                    def_paper = (raw_attr >> 3) & 7
                    def_bright = bool(raw_attr & 64)
                    def_flash = bool(raw_attr & 128)

                    final_ink = (ink & 7) if ink is not None else def_ink
                    final_paper = (paper & 7) if paper is not None else def_paper
                    final_bright = bool(bright) if bright is not None else def_bright
                    final_flash = bool(flash) if flash is not None else def_flash

                    if inverse:
                        final_ink, final_paper = final_paper, final_ink

                    attr_ink[cr][cc] = final_ink
                    attr_paper[cr][cc] = final_paper
                    if attr_bright is not None:
                        attr_bright[cr][cc] = final_bright
                    if attr_flash is not None:
                        attr_flash[cr][cc] = final_flash
                    if attr_used is not None:
                        attr_used[cr][cc] = True

        if hasattr(ctx, 'canvas_dirty'):
            ctx.canvas_dirty = True

    # --------------------------------------------------------------------------
    # SCREEN$ (.scr / .scn) Extraction & Generation
    # --------------------------------------------------------------------------
    def grab_from_screen_bytes(self, block, address=None):
        """
        Slices a standard 6912-byte ZX Spectrum SCREEN$ (256x192) into 192 tiles (16x12 grid).
        Each tile receives its 16x16 pixel monochrome bitmap and 2x2 cell attributes.
        """
        if not block or len(block) < 6144:
            raise ValueError(f"Invalid screen data length ({len(block) if block else 0} bytes, expected 6912)")

        if address is not None:
            self.set_base_address(address)

        for t in range(NUM_TILES):
            tile_col = t % 16   # 0..15 (columns across)
            tile_row = t // 16  # 0..11 (rows down)
            base_x = tile_col * 16
            base_y = tile_row * 16

            # Extract 16x16 pixels
            t_data = bytearray(TILE_SIZE_BYTES)
            for py in range(16):
                sy = base_y + py
                third = sy // 64
                row_in_third = (sy % 64) // 8
                line_in_row = sy % 8
                for px in range(16):
                    sx = base_x + px
                    x_byte = sx // 8
                    bit = 7 - (sx % 8)
                    addr = (third * 2048) + (row_in_third * 32) + (line_in_row * 256) + x_byte
                    if addr < len(block):
                        pixel_on = bool((block[addr] >> bit) & 1)
                        t_data[py * 16 + px] = 1 if pixel_on else 0
            self.tiles[t] = t_data

            # Extract 2x2 cell attributes
            cr0 = tile_row * 2
            cc0 = tile_col * 2
            t_attr = bytearray(4)
            # TL, TR, BL, BR
            cells = [(cr0, cc0), (cr0, cc0 + 1), (cr0 + 1, cc0), (cr0 + 1, cc0 + 1)]
            for c_idx, (cr, cc) in enumerate(cells):
                attr_addr = 6144 + (cr * 32) + cc
                if attr_addr < len(block):
                    t_attr[c_idx] = block[attr_addr]
                else:
                    t_attr[c_idx] = 7
            self.attrs[t] = t_attr

        self.sync_to_memory()

    def export_to_screen_bytes(self):
        """
        Arranges all 192 tiles (16 columns x 12 rows) into a full 256x192 ZX Spectrum SCREEN$ block
        (6144 bytes pixel bitmap + 768 bytes attribute table = 6912 bytes total).
        """
        block = bytearray(6912)

        # 1. Pixel Bitmaps (6144 bytes)
        for t in range(NUM_TILES):
            tile_col = t % 16
            tile_row = t // 16
            base_x = tile_col * 16
            base_y = tile_row * 16
            t_data = self.tiles[t]

            for py in range(16):
                sy = base_y + py
                third = sy // 64
                row_in_third = (sy % 64) // 8
                line_in_row = sy % 8
                for b_col in range(2):  # 2 bytes per 16-pixel row
                    byte_val = 0
                    for bit in range(8):
                        px = b_col * 8 + bit
                        if t_data[py * 16 + px]:
                            byte_val |= (1 << (7 - bit))
                    x_byte = (base_x // 8) + b_col
                    addr = (third * 2048) + (row_in_third * 32) + (line_in_row * 256) + x_byte
                    block[addr] = byte_val

        # 2. Attribute Map (768 bytes)
        for t in range(NUM_TILES):
            tile_col = t % 16
            tile_row = t // 16
            cr0 = tile_row * 2
            cc0 = tile_col * 2
            t_attr = self.attrs[t]
            cells = [
                (cr0, cc0, 0),          # TL
                (cr0, cc0 + 1, 1),      # TR
                (cr0 + 1, cc0, 2),      # BL
                (cr0 + 1, cc0 + 1, 3),  # BR
            ]
            for cr, cc, a_idx in cells:
                addr = 6144 + (cr * 32) + cc
                block[addr] = t_attr[a_idx]

        return bytes(block)

    # --------------------------------------------------------------------------
    # File I/O: .map and .scn / .scr
    # --------------------------------------------------------------------------
    def save_map_file(self, filepath):
        """
        Saves all 192 tiles to a .map file:
        49,152 bytes of pixel bitmap data (192 * 256 bytes) + 768 bytes attributes (192 * 4 bytes)
        = 49,920 bytes total.
        """
        with open(filepath, "wb") as f:
            for i in range(NUM_TILES):
                f.write(self.tiles[i])
            for i in range(NUM_TILES):
                f.write(self.attrs[i])

    def load_map_file(self, filepath, address=None):
        """
        Loads a .map or .scn/.scr file into the tilemap engine.
        Automatically detects whether file is a 6912-byte screen or a .map tile file.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        with open(filepath, "rb") as f:
            data = f.read()

        if address is not None:
            self.set_base_address(address)

        # Case 1: Standard Spectrum SCREEN$ (6912 bytes) or .scn/.scr file
        if len(data) == 6912 or filepath.lower().endswith((".scn", ".scr")):
            self.grab_from_screen_bytes(data, address=address)
            return "SCN"

        # Case 2: .map Tilemap binary
        total_pixels = NUM_TILES * TILE_SIZE_BYTES  # 49,152 bytes
        for i in range(NUM_TILES):
            o = i * TILE_SIZE_BYTES
            if o + TILE_SIZE_BYTES <= len(data):
                self.tiles[i] = bytearray(data[o : o + TILE_SIZE_BYTES])

        # Optional attributes trailer (192 * 4 = 768 bytes)
        attr_offset = total_pixels
        if len(data) >= attr_offset + NUM_TILES * 4:
            for i in range(NUM_TILES):
                ao = attr_offset + i * 4
                self.attrs[i] = bytearray(data[ao : ao + 4])

        self.sync_to_memory()
        return "MAP"

    def save_scn_file(self, filepath):
        """Saves the 192 tiles as a standard 6912-byte ZX Spectrum SCREEN$ (.scn / .scr) file."""
        block = self.export_to_screen_bytes()
        with open(filepath, "wb") as f:
            f.write(block)


# Global Engine Singleton
_global_tilemap_engine = None

def get_tilemap_engine():
    global _global_tilemap_engine
    if _global_tilemap_engine is None:
        _global_tilemap_engine = TilemapEngine(DEFAULT_TILEMAP_BASE)
    return _global_tilemap_engine
