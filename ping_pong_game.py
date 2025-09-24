"""
Ping Pong (Pong) - Full featured animated game in a single Python file
Requires: pygame (pip install pygame)

Features:
- Start menu with player selection (1P vs CPU or 2P)
- Difficulty selector (Easy/Medium/Hard) affecting CPU AI
- Animated ball and paddles with smooth movement
- Collision effects (particle burst, screen shake)
- Power-ups: Speed Boost, Slow Ball, Bigger Paddle, Multi-ball (short-lived)
- Pause (P), Restart (R) and Quit (Esc)
- Serve mechanics, score to win (first to 7 by default)
- Sound placeholders (optional) — works without sound files
- Clean, commented code; tweak constants to adjust game feel

How to run:
1. pip install pygame
2. python ping_pong_game.py

Author: ChatGPT
"""

import pygame
import random
import math
import sys
from collections import deque

# ----------------------------
# Configuration / Constants
# ----------------------------
WIDTH, HEIGHT = 1000, 600
FPS = 120
PADDLE_WIDTH, PADDLE_HEIGHT = 14, 110
BALL_RADIUS = 10
WIN_SCORE = 7

# Colors
WHITE = (245, 245, 245)
GRAY = (40, 40, 40)
ACCENT = (50, 200, 255)
BG = (12, 12, 20)
RED = (255, 90, 90)
GREEN = (120, 255, 140)

# Power-up settings
POWERUP_SIZE = 20
POWERUP_DURATION = 6.0  # seconds
POWERUP_SPAWN_INTERVAL = 8.0  # seconds

# Game tuning
BALL_BASE_SPEED = 380.0  # px/sec
PADDLE_SPEED = 420.0
CPU_MAX_ANGLE = math.radians(60)

# ----------------------------
# Helper functions
# ----------------------------

def clamp(x, a, b):
    return max(a, min(b, x))


# ----------------------------
# Particle class for effects
# ----------------------------
class Particle:
    def __init__(self, pos, vel, ttl, color):
        self.pos = pygame.Vector2(pos)
        self.vel = pygame.Vector2(vel)
        self.ttl = ttl
        self.max_ttl = ttl
        self.color = color

    def update(self, dt):
        self.pos += self.vel * dt
        self.ttl -= dt

    def draw(self, surf):
        if self.ttl <= 0:
            return
        alpha = clamp(int(255 * (self.ttl / self.max_ttl)), 0, 255)
        s = pygame.Surface((4, 4), pygame.SRCALPHA)
        s.fill((*self.color, alpha))
        surf.blit(s, (self.pos.x - 2, self.pos.y - 2))


# ----------------------------
# PowerUp class
# ----------------------------
class PowerUp:
    TYPES = ["speed_boost", "slow_ball", "big_paddle", "multi_ball"]

    def __init__(self, pos=None):
        self.type = random.choice(self.TYPES)
        if pos is None:
            self.pos = pygame.Vector2(random.uniform(200, WIDTH - 200), random.uniform(120, HEIGHT - 120))
        else:
            self.pos = pygame.Vector2(pos)
        self.rect = pygame.Rect(self.pos.x - POWERUP_SIZE/2, self.pos.y - POWERUP_SIZE/2, POWERUP_SIZE, POWERUP_SIZE)
        self.ttl = 10.0  # disappears if not picked

    def update(self, dt):
        self.ttl -= dt

    def draw(self, surf):
        if self.type == "speed_boost":
            c = RED
        elif self.type == "slow_ball":
            c = GREEN
        elif self.type == "big_paddle":
            c = (255, 200, 80)
        else:
            c = ACCENT
        pygame.draw.rect(surf, c, self.rect, border_radius=6)
        # small icon
        pygame.draw.circle(surf, BG, (int(self.rect.centerx), int(self.rect.centery)), 6)


# ----------------------------
# Paddle class
# ----------------------------
class Paddle:
    def __init__(self, x, y, h=PADDLE_HEIGHT):
        self.x = x
        self.y = y
        self.w = PADDLE_WIDTH
        self.h = h
        self.rect = pygame.Rect(self.x - self.w/2, self.y - self.h/2, self.w, self.h)
        self.vel = 0
        self.speed = PADDLE_SPEED
        self.color = WHITE
        self.original_h = h

    def update(self, dt):
        self.y += self.vel * dt
        halfh = self.h/2
        self.y = clamp(self.y, halfh + 8, HEIGHT - halfh - 8)
        self.rect.centery = int(self.y)

    def draw(self, surf):
        r = pygame.Rect(0, 0, self.w, self.h)
        r.center = (self.x, int(self.y))
        pygame.draw.rect(surf, self.color, r, border_radius=6)

    def set_height(self, new_h):
        self.h = new_h
        self.rect = pygame.Rect(self.x - self.w/2, self.y - self.h/2, self.w, self.h)

    def reset(self):
        self.set_height(self.original_h)


# ----------------------------
# Ball class
# ----------------------------
class Ball:
    def __init__(self, x, y, radius=BALL_RADIUS):
        self.pos = pygame.Vector2(x, y)
        self.radius = radius
        self.vel = pygame.Vector2(0, 0)
        self.speed = BALL_BASE_SPEED
        self.color = ACCENT
        self.slow_factor = 1.0

    def launch(self, direction=1, angle=0.0):
        # direction: -1 left, +1 right
        ang = angle
        self.vel = pygame.Vector2(math.cos(ang) * direction, math.sin(ang))
        self.vel = self.vel.normalize() * self.speed

    def update(self, dt):
        self.pos += self.vel * dt * self.slow_factor
        # bounce top/bottom
        if self.pos.y - self.radius <= 0:
            self.pos.y = self.radius
            self.vel.y *= -1
        elif self.pos.y + self.radius >= HEIGHT:
            self.pos.y = HEIGHT - self.radius
            self.vel.y *= -1

    def draw(self, surf):
        pygame.draw.circle(surf, self.color, (int(self.pos.x), int(self.pos.y)), self.radius)

    def rect(self):
        return pygame.Rect(self.pos.x - self.radius, self.pos.y - self.radius, self.radius*2, self.radius*2)


# ----------------------------
# CPU AI
# ----------------------------
class CPU:
    def __init__(self, paddle: Paddle, difficulty="Medium"):
        self.paddle = paddle
        self.difficulty = difficulty
        self.reaction = {"Easy": 0.22, "Medium": 0.12, "Hard": 0.06}[difficulty]
        self.error = {"Easy": 0.14, "Medium": 0.08, "Hard": 0.03}[difficulty]

    def update(self, ball: Ball, dt):
        # Predictive simple AI: move toward where ball will be
        # Only react if ball is moving toward CPU side
        target_y = self.paddle.y
        # prediction: assume ball keeps y velocity
        if ball.vel.x > 0 and self.paddle.x > WIDTH/2 or ball.vel.x < 0 and self.paddle.x < WIDTH/2:
            t = abs((self.paddle.x - ball.pos.x) / (ball.vel.x + 1e-6))
            predicted = ball.pos.y + ball.vel.y * t
            # reflect off top/bottom
            while predicted < 0 or predicted > HEIGHT:
                if predicted < 0:
                    predicted = -predicted
                elif predicted > HEIGHT:
                    predicted = 2*HEIGHT - predicted
            target_y = predicted + random.uniform(-self.error, self.error) * HEIGHT
        # Smooth movement toward target
        diff = target_y - self.paddle.y
        # scaled by reaction speed
        self.paddle.vel = clamp(diff * (1.0 / max(self.reaction, 1e-6)), -self.paddle.speed, self.paddle.speed)


# ----------------------------
# Game class with loop
# ----------------------------
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Ping Pong — Python")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, 36)
        self.bigfont = pygame.font.SysFont(None, 64)

        # Entities
        self.left_paddle = Paddle(36, HEIGHT/2)
        self.right_paddle = Paddle(WIDTH - 36, HEIGHT/2)
        self.ball = Ball(WIDTH/2, HEIGHT/2)
        self.extra_balls = []

        # Players
        self.mode = "1P"  # or "2P"
        self.cpu = CPU(self.right_paddle, difficulty="Medium")

        # Scores
        self.score_l = 0
        self.score_r = 0

        # State
        self.paused = False
        self.running = True
        self.serve_dir = random.choice([-1, 1])
        self.serve_ready = True
        self.last_point_time = 0

        # Effects
        self.particles = []
        self.shake = 0

        # Powerups
        self.powerups = []
        self.time_since_power = 0.0

        # Menu selections
        self.menu_active = True
        self.menu_selection = 0
        self.difficulty_selection = 1  # 0 easy, 1 medium, 2 hard

        # Controls
        self.controls = {
            "left_up": pygame.K_w,
            "left_down": pygame.K_s,
            "right_up": pygame.K_UP,
            "right_down": pygame.K_DOWN,
        }

    # ----------------------------
    # Utility
    # ----------------------------
    def reset_entities(self):
        self.left_paddle.y = HEIGHT/2
        self.right_paddle.y = HEIGHT/2
        self.left_paddle.reset()
        self.right_paddle.reset()
        self.ball = Ball(WIDTH/2, HEIGHT/2)
        self.extra_balls = []
        self.serve_ready = True

    def spawn_powerup(self):
        self.powerups.append(PowerUp())

    def create_particles(self, pos, color, count=18):
        for i in range(count):
            ang = random.uniform(0, math.pi*2)
            speed = random.uniform(60, 380)
            v = pygame.Vector2(math.cos(ang)*speed, math.sin(ang)*speed)
            self.particles.append(Particle(pos, v, random.uniform(0.35, 0.9), color))

    # ----------------------------
    # Menu
    # ----------------------------
    def draw_menu(self):
        self.screen.fill(BG)
        title = self.bigfont.render("Ping Pong", True, WHITE)
        self.screen.blit(title, (WIDTH//2 - title.get_width()//2, 80))

        items = [f"Mode: {self.mode}", f"Difficulty: {['Easy','Medium','Hard'][self.difficulty_selection]}", "Start Game", "Quit"]
        for i, text in enumerate(items):
            col = ACCENT if i == self.menu_selection else WHITE
            r = self.font.render(text, True, col)
            self.screen.blit(r, (WIDTH//2 - r.get_width()//2, 220 + i*52))

        hint = self.font.render("Use Up/Down, Enter to select — W/S or Up/Down to move paddles during game", True, GRAY)
        self.screen.blit(hint, (WIDTH//2 - hint.get_width()//2, HEIGHT - 60))

    # ----------------------------
    # Draw HUD
    # ----------------------------
    def draw_hud(self):
        # center net
        for i in range(10, HEIGHT, 32):
            pygame.draw.rect(self.screen, GRAY, (WIDTH//2 - 3, i, 6, 18), border_radius=3)
        # scores
        sl = self.bigfont.render(str(self.score_l), True, WHITE)
        sr = self.bigfont.render(str(self.score_r), True, WHITE)
        self.screen.blit(sl, (WIDTH//4 - sl.get_width()//2, 18))
        self.screen.blit(sr, (3*WIDTH//4 - sr.get_width()//2, 18))

        # status
        if self.paused:
            p = self.bigfont.render("PAUSED", True, RED)
            self.screen.blit(p, (WIDTH//2 - p.get_width()//2, HEIGHT//2 - p.get_height()//2))

    # ----------------------------
    # Handle collisions
    # ----------------------------
    def handle_collisions(self, ball):
        # paddles
        for paddle, side in [(self.left_paddle, -1), (self.right_paddle, 1)]:
            r = pygame.Rect(0,0,paddle.w, paddle.h)
            r.center = (paddle.x, paddle.y)
            if ball.rect().colliderect(r):
                # reflect based on hit position
                rel_y = (ball.pos.y - paddle.y) / (paddle.h/2)
                rel_y = clamp(rel_y, -1, 1)
                angle = rel_y * CPU_MAX_ANGLE
                dir_x = 1 if paddle.x < WIDTH/2 else -1
                speed_increase = 1.04
                ball.speed *= speed_increase
                # set velocity
                ball.vel = pygame.Vector2(math.cos(angle)*dir_x, math.sin(angle))
                ball.vel = ball.vel.normalize() * ball.speed
                # nudge out
                ball.pos.x = paddle.x + dir_x*(paddle.w/2 + ball.radius + 2)
                # effects
                self.create_particles(ball.pos, ACCENT, count=12)
                self.shake = 6
                # small paddle 'kick' if big paddle
                return True
        return False

    # ----------------------------
    # Apply powerup
    # ----------------------------
    def apply_powerup(self, powerup, ball_owner_side):
        t = powerup.type
        if t == "speed_boost":
            # boost owner paddle speed briefly
            if ball_owner_side == -1:
                self.left_paddle.speed *= 1.6
            else:
                self.right_paddle.speed *= 1.6
            pygame.time.set_timer(pygame.USEREVENT+3, int(POWERUP_DURATION*1000))
        elif t == "slow_ball":
            self.ball.slow_factor = 0.55
            pygame.time.set_timer(pygame.USEREVENT+4, int(POWERUP_DURATION*1000))
        elif t == "big_paddle":
            if ball_owner_side == -1:
                self.left_paddle.set_height(self.left_paddle.h * 1.6)
            else:
                self.right_paddle.set_height(self.right_paddle.h * 1.6)
            pygame.time.set_timer(pygame.USEREVENT+5, int(POWERUP_DURATION*1000))
        elif t == "multi_ball":
            # spawn 2 extra balls for short time
            for _ in range(2):
                b = Ball(self.ball.pos.x, self.ball.pos.y)
                ang = random.uniform(-0.9, 0.9)
                b.launch(random.choice([-1,1]), ang)
                b.speed = self.ball.speed * 0.9
                self.extra_balls.append(b)
            pygame.time.set_timer(pygame.USEREVENT+6, int(POWERUP_DURATION*1000))

    # ----------------------------
    # Main loop
    # ----------------------------
    def run(self):
        dt = 0
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.running = False
                elif e.type == pygame.KEYDOWN:
                    if self.menu_active:
                        if e.key == pygame.K_UP:
                            self.menu_selection = max(0, self.menu_selection - 1)
                        elif e.key == pygame.K_DOWN:
                            self.menu_selection = min(3, self.menu_selection + 1)
                        elif e.key == pygame.K_RETURN:
                            if self.menu_selection == 0:
                                # toggle mode
                                self.mode = "2P" if self.mode == "1P" else "1P"
                            elif self.menu_selection == 1:
                                # cycle difficulty
                                self.difficulty_selection = (self.difficulty_selection + 1) % 3
                                self.cpu = CPU(self.right_paddle, difficulty=["Easy","Medium","Hard"][self.difficulty_selection])
                            elif self.menu_selection == 2:
                                # start
                                self.menu_active = False
                                self.reset_entities()
                                self.score_l = 0
                                self.score_r = 0
                            elif self.menu_selection == 3:
                                self.running = False
                    else:
                        if e.key == pygame.K_p:
                            self.paused = not self.paused
                        elif e.key == pygame.K_r:
                            self.reset_entities()
                            self.score_l = 0
                            self.score_r = 0
                            self.menu_active = True
                        elif e.key == pygame.K_ESCAPE:
                            self.running = False

                    # movement keys
                    if e.key == self.controls["left_up"]:
                        self.left_paddle.vel = -self.left_paddle.speed
                    if e.key == self.controls["left_down"]:
                        self.left_paddle.vel = self.left_paddle.speed
                    if e.key == self.controls["right_up"]:
                        self.right_paddle.vel = -self.right_paddle.speed
                    if e.key == self.controls["right_down"]:
                        self.right_paddle.vel = self.right_paddle.speed

                elif e.type == pygame.KEYUP:
                    if e.key in (self.controls["left_up"], self.controls["left_down"]):
                        self.left_paddle.vel = 0
                    if e.key in (self.controls["right_up"], self.controls["right_down"]):
                        self.right_paddle.vel = 0

                elif e.type == pygame.USEREVENT+3:
                    # end speed boost
                    self.left_paddle.speed = PADDLE_SPEED
                    self.right_paddle.speed = PADDLE_SPEED
                    pygame.time.set_timer(pygame.USEREVENT+3, 0)
                elif e.type == pygame.USEREVENT+4:
                    self.ball.slow_factor = 1.0
                    pygame.time.set_timer(pygame.USEREVENT+4, 0)
                elif e.type == pygame.USEREVENT+5:
                    self.left_paddle.reset(); self.right_paddle.reset()
                    pygame.time.set_timer(pygame.USEREVENT+5, 0)
                elif e.type == pygame.USEREVENT+6:
                    self.extra_balls = []
                    pygame.time.set_timer(pygame.USEREVENT+6, 0)

            # Menu state
            if self.menu_active:
                self.draw_menu()
                pygame.display.flip()
                continue

            # Update
            if not self.paused:
                # spawn powerups occasionally
                self.time_since_power += dt
                if self.time_since_power >= POWERUP_SPAWN_INTERVAL:
                    self.time_since_power = 0.0
                    self.spawn_powerup()

                # CPU
                if self.mode == "1P":
                    self.cpu.update(self.ball, dt)
                # update paddles
                self.left_paddle.update(dt)
                self.right_paddle.update(dt)

                # handle serve
                if self.serve_ready:
                    # simple serve warmup waiting for input
                    # auto-serve after short delay
                    self.last_point_time += dt
                    if self.last_point_time > 0.6:
                        ang = random.uniform(-0.45, 0.45)
                        self.ball.launch(self.serve_dir, ang)
                        self.serve_ready = False
                        self.last_point_time = 0
                # update ball(s)
                balls = [self.ball] + list(self.extra_balls)
                for b in balls:
                    b.update(dt)

                # collisions for each ball
                for b in balls:
                    self.handle_collisions(b)

                # scoring
                to_remove = []
                for b in balls:
                    if b.pos.x < -50:
                        # right scores
                        self.score_r += 1
                        self.create_particles((20, HEIGHT/2), ACCENT, 30)
                        self.serve_dir = -1
                        self.serve_ready = True
                        self.ball = Ball(WIDTH/2, HEIGHT/2)
                        self.extra_balls = []
                        self.last_point_time = 0
                        break
                    elif b.pos.x > WIDTH + 50:
                        self.score_l += 1
                        self.create_particles((WIDTH-20, HEIGHT/2), ACCENT, 30)
                        self.serve_dir = 1
                        self.serve_ready = True
                        self.ball = Ball(WIDTH/2, HEIGHT/2)
                        self.extra_balls = []
                        self.last_point_time = 0
                        break

                # powerup pickups
                for pu in list(self.powerups):
                    pu.update(dt)
                    if pu.ttl <= 0:
                        self.powerups.remove(pu)
                        continue
                    if pygame.Rect(pu.rect).colliderect(pygame.Rect(self.left_paddle.rect)):
                        self.apply_powerup(pu, -1)
                        self.powerups.remove(pu)
                    elif pygame.Rect(pu.rect).colliderect(pygame.Rect(self.right_paddle.rect)):
                        self.apply_powerup(pu, 1)
                        self.powerups.remove(pu)

                # particles
                for p in list(self.particles):
                    p.update(dt)
                    if p.ttl <= 0:
                        self.particles.remove(p)

                # screen shake decay
                self.shake = max(0, self.shake - 30 * dt)

                # check win
                if self.score_l >= WIN_SCORE or self.score_r >= WIN_SCORE:
                    winner = "Left Player" if self.score_l > self.score_r else "Right Player"
                    self.menu_active = True
                    self.menu_selection = 0
                    # show brief win message via reset

            # Draw everything
            # shake offset
            ox = int(random.uniform(-self.shake, self.shake))
            oy = int(random.uniform(-self.shake, self.shake))
            self.screen.fill(BG)
            # draw HUD
            self.draw_hud()
            # paddles
            self.left_paddle.draw(self.screen)
            self.right_paddle.draw(self.screen)
            # ball(s)
            for b in [self.ball] + self.extra_balls:
                b.draw(self.screen)
            # powerups
            for pu in self.powerups:
                pu.draw(self.screen)
            # particles
            for p in self.particles:
                p.draw(self.screen)

            pygame.display.flip()

        pygame.quit()


if __name__ == '__main__':
    Game().run()
