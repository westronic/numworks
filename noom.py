# NumWorks / Epsilon Python
# Wolfenstein-style (3A) raycaster demo (reduced flicker on device)
# - Beige walls with distance shading (palette lookup)
# - Dark brown floor, white ceiling
# - Grid map (strings)
# - DDA raycasting
# - Half horizontal resolution for speed (each ray draws a 2px-wide column)
# - Reduced flicker via:
#     (1) Only render when input indicates motion/turning
#     (2) Run-length merging of identical wall slices (fewer fill_rect calls)
#     (3) No FPS overlay + no artificial sleep
#
# Controls:
#   LEFT/RIGHT  = turn
#   UP/DOWN     = forward/back
#   OK          = strafe left
#   EXE         = strafe right

from kandinsky import fill_rect
from ion import keydown, KEY_LEFT, KEY_RIGHT, KEY_UP, KEY_DOWN, KEY_TWO, KEY_FOUR, KEY_SIX, KEY_EIGHT
from time import monotonic
import math

# -----------------------------
# Screen / render settings
# -----------------------------
W, H = 320, 240
HALF_H = H // 2

# Render at half width for speed (each ray draws COL_W pixels wide)
RENDER_W = 80  # Lower for more speed, factor of 320
COL_W = W // RENDER_W  # width in px on NumWorks 320px screen

FOV_DEG = 60.0
FOV = math.radians(FOV_DEG)

# Colors (RGB tuples for kandinsky)
CEILING = (235, 235, 235)    # light gray
FLOOR   = (70, 40, 20)       # dark brown
WALL    = (220, 200, 160)    # beige
DOOR    = (200, 40, 40)      # apple red

# -----------------------------
# Map (grid) - NumWorks-friendly
# -----------------------------
MAP = [
  "#########################################",
  "##########################.....##########",
  "######################.........##########",
  "#.........############.###.........######",
  "#...####..#.####.......#####.#####..#####",
  "#...#.........................#####.....#",
  "#...####..#.####.......#.......####..##.#",
  "#.........######.......#..............#.#",
  "##################...###..............#.#",
  "########################..............#.#",
  "#################################.#####.#",
  "#################################.#####.#",
  "#################################.###...#",
  "###############################....##...#",
  "##############################......#...#",
  "##############################......#####",
  "#################################.#######",
  "#################################D#######"
]
MAP_H = len(MAP)
MAP_W = len(MAP[0])

def is_wall(mx, my):
  if mx < 0 or my < 0 or mx >= MAP_W or my >= MAP_H:
    return True
  return MAP[my][mx] == "#"
  
def is_door(mx, my):
  if mx < 0 or my < 0 or mx >= MAP_W or my >= MAP_H:
    return False
  return MAP[my][mx] == "D"

# -----------------------------
# Player state
# -----------------------------
px, py = 19.5, 6.5   # position in map units
ang = 0              # degrees (0..359)

MOVE_SPEED = 2.2     # units/sec
TURN_SPEED = 120.0   # deg/sec
RADIUS = 0.18        # collision radius

# -----------------------------
# Precompute trig tables
# -----------------------------
SIN = [math.sin(math.radians(a)) for a in range(360)]
COS = [math.cos(math.radians(a)) for a in range(360)]

# Precompute per-column ray relative angles (offset from center)
RAY_SIN = [0.0] * RENDER_W
RAY_COS = [0.0] * RENDER_W
for i in range(RENDER_W):
  t = (i + 0.5) / RENDER_W
  off = (t - 0.5) * FOV
  RAY_SIN[i] = math.sin(off)
  RAY_COS[i] = math.cos(off)

# Projection plane distance in pixels
PROJ_PLANE = (W / 2.0) / math.tan(FOV / 2.0)

# -----------------------------
# Distance shading palette (Option B)
# -----------------------------
SHADE_LEVELS = 16
MIN_FACTOR = 0.25
MAX_SHADE_DIST = 6.0

WALL_SHADES = []
for i in range(SHADE_LEVELS):
  factor = MIN_FACTOR + (i / (SHADE_LEVELS - 1)) * (1.0 - MIN_FACTOR)
  r, g, b = WALL
  WALL_SHADES.append((int(r * factor), int(g * factor), int(b * factor)))

DOOR_SHADES = []
for i in range(SHADE_LEVELS):
  factor = MIN_FACTOR + (i / (SHADE_LEVELS - 1)) * (1.0 - MIN_FACTOR)
  r, g, b = DOOR
  DOOR_SHADES.append((int(r * factor), int(g * factor), int(b * factor)))

# -----------------------------
# Collision helper (circle vs grid)
# -----------------------------
def collides(x, y):
  left   = int(x - RADIUS)
  right  = int(x + RADIUS)
  top    = int(y - RADIUS)
  bottom = int(y + RADIUS)

  if is_wall(left, top) or is_door(left, top): return True
  if is_wall(right, top) or is_door(right, top): return True
  if is_wall(left, bottom) or is_door(left, bottom): return True
  if is_wall(right, bottom) or is_door(right, bottom): return True
  return False

def try_move(nx, ny):
  global px, py

  # Move X then Y (simple sliding)
  if not collides(nx, py):
    px = nx
  if not collides(px, ny):
    py = ny

# -----------------------------
# Raycast (DDA)
# -----------------------------
def cast_ray(ray_dx, ray_dy):
  map_x = int(px)
  map_y = int(py)

  if ray_dx == 0.0: ray_dx = 1e-9
  if ray_dy == 0.0: ray_dy = 1e-9

  delta_dist_x = abs(1.0 / ray_dx)
  delta_dist_y = abs(1.0 / ray_dy)

  if ray_dx < 0:
    step_x = -1
    side_dist_x = (px - map_x) * delta_dist_x
  else:
    step_x = 1
    side_dist_x = (map_x + 1.0 - px) * delta_dist_x

  if ray_dy < 0:
    step_y = -1
    side_dist_y = (py - map_y) * delta_dist_y
  else:
    step_y = 1
    side_dist_y = (map_y + 1.0 - py) * delta_dist_y

  hit = False
  side = 0
  hit_tile = "#"

  for _ in range(64):
    if side_dist_x < side_dist_y:
      side_dist_x += delta_dist_x
      map_x += step_x
      side = 0
    else:
      side_dist_y += delta_dist_y
      map_y += step_y
      side = 1

    if map_x < 0 or map_y < 0 or map_x >= MAP_W or map_y >= MAP_H:
      hit = True
      hit_tile = "#"
      break

    tile = MAP[map_y][map_x]
    if tile == "#" or tile == "D":
      hit = True
      hit_tile = tile
      break

  if not hit:
    return 1e9, "#"

  if side == 0:
    dist = (map_x - px + (1.0 - step_x) * 0.5) / ray_dx
  else:
    dist = (map_y - py + (1.0 - step_y) * 0.5) / ray_dy

  return dist, hit_tile

# -----------------------------
# Render (merged runs to reduce draw calls)
# -----------------------------
def render():
  fill_rect(0, 0, W, HALF_H, CEILING)
  fill_rect(0, HALF_H, W, H - HALF_H, FLOOR)

  ca = COS[ang]
  sa = SIN[ang]

  run_col = None
  run_x = 0
  run_w = 0
  run_y0 = 0
  run_h = 0

  for i in range(RENDER_W):
    rcos = RAY_COS[i]
    rsin = RAY_SIN[i]

    ray_dx = ca * rsin - sa * rcos
    ray_dy = sa * rsin + ca * rcos

    dist, hit_tile = cast_ray(ray_dx, ray_dy)
    if dist < 0.05:
      dist = 0.05

    line_h = int((1.0 / dist) * PROJ_PLANE)

    y0 = HALF_H - (line_h >> 1)
    if y0 < 0:
      y0 = 0
    y1 = HALF_H + (line_h >> 1)
    if y1 >= H:
      y1 = H - 1
    h = y1 - y0 + 1

    t = dist / MAX_SHADE_DIST
    if t > 1.0:
      t = 1.0
    shade_idx = int((1.0 - t) * (SHADE_LEVELS - 1))

    # Choose palette based on what we hit
    if hit_tile == "D":
      col = DOOR_SHADES[shade_idx]
    else:
      col = WALL_SHADES[shade_idx]

    x = i * COL_W

    # Merge consecutive identical slices (must include col, y0, h)
    if run_col is None:
      run_col = col
      run_x = x
      run_w = COL_W
      run_y0 = y0
      run_h = h
    elif (col == run_col) and (y0 == run_y0) and (h == run_h) and (x == run_x + run_w):
      run_w += COL_W
    else:
      fill_rect(run_x, run_y0, run_w, run_h, run_col)
      run_col = col
      run_x = x
      run_w = COL_W
      run_y0 = y0
      run_h = h

  if run_col is not None:
    fill_rect(run_x, run_y0, run_w, run_h, run_col)

# -----------------------------
# Main loop
# -----------------------------
last = monotonic()

# Force an initial render
render()

while True:
  now = monotonic()
  dt = now - last
  last = now

  # --- Input ---
  turn = 0.0
  fwd = 0.0
  strafe = 0.0

  # NOTE: swapped behavior vs your original (fixes "reversed" feel)
  if keydown(KEY_LEFT):   turn += 1.0   # LEFT turns left
  if keydown(KEY_RIGHT):  turn -= 1.0   # RIGHT turns right
  if keydown(KEY_UP) or keydown(KEY_EIGHT):   fwd += 1.0
  if keydown(KEY_DOWN) or keydown(KEY_TWO):   fwd -= 1.0
  if keydown(KEY_FOUR):     strafe -= 1.0
  if keydown(KEY_SIX):    strafe += 1.0

  need_render = (turn != 0.0) or (fwd != 0.0) or (strafe != 0.0)

  # --- Update angle ---
  if turn != 0.0:
    ang = int((ang + turn * TURN_SPEED * dt)) % 360

  # --- Movement ---
  if (fwd != 0.0) or (strafe != 0.0):
    ca = COS[ang]
    sa = SIN[ang]

    # With angle=0 facing +Y, a convenient forward vector is:
    # forward = (-sin, cos)
    fwd_x = -sa
    fwd_y =  ca

    # Right vector is perpendicular:
    right_x = ca
    right_y = sa

    step = MOVE_SPEED * dt
    nx = px + (fwd * fwd_x + strafe * right_x) * step
    ny = py + (fwd * fwd_y + strafe * right_y) * step

    try_move(nx, ny)

  # --- Render only if changed (reduces flicker on hardware) ---
  if need_render:
    render()
