"""
Golf Game for NumWorks N0120 (Epsilon/MicroPython)
Uses kandinsky for drawing and ion for input.
Screen: 320x222 pixels
"""

import kandinsky as k
import ion
import math
import time

# ─── Colors ───────────────────────────────────────────────────────────────────
C_DARK_GREEN  = (34,  85,  34)   # rough
C_FAIRWAY     = (80, 160,  60)   # fairway
C_GREEN_PATCH = (144, 238, 144)  # putting green
C_SAND        = (180, 150,  80)  # bunker
C_SKY         = (135, 206, 235)  # sky (3D view)
C_WHITE       = (255, 255, 255)
C_BLACK       = (0,   0,   0)
C_GRAY        = (150, 150, 150)
C_GOLFER      = (120,  40,  40)  # dark red dot
C_AIM         = (200, 200, 200)  # gray +
C_BALL        = (255, 255, 255)
C_RED         = (180,   0,   0)
C_GOLD        = (180, 150,  80)
C_YELLOW      = (240, 220,   0)
C_LGREEN      = (100, 200, 100)

# ─── Screen dimensions ────────────────────────────────────────────────────────
SW, SH = 320, 222

# ─── Key codes (ion) ──────────────────────────────────────────────────────────
KEY_LEFT  = ion.KEY_LEFT
KEY_RIGHT = ion.KEY_RIGHT
KEY_UP    = ion.KEY_UP
KEY_DOWN  = ion.KEY_DOWN
KEY_OK    = ion.KEY_OK
KEY_EXE   = ion.KEY_EXE

# ─── Club definitions ─────────────────────────────────────────────────────────
#  name, distance (map pixels from golfer to aim cross)
CLUBS = [
    ("Driver", 90),
    ("Iron",   60),
    ("Wedge",  35),
    ("Putter", 18),
]

# ─── Course definition (map) ──────────────────────────────────────────────────
# Fairway polygons stored as list of filled rectangles (x, y, w, h)
FAIRWAY_RECTS = [
    (30,  80, 200, 40),   # main horizontal strip
    (80,  50, 120, 30),   # upper diagonal (approximated)
    (160, 120, 90, 30),   # lower-right section
    (200, 60,  80, 60),   # right section
]
SAND_RECT = (190, 115, 40, 22)   # bunker on map
GREEN_RECT = (260, 128, 45, 28)  # putting green on map

GOLFER_POS = (60, 98)            # golfer map position
HOLE_POS   = (272, 142)          # pin position (center of green)

# --- Green (putting) zoom view ---
# Scale factor: 1 map pixel = GREEN_ZOOM screen pixels in the putting view
GREEN_ZOOM = 7
GV_Y = 28         # green view top edge on screen (below meter bar)
GV_H = SH - GV_Y  # green view height on screen
GV_BORDER = 10    # rough border thickness (screen px)
PUTTER_IDX = 3    # index of Putter in CLUBS

# ─── Utility ──────────────────────────────────────────────────────────────────

def fill_rect(x, y, w, h, color):
    k.fill_rect(x, y, w, h, color)

def draw_text(text, x, y, fg, bg):
    k.draw_string(text, x, y, fg, bg)

def draw_plus(x, y, color, size=5):
    fill_rect(x - size, y - 1, size*2+1, 3, color)
    fill_rect(x - 1, y - size, 3, size*2+1, color)

def wait_for_ok():
    """Wait until OK/EXE pressed then released."""
    while not (ion.keydown(KEY_OK) or ion.keydown(KEY_EXE)):
        pass
    while ion.keydown(KEY_OK) or ion.keydown(KEY_EXE):
        pass

def key_pressed_once(key):
    if ion.keydown(key):
        while ion.keydown(key):
            pass
        return True
    return False

# ─── State ────────────────────────────────────────────────────────────────────
state = {
    "hole": 1,
    "par": 5,
    "stroke": 1,
    "club_idx": 0,
    "aim_angle": -math.pi / 4,   # radians from golfer, 0=right
    # after shot:
    "ball_pos": list(GOLFER_POS),
    "last_accuracy": 0.0,   # -1..1 (negative=left, positive=right)
    "last_power": 1.0,      # 0..1
    "phase": "map",         # "map" | "meters" | "motion" | "result"
}

# ─── MAP PHASE ────────────────────────────────────────────────────────────────

def draw_map():
    s = state
    # Background (rough)
    fill_rect(0, 0, SW, SH, C_DARK_GREEN)
    # Fairway
    for r in FAIRWAY_RECTS:
        fill_rect(r[0], r[1], r[2], r[3], C_FAIRWAY)
    # Sand bunker
    fill_rect(SAND_RECT[0], SAND_RECT[1], SAND_RECT[2], SAND_RECT[3], C_SAND)
    # Green
    fill_rect(GREEN_RECT[0], GREEN_RECT[1], GREEN_RECT[2], GREEN_RECT[3], C_GREEN_PATCH)
    # Hole pin (tiny dot)
    fill_rect(HOLE_POS[0]-1, HOLE_POS[1]-1, 3, 3, C_BLACK)

    # Ball / Golfer position
    bx, by = int(s["ball_pos"][0]), int(s["ball_pos"][1])
    fill_rect(bx-3, by-3, 7, 7, C_GOLFER)

    # Aim cross
    club = CLUBS[s["club_idx"]]
    dist = club[1]
    ax = int(bx + dist * math.cos(s["aim_angle"]))
    ay = int(by + dist * math.sin(s["aim_angle"]))
    draw_plus(ax, ay, C_AIM)

    # HUD overlay (bottom-left)
    fill_rect(0, SH - 40, 180, 40, (0, 0, 0))
    draw_text("Hole %d, Par %d" % (s["hole"], s["par"]),
              4, SH - 38, C_WHITE, C_BLACK)
    draw_text("Stroke %d, %s" % (s["stroke"], club[0]),
              4, SH - 20, C_YELLOW, C_BLACK)

def map_phase():
    s = state
    # If ball is on the green, switch to putting view immediately
    if on_green(s["ball_pos"][0], s["ball_pos"][1]):
        s["phase"] = "green"
        return
    # Draw once on entry
    draw_map()
    while True:
        # Only redraw when something changes
        if ion.keydown(KEY_LEFT):
            s["aim_angle"] -= 0.05
            draw_map()
            time.sleep(0.05)
        elif ion.keydown(KEY_RIGHT):
            s["aim_angle"] += 0.05
            draw_map()
            time.sleep(0.05)
        elif key_pressed_once(KEY_DOWN):
            s["club_idx"] = (s["club_idx"] + 1) % len(CLUBS)
            draw_map()
        elif key_pressed_once(KEY_UP):
            s["club_idx"] = (s["club_idx"] - 1) % len(CLUBS)
            draw_map()
        elif ion.keydown(KEY_OK) or ion.keydown(KEY_EXE):
            while ion.keydown(KEY_OK) or ion.keydown(KEY_EXE):
                pass
            s["phase"] = "meters"
            return

# ─── METERS PHASE (3D view + accuracy + power) ────────────────────────────────

def draw_3d_scene(accuracy_marker=None, power_marker=None):
    """Draw the pseudo-3D fairway view."""
    # Sky
    fill_rect(0, 30, SW, 110, C_SKY)
    # Ground (fairway)
    fill_rect(0, 140, SW, SH - 140, C_FAIRWAY)
    # Rough left
    fill_rect(0, 100, 60, SH - 100, C_DARK_GREEN)
    # Rough right hint
    fill_rect(260, 120, SW - 260, SH - 120, C_DARK_GREEN)

    # Sand bunker as trapezoid (approximated with diminishing-width rects)
    # In 3D: bunker appears roughly at center-right, nearer = wider
    bx_center, by_base = 190, 165
    for i in range(20):
        prog = i / 20.0
        w = int(80 * (1 - prog * 0.5))
        y = by_base - i
        x = bx_center - w // 2
        fill_rect(x, y, w, 1, C_SAND)

    # Golf ball
    fill_rect(SW//2 - 5, 172, 10, 10, C_WHITE)

    # Meters bar at top
    draw_meters_bar(accuracy_marker, power_marker)

def draw_meters_bar(accuracy_marker, power_marker):
    """Draw the top HUD bar with accuracy and power meters."""
    bar_y = 0
    bar_h = 28
    fill_rect(0, bar_y, SW, bar_h, (60, 60, 60))

    # Accuracy meter (left half): gray gradient bar
    acc_x, acc_y, acc_w, acc_h = 5, 3, 140, 22
    # Draw gradient: dark gray -> light gray -> dark gray
    for i in range(acc_w):
        t = abs(i - acc_w // 2) / (acc_w // 2)
        gray = int(200 - 100 * t)
        fill_rect(acc_x + i, acc_y, 1, acc_h, (gray, gray, gray))
    # Black border
    fill_rect(acc_x, acc_y, acc_w, 2, C_BLACK)
    fill_rect(acc_x, acc_y + acc_h - 2, acc_w, 2, C_BLACK)
    # Accuracy marker
    if accuracy_marker is not None:
        mx = acc_x + int((accuracy_marker + 1) / 2 * acc_w)
        mx = max(acc_x, min(acc_x + acc_w - 3, mx))
        fill_rect(mx, acc_y, 3, acc_h, C_BLACK)

    # Power meter (right half): red-gold-yellow-green
    pw_x, pw_y, pw_w, pw_h = 155, 3, 155, 22
    seg = pw_w // 4
    fill_rect(pw_x,           pw_y, seg,   pw_h, C_RED)
    fill_rect(pw_x + seg,     pw_y, seg,   pw_h, C_GOLD)
    fill_rect(pw_x + seg*2,   pw_y, seg,   pw_h, C_YELLOW)
    fill_rect(pw_x + seg*3,   pw_y, pw_w - seg*3, pw_h, C_LGREEN)
    fill_rect(pw_x, pw_y, pw_w, 2, C_BLACK)
    fill_rect(pw_x, pw_y + pw_h - 2, pw_w, 2, C_BLACK)
    # Power marker
    if power_marker is not None:
        mx = pw_x + int(power_marker * pw_w)
        mx = max(pw_x, min(pw_x + pw_w - 3, mx))
        fill_rect(mx, pw_y, 3, pw_h, C_BLACK)

    # Labels
    draw_text("AIM", 50, 0, C_WHITE, (60,60,60))
    draw_text("PWR", 205, 0, C_WHITE, (60,60,60))

def meters_phase():
    s = state

    # Draw the 3D scene once — it won't change during meter sweeps
    draw_3d_scene(accuracy_marker=None, power_marker=None)

    # ── Accuracy sweep — only redraw the top bar ──
    acc_pos = 0.0   # -1 to 1
    direction = 1
    speed = 0.12    # 4x original 0.03

    while True:
        acc_pos += direction * speed
        if acc_pos > 1.0:
            acc_pos = 1.0
            direction = -1
        elif acc_pos < -1.0:
            acc_pos = -1.0
            direction = 1

        draw_meters_bar(acc_pos, None)

        if ion.keydown(KEY_OK) or ion.keydown(KEY_EXE):
            while ion.keydown(KEY_OK) or ion.keydown(KEY_EXE):
                pass
            s["last_accuracy"] = acc_pos
            break

        time.sleep(0.02)

    # ── Power sweep — only redraw the top bar ──
    pwr_pos = 0.0
    direction = 1
    speed = 0.075   # 3x original 0.025

    while True:
        pwr_pos += direction * speed
        if pwr_pos >= 1.0:
            pwr_pos = 1.0
            direction = -1
        elif pwr_pos <= 0.0:
            pwr_pos = 0.0
            direction = 1

        draw_meters_bar(s["last_accuracy"], pwr_pos)

        if ion.keydown(KEY_OK) or ion.keydown(KEY_EXE):
            while ion.keydown(KEY_OK) or ion.keydown(KEY_EXE):
                pass
            s["last_power"] = pwr_pos
            break

        time.sleep(0.02)

    s["phase"] = "motion"

# ─── MOTION PHASE (ball arc in 3D) ────────────────────────────────────────────

def motion_phase():
    s = state
    accuracy = s["last_accuracy"]   # -1..1
    power    = s["last_power"]      # 0..1

    steps = 40
    ball_start_x = SW // 2
    ball_start_y = 172

    for i in range(steps + 1):
        t = i / steps  # 0..1

        # Horizontal drift due to accuracy (accuracy>0 means slice right)
        drift = accuracy * 40 * t
        bx = ball_start_x + int(drift)

        # Vertical: parabolic arc going up then coming back (perspective)
        # Ball shrinks as it goes away
        arc_height = 80 * power
        vertical = int(arc_height * 4 * t * (1 - t))   # parabola peak midway
        # As ball goes away, its screen y rises (moves toward horizon at y=140)
        screen_y_base = ball_start_y - int((ball_start_y - 145) * t)
        ball_screen_y = screen_y_base - vertical
        ball_screen_x = bx
        ball_size = max(2, int(10 * (1 - t * 0.7)))

        # Redraw scene
        draw_3d_scene(accuracy_marker=s["last_accuracy"],
                      power_marker=s["last_power"])

        # Draw gray arc up to current point
        for j in range(i):
            tj = j / steps
            dj = accuracy * 40 * tj
            xj = ball_start_x + int(dj)
            vj = int(arc_height * 4 * tj * (1 - tj))
            syj_base = ball_start_y - int((ball_start_y - 145) * tj)
            syj = syj_base - vj
            fill_rect(xj, syj, 2, 2, C_GRAY)

        # Draw ball
        fill_rect(ball_screen_x - ball_size//2,
                  ball_screen_y - ball_size//2,
                  ball_size, ball_size, C_WHITE)

        time.sleep(0.04)

    # ── Compute new ball position on map ──
    club = CLUBS[s["club_idx"]]
    dist = club[1] * power
    # Accuracy offsets angle slightly
    angle_offset = accuracy * 0.3
    actual_angle = s["aim_angle"] + angle_offset

    bx0, by0 = s["ball_pos"]
    new_bx = bx0 + dist * math.cos(actual_angle)
    new_by = by0 + dist * math.sin(actual_angle)

    # Clamp to screen
    new_bx = max(5, min(SW - 5, new_bx))
    new_by = max(5, min(SH - 5, new_by))

    s["phase"] = "ball_travel"
    s["travel_target"] = (new_bx, new_by)
    s["travel_steps"] = 20
    # Note: green detection is handled at end of ball_travel_phase


def on_green(mx, my):
    """Return True if map position (mx, my) is inside GREEN_RECT."""
    gx, gy, gw, gh = GREEN_RECT
    return gx <= mx <= gx + gw and gy <= my <= gy + gh

def map_to_green_screen(mx, my):
    """Convert a map coordinate to green-view screen coordinate."""
    gx, gy, gw, gh = GREEN_RECT
    # Centre the green rect content in the screen area below the meter bar
    # Screen area: SW x GV_H, but green rect zoomed is gw*GREEN_ZOOM x gh*GREEN_ZOOM
    zoomed_w = gw * GREEN_ZOOM
    zoomed_h = gh * GREEN_ZOOM
    # Offset so the zoomed green is centred horizontally, top-aligned to GV_Y
    ox = (SW - zoomed_w) // 2
    sx = ox + int((mx - gx) * GREEN_ZOOM)
    sy = GV_Y + int((my - gy) * GREEN_ZOOM)
    return sx, sy

def draw_green_view(show_aim=True):
    """Draw the zoomed overhead putting green view."""
    s = state
    gx, gy, gw, gh = GREEN_RECT

    # Compute zoomed green screen rect
    zoomed_w = gw * GREEN_ZOOM
    zoomed_h = gh * GREEN_ZOOM
    ox = (SW - zoomed_w) // 2

    # Rough surround (whole screen below meter bar)
    fill_rect(0, GV_Y, SW, GV_H, C_DARK_GREEN)
    # Green surface
    fill_rect(ox, GV_Y, zoomed_w, zoomed_h, C_GREEN_PATCH)

    # Hole (black dot) — scaled position
    hsx, hsy = map_to_green_screen(HOLE_POS[0], HOLE_POS[1])
    fill_rect(hsx - 3, hsy - 3, 7, 7, C_BLACK)

    # Golfer / ball (red dot)
    bx, by = s["ball_pos"]
    gsx, gsy = map_to_green_screen(bx, by)
    fill_rect(gsx - 3, gsy - 3, 7, 7, C_GOLFER)

    # Aim cross
    if show_aim:
        club = CLUBS[s["club_idx"]]
        # Club distance is in map pixels; scale to screen pixels for display
        dist_screen = club[1] * GREEN_ZOOM
        ax = int(gsx + dist_screen * math.cos(s["aim_angle"]))
        ay = int(gsy + dist_screen * math.sin(s["aim_angle"]))
        draw_plus(ax, ay, C_AIM)

    # HUD overlay (bottom-left)
    club = CLUBS[s["club_idx"]]
    fill_rect(0, SH - 40, 180, 40, C_BLACK)
    draw_text("Hole %d, Par %d" % (s["hole"], s["par"]),
              4, SH - 38, C_WHITE, C_BLACK)
    draw_text("Stroke %d, %s" % (s["stroke"], club[0]),
              4, SH - 20, C_YELLOW, C_BLACK)

    # Meter bar at top (static — no markers during aiming)
    draw_meters_bar(None, None)

def green_phase():
    """Overhead putting view. Stays here while ball is on the green."""
    s = state

    # Default to putter when entering green phase
    s["club_idx"] = PUTTER_IDX

    draw_green_view(show_aim=True)

    while True:
        if ion.keydown(KEY_LEFT):
            s["aim_angle"] -= 0.05
            draw_green_view(show_aim=True)
            time.sleep(0.05)
        elif ion.keydown(KEY_RIGHT):
            s["aim_angle"] += 0.05
            draw_green_view(show_aim=True)
            time.sleep(0.05)
        elif key_pressed_once(KEY_DOWN):
            s["club_idx"] = (s["club_idx"] + 1) % len(CLUBS)
            draw_green_view(show_aim=True)
        elif key_pressed_once(KEY_UP):
            s["club_idx"] = (s["club_idx"] - 1) % len(CLUBS)
            draw_green_view(show_aim=True)
        elif ion.keydown(KEY_OK) or ion.keydown(KEY_EXE):
            while ion.keydown(KEY_OK) or ion.keydown(KEY_EXE):
                pass
            s["phase"] = "green_meters"
            return

def green_meters_phase():
    """Accuracy + power meters while staying in the green overhead view."""
    s = state

    # Draw green view once (no aim cross during meter sweep)
    draw_green_view(show_aim=False)

    # ── Accuracy sweep ──
    acc_pos = 0.0
    direction = 1
    speed = 0.12

    while True:
        acc_pos += direction * speed
        if acc_pos > 1.0:
            acc_pos = 1.0
            direction = -1
        elif acc_pos < -1.0:
            acc_pos = -1.0
            direction = 1

        draw_meters_bar(acc_pos, None)

        if ion.keydown(KEY_OK) or ion.keydown(KEY_EXE):
            while ion.keydown(KEY_OK) or ion.keydown(KEY_EXE):
                pass
            s["last_accuracy"] = acc_pos
            break

        time.sleep(0.02)

    # ── Power sweep ──
    pwr_pos = 0.0
    direction = 1
    speed = 0.075

    while True:
        pwr_pos += direction * speed
        if pwr_pos >= 1.0:
            pwr_pos = 1.0
            direction = -1
        elif pwr_pos <= 0.0:
            pwr_pos = 0.0
            direction = 1

        draw_meters_bar(s["last_accuracy"], pwr_pos)

        if ion.keydown(KEY_OK) or ion.keydown(KEY_EXE):
            while ion.keydown(KEY_OK) or ion.keydown(KEY_EXE):
                pass
            s["last_power"] = pwr_pos
            break

        time.sleep(0.02)

    s["phase"] = "green_putt"

def green_putt_phase():
    """Animate the ball rolling across the green view (no 3D arc)."""
    s = state
    accuracy = s["last_accuracy"]
    power    = s["last_power"]

    club = CLUBS[s["club_idx"]]
    dist_map = club[1] * power
    angle_offset = accuracy * 0.3
    actual_angle = s["aim_angle"] + angle_offset

    bx0, by0 = s["ball_pos"]
    new_bx = bx0 + dist_map * math.cos(actual_angle)
    new_by = by0 + dist_map * math.sin(actual_angle)

    # Animate ball rolling in green view
    steps = 20
    for i in range(steps + 1):
        t = i / steps
        cx = bx0 + (new_bx - bx0) * t
        cy = by0 + (new_by - by0) * t

        draw_green_view(show_aim=False)
        # Erase golfer dot and draw white ball dot at current position
        gsx, gsy = map_to_green_screen(cx, cy)
        fill_rect(gsx - 2, gsy - 2, 5, 5, C_WHITE)
        time.sleep(0.05)

    # Final position
    s["ball_pos"] = [new_bx, new_by]
    s["stroke"] += 1

    # Decide next phase: still on green -> green_phase, else map
    if on_green(new_bx, new_by):
        s["phase"] = "green"
    else:
        s["phase"] = "map"

def draw_map_no_aim():
    """Draw the map without the aim cross — used during ball travel."""
    s = state
    fill_rect(0, 0, SW, SH, C_DARK_GREEN)
    for r in FAIRWAY_RECTS:
        fill_rect(r[0], r[1], r[2], r[3], C_FAIRWAY)
    fill_rect(SAND_RECT[0], SAND_RECT[1], SAND_RECT[2], SAND_RECT[3], C_SAND)
    fill_rect(GREEN_RECT[0], GREEN_RECT[1], GREEN_RECT[2], GREEN_RECT[3], C_GREEN_PATCH)
    fill_rect(HOLE_POS[0]-1, HOLE_POS[1]-1, 3, 3, C_BLACK)
    # HUD
    club = CLUBS[s["club_idx"]]
    fill_rect(0, SH - 40, 180, 40, C_BLACK)
    draw_text("Hole %d, Par %d" % (s["hole"], s["par"]),
              4, SH - 38, C_WHITE, C_BLACK)
    draw_text("Stroke %d, %s" % (s["stroke"], club[0]),
              4, SH - 20, C_YELLOW, C_BLACK)

def ball_travel_phase():
    """Animate white dot moving on map, no aim cross shown."""
    s = state
    bx0, by0 = s["ball_pos"]
    tx, ty   = s["travel_target"]
    steps    = s["travel_steps"]

    for i in range(steps + 1):
        t = i / steps
        cx = bx0 + (tx - bx0) * t
        cy = by0 + (ty - by0) * t

        draw_map_no_aim()
        # White dot for the ball in flight
        fill_rect(int(cx)-2, int(cy)-2, 5, 5, C_WHITE)
        time.sleep(0.04)

    # Update ball position; enter green view if ball landed on green
    s["ball_pos"] = [tx, ty]
    s["stroke"] += 1
    if on_green(tx, ty):
        s["phase"] = "green"
    else:
        s["phase"] = "map"

# ─── MAIN LOOP ────────────────────────────────────────────────────────────────

def main():
    s = state
    while True:
        if s["phase"] == "map":
            map_phase()
        elif s["phase"] == "meters":
            meters_phase()
        elif s["phase"] == "motion":
            motion_phase()
        elif s["phase"] == "ball_travel":
            ball_travel_phase()
        elif s["phase"] == "green":
            green_phase()
        elif s["phase"] == "green_meters":
            green_meters_phase()
        elif s["phase"] == "green_putt":
            green_putt_phase()

        # Win condition: ball within 6px of hole (smaller target = harder)
        bx, by = s["ball_pos"]
        hx, hy = HOLE_POS
        if math.sqrt((bx-hx)**2 + (by-hy)**2) < 6:
            fill_rect(0, 0, SW, SH, C_BLACK)
            draw_text("HOLE IN %d!" % s["stroke"], 80, 100, C_YELLOW, C_BLACK)
            draw_text("Press OK to exit", 80, 120, C_WHITE, C_BLACK)
            wait_for_ok()
            break

main()
