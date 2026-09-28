#!/usr/bin/env python3
"""
================================================================================
SUPER MARIO BROS - SMOOTH PARALLAX SCROLLING DEMO
================================================================================
A high-performance, cycle-smooth multi-layer parallax scrolling demonstration
engineered in the authentic visual style of Super Mario Bros (NES / Arcade).

Features:
  - 4 Independent Depth Planes:
      1. Sky & Cloud Plane (Far Background): Scrolls at 0.5 px/frame
      2. Rolling Hills & Distant Bushes (Mid-Ground): Scrolls at 1.0 px/frame
      3. Ground, Pipes, Bricks, [?] Blocks & Coins (Foreground): Scrolls at 2.5 px/frame
      4. Animated Entities (Mario & Goomba): Authentic 3-frame Mario run stride (12 FPS),
         2-frame Goomba walking waddle, shimmering gold coins, pulsing [?] blocks
  - Authentic NES Color Palette (92, 148, 252 sky blue, brick reds, pipe greens, gold coins)
  - Interactive Keyboard Controls:
      [SPACE]      : Pause / Resume scrolling
      [UP] / [DOWN]: Increase / Decrease scroll speed (0.5x to 4.0x)
      [R]          : Reverse scrolling direction
      [1]          : Toggle Far Cloud plane ON/OFF
      [2]          : Toggle Midground Hills plane ON/OFF
      [3]          : Toggle Foreground Terrain plane ON/OFF
      [M]          : Toggle Mario running / idle pose
      [ESC] / [Q]  : Exit demo
  - Command Line Arguments:
      --headless       : Run in off-screen headless mode for verification
      --frames <N>     : Number of frames to simulate before exiting (default 120 in headless)
      --output <file>  : Path to save rendered screenshot (default: mario_scroller_verified.png)
      --scale <N>      : Window display scale factor (default: 3x -> 768x576)
================================================================================
"""

import os
import sys
import argparse
import time
import math
import pygame

# Set up paths
root_dir = os.path.abspath(os.path.dirname(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

scratch_dir = os.path.join(root_dir, "scratch")
if scratch_dir not in sys.path:
    sys.path.insert(0, scratch_dir)

import build_mario_patterns as bmp

# --- PALETTE DEFINITION (Authentic NES Super Mario Bros RGB) ---
SKY_BLUE    = (92, 148, 252)
GROUND_TAN  = (218, 109, 0)
DARK_BROWN  = (109, 36, 0)
BRICK_RED   = (182, 72, 0)
COIN_GOLD   = (255, 218, 0)
WHITE       = (255, 255, 255)
BLACK       = (0, 0, 0)
PIPE_GREEN  = (36, 218, 0)
PIPE_DARK   = (0, 145, 0)
PIPE_LIGHT  = (145, 255, 85)
HILL_GREEN  = (36, 182, 0)
HUD_YELLOW  = (255, 204, 0)


def create_sprite_surfaces():
    """Generates 16x16 pygame surfaces with alpha transparency for all Mario assets."""
    m0, m1, m2 = bmp.make_mario_frames()
    ground = bmp.make_ground_block()
    qblock = bmp.make_question_block()
    brick = bmp.make_brick_block()
    ptl, ptr, pbl, pbr = bmp.make_pipe_parts()
    cl, cr = bmp.make_cloud_parts()
    hp = bmp.make_hill_parts()
    g1, g2 = bmp.make_goomba_frames()
    coin = bmp.make_coin()

    raw_patterns = {
        "mario0": m0,
        "mario1": m1,
        "mario2": m2,
        "ground": ground,
        "qblock": qblock,
        "brick": brick,
        "pipe_tl": ptl,
        "pipe_tr": ptr,
        "pipe_bl": pbl,
        "pipe_br": pbr,
        "cloud_l": cl,
        "cloud_r": cr,
        "hill": hp,
        "goomba1": g1,
        "goomba2": g2,
        "coin": coin,
    }

    def next_to_rgb(c):
        if c == bmp.T:
            return None
        r = ((c >> 5) & 7) * 255 // 7
        g = ((c >> 2) & 7) * 255 // 7
        b = (c & 3) * 255 // 3
        return (r, g, b)

    surfaces = {}
    for name, p in raw_patterns.items():
        surf = pygame.Surface((16, 16), pygame.SRCALPHA)
        for y in range(16):
            for x in range(16):
                val = p[y * 16 + x]
                rgb = next_to_rgb(val)
                if rgb is not None:
                    surf.set_at((x, y), (rgb[0], rgb[1], rgb[2], 255))
                else:
                    surf.set_at((x, y), (0, 0, 0, 0))
        surfaces[name] = surf

    # Create narrow coin frame for spinning animation
    narrow_coin = pygame.Surface((16, 16), pygame.SRCALPHA)
    for y in range(2, 14):
        narrow_coin.set_at((6, y), (0, 0, 0, 255))
        narrow_coin.set_at((7, y), (255, 218, 0, 255))
        narrow_coin.set_at((8, y), (255, 255, 255, 255))
        narrow_coin.set_at((9, y), (0, 0, 0, 255))
    surfaces["coin_narrow"] = narrow_coin

    return surfaces


class MarioParallaxDemo:
    def __init__(self, headless=False, scale=3, target_fps=60):
        self.headless = headless
        self.scale = scale
        self.target_fps = target_fps
        self.base_w = 256
        self.base_h = 192

        if self.headless:
            os.environ["SDL_VIDEODRIVER"] = "dummy"
            os.environ["SDL_AUDIODRIVER"] = "dummy"

        pygame.init()
        pygame.display.set_caption("Super Mario Bros - Smooth Parallax Scrolling Demo")

        self.canvas = pygame.Surface((self.base_w, self.base_h))
        if not self.headless:
            self.screen = pygame.display.set_mode((self.base_w * self.scale, self.base_h * self.scale))
        else:
            self.screen = pygame.Surface((self.base_w * self.scale, self.base_h * self.scale))

        self.clock = pygame.time.Clock()
        self.surfaces = create_sprite_surfaces()

        # Parallax layer scroll offsets (floating point for sub-pixel precision)
        self.scroll_bg = 0.0     # Clouds: 0.5 px/frame
        self.scroll_mid = 0.0    # Hills/Bushes: 1.0 px/frame
        self.scroll_fg = 0.0     # Ground/Pipes/Blocks: 2.5 px/frame

        # Speed and direction multipliers
        self.speed_mult = 1.0
        self.paused = False
        self.direction = 1.0     # 1 = forward (scroll right->left), -1 = backward

        # Layer visibility toggles
        self.show_bg = True
        self.show_mid = True
        self.show_fg = True
        self.mario_running = True

        # Frame counter & timers
        self.tick = 0
        self.mario_anim_frame = 0
        self.goomba_x = 220.0
        self.goomba_frame = 0

        # Pre-construct World elements (Repeating horizontal loop width = 512 pixels)
        self.world_w = 512

        # Clouds: list of (x, y)
        self.clouds = [
            (24, 24), (160, 32), (280, 20), (410, 36)
        ]

        # Hills: list of (x, y)
        self.hills = [
            (16, 144), (170, 144), (320, 144), (460, 144)
        ]

        # Foreground scenery: pipes, question blocks, bricks, coins
        self.pipes = [
            (192, 128, 2),  # x=192, y=128, height in 16px blocks (2 blocks = 32px tall)
            (384, 112, 3),  # x=384, y=112, height in 16px blocks (3 blocks = 48px tall)
        ]

        self.blocks = [
            # (x, y, type: 'q' or 'b', has_coin)
            (80, 96, 'q', True),
            (96, 96, 'b', False),
            (112, 96, 'q', True),
            (128, 96, 'b', False),
            (272, 96, 'b', False),
            (288, 96, 'q', True),
            (304, 96, 'b', False),
        ]

    def update(self):
        """Advances physics, parallax offsets, and actor animation cycles."""
        if self.paused:
            return

        effective_speed = self.speed_mult * self.direction
        self.scroll_bg = (self.scroll_bg + 0.5 * effective_speed) % self.world_w
        self.scroll_mid = (self.scroll_mid + 1.0 * effective_speed) % self.world_w
        self.scroll_fg = (self.scroll_fg + 2.5 * effective_speed) % self.world_w

        self.tick += 1

        # Mario animation: 3 frames cycling every 5 ticks (12 FPS at 60 Hz)
        if self.mario_running:
            if self.tick % 5 == 0:
                self.mario_anim_frame = (self.mario_anim_frame + 1) % 4
        else:
            self.mario_anim_frame = 1  # Standing frame

        # Goomba walking waddle: scrolls with foreground (2.5) + walks forward (0.6) = 3.1 px/frame
        self.goomba_x -= (3.1 * effective_speed)
        if self.goomba_x < -20:
            self.goomba_x = self.base_w + 30
        elif self.goomba_x > self.base_w + 50:
            self.goomba_x = -10

        if self.tick % 8 == 0:
            self.goomba_frame = 1 - self.goomba_frame

    def render(self):
        """Draws all depth layers onto the 256x192 canvas with sub-pixel precision."""
        # 1. Sky Plane
        self.canvas.fill(SKY_BLUE)

        # 2. Far Background Plane: Puffy Clouds (0.5 px/frame)
        if self.show_bg:
            for cx_orig, cy in self.clouds:
                # Calculate wrapped screen position
                cx = (cx_orig - int(self.scroll_bg)) % self.world_w
                if cx > self.base_w:
                    cx -= self.world_w
                # Draw 32x16 cloud (cloud_l + cloud_r)
                if -32 <= cx <= self.base_w:
                    self.canvas.blit(self.surfaces["cloud_l"], (cx, cy))
                    self.canvas.blit(self.surfaces["cloud_r"], (cx + 16, cy))

        # 3. Mid-Ground Plane: Rolling Green Hills (1.0 px/frame)
        if self.show_mid:
            for hx_orig, hy in self.hills:
                hx = (hx_orig - int(self.scroll_mid)) % self.world_w
                if hx > self.base_w:
                    hx -= self.world_w
                if -24 <= hx <= self.base_w:
                    self.canvas.blit(self.surfaces["hill"], (hx, hy))
                    # Little side bushes on the hill
                    self.canvas.blit(self.surfaces["hill"], (hx + 12, hy + 4))

        # 4. Foreground Plane: Scenery Blocks, Pipes, Coins (2.5 px/frame)
        if self.show_fg:
            # Floating Blocks & Coins
            coin_pulsing = (self.tick // 10) % 2 == 0
            coin_surf = self.surfaces["coin"] if coin_pulsing else self.surfaces["coin_narrow"]

            for bx_orig, by, btype, has_coin in self.blocks:
                bx = (bx_orig - int(self.scroll_fg)) % self.world_w
                if bx > self.base_w:
                    bx -= self.world_w
                if -16 <= bx <= self.base_w:
                    b_surf = self.surfaces["qblock"] if btype == 'q' else self.surfaces["brick"]
                    self.canvas.blit(b_surf, (bx, by))
                    if has_coin:
                        self.canvas.blit(coin_surf, (bx, by - 18))

            # Warp Pipes
            for px_orig, py_top, num_blocks in self.pipes:
                px = (px_orig - int(self.scroll_fg)) % self.world_w
                if px > self.base_w:
                    px -= self.world_w
                if -32 <= px <= self.base_w:
                    # Pipe Rim (top)
                    self.canvas.blit(self.surfaces["pipe_tl"], (px, py_top))
                    self.canvas.blit(self.surfaces["pipe_tr"], (px + 16, py_top))
                    # Pipe Body (middle/bottom)
                    for b_row in range(1, num_blocks):
                        by = py_top + b_row * 16
                        self.canvas.blit(self.surfaces["pipe_bl"], (px, by))
                        self.canvas.blit(self.surfaces["pipe_br"], (px + 16, by))

            # Continuous Ground Blocks (Y=160 and Y=176)
            # Offset within a single 16px tile
            ground_tile_off = int(self.scroll_fg) % 16
            for col in range(18):
                gx = col * 16 - ground_tile_off
                self.canvas.blit(self.surfaces["ground"], (gx, 160))
                self.canvas.blit(self.surfaces["ground"], (gx, 176))

        # 5. Actors: Goomba & Mario
        # Goomba walking along the ground
        g_surf = self.surfaces["goomba1"] if self.goomba_frame == 0 else self.surfaces["goomba2"]
        if -16 <= self.goomba_x <= self.base_w:
            self.canvas.blit(g_surf, (int(self.goomba_x), 144))

        # Mario running at fixed screen position X=68, Y=144
        m_frame_idx = self.mario_anim_frame
        if m_frame_idx == 3:
            m_frame_idx = 1  # 0, 1, 2, 1 cycle
        m_surf = self.surfaces[f"mario{m_frame_idx}"]
        self.canvas.blit(m_surf, (68, 144))

        # 6. Classic Super Mario Bros HUD (World 1-1)
        font = getattr(self, 'hud_font', None)
        if font is None:
            self.hud_font = pygame.font.Font(None, 14)
            font = self.hud_font
        hud_line1 = font.render("MARIO   WORLD  TIME", True, WHITE)
        hud_score = f"{int(self.tick * 10) % 999990:06d}"
        hud_time = f"{max(0, 400 - int(self.tick / 60)):03d}"
        hud_line2 = font.render(f"{hud_score}   1-1   {hud_time}", True, WHITE)
        self.canvas.blit(hud_line1, (16, 6))
        self.canvas.blit(hud_line2, (16, 18))

        # Coin icon in HUD
        self.canvas.blit(self.surfaces["coin"], (88, 17))
        coin_txt = font.render("x14", True, WHITE)
        self.canvas.blit(coin_txt, (106, 18))

        # 7. Parallax Statistics & Control Info Bar (Bottom Banner)
        status_bar = pygame.Surface((self.base_w, 14))
        status_bar.fill((20, 20, 30))
        status_font = getattr(self, 'status_font', None)
        if status_font is None:
            self.status_font = pygame.font.Font(None, 12)
            status_font = self.status_font
        status_str = f"BG: 0.5px/f | MID: 1.0px/f | FG: 2.5px/f | SPD: {self.speed_mult:.1f}x"
        if self.paused:
            status_str += " [PAUSED]"
        txt = status_font.render(status_str, True, (255, 230, 100))
        status_bar.blit(txt, (4, 1))
        self.canvas.blit(status_bar, (0, 178))

        # Upscale to display window
        pygame.transform.scale(self.canvas, (self.base_w * self.scale, self.base_h * self.scale), self.screen)
        if not self.headless:
            pygame.display.flip()

    def handle_input(self):
        """Processes keyboard input for interactive real-time control."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    return False
                elif event.key == pygame.K_SPACE:
                    self.paused = not self.paused
                elif event.key == pygame.K_UP:
                    self.speed_mult = min(5.0, round(self.speed_mult + 0.5, 1))
                elif event.key == pygame.K_DOWN:
                    self.speed_mult = max(0.5, round(self.speed_mult - 0.5, 1))
                elif event.key == pygame.K_r:
                    self.direction = -self.direction
                elif event.key == pygame.K_1:
                    self.show_bg = not self.show_bg
                elif event.key == pygame.K_2:
                    self.show_mid = not self.show_mid
                elif event.key == pygame.K_3:
                    self.show_fg = not self.show_fg
                elif event.key == pygame.K_m:
                    self.mario_running = not self.mario_running
        return True

    def run(self, max_frames=None, output_path=None):
        """Executes the main 60 FPS demo loop."""
        frame_count = 0
        running = True
        t_start = time.time()

        while running:
            if not self.headless:
                running = self.handle_input()
            self.update()
            self.render()
            frame_count += 1

            if max_frames and frame_count >= max_frames:
                break

            if not self.headless:
                self.clock.tick(self.target_fps)

        t_elapsed = time.time() - t_start
        fps = frame_count / t_elapsed if t_elapsed > 0 else 0
        print(f"Rendered {frame_count} frames in {t_elapsed:.2f}s ({fps:.1f} FPS)")

        if output_path:
            out_dir = os.path.dirname(os.path.abspath(output_path))
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            pygame.image.save(self.screen, output_path)
            print(f"Saved verified screenshot to {output_path}")

        pygame.quit()
        return fps


def main():
    parser = argparse.ArgumentParser(description="Super Mario Bros Smooth Parallax Scrolling Demo")
    parser.add_argument("--headless", action="store_true", help="Run without graphical display window")
    parser.add_argument("--frames", type=int, default=120, help="Number of frames to simulate in headless mode")
    parser.add_argument("--output", type=str, default="mario_scroller_verified.png", help="Path to save screenshot")
    parser.add_argument("--scale", type=int, default=3, help="Window display scale factor (default: 3x -> 768x576)")
    parser.add_argument("--fps", type=int, default=60, help="Target frames per second (default: 60)")

    args = parser.parse_args()

    demo = MarioParallaxDemo(
        headless=args.headless,
        scale=args.scale,
        target_fps=args.fps
    )

    demo.run(
        max_frames=args.frames if args.headless else None,
        output_path=args.output
    )


if __name__ == "__main__":
    main()
