# Breakoid Bricks - NumWorks (Epsilon) port (reduced flicker / dirty redraw)
# Controls: LEFT/RIGHT to move paddle (accelerates), OK/EXE to launch ball

from kandinsky import fill_rect, draw_string
from ion import keydown, KEY_LEFT, KEY_RIGHT, KEY_OK, KEY_EXE
from time import monotonic, sleep

# Screen coords used by kandinsky on N0120
W, H = 320, 240

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

# Layout bands
HUD_H = 24
CRED_Y = 24
CRED_H = 16
TOP = 0  # top of playfield region (prevents ball in HUD)

# Geometry
BALL = 6
PADDLE_W = 52
PADDLE_H = 8
PADDLE_Y = H - 24

BRICK_W = 30
BRICK_H = 8
BRICK_GAP_X = 6
BRICK_GAP_Y = 6
BRICKS_PER_ROW = 8

BRICK_X0 = 10
BRICK_Y0 = 50  # should be below TOP

# Paddle motion
PADDLE_ACCEL = 0.9
PADDLE_FRICTION = 0.85
PADDLE_MAX_V = 9.0

# Ball physics
BALL_SPEED_X0 = 2.6
BASE_BALL_SPEED_Y = -2.8
BALL_MAX_VX = 6.5
ENGLISH = 0.55

# Timing
TARGET_DT = 1 / 60

def clamp(x, lo, hi):
    if x < lo: return lo
    if x > hi: return hi
    return x

def reset_bricks():
    return [1] * BRICKS_PER_ROW, [1] * BRICKS_PER_ROW

def brick_rect(i, row_index):
    x = BRICK_X0 + i * (BRICK_W + BRICK_GAP_X)
    y = BRICK_Y0 + row_index * (BRICK_H + BRICK_GAP_Y)
    return x, y, BRICK_W, BRICK_H

def rects_overlap(ax, ay, aw, ah, bx, by, bw, bh):
    return (ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by)

def draw_hud_and_credits(score):
    # Clear HUD + credits area
    fill_rect(0, 0, W, HUD_H, BLACK)
    draw_string("Score:", 6, 4, WHITE, BLACK)
    draw_string(str(score), 70, 4, WHITE, BLACK)
    if score == 0:
        draw_string("Breakoid Bricks", 130, 4, WHITE, BLACK)
        draw_string("Game wloucks '22, Port GPT '26", 6, CRED_Y + 2, WHITE, BLACK)
    if score == 1:
        draw_string("Breakoid Bricks", 130, 4, BLACK, BLACK)
        draw_string("Game wloucks '22, Port GPT '26", 6, CRED_Y + 2, BLACK, BLACK)

def clear_credits():
    fill_rect(0, CRED_Y, W, CRED_H, BLACK)

def draw_all_bricks(row1, row2):
    # Draw both rows
    for i in range(BRICKS_PER_ROW):
        if row1[i]:
            x, y, w, h = brick_rect(i, 0)
            fill_rect(x, y, w, h, WHITE)
        else:
            x, y, w, h = brick_rect(i, 0)
            fill_rect(x, y, w, h, BLACK)

        if row2[i]:
            x, y, w, h = brick_rect(i, 1)
            fill_rect(x, y, w, h, WHITE)
        else:
            x, y, w, h = brick_rect(i, 1)
            fill_rect(x, y, w, h, BLACK)

def draw_static_scene(score, row1, row2):
    fill_rect(0, 0, W, H, BLACK)
    draw_hud_and_credits(score)
    draw_all_bricks(row1, row2)

def main():
    score = 0
    row1, row2 = reset_bricks()

    # Paddle state
    armed = False  # becomes True after the player moves once
    px = (W - PADDLE_W) / 2
    pv = 0.0

    # Ball state
    ball_reset = True
    bx = px + PADDLE_W/2 - BALL/2
    by = PADDLE_Y - BALL - 2
    vx = BALL_SPEED_X0
    vy = BASE_BALL_SPEED_Y

    # Draw static once
    draw_static_scene(score, row1, row2)

    # Track previously drawn positions for dirty redraw
    prev_px = int(px)
    prev_bx = int(bx)
    prev_by = int(by)

    last_score = score

    last_t = monotonic()

    while True:
        # --- Timing ---
        now = monotonic()
        dt = now - last_t
        if dt < TARGET_DT:
            sleep(TARGET_DT - dt)
            now = monotonic()
            dt = now - last_t
        last_t = now
        if dt > 0.05:
            dt = 0.05

        # --- Input ---
        left = keydown(KEY_LEFT)
        right = keydown(KEY_RIGHT)
        
        if left or right:
            armed = True

        if left and not right:
            pv -= PADDLE_ACCEL
        elif right and not left:
            pv += PADDLE_ACCEL
        else:
            pv *= PADDLE_FRICTION

        pv = clamp(pv, -PADDLE_MAX_V, PADDLE_MAX_V)

        px += pv
        px = clamp(px, 0, W - PADDLE_W)

        # --- Save old draw positions (for erasing) ---
        old_px = prev_px
        old_bx = prev_bx
        old_by = prev_by

        # --- Ball reset/launch ---
        if ball_reset:
            bx = px + PADDLE_W/2 - BALL/2
            by = PADDLE_Y - BALL - 2

            if armed and (keydown(KEY_OK) or keydown(KEY_EXE)):
                ramp_score = score if score <= 96 else 96
                vy = -(2.8 + 0.05 * ramp_score)
                vx = -abs(BALL_SPEED_X0) if vx < 0 else abs(BALL_SPEED_X0)
                ball_reset = False

        else:
            bx += vx
            by += vy

            # Walls
            if bx <= 0:
                bx = 0
                vx = -vx
            elif bx + BALL >= W:
                bx = W - BALL
                vx = -vx

            if by <= TOP:
                by = TOP
                vy = -vy

            # Brick collisions (simple, works well enough)
            brick_removed = False

            for i in range(BRICKS_PER_ROW):
                if row1[i]:
                    rx, ry, rw, rh = brick_rect(i, 0)
                    if rects_overlap(bx, by, BALL, BALL, rx, ry, rw, rh):
                        row1[i] = 0
                        fill_rect(rx, ry, rw, rh, BLACK)  # erase just that brick
                        vy = -vy
                        score += 1
                        brick_removed = True
                        break

            if not brick_removed:
                for i in range(BRICKS_PER_ROW):
                    if row2[i]:
                        rx, ry, rw, rh = brick_rect(i, 1)
                        if rects_overlap(bx, by, BALL, BALL, rx, ry, rw, rh):
                            row2[i] = 0
                            fill_rect(rx, ry, rw, rh, BLACK)
                            vy = -vy
                            score += 1
                            break

            # Paddle collision
            if vy > 0 and rects_overlap(bx, by, BALL, BALL, px, PADDLE_Y, PADDLE_W, PADDLE_H):
                by = PADDLE_Y - BALL - 1
                vy = -vy

                # English: held key at impact
                if left and not right:
                    vx -= ENGLISH
                elif right and not left:
                    vx += ENGLISH
                vx = clamp(vx, -BALL_MAX_VX, BALL_MAX_VX)

            # Missed
            if by > H:
                ball_reset = True
                armed = False

            # Next level
            if row1 == [0]*BRICKS_PER_ROW and row2 == [0]*BRICKS_PER_ROW and by > H/2:
                row1, row2 = reset_bricks()
                ball_reset = True
                armed = False
                # Redraw all bricks for new level
                draw_all_bricks(row1, row2)

        # --- Update HUD when score changed or ball in top-left ---
        if score != last_score or (bx < W/3 and by < HUD_H):
            if last_score == 0 and score == 1:
                clear_credits()     # permanently erase credits area
            draw_hud_and_credits(score)
            last_score = score

        # --- Dirty redraw: erase old paddle/ball, then draw new ---
        # Erase old ball and paddle
        fill_rect(old_bx, old_by, BALL, BALL, BLACK)
        fill_rect(old_px, PADDLE_Y, PADDLE_W, PADDLE_H, BLACK)

        # Draw new paddle/ball
        prev_px = int(px)
        prev_bx = int(bx)
        prev_by = int(by)

        fill_rect(prev_px, PADDLE_Y, PADDLE_W, PADDLE_H, WHITE)
        fill_rect(prev_bx, prev_by, BALL, BALL, WHITE)

# Run
main()
