# Pseudo-3D Driving Sim (NumWorks / Epsilon Python)
# Resolution: 320x240
# Only redraws when driving forward or strafing (prevents flicker)
# Trees spawn farther out (Option A) so they spread out more and overlap less.

import kandinsky as kd
import ion
import time
import random

W, H = 320, 240
HORIZON_Y = H // 2

MAX_ROAD_SEGS = 48
MIN_ROAD_HALF_W = 6
MAX_ROAD_HALF_W = 140
ROAD_X_LIMIT = 180.0
CLOCK = 0

road_target_x = 0.0
target_timer = 0.0   # counts down while moving

MAX_TREES = 6
MAX_CLOUDS = 20

SKY = [0x99, 0xDD, 0xFF]
SKY_DIR = -1  # start by darkening the sky

SKY_MIN = [0x10, 0x02, 0x40]  # "night" (tune)
SKY_MAX = [0x99, 0xDD, 0xFF]  # "day"

GRASS = (0x22, 0xAA, 0x33)
ROAD = (0x77, 0x77, 0x77)
LANE = (0xDD, 0xDD, 0xDD)
TRUNK = (0x8B, 0x5A, 0x2B)
LEAVES = (0x22, 0x8B, 0x22)
BLACK = (0, 0, 0)
WHITE = (0xFF, 0xFF, 0xFF)

def clamp_inclusive(x, a, b):
  if x < a: return a
  if x > b: return b
  return x
  
def clamp_index(x, limit):
  # clamps to [0, limit-1]
  if x < 0: return 0
  if x >= limit: return limit - 1
  return x

def persp(z):
  # Cheap but convincing. Try z*z*z for stronger depth.
  return z * z

def screen_y(z):
  p = persp(z)
  return HORIZON_Y + int(p * (H // 2))
    
def screen_y_sky(z):
  p = persp(z)
  top = 10
  bottom = HORIZON_Y - 1
  return int(top + (bottom - top) * (1 - p))

def road_half_w(z):
  p = persp(z)
  return MIN_ROAD_HALF_W + p * (MAX_ROAD_HALF_W - MIN_ROAD_HALF_W)

def screen_x_from_world(x_world, z, camera_x):
  p = persp(z)
  scale = 0.25 + 1.75 * p  # small at horizon, larger near bottom
  return (W // 2) + int((x_world - camera_x) * scale)

def draw_background():
  kd.fill_rect(0, 0, W, HORIZON_Y, SKY)
  kd.fill_rect(0, HORIZON_Y, W, H - HORIZON_Y, GRASS)
  kd.fill_rect(0, HORIZON_Y, W, 1, BLACK)

def fill_trapezoid_scanlines(y0, l0, r0, y1, l1, r1, color):
  # Draw using 1px scanlines
  if y1 < y0:
    y0, y1 = y1, y0
    l0, l1 = l1, l0
    r0, r1 = r1, r0

  if y1 == y0:
    return

  if y1 < 0 or y0 >= H:
    return

  y0i = clamp_index(int(y0), H)
  y1i = clamp_index(int(y1), H)

  dy = (y1 - y0)
  if dy == 0:
    return
  for y in range(y0i, y1i + 1):
    t = (y - y0) / dy
    l = l0 + t * (l1 - l0)
    r = r0 + t * (r1 - r0)
    if r < l:
      l, r = r, l

    x0 = clamp_index(int(l), W)
    x1 = clamp_index(int(r), W)
    if x1 >= x0:
      kd.fill_rect(int(x0), int(y), int(x1 - x0 + 1), 1, color)

# -------------------------
# State
# -------------------------
road = []   # each: [z, cx_world]
trees = []  # each: [z, x_world]
clouds = []  # each: [z, x_world]
camera_x = 0.0

road_gen_x = 0.0
road_gen_v = 0.0

speed = 0.0
target = 0.0

def reset_world():
  global road, trees, camera_x, road_gen_x, road_gen_v, speed, road_target_x, target_timer
  camera_x = 0.0
  road_gen_x = 0.0
  road_gen_v = 0.0
  road_target_x = 0.0
  target_timer = 1.0   # hold straight for the first ~1.0 "dz units"
  speed = 0.0

  # Prefill a straight road so player starts on it
  road = []
  for i in range(MAX_ROAD_SEGS):
    z = i / (MAX_ROAD_SEGS - 1)
    road.append([z, 0.0])

  trees = []
  clouds = []

def ensure_spawn_road_segment():
  global road, road_gen_x, road_gen_v

  if not road:
    road.append([0.0, road_gen_x])
    return

  # Find nearest segment to horizon
  min_z = min(seg[0] for seg in road)

  # If the nearest segment has moved forward enough, spawn another at z=0
  if min_z > 0.03 and len(road) < MAX_ROAD_SEGS:
    # Curvature drift
    # accel = random.uniform(-0.35, 0.35)
    # road_gen_v = clamp_inclusive(road_gen_v + accel, -1.6, 1.6)
    # road_gen_x = clamp_inclusive(road_gen_x + road_gen_v, -180.0, 180.0)

    road.append([0.0, road_gen_x])

def step_road(dz):
  global road
  if dz <= 0:
    return

  for seg in road:
    seg[0] += dz

  # remove beyond view
  road = [seg for seg in road if seg[0] <= 1.02]

  ensure_spawn_road_segment()

def try_spawn_tree():
  global trees

  if len(trees) >= MAX_TREES:
    return False

  # Spawn at horizon, off road at spawn time only (Option A: farther out)
  rc = road_gen_x
  w = road_half_w(0.0)

  # Increased buffer + distance so trees spread out more
  margin = w + 30
  side = -1 if random.getrandbits(1) == 0 else 1
  x = rc + side * (margin + random.uniform(60, 180))

  trees.append([0.0, x])
  return True
  
def try_spawn_cloud():
  global clouds

  if len(clouds) >= MAX_CLOUDS:
    return False

  # Spawn at horizon
  rc = road_gen_x
  w = road_half_w(0.0)

  # Increased buffer + distance so clouds spread out more
  side = -1 if random.getrandbits(1) == 0 else 1
  x = rc + side * (random.uniform(60, 360))

  clouds.append([0.0, x])
  return True

def step_trees(dz):
  global trees
  if dz <= 0:
    return

  for t in trees:
    t[0] += dz

  trees = [t for t in trees if t[0] <= 1.02]

  # chance spawn while moving
  if random.random() < 0.06:
    try_spawn_tree()
    
def step_clouds(dz):
  global clouds
  if dz <= 0:
    return

  for t in clouds:
    t[0] += dz * 0.01

  clouds = [c for c in clouds if c[0] <= 1.02]

  # chance spawn while moving
  if random.random() < 0.02:
    try_spawn_cloud()
    
def update_road_steering(dz):
  global road_gen_x, road_gen_v, road_target_x, target_timer

  if dz <= 0:
    return

  # How often we pick a new "curve goal"
  target_timer -= dz
  if target_timer <= 0:
    # Hold this target for a bit (bigger = longer curves)
    target_timer = random.uniform(1.80, 2.40)

    # Choose a new target near the current position (prevents wild jumps)
    road_target_x = clamp_inclusive(
      road_gen_x + random.uniform(-120.0, 120.0),
      -ROAD_X_LIMIT, ROAD_X_LIMIT
    )

  # Steering dynamics (tune these)
  k = 0.82      # steering strength (higher = snaps to target faster)
  damping = 0.32  # velocity damping (lower = more “floaty”, higher = more stable)

  # Accelerate toward target like a spring
  error = (road_target_x - road_gen_x)
  road_gen_v = road_gen_v * damping + error * k

  # Limit max lateral speed so it doesn't whip
  road_gen_v = clamp_inclusive(road_gen_v, -2.2, 2.2)

  # Move road generator
  road_gen_x += road_gen_v
  road_gen_x = clamp_inclusive(road_gen_x, -ROAD_X_LIMIT, ROAD_X_LIMIT)

def draw_road():
  if len(road) < 2:
    return

  # sort far->near
  road.sort(key=lambda s: s[0])

  for i in range(len(road) - 1):
    za, cxa_world = road[i]
    zb, cxb_world = road[i + 1]

    ya = screen_y(za)
    yb = screen_y(zb)

    wa = road_half_w(za)
    wb = road_half_w(zb)

    cxa = screen_x_from_world(cxa_world, za, camera_x)
    cxb = screen_x_from_world(cxb_world, zb, camera_x)

    la = cxa - wa
    ra = cxa + wa
    lb = cxb - wb
    rb = cxb + wb

    fill_trapezoid_scanlines(ya, la, ra, yb, lb, rb, ROAD)

    # center dashes (cheap)
    if (i % 4) == 0:
      xm = (cxa + cxb) // 2
      ym = (ya + yb) // 2
      kd.fill_rect(xm - 1, ym - 1, 3, 3, LANE)

def draw_trees():
  # Trees drawn AFTER road so they appear in front.
  for z, xw in reversed(trees):
    p = persp(z)
    x = screen_x_from_world(xw, z, camera_x)
    y = screen_y(z)

    h = int(6 + p * 60)
    w = int(6 + p * 60)

    if h <= 2:
      kd.fill_rect(x, y, 2, 2, LEAVES)
      continue

    trunk_w = w // 5 + 2
    trunk_h = h // 2
    kd.fill_rect(int(x - trunk_w // 2), int(y - trunk_h), int(trunk_w), int(trunk_h), TRUNK)

    fol_w = w
    fol_h = h // 2
    kd.fill_rect(int(x - fol_w // 2), int(y - trunk_h - fol_h), int(fol_w), int(fol_h), LEAVES)
    kd.fill_rect(int(x - fol_w // 3), int(y - trunk_h - 2*fol_h), int(2*fol_w // 3), int(2*fol_h), LEAVES)
    kd.fill_rect(int(x - fol_w // 5), int(y - trunk_h - 3*fol_h), int(2*fol_w // 5), int(3*fol_h), LEAVES)

def draw_clouds():
  for z, xw in clouds:
    p = persp(z)
    x = screen_x_from_world(xw, z, camera_x * 0.1)
    y = screen_y_sky(z)

    h = 0.25 * int(6 + p * 60)
    w = int(6 + p * 60)

    if h <= 2:
      kd.fill_rect(x, y, 2, 2, WHITE)
      continue
    
    clo_w = w
    clo_h = h // 2
    kd.fill_rect(int(x - clo_w // 2), int(y - clo_h), int(clo_w), int(clo_h), WHITE)

def update_sky():
  global SKY, SKY_DIR

  # Only update every N frames
  if CLOCK % 50 != 0:
    return False

  old0, old1, old2 = SKY[0], SKY[1], SKY[2]

  # Step sizes
  dr = 0x02
  dg = 0x01
  db = 0x01

  SKY[0] += SKY_DIR * dr
  SKY[1] += SKY_DIR * dg
  SKY[2] += SKY_DIR * db

  # Clamp
  SKY[0] = clamp_inclusive(SKY[0], SKY_MIN[0], SKY_MAX[0])
  SKY[1] = clamp_inclusive(SKY[1], SKY_MIN[1], SKY_MAX[1])
  SKY[2] = clamp_inclusive(SKY[2], SKY_MIN[2], SKY_MAX[2])

  # Reverse at endpoints
  if SKY == SKY_MIN:
    SKY_DIR = +1
  elif SKY == SKY_MAX:
    SKY_DIR = -1

  # Did anything actually change?
  return (SKY[0] != old0 or SKY[1] != old1 or SKY[2] != old2)

def handle_input():
  global speed, camera_x, target

  changed = False

  up = ion.keydown(ion.KEY_UP)
  left = ion.keydown(ion.KEY_LEFT)
  right = ion.keydown(ion.KEY_RIGHT)
  down = ion.keydown(ion.KEY_DOWN)
  
  if down: target -= 0.002
  if up and speed < 0.35: target += 0.001

  new_speed = speed + (target - speed) * 0.25
  if abs(new_speed - speed) > 1e-4:
    speed = new_speed
    changed = True
    
  if target < 0:
    target = 0.0
    speed = 0.0

  strafe = 0
  if left: strafe -= 1
  if right: strafe += 1

  if strafe != 0:
    camera_x += strafe * (2.8 + 40.0 * speed)
    changed = True

  return changed

def main():
  global SKY, CLOCK
  reset_world()

  # Deterministic seed; change/remove if you prefer
  random.seed(12345)

  # First draw
  draw_background()
  draw_clouds()
  draw_road()
  draw_trees()

  while True:
  CLOCK += 1

  input_changed = handle_input()
  world_changed = False

  if speed > 0:
    update_road_steering(speed)
    step_road(speed)
    step_trees(speed)
    step_clouds(speed)
    world_changed = True

  sky_changed = update_sky()

  if input_changed or world_changed or sky_changed:
    draw_background()
    draw_clouds()
    draw_road()
    draw_trees()

  time.sleep(0.02)

main()

