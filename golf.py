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
C_GREEN_PATCH = (127, 238, 127)  # putting green
C_SAND        = (180, 150,  80)  # bunker
C_SKY         = (135, 206, 235)  # sky (3D view)
C_WHITE       = (255, 255, 255)
C_BLACK       = (0,   0,   0)
C_GRAY        = (100, 100, 100)
C_GOLFER      = (160,  60,  60)  # dark red dot
C_AIM         = (20, 20, 120)    # dark blue
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
    ("Driver", 115),
    ("Iron",   60),
    ("Wedge",  35),
    ("Putter", 15),
]

# ─── Sand bunker penalty modifiers ────────────────────────────────────────────
# When the ball is in sand, the wedge is best (1.0).
# Other clubs are penalised because they are less suited to bunker play.
# Index matches CLUBS: 0=Driver, 1=Iron, 2=Wedge, 3=Putter
SAND_MODIFIERS = [0.28, 0.50, 1.00, 0.40]

# When in rough, all clubs lose distance. Driver loses most (harder to control
# through long grass); wedge and putter are least affected.
# Index matches CLUBS: 0=Driver, 1=Iron, 2=Wedge, 3=Putter
ROUGH_MODIFIERS = [0.65, 0.78, 0.88, 0.80]

# ─── Course definition (map) ──────────────────────────────────────────────────
# Fairway polygons stored as list of filled rectangles (x, y, w, h)
FAIRWAY_RECTS = [
    (30,  80, 200, 40),   # main horizontal strip
    (80,  50, 120, 30),   # upper diagonal (approximated)
    (160, 120, 90, 30),   # lower-right section
    (200, 60,  80, 60),   # right section
]
SAND_RECT  = (190, 115, 40, 22)   # bunker on map
GREEN_RECT = (260, 128, 45, 28)   # putting green on map

GOLFER_POS = (60, 98)             # golfer map position
HOLE_POS   = (272, 142)           # pin position (center of green)

# --- Green (putting) zoom view ---
GREEN_ZOOM = 7
GV_Y = 28
GV_H = SH - GV_Y
GV_BORDER = 10
PUTTER_IDX = 3

# ─── Utility ──────────────────────────────────────────────────────────────────

def fill_rect(x, y, w, h, color):
    k.fill_rect(x, y, w, h, color)

def draw_text(text, x, y, fg, bg):
    k.draw_string(text, x, y, fg, bg)

def draw_plus(x, y, color, size=5):
    fill_rect(x - size, y - 1, size*2+1, 3, color)
    fill_rect(x - 1, y - size, 3, size*2+1, color)

def wait_for_ok():
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

# ─── Terrain helpers ──────────────────────────────────────────────────────────

def on_green(mx, my):
    gx, gy, gw, gh = GREEN_RECT
    return gx <= mx <= gx + gw and gy <= my <= gy + gh

def on_sand(mx, my):
    sx, sy, sw, sh = SAND_RECT
    return sx <= mx <= sx + sw and sy <= my <= sy + sh

def sand_modifier(club_idx):
    """Return the distance multiplier for a club when playing from sand."""
    return SAND_MODIFIERS[club_idx]

def on_rough(mx, my):
    """Return True if position is not on fairway, green, or sand."""
    if on_green(mx, my) or on_sand(mx, my):
        return False
    for r in FAIRWAY_RECTS:
        if r[0] <= mx <= r[0] + r[2] and r[1] <= my <= r[1] + r[3]:
            return False
    return True

def rough_modifier(club_idx):
    """Return the distance multiplier for a club when playing from rough."""
    return ROUGH_MODIFIERS[club_idx]

# ─── State ────────────────────────────────────────────────────────────────────
state = {
    "hole": 1,
    "par": 5,
    "stroke": 1,
    "club_idx": 0,
    "aim_angle": -math.pi / 4,
    "ball_pos": list(GOLFER_POS),
    "last_accuracy": 0.0,
    "last_power": 1.0,
    "phase": "map",
}

# ─── MAP PHASE ────────────────────────────────────────────────────────────────

def draw_map():
    s = state
    fill_rect(0, 0, SW, SH, C_DARK_GREEN)
    for r in FAIRWAY_RECTS:
        fill_rect(r[0], r[1], r[2], r[3], C_FAIRWAY)
    fill_rect(SAND_RECT[0], SAND_RECT[1], SAND_RECT[2], SAND_RECT[3], C_SAND)
    fill_rect(GREEN_RECT[0], GREEN_RECT[1], GREEN_RECT[2], GREEN_RECT[3], C_GREEN_PATCH)
    fill_rect(HOLE_POS[0]-1, HOLE_POS[1]-1, 3, 3, C_BLACK)

    bx, by = int(s["ball_pos"][0]), int(s["ball_pos"][1])
    # White dot = ball; red dot = golfer, offset away from aim cross
    fill_rect(bx-3, by-3, 7, 7, C_WHITE)
    gdx = -int(round(math.cos(s["aim_angle"]) * 7))
    gdy = -int(round(math.sin(s["aim_angle"]) * 7))
    fill_rect(bx + gdx - 3, by + gdy - 3, 7, 7, C_GOLFER)

    club = CLUBS[s["club_idx"]]
    dist = club[1]
    # Shorten aim cross to reflect terrain penalty
    if on_sand(s["ball_pos"][0], s["ball_pos"][1]):
        dist = dist * sand_modifier(s["club_idx"])
    elif on_rough(s["ball_pos"][0], s["ball_pos"][1]):
        dist = dist * rough_modifier(s["club_idx"])
    ax = int(bx + dist * math.cos(s["aim_angle"]))
    ay = int(by + dist * math.sin(s["aim_angle"]))
    draw_plus(ax, ay, C_AIM)

    # HUD: avoid overlapping the aim cross
    if ay < SH - 50:
        fill_rect(0, SH - 40, 180, 40, C_BLACK)
        draw_text("Hole %d, Par %d" % (s["hole"], s["par"]),
                  4, SH - 38, C_WHITE, C_BLACK)
        draw_text("Stroke %d, %s" % (s["stroke"], club[0]),
                  4, SH - 20, C_YELLOW, C_BLACK)
    else:
        fill_rect(0, 0, 180, 40, C_BLACK)
        draw_text("Hole %d, Par %d" % (s["hole"], s["par"]),
                  4, 2, C_WHITE, C_BLACK)
        draw_text("Stroke %d, %s" % (s["stroke"], club[0]),
                  4, 20, C_YELLOW, C_BLACK)

    # Sand indicator: show modifier if in bunker
    if on_sand(s["ball_pos"][0], s["ball_pos"][1]):
        mod = sand_modifier(s["club_idx"])
        pct = int(mod * 100)
        fill_rect(SW - 100, SH - 20, 100, 18, C_BLACK)
        draw_text("Sand %d%%" % pct, SW - 98, SH - 18, C_SAND, C_BLACK)
    elif on_rough(s["ball_pos"][0], s["ball_pos"][1]):
        mod = rough_modifier(s["club_idx"])
        pct = int(mod * 100)
        fill_rect(SW - 100, SH - 20, 100, 18, C_BLACK)
        draw_text("Rough %d%%" % pct, SW - 98, SH - 18, C_FAIRWAY, C_BLACK)

def map_phase():
    s = state
    if on_green(s["ball_pos"][0], s["ball_pos"][1]):
        s["phase"] = "green"
        return
    draw_map()
    while True:
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

# ─── METERS PHASE ─────────────────────────────────────────────────────────────

TERRAIN_COLORS = {
    "rough":   C_DARK_GREEN,
    "fairway": C_FAIRWAY,
    "sand":    C_SAND,
    "green":   C_GREEN_PATCH,
}

def classify_point(mx, my):
    gx, gy, gw, gh = GREEN_RECT
    if gx <= mx <= gx + gw and gy <= my <= gy + gh:
        return "green"
    sx, sy, sw2, sh2 = SAND_RECT
    if sx <= mx <= sx + sw2 and sy <= my <= sy + sh2:
        return "sand"
    for r in FAIRWAY_RECTS:
        if r[0] <= mx <= r[0] + r[2] and r[1] <= my <= r[1] + r[3]:
            return "fairway"
    return "rough"

def build_scene_bands():
    s = state
    bx, by = s["ball_pos"]
    angle  = s["aim_angle"]
    club   = CLUBS[s["club_idx"]]
    dist   = club[1]
    perp   = angle - math.pi / 2
    depth_fracs  = [0.05, 0.35, 0.65]
    lateral_offs = [-dist * 0.35, 0.0, dist * 0.35]
    bands = []
    for df in depth_fracs:
        row = []
        cx = bx + dist * df * math.cos(angle)
        cy = by + dist * df * math.sin(angle)
        for lo in lateral_offs:
            px = cx + lo * math.cos(perp)
            py = cy + lo * math.sin(perp)
            row.append(classify_point(px, py))
        bands.append(row)
    return bands

def draw_3d_scene(accuracy_marker=None, power_marker=None, scene_bands=None):
    fill_rect(0, 30, SW, 110, C_SKY)
    band_tops = [185, 158, 140]
    band_bots = [222, 185, 158]
    horizon_y = 140
    fill_rect(0, horizon_y, SW, SH - horizon_y, C_DARK_GREEN)
    if scene_bands is None:
        scene_bands = [["fairway", "fairway", "fairway"]] * 3
    for band_idx in range(3):
        row   = scene_bands[band_idx]
        y_top = band_tops[band_idx]
        y_bot = band_bots[band_idx]
        for y in range(y_top, y_bot):
            t  = (y - horizon_y) / (222 - horizon_y)
            hw = int(SW // 2 * t + 60 * (1 - t))
            xl = SW // 2 - hw
            total_w = hw * 2
            if total_w <= 0:
                continue
            seg = total_w // 3
            rem = total_w - seg * 2
            fill_rect(xl,         y, seg, 1, TERRAIN_COLORS.get(row[0], C_FAIRWAY))
            fill_rect(xl + seg,   y, seg, 1, TERRAIN_COLORS.get(row[1], C_FAIRWAY))
            fill_rect(xl + seg*2, y, rem, 1, TERRAIN_COLORS.get(row[2], C_FAIRWAY))
    fill_rect(SW//2 - 5, 196, 10, 10, C_WHITE)
    draw_meters_bar(accuracy_marker, power_marker)

def draw_meters_bar(accuracy_marker, power_marker):
    fill_rect(0, 0, SW, 28, (60, 60, 60))
    acc_x, acc_y, acc_w, acc_h = 5, 3, 140, 22
    for i in range(acc_w):
        t = abs(i - acc_w // 2) / (acc_w // 2)
        gray = int(200 - 100 * t)
        fill_rect(acc_x + i, acc_y, 1, acc_h, (gray, gray, gray))
    fill_rect(acc_x, acc_y, acc_w, 2, C_BLACK)
    fill_rect(acc_x, acc_y + acc_h - 2, acc_w, 2, C_BLACK)
    if accuracy_marker is not None:
        mx = acc_x + int((accuracy_marker + 1) / 2 * acc_w)
        mx = max(acc_x, min(acc_x + acc_w - 3, mx))
        fill_rect(mx, acc_y, 3, acc_h, C_BLACK)
    pw_x, pw_y, pw_w, pw_h = 155, 3, 155, 22
    seg = pw_w // 4
    fill_rect(pw_x,         pw_y, seg,          pw_h, C_RED)
    fill_rect(pw_x + seg,   pw_y, seg,          pw_h, C_GOLD)
    fill_rect(pw_x + seg*2, pw_y, seg,          pw_h, C_YELLOW)
    fill_rect(pw_x + seg*3, pw_y, pw_w - seg*3, pw_h, C_LGREEN)
    fill_rect(pw_x, pw_y, pw_w, 2, C_BLACK)
    fill_rect(pw_x, pw_y + pw_h - 2, pw_w, 2, C_BLACK)
    if power_marker is not None:
        mx = pw_x + int(power_marker * pw_w)
        mx = max(pw_x, min(pw_x + pw_w - 3, mx))
        fill_rect(mx, pw_y, 3, pw_h, C_BLACK)
    draw_text("AIM", 50, 0, C_WHITE, (60, 60, 60))
    draw_text("PWR", 205, 0, C_WHITE, (60, 60, 60))

def meters_phase():
    s = state
    scene_bands = build_scene_bands()
    s["scene_bands"] = scene_bands
    draw_3d_scene(accuracy_marker=None, power_marker=None, scene_bands=scene_bands)

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

    pwr_pos = 0.0
    direction = 1
    speed = 0.05625
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

# ─── MOTION PHASE ─────────────────────────────────────────────────────────────

def motion_phase():
    s = state
    accuracy = s["last_accuracy"]
    power    = s["last_power"]

    steps = 40
    ball_start_x = SW // 2
    ball_start_y = 196

    for i in range(steps + 1):
        t = i / steps
        drift = accuracy * 40 * t
        bx = ball_start_x + int(drift)
        arc_height = 80 * power
        vertical = int(arc_height * 4 * t * (1 - t))
        screen_y_base = ball_start_y - int((ball_start_y - 145) * t)
        ball_screen_y = screen_y_base - vertical
        ball_screen_x = bx
        ball_size = max(2, int(10 * (1 - t * 0.7)))

        draw_3d_scene(accuracy_marker=s["last_accuracy"],
                      power_marker=s["last_power"],
                      scene_bands=s.get("scene_bands"))

        for j in range(i):
            tj = j / steps
            dj = accuracy * 40 * tj
            xj = ball_start_x + int(dj)
            vj = int(arc_height * 4 * tj * (1 - tj))
            syj_base = ball_start_y - int((ball_start_y - 145) * tj)
            syj = syj_base - vj
            fill_rect(xj, syj, 2, 2, C_GRAY)

        fill_rect(ball_screen_x - ball_size//2,
                  ball_screen_y - ball_size//2,
                  ball_size, ball_size, C_WHITE)
        time.sleep(0.04)

    # Compute landing position — apply sand modifier if needed
    club = CLUBS[s["club_idx"]]
    dist = club[1] * power
    if on_sand(s["ball_pos"][0], s["ball_pos"][1]):
        dist = dist * sand_modifier(s["club_idx"])
    elif on_rough(s["ball_pos"][0], s["ball_pos"][1]):
        dist = dist * rough_modifier(s["club_idx"])

    angle_offset = accuracy * 0.3
    actual_angle = s["aim_angle"] + angle_offset
    bx0, by0 = s["ball_pos"]
    new_bx = bx0 + dist * math.cos(actual_angle)
    new_by = by0 + dist * math.sin(actual_angle)
    new_bx = max(5, min(SW - 5, new_bx))
    new_by = max(5, min(SH - 5, new_by))

    s["phase"] = "ball_travel"
    s["travel_target"] = (new_bx, new_by)
    s["travel_steps"] = 20

# ─── GREEN PHASE ──────────────────────────────────────────────────────────────

def map_to_green_screen(mx, my):
    gx, gy, gw, gh = GREEN_RECT
    zoomed_w = gw * GREEN_ZOOM
    ox = (SW - zoomed_w) // 2
    sx = ox + int((mx - gx) * GREEN_ZOOM)
    sy = GV_Y + int((my - gy) * GREEN_ZOOM)
    return sx, sy

def draw_green_view(show_aim=True):
    s = state
    gx, gy, gw, gh = GREEN_RECT
    zoomed_w = gw * GREEN_ZOOM
    zoomed_h = gh * GREEN_ZOOM
    ox = (SW - zoomed_w) // 2

    fill_rect(0, GV_Y, SW, GV_H, C_DARK_GREEN)
    fill_rect(ox, GV_Y, zoomed_w, zoomed_h, C_GREEN_PATCH)

    hsx, hsy = map_to_green_screen(HOLE_POS[0], HOLE_POS[1])
    fill_rect(hsx - 3, hsy - 3, 7, 7, C_BLACK)

    bx, by = s["ball_pos"]
    gsx, gsy = map_to_green_screen(bx, by)
    # White dot = ball; red dot = golfer offset away from aim direction
    fill_rect(gsx - 3, gsy - 3, 7, 7, C_WHITE)
    gdx = -int(round(math.cos(s["aim_angle"]) * 7))
    gdy = -int(round(math.sin(s["aim_angle"]) * 7))
    fill_rect(gsx + gdx - 3, gsy + gdy - 3, 7, 7, C_GOLFER)

    if show_aim:
        club = CLUBS[s["club_idx"]]
        dist_screen = club[1] * GREEN_ZOOM
        ax = int(gsx + dist_screen * math.cos(s["aim_angle"]))
        ay = int(gsy + dist_screen * math.sin(s["aim_angle"]))
        draw_plus(ax, ay, C_AIM)
        # Distance guide crosses at 25%, 50%, 75% of full putt distance
        for frac, col in [(0.25, C_RED), (0.50, C_GOLD), (0.75, C_YELLOW)]:
            gx2 = int(gsx + dist_screen * frac * math.cos(s["aim_angle"]))
            gy2 = int(gsy + dist_screen * frac * math.sin(s["aim_angle"]))
            draw_plus(gx2, gy2, col, size=3)

        if ay < SH - 50 and (gsy < SH - 50 or gsx > 2 * SW // 3):
            fill_rect(0, SH - 40, 180, 40, C_BLACK)
            draw_text("Hole %d, Par %d" % (s["hole"], s["par"]),
                      4, SH - 38, C_WHITE, C_BLACK)
            draw_text("Stroke %d, %s" % (s["stroke"], club[0]),
                      4, SH - 20, C_YELLOW, C_BLACK)
        else:
            fill_rect(0, 30, 180, 40, C_BLACK)
            draw_text("Hole %d, Par %d" % (s["hole"], s["par"]),
                      4, 32, C_WHITE, C_BLACK)
            draw_text("Stroke %d, %s" % (s["stroke"], club[0]),
                      4, 50, C_YELLOW, C_BLACK)

    draw_meters_bar(None, None)

def green_phase():
    s = state
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
    s = state
    draw_green_view(show_aim=False)

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

    pwr_pos = 0.0
    direction = 1
    speed = 0.05625
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

    steps = 20
    for i in range(steps + 1):
        t = i / steps
        cx = bx0 + (new_bx - bx0) * t
        cy = by0 + (new_by - by0) * t
        draw_green_view(show_aim=False)
        gsx, gsy = map_to_green_screen(cx, cy)
        fill_rect(gsx - 2, gsy - 2, 5, 5, C_WHITE)
        time.sleep(0.05)

    s["ball_pos"] = [new_bx, new_by]
    s["stroke"] += 1
    if on_green(new_bx, new_by):
        s["phase"] = "green"
    else:
        s["phase"] = "map"

# ─── MAP TRAVEL ───────────────────────────────────────────────────────────────

def draw_map_no_aim():
    s = state
    fill_rect(0, 0, SW, SH, C_DARK_GREEN)
    for r in FAIRWAY_RECTS:
        fill_rect(r[0], r[1], r[2], r[3], C_FAIRWAY)
    fill_rect(SAND_RECT[0], SAND_RECT[1], SAND_RECT[2], SAND_RECT[3], C_SAND)
    fill_rect(GREEN_RECT[0], GREEN_RECT[1], GREEN_RECT[2], GREEN_RECT[3], C_GREEN_PATCH)
    fill_rect(HOLE_POS[0]-1, HOLE_POS[1]-1, 3, 3, C_BLACK)
    club = CLUBS[s["club_idx"]]
    fill_rect(0, SH - 40, 180, 40, C_BLACK)
    draw_text("Hole %d, Par %d" % (s["hole"], s["par"]),
              4, SH - 38, C_WHITE, C_BLACK)
    draw_text("Stroke %d, %s" % (s["stroke"], club[0]),
              4, SH - 20, C_YELLOW, C_BLACK)

def ball_travel_phase():
    s = state
    bx0, by0 = s["ball_pos"]
    tx, ty   = s["travel_target"]
    steps    = s["travel_steps"]
    for i in range(steps + 1):
        t = i / steps
        cx = bx0 + (tx - bx0) * t
        cy = by0 + (ty - by0) * t
        draw_map_no_aim()
        fill_rect(int(cx)-2, int(cy)-2, 5, 5, C_WHITE)
        time.sleep(0.04)
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

        # Win condition
        bx, by = s["ball_pos"]
        hx, hy = HOLE_POS
        if math.sqrt((bx-hx)**2 + (by-hy)**2) < 3:
            fill_rect(0, 0, SW, SH, C_BLACK)
            draw_text("HOLE IN %d!" % s["stroke"], 80, 100, C_YELLOW, C_BLACK)
            draw_text("Press OK to exit", 80, 120, C_WHITE, C_BLACK)
            wait_for_ok()
            break

main()
