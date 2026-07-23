"""
AC's Pong — PC Port 0.1
Famicom graphics · Famicom speed · 60 FPS
"""

import sys
import math
import random
import pygame

# ---------------------------------------------------------------------------
# Constants — Famicom feel at 60 FPS
# ---------------------------------------------------------------------------
VERSION = "0.1"
TITLE = "AC's Pong PC Port 0.1"

# Internal Famicom-like resolution (scaled up for modern displays)
INTERNAL_W, INTERNAL_H = 256, 240
SCALE = 3
SCREEN_W, SCREEN_H = INTERNAL_W * SCALE, INTERNAL_H * SCALE
FPS = 60

# NES / Famicom palette (approx)
COL_BG = (15, 15, 35)          # deep navy
COL_BG2 = (20, 20, 50)         # slightly lighter navy (scan bands)
COL_WHITE = (236, 236, 236)    # soft white
COL_GRAY = (140, 140, 160)
COL_DIM = (80, 80, 110)
COL_PADDLE = (220, 220, 230)
COL_BALL = (255, 255, 255)
COL_ACCENT = (228, 60, 60)     # Famicom red
COL_GREEN = (76, 200, 100)
COL_YELLOW = (240, 200, 60)
COL_CYAN = (100, 200, 220)
COL_BORDER = (50, 50, 90)

# Famicom-style speeds (pixels per frame at 60 FPS, in internal coords)
PADDLE_SPEED = 2.4
BALL_SPEED_BASE = 2.0
BALL_SPEED_MAX = 4.2
BALL_SPEED_SPIN = 0.12
AI_SPEED = 1.85
AI_REACTION = 0.72  # how tightly AI tracks the ball (less = more human)

PADDLE_W, PADDLE_H = 4, 28
BALL_SIZE = 4
PADDLE_MARGIN = 16
SCORE_TO_WIN = 5

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def draw_text(surf, text, font, color, x, y, center=False, shadow=False):
    img = font.render(text, False, color)
    r = img.get_rect()
    if center:
        r.center = (x, y)
    else:
        r.topleft = (x, y)
    if shadow:
        sh = font.render(text, False, (0, 0, 0))
        sr = sh.get_rect()
        if center:
            sr.center = (x + 1, y + 1)
        else:
            sr.topleft = (x + 1, y + 1)
        surf.blit(sh, sr)
    surf.blit(img, r)
    return r


def draw_rect_pixel(surf, color, rect, border=0):
    pygame.draw.rect(surf, color, rect, border)


def famicon_bg(surf, frame=0):
    """Subtle scanline / tile background like old CRT Famicom."""
    surf.fill(COL_BG)
    for y in range(0, INTERNAL_H, 2):
        pygame.draw.line(surf, COL_BG2, (0, y), (INTERNAL_W, y))
    # soft vignette corners via dim border
    pygame.draw.rect(surf, COL_BORDER, (0, 0, INTERNAL_W, INTERNAL_H), 1)


# ---------------------------------------------------------------------------
# Button
# ---------------------------------------------------------------------------

class Button:
    def __init__(self, x, y, w, h, label, font):
        self.rect = pygame.Rect(x, y, w, h)
        self.label = label
        self.font = font
        self.hover = False
        self.pressed = False

    def update(self, mouse_pos, mouse_down):
        # mouse in screen space → convert later; we receive internal coords
        self.hover = self.rect.collidepoint(mouse_pos)
        clicked = False
        if self.hover and mouse_down:
            self.pressed = True
        elif self.pressed and not mouse_down:
            self.pressed = False
            if self.hover:
                clicked = True
        if not mouse_down:
            self.pressed = False
        return clicked

    def draw(self, surf):
        if self.pressed:
            fill, border, text_c = COL_ACCENT, COL_WHITE, COL_WHITE
            oy = 1
        elif self.hover:
            fill, border, text_c = (40, 40, 80), COL_CYAN, COL_CYAN
            oy = 0
        else:
            fill, border, text_c = (25, 25, 55), COL_GRAY, COL_WHITE
            oy = 0
        r = self.rect.move(0, oy)
        draw_rect_pixel(surf, fill, r)
        draw_rect_pixel(surf, border, r, 1)
        # pixel corner ticks
        for dx, dy in ((0, 0), (r.w - 1, 0), (0, r.h - 1), (r.w - 1, r.h - 1)):
            surf.set_at((r.x + dx, r.y + dy), COL_WHITE)
        draw_text(surf, self.label, self.font, text_c, r.centerx, r.centery, center=True)


# ---------------------------------------------------------------------------
# Game objects
# ---------------------------------------------------------------------------

class Paddle:
    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
        self.w = PADDLE_W
        self.h = PADDLE_H
        self.dy = 0.0

    @property
    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.w, self.h)

    def move(self, dy):
        self.y = clamp(self.y + dy, 4, INTERNAL_H - self.h - 4)

    def draw(self, surf, color=COL_PADDLE):
        r = self.rect
        draw_rect_pixel(surf, color, r)
        # highlight strip (Famicom-ish depth)
        pygame.draw.line(surf, COL_WHITE, (r.x, r.y), (r.x, r.bottom - 1))


class Ball:
    def __init__(self):
        self.reset(direction=1)

    def reset(self, direction=None):
        self.x = INTERNAL_W / 2 - BALL_SIZE / 2
        self.y = INTERNAL_H / 2 - BALL_SIZE / 2
        if direction is None:
            direction = random.choice([-1, 1])
        angle = random.uniform(-0.45, 0.45)
        speed = BALL_SPEED_BASE
        self.vx = direction * speed * math.cos(angle)
        self.vy = speed * math.sin(angle)
        if abs(self.vy) < 0.4:
            self.vy = 0.4 * random.choice([-1, 1])

    @property
    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), BALL_SIZE, BALL_SIZE)

    def speed(self):
        return math.hypot(self.vx, self.vy)

    def draw(self, surf):
        r = self.rect
        draw_rect_pixel(surf, COL_BALL, r)
        # tiny shine pixel
        if r.w > 1 and r.h > 1:
            surf.set_at((r.x, r.y), COL_CYAN)


# ---------------------------------------------------------------------------
# Screens / states
# ---------------------------------------------------------------------------

STATE_MENU = "menu"
STATE_PLAY = "play"
STATE_PAUSE = "pause"
STATE_WIN = "win"


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(TITLE)
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self.clock = pygame.time.Clock()
        self.canvas = pygame.Surface((INTERNAL_W, INTERNAL_H))
        self.running = True
        self.state = STATE_MENU
        self.frame = 0

        # Pixel fonts (pygame default scaled = chunky)
        self.font_sm = pygame.font.Font(None, 14)
        self.font_md = pygame.font.Font(None, 18)
        self.font_lg = pygame.font.Font(None, 28)
        self.font_xl = pygame.font.Font(None, 36)
        self.font_title = pygame.font.Font(None, 32)

        # Menu buttons (centered)
        bw, bh = 100, 16
        cx = INTERNAL_W // 2 - bw // 2
        self.btn_play = Button(cx, 148, bw, bh, "PLAY GAME", self.font_sm)
        self.btn_exit = Button(cx, 172, bw, bh, "EXIT GAME", self.font_sm)

        self.btn_again = Button(cx, 168, bw, bh, "PLAY AGAIN", self.font_sm)
        self.btn_menu = Button(cx, 190, bw, bh, "MAIN MENU", self.font_sm)

        self.reset_match()
        self.mouse_down_edge = False  # click edge detect
        self.prev_mouse = False

        # Simple blip sounds via pygame.sndarray if available — skip if no mixer
        self._init_audio()

    def _init_audio(self):
        self.sfx = {}
        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=256)
            self.sfx["hit"] = self._tone(440, 0.04)
            self.sfx["wall"] = self._tone(220, 0.03)
            self.sfx["score"] = self._tone(330, 0.08)
            self.sfx["win"] = self._tone(523, 0.15)
            self.sfx["click"] = self._tone(660, 0.03)
            self.audio_ok = True
        except Exception:
            self.audio_ok = False

    def _tone(self, freq, duration):
        import array
        sample_rate = 22050
        n = int(sample_rate * duration)
        buf = array.array("h")
        for i in range(n):
            # square wave (Famicom-ish)
            t = i / sample_rate
            val = 8000 if math.sin(2 * math.pi * freq * t) > 0 else -8000
            env = 1.0 - (i / n)
            buf.append(int(val * env))
        return pygame.mixer.Sound(buffer=buf)

    def play_sfx(self, name):
        if self.audio_ok and name in self.sfx:
            self.sfx[name].play()

    def reset_match(self):
        self.left = Paddle(PADDLE_MARGIN, INTERNAL_H // 2 - PADDLE_H // 2)
        self.right = Paddle(INTERNAL_W - PADDLE_MARGIN - PADDLE_W,
                            INTERNAL_H // 2 - PADDLE_H // 2)
        self.ball = Ball()
        self.score_l = 0
        self.score_r = 0
        self.serve_timer = 60  # 1 second at 60 FPS
        self.winner = None
        self.serve_dir = random.choice([-1, 1])

    def screen_to_internal(self, pos):
        mx, my = pos
        return (mx // SCALE, my // SCALE)

    # ---- input ----
    def handle_events(self):
        mouse = pygame.mouse.get_pressed()[0]
        self.mouse_down_edge = mouse and not self.prev_mouse
        self.prev_mouse = mouse

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    if self.state == STATE_PLAY:
                        self.state = STATE_PAUSE
                    elif self.state == STATE_PAUSE:
                        self.state = STATE_PLAY
                    elif self.state == STATE_MENU:
                        self.running = False
                    elif self.state == STATE_WIN:
                        self.state = STATE_MENU
                elif e.key == pygame.K_RETURN or e.key == pygame.K_SPACE:
                    if self.state == STATE_MENU:
                        self.play_sfx("click")
                        self.reset_match()
                        self.state = STATE_PLAY
                    elif self.state == STATE_PAUSE:
                        self.state = STATE_PLAY
                    elif self.state == STATE_WIN:
                        # Y / Enter / Space = restart
                        self.play_sfx("click")
                        self.reset_match()
                        self.state = STATE_PLAY
                elif e.key == pygame.K_y:
                    if self.state == STATE_WIN:
                        self.play_sfx("click")
                        self.reset_match()
                        self.state = STATE_PLAY
                elif e.key == pygame.K_n:
                    if self.state == STATE_WIN:
                        self.play_sfx("click")
                        self.state = STATE_MENU
                elif e.key == pygame.K_p and self.state == STATE_PLAY:
                    self.state = STATE_PAUSE

    # ---- update ----
    def update_menu(self):
        mpos = self.screen_to_internal(pygame.mouse.get_pos())
        # use held state for Button; fire on release inside
        mouse = pygame.mouse.get_pressed()[0]
        if self.btn_play.update(mpos, mouse):
            self.play_sfx("click")
            self.reset_match()
            self.state = STATE_PLAY
        if self.btn_exit.update(mpos, mouse):
            self.play_sfx("click")
            self.running = False

    def update_play(self):
        keys = pygame.key.get_pressed()

        # Player (left paddle) — W/S or Up/Down
        dy = 0.0
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            dy -= PADDLE_SPEED
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            dy += PADDLE_SPEED
        self.left.move(dy)

        # AI (right paddle) — Famicom-style imperfect tracking
        if self.serve_timer <= 0:
            target = self.ball.y + BALL_SIZE / 2
            center = self.right.y + self.right.h / 2
            # slight delay / deadzone so AI is beatable
            if abs(target - center) > 3:
                if target > center:
                    self.right.move(AI_SPEED * AI_REACTION)
                else:
                    self.right.move(-AI_SPEED * AI_REACTION)

        if self.serve_timer > 0:
            self.serve_timer -= 1
            # hold ball center until serve
            self.ball.x = INTERNAL_W / 2 - BALL_SIZE / 2
            self.ball.y = INTERNAL_H / 2 - BALL_SIZE / 2
            if self.serve_timer == 0:
                self.ball.reset(direction=self.serve_dir)
            return

        # Move ball
        self.ball.x += self.ball.vx
        self.ball.y += self.ball.vy

        # Wall bounce
        if self.ball.y <= 2:
            self.ball.y = 2
            self.ball.vy = abs(self.ball.vy)
            self.play_sfx("wall")
        elif self.ball.y + BALL_SIZE >= INTERNAL_H - 2:
            self.ball.y = INTERNAL_H - 2 - BALL_SIZE
            self.ball.vy = -abs(self.ball.vy)
            self.play_sfx("wall")

        # Paddle collisions
        br = self.ball.rect
        if br.colliderect(self.left.rect) and self.ball.vx < 0:
            self._bounce_paddle(self.left, side=1)
        elif br.colliderect(self.right.rect) and self.ball.vx > 0:
            self._bounce_paddle(self.right, side=-1)

        # Score
        if self.ball.x + BALL_SIZE < 0:
            self.score_r += 1
            self.play_sfx("score")
            self._after_score(direction=1)
        elif self.ball.x > INTERNAL_W:
            self.score_l += 1
            self.play_sfx("score")
            self._after_score(direction=-1)

    def _bounce_paddle(self, paddle, side):
        # Reflect X and add spin from hit position
        offset = (self.ball.y + BALL_SIZE / 2) - (paddle.y + paddle.h / 2)
        norm = offset / (paddle.h / 2)  # -1 .. 1
        speed = min(self.ball.speed() + BALL_SPEED_SPIN * 4, BALL_SPEED_MAX)
        self.ball.vx = side * abs(speed * math.cos(norm * 0.7))
        self.ball.vy = speed * math.sin(norm * 0.85)
        if abs(self.ball.vy) < 0.35:
            self.ball.vy = 0.35 * (1 if norm >= 0 else -1)
        # nudge out of paddle
        if side > 0:
            self.ball.x = paddle.x + paddle.w
        else:
            self.ball.x = paddle.x - BALL_SIZE
        self.play_sfx("hit")

    def _after_score(self, direction):
        if self.score_l >= SCORE_TO_WIN or self.score_r >= SCORE_TO_WIN:
            self.winner = "YOU" if self.score_l >= SCORE_TO_WIN else "CPU"
            self.play_sfx("win")
            self.state = STATE_WIN
            return
        self.serve_dir = direction
        self.serve_timer = 45
        self.ball.reset(direction=direction)
        self.ball.vx = 0
        self.ball.vy = 0

    def update_win(self):
        mpos = self.screen_to_internal(pygame.mouse.get_pos())
        mouse = pygame.mouse.get_pressed()[0]
        if self.btn_again.update(mpos, mouse):
            self.play_sfx("click")
            self.reset_match()
            self.state = STATE_PLAY
        if self.btn_menu.update(mpos, mouse):
            self.play_sfx("click")
            self.state = STATE_MENU

    def update_pause(self):
        keys = pygame.key.get_pressed()
        # click anywhere or space handled in events
        pass

    # ---- draw ----
    def draw_center_line(self):
        # dashed net
        dash_h = 6
        gap = 4
        x = INTERNAL_W // 2
        y = 4
        while y < INTERNAL_H - 4:
            pygame.draw.rect(self.canvas, COL_DIM, (x - 1, y, 2, dash_h))
            y += dash_h + gap

    def draw_menu(self):
        famicon_bg(self.canvas, self.frame)

        # decorative top bar
        pygame.draw.rect(self.canvas, COL_ACCENT, (0, 0, INTERNAL_W, 3))
        pygame.draw.rect(self.canvas, COL_ACCENT, (0, INTERNAL_H - 3, INTERNAL_W, 3))

        # Title block — centered
        cy = 70
        # blink-ish subtitle line
        draw_text(self.canvas, "AC'S!PONG", self.font_xl, COL_WHITE,
                  INTERNAL_W // 2, cy, center=True, shadow=True)
        draw_text(self.canvas, "PC PORT", self.font_lg, COL_CYAN,
                  INTERNAL_W // 2, cy + 22, center=True, shadow=True)
        draw_text(self.canvas, "60 FPS  ·  PC PORT", self.font_md, COL_YELLOW,
                  INTERNAL_W // 2, cy + 40, center=True)

        # version / style tags
        draw_text(self.canvas, f"v{VERSION}  FAMICON GRAPHICS  FAMICON SPEED",
                  self.font_sm, COL_GRAY, INTERNAL_W // 2, cy + 56, center=True)

        # pixel art ball decoration
        for i, ox in enumerate((-40, 40)):
            bx = INTERNAL_W // 2 + ox
            by = cy - 28
            pygame.draw.rect(self.canvas, COL_BALL, (bx, by, 4, 4))

        # buttons
        self.btn_play.draw(self.canvas)
        self.btn_exit.draw(self.canvas)

        # controls hint
        draw_text(self.canvas, "W/S or ARROWS  ·  ESC menu  ·  P pause",
                  self.font_sm, COL_DIM, INTERNAL_W // 2, INTERNAL_H - 20, center=True)

        # flashing press start
        if (self.frame // 30) % 2 == 0:
            draw_text(self.canvas, "— SELECT —", self.font_sm, COL_GREEN,
                      INTERNAL_W // 2, 132, center=True)

    def draw_play(self, paused=False):
        famicon_bg(self.canvas, self.frame)
        self.draw_center_line()

        # scores
        draw_text(self.canvas, str(self.score_l), self.font_lg, COL_WHITE,
                  INTERNAL_W // 2 - 30, 12, center=True)
        draw_text(self.canvas, str(self.score_r), self.font_lg, COL_WHITE,
                  INTERNAL_W // 2 + 30, 12, center=True)

        # labels
        draw_text(self.canvas, "YOU", self.font_sm, COL_CYAN, 20, 8)
        draw_text(self.canvas, "CPU", self.font_sm, COL_ACCENT, INTERNAL_W - 36, 8)

        self.left.draw(self.canvas, COL_CYAN)
        self.right.draw(self.canvas, COL_ACCENT)
        if self.serve_timer <= 0 or (self.frame // 8) % 2 == 0:
            self.ball.draw(self.canvas)

        # serve countdown
        if self.serve_timer > 0 and not paused:
            n = max(1, (self.serve_timer + 19) // 20)
            draw_text(self.canvas, str(n) if self.serve_timer > 15 else "GO!",
                      self.font_lg, COL_YELLOW, INTERNAL_W // 2, INTERNAL_H // 2 - 20,
                      center=True, shadow=True)

        # footer
        draw_text(self.canvas, "AC'S PONG  PC PORT  60FPS", self.font_sm, COL_DIM,
                  INTERNAL_W // 2, INTERNAL_H - 12, center=True)

        if paused:
            # dim overlay
            overlay = pygame.Surface((INTERNAL_W, INTERNAL_H), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 140))
            self.canvas.blit(overlay, (0, 0))
            draw_text(self.canvas, "PAUSED", self.font_xl, COL_WHITE,
                      INTERNAL_W // 2, INTERNAL_H // 2 - 10, center=True, shadow=True)
            draw_text(self.canvas, "ESC / ENTER to resume", self.font_sm, COL_GRAY,
                      INTERNAL_W // 2, INTERNAL_H // 2 + 16, center=True)

    def draw_win(self):
        famicon_bg(self.canvas, self.frame)
        pygame.draw.rect(self.canvas, COL_ACCENT, (0, 0, INTERNAL_W, 3))
        pygame.draw.rect(self.canvas, COL_ACCENT, (0, INTERNAL_H - 3, INTERNAL_W, 3))

        # GAME OVER banner
        draw_text(self.canvas, "GAME OVER", self.font_xl, COL_ACCENT,
                  INTERNAL_W // 2, 55, center=True, shadow=True)

        msg = "YOU WIN!" if self.winner == "YOU" else "CPU WINS!"
        color = COL_GREEN if self.winner == "YOU" else COL_YELLOW
        draw_text(self.canvas, msg, self.font_lg, color,
                  INTERNAL_W // 2, 82, center=True, shadow=True)
        draw_text(self.canvas, f"{self.score_l}  -  {self.score_r}", self.font_lg, COL_WHITE,
                  INTERNAL_W // 2, 104, center=True)

        # Y/N restart prompt (blink)
        if (self.frame // 30) % 2 == 0:
            draw_text(self.canvas, "RESTART?  Y / N", self.font_md, COL_YELLOW,
                      INTERNAL_W // 2, 130, center=True, shadow=True)
        else:
            draw_text(self.canvas, "RESTART?  Y / N", self.font_md, COL_WHITE,
                      INTERNAL_W // 2, 130, center=True, shadow=True)

        draw_text(self.canvas, "Y = PLAY AGAIN   N = MAIN MENU", self.font_sm, COL_GRAY,
                  INTERNAL_W // 2, 148, center=True)

        self.btn_again.draw(self.canvas)
        self.btn_menu.draw(self.canvas)

    def present(self):
        # nearest-neighbor scale for crisp Famicom pixels
        scaled = pygame.transform.scale(self.canvas, (SCREEN_W, SCREEN_H))
        self.screen.blit(scaled, (0, 0))
        pygame.display.flip()

    def run(self):
        while self.running:
            self.handle_events()

            if self.state == STATE_MENU:
                self.update_menu()
                self.draw_menu()
            elif self.state == STATE_PLAY:
                self.update_play()
                self.draw_play(paused=False)
            elif self.state == STATE_PAUSE:
                self.draw_play(paused=True)
            elif self.state == STATE_WIN:
                self.update_win()
                self.draw_win()

            self.present()
            self.frame += 1
            self.clock.tick(FPS)

        pygame.quit()
        sys.exit(0)


def main():
    Game().run()


if __name__ == "__main__":
    main()
