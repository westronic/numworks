"""
Golf Game for NumWorks N0120 (Epsilon/MicroPython)
Uses kandinsky for drawing and ion for input.
Screen: 320x222 pixels
"""

import kandinsky as k
import ion
import math
import time
#import gc

# Colors
C_DARK_GREEN  = (34,  85,  34)
C_FAIRWAY     = (80, 160,  60)
C_GREEN_PATCH = (127, 238, 127)
C_SAND        = (180, 150,  80)
C_SKY         = (135, 206, 235)
C_WHITE       = (255, 255, 255)
C_BLACK       = (0,   0,   0)
C_GRAY        = (100, 100, 100)
C_RED         = (160,  60,  60)
C_AIM         = (20,  20, 120)
C_GOLD        = (180, 150,  80)
C_YELLOW      = (240, 220,   0)
C_LGREEN      = (100, 200, 100)
C_WATER       = (30,  100, 200)

# Screen
SW, SH = 320, 222

# Keys
KEY_LEFT  = ion.KEY_LEFT
KEY_RIGHT = ion.KEY_RIGHT
KEY_UP    = ion.KEY_UP
KEY_DOWN  = ion.KEY_DOWN
KEY_OK    = ion.KEY_OK
KEY_EXE   = ion.KEY_EXE

# Clubs: parallel tuples (cheaper than list-of-tuples)
CLUB_NAMES = ("Driver", "Iron", "Wedge", "Putter")
CLUB_DISTS = (115, 60, 35, 15)
PUTTER_IDX = 3
NUM_CLUBS  = 4

# Terrain modifiers: tuples not lists
# Index: 0=Driver 1=Iron 2=Wedge 3=Putter
SAND_MOD  = (0.28, 0.50, 1.00, 0.40)
ROUGH_MOD = (0.65, 0.78, 0.88, 0.80)

# Shared rect sizes — only positions differ per hole
# 4 fairway sizes (w,h):
FW_SZ = ((200,40),(90,30),(80,55),(70,25))
# Fixed sand size:
SAND_W, SAND_H = 40, 22
# Fixed water size (second rect uses half-width for narrow-strip effect):
WAT_W, WAT_H = 60, 40
# Fixed green size and pin offset from green top-left:
GREEN_W, GREEN_H = 45, 28
PIN_OX, PIN_OY   = 34, 14

# Fixed tee position every hole
TEE_X, TEE_Y = 60, 115

# Green zoom view constants
GV_Y = 28
GV_H = SH - GV_Y

# Global score
SCORE = 0

# Hole data: plain tuples, no dicts or nested lists
# Format per hole:
#   ( ((fx0,fy0),(fx1,fy1),(fx2,fy2),(fx3,fy3)),  <- fairway positions (4)
#     (sx,sy) or None,                             <- sand position
#     (wx,wy) or None,                             <- water rect 1 position
#     (wx,wy) or None,                             <- water rect 2 position (half-width)
#     (gx,gy),                                     <- green position
#     par, wind_dx, wind_dy )
#
# Hole 1 - Par 5, no wind
# Wide fairway sweeping right then up toward green upper-right
H1 = (
    ((30,80),(130,55),(210,60),(240,100)),
    (190,115),
    None, None,
    (262,128),
    5, 0.0, 0.0
)
# Hole 2 - Par 4, 10 mph South
# Fairway bends upward; sand in middle; small stacked water lower-right
H2 = (
    ((40,105),(100,80),(165,58),(225,75)),
    (158,92),
    (238,138), (238,138),
    (258,58),
    4, 0.0, 12.0
)
# Hole 3 - Par 4, 15 mph NE
# Narrow fairway around large water body; two water rects share top edge
H3 = (
    ((40,112),(95,90),(205,52),(248,78)),
    (198,142),
    (105,58), (165,58),
    (260,82),
    5, 12.7, -12.7
)

# Active hole globals — set by load_hole()
g_fairway = []
g_sand_on = False
g_sand_x  = 0
g_sand_y  = 0
g_water   = []
g_green_x = 0
g_green_y = 0
g_pin_x   = 0
g_pin_y   = 0
g_par     = 4
g_wind_dx = 0.0
g_wind_dy = 0.0

def load_hole(hd):
    global g_fairway, g_sand_on, g_sand_x, g_sand_y
    global g_water, g_green_x, g_green_y, g_pin_x, g_pin_y
    global g_par, g_wind_dx, g_wind_dy
    fp, sp, w1, w2, gp, par, wdx, wdy = hd
    g_fairway = [
        (fp[0][0], fp[0][1], FW_SZ[0][0], FW_SZ[0][1]),
        (fp[1][0], fp[1][1], FW_SZ[1][0], FW_SZ[1][1]),
        (fp[2][0], fp[2][1], FW_SZ[2][0], FW_SZ[2][1]),
        (fp[3][0], fp[3][1], FW_SZ[3][0], FW_SZ[3][1]),
    ]
    if sp is not None:
        g_sand_on = True; g_sand_x = sp[0]; g_sand_y = sp[1]
    else:
        g_sand_on = False; g_sand_x = -999; g_sand_y = -999
    g_water = []
    if w1 is not None:
        g_water.append((w1[0], w1[1], WAT_W, WAT_H))
    if w2 is not None:
        g_water.append((w2[0], w2[1], WAT_W//2, WAT_H))
    g_green_x = gp[0]; g_green_y = gp[1]
    g_pin_x = gp[0] + PIN_OX
    g_pin_y = gp[1] + PIN_OY
    g_par = par; g_wind_dx = wdx; g_wind_dy = wdy

# Game state: flat globals, no dict
g_hole_idx    = 0
g_hole_num    = 1
g_stroke      = 0
g_club_idx    = 0
g_aim_angle   = -math.pi / 4
g_ball_x      = float(TEE_X)
g_ball_y      = float(TEE_Y)
g_prev_bx     = float(TEE_X)
g_prev_by     = float(TEE_Y)
g_last_acc    = 0.0
g_last_pwr    = 1.0
g_phase       = "map"
g_scene_bands = None
g_travel_tx   = 0.0
g_travel_ty   = 0.0

# Utility

def fill_rect(x, y, w, h, color):
    k.fill_rect(x, y, w, h, color)

def draw_text(text, x, y, fg, bg):
    k.draw_string(text, x, y, fg, bg)

def draw_plus(x, y, color, size=5):
    fill_rect(x-size, y-1, size*2+1, 3, color)
    fill_rect(x-1, y-size, 3, size*2+1, color)

def wait_for_ok():
    while not (ion.keydown(KEY_OK) or ion.keydown(KEY_EXE)):
        pass
    while ion.keydown(KEY_OK) or ion.keydown(KEY_EXE):
        pass

def key_pressed_once(key):
    if ion.keydown(key):
        while ion.keydown(key): pass
        return True
    return False

# Terrain queries

def on_green(mx, my):
    return g_green_x <= mx <= g_green_x+GREEN_W and g_green_y <= my <= g_green_y+GREEN_H

def on_sand(mx, my):
    if not g_sand_on: return False
    return g_sand_x <= mx <= g_sand_x+SAND_W and g_sand_y <= my <= g_sand_y+SAND_H

def on_water(mx, my):
    for r in g_water:
        if r[0] <= mx <= r[0]+r[2] and r[1] <= my <= r[1]+r[3]:
            return True
    return False

def on_fairway(mx, my):
    for r in g_fairway:
        if r[0] <= mx <= r[0]+r[2] and r[1] <= my <= r[1]+r[3]:
            return True
    return False

def on_rough(mx, my):
    if on_green(mx,my) or on_sand(mx,my) or on_water(mx,my) or on_fairway(mx,my):
        return False
    return True

def terrain_color(mx, my):
    if on_green(mx,my):   return C_GREEN_PATCH
    if on_water(mx,my):   return C_WATER
    if on_sand(mx,my):    return C_SAND
    if on_fairway(mx,my): return C_FAIRWAY
    return C_DARK_GREEN

# Map drawing

def draw_map_base():
    fill_rect(0, 0, SW, SH, C_DARK_GREEN)
    for r in g_fairway:
        fill_rect(r[0], r[1], r[2], r[3], C_FAIRWAY)
    for r in g_water:
        fill_rect(r[0], r[1], r[2], r[3], C_WATER)
    if g_sand_on:
        fill_rect(g_sand_x, g_sand_y, SAND_W, SAND_H, C_SAND)
    fill_rect(g_green_x, g_green_y, GREEN_W, GREEN_H, C_GREEN_PATCH)
    fill_rect(g_pin_x-1, g_pin_y-1, 3, 3, C_BLACK)

def draw_wind():
    fill_rect(SW-95, 0, 95, 16, C_BLACK)
    if   g_hole_num == 1: lbl = "0 mph"
    elif g_hole_num == 2: lbl = "10 mph S"
    else:                 lbl = "15 mph NE"
    draw_text(lbl, SW-93, 2, C_WHITE, C_BLACK)

def draw_hud(ay_hint):
    if ay_hint < SH-50:
        fill_rect(0, SH-40, 180, 40, C_BLACK)
        draw_text("Hole %d, Par %d"%(g_hole_num,g_par),       4,SH-38,C_WHITE, C_BLACK)
        draw_text("%d Strokes, %s"  %(g_stroke,CLUB_NAMES[g_club_idx]),4,SH-20,C_YELLOW,C_BLACK)
    else:
        fill_rect(0, 0, 180, 40, C_BLACK)
        draw_text("Hole %d, Par %d"%(g_hole_num,g_par),       4,2, C_WHITE, C_BLACK)
        draw_text("%d Strokes, %s"  %(g_stroke,CLUB_NAMES[g_club_idx]),4,20,C_YELLOW,C_BLACK)

def draw_map():
    bx = int(g_ball_x); by = int(g_ball_y)
    draw_map_base()
    fill_rect(bx-3, by-3, 7, 7, C_WHITE)
    gdx = -int(round(math.cos(g_aim_angle)*7))
    gdy = -int(round(math.sin(g_aim_angle)*7))
    fill_rect(bx+gdx-3, by+gdy-3, 7, 7, C_RED)
    dist = CLUB_DISTS[g_club_idx]
    if on_sand(g_ball_x, g_ball_y):   dist = dist * SAND_MOD[g_club_idx]
    elif on_rough(g_ball_x, g_ball_y): dist = dist * ROUGH_MOD[g_club_idx]
    ax = int(bx + dist*math.cos(g_aim_angle))
    ay = int(by + dist*math.sin(g_aim_angle))
    draw_plus(ax, ay, C_AIM)
    draw_hud(ay)
    draw_wind()
    if on_sand(g_ball_x, g_ball_y):
        pct = int(SAND_MOD[g_club_idx]*100)
        fill_rect(SW-100,SH-20,100,18,C_BLACK)
        draw_text("Sand %d%%"%pct, SW-98,SH-18,C_SAND,C_BLACK)
    elif on_rough(g_ball_x, g_ball_y):
        pct = int(ROUGH_MOD[g_club_idx]*100)
        fill_rect(SW-100,SH-20,100,18,C_BLACK)
        draw_text("Rough %d%%"%pct, SW-98,SH-18,C_FAIRWAY,C_BLACK)

def draw_map_no_aim():
    draw_map_base()
    fill_rect(0,SH-40,180,40,C_BLACK)
    draw_text("Hole %d, Par %d"%(g_hole_num,g_par),        4,SH-38,C_WHITE, C_BLACK)
    draw_text("%d Strokes, %s"  %(g_stroke,CLUB_NAMES[g_club_idx]),4,SH-20,C_YELLOW,C_BLACK)

# Map phase

def map_phase():
    global g_phase, g_aim_angle, g_club_idx
    if on_green(g_ball_x, g_ball_y):
        g_phase = "green"; return
    draw_map()
    while True:
        if ion.keydown(KEY_LEFT):
            g_aim_angle -= 0.05; draw_map(); time.sleep(0.05)
        elif ion.keydown(KEY_RIGHT):
            g_aim_angle += 0.05; draw_map(); time.sleep(0.05)
        elif key_pressed_once(KEY_DOWN):
            g_club_idx = (g_club_idx+1)%NUM_CLUBS; draw_map()
        elif key_pressed_once(KEY_UP):
            g_club_idx = (g_club_idx-1)%NUM_CLUBS; draw_map()
        elif ion.keydown(KEY_OK) or ion.keydown(KEY_EXE):
            while ion.keydown(KEY_OK) or ion.keydown(KEY_EXE): pass
            g_phase = "meters"; return

# Meters bar

def draw_meters_bar(acc, pwr):
    fill_rect(0, 0, SW, 28, (60,60,60))
    ax,ay,aw,ah = 5,3,140,22
    for i in range(aw):
        t = abs(i-aw//2)/(aw//2)
        g = int(200-100*t)
        fill_rect(ax+i,ay,1,ah,(g,g,g))
    fill_rect(ax,ay,aw,2,C_BLACK)
    fill_rect(ax,ay+ah-2,aw,2,C_BLACK)
    if acc is not None:
        mx = ax+int((acc+1)/2*aw)
        mx = max(ax,min(ax+aw-3,mx))
        fill_rect(mx,ay,3,ah,C_BLACK)
    px,py,pw,ph = 155,3,155,22
    sg = pw//4
    fill_rect(px,     py,sg,     ph,C_RED)
    fill_rect(px+sg,  py,sg,     ph,C_GOLD)
    fill_rect(px+sg*2,py,sg,     ph,C_YELLOW)
    fill_rect(px+sg*3,py,pw-sg*3,ph,C_LGREEN)
    fill_rect(px,py,pw,2,C_BLACK)
    fill_rect(px,py+ph-2,pw,2,C_BLACK)
    if pwr is not None:
        mx = px+int(pwr*pw)
        mx = max(px,min(px+pw-3,mx))
        fill_rect(mx,py,3,ph,C_BLACK)
    draw_text("AIM",50, 0,C_WHITE,(60,60,60))
    draw_text("PWR",205,0,C_WHITE,(60,60,60))

# 3D scene

def build_scene_bands():
    dist = CLUB_DISTS[g_club_idx]
    perp = g_aim_angle - math.pi/2
    bands = []
    for df in (0.05, 0.35, 0.65):
        row = []
        cx = g_ball_x + dist*df*math.cos(g_aim_angle)
        cy = g_ball_y + dist*df*math.sin(g_aim_angle)
        for lo in (-dist*0.35, 0.0, dist*0.35):
            row.append(terrain_color(cx+lo*math.cos(perp), cy+lo*math.sin(perp)))
        bands.append(row)
    return bands

def draw_3d_scene(acc=None, pwr=None, bands=None):
    fill_rect(0,30,SW,110,C_SKY)
    hy = 140
    fill_rect(0,hy,SW,SH-hy,C_DARK_GREEN)
    if bands is None:
        bands = [(C_FAIRWAY,C_FAIRWAY,C_FAIRWAY)]*3
    tops = (185,158,140)
    bots = (222,185,158)
    for bi in range(3):
        row = bands[bi]
        for y in range(tops[bi],bots[bi]):
            t  = (y-hy)/(222-hy)
            hw = int(SW//2*t+60*(1-t))
            xl = SW//2-hw
            tw = hw*2
            if tw <= 0: continue
            sg = tw//3
            fill_rect(xl,     y,sg,     1,row[0])
            fill_rect(xl+sg,  y,sg,     1,row[1])
            fill_rect(xl+sg*2,y,tw-sg*2,1,row[2])
    fill_rect(SW//2-5,196,10,10,C_WHITE)
    draw_meters_bar(acc,pwr)

# Meters phase

def meters_phase():
    global g_phase, g_last_acc, g_last_pwr, g_scene_bands
    g_scene_bands = build_scene_bands()
    draw_3d_scene(bands=g_scene_bands)
    acc=0.0; d=1
    while True:
        acc += d*0.12
        if acc>1.0:  acc=1.0;  d=-1
        elif acc<-1.0: acc=-1.0; d=1
        draw_meters_bar(acc,None)
        if ion.keydown(KEY_OK) or ion.keydown(KEY_EXE):
            while ion.keydown(KEY_OK) or ion.keydown(KEY_EXE): pass
            g_last_acc=acc; break
        time.sleep(0.02)
    pwr=0.0; d=1
    while True:
        pwr += d*0.05625
        if pwr>=1.0: pwr=1.0; d=-1
        elif pwr<=0.0: pwr=0.0; d=1
        draw_meters_bar(g_last_acc,pwr)
        if ion.keydown(KEY_OK) or ion.keydown(KEY_EXE):
            while ion.keydown(KEY_OK) or ion.keydown(KEY_EXE): pass
            g_last_pwr=pwr; break
        time.sleep(0.02)
    g_phase="motion"

# Motion phase

def motion_phase():
    global g_phase, g_travel_tx, g_travel_ty
    acc=g_last_acc; pwr=g_last_pwr
    bsx=SW//2; bsy=196
    wsd=g_wind_dx*pwr*0.3
    steps=40
    for i in range(steps+1):
        t=i/steps
        drift=acc*40*t+wsd*t
        bx=bsx+int(drift)
        ah=80*pwr
        vert=int(ah*4*t*(1-t))
        syb=bsy-int((bsy-145)*t)
        bsz=max(2,int(10*(1-t*0.7)))
        draw_3d_scene(acc=g_last_acc,pwr=g_last_pwr,bands=g_scene_bands)
        for j in range(i):
            tj=j/steps
            dj=acc*40*tj+wsd*tj
            xj=bsx+int(dj)
            vj=int(ah*4*tj*(1-tj))
            sj=bsy-int((bsy-145)*tj)-vj
            fill_rect(xj,sj,2,2,C_GRAY)
        fill_rect(bx-bsz//2,syb-vert-bsz//2,bsz,bsz,C_WHITE)
        time.sleep(0.04)
    dist=CLUB_DISTS[g_club_idx]*pwr
    if on_sand(g_ball_x,g_ball_y):    dist*=SAND_MOD[g_club_idx]
    elif on_rough(g_ball_x,g_ball_y): dist*=ROUGH_MOD[g_club_idx]
    ang=g_aim_angle+acc*0.3
    nx=g_ball_x+dist*math.cos(ang)+g_wind_dx*pwr
    ny=g_ball_y+dist*math.sin(ang)+g_wind_dy*pwr
    g_travel_tx=max(5.0,min(SW-5.0,nx))
    g_travel_ty=max(5.0,min(SH-5.0,ny))
    g_phase="ball_travel"

# Ball travel phase

def ball_travel_phase():
    global g_phase,g_ball_x,g_ball_y,g_prev_bx,g_prev_by,g_stroke
    bx0=g_ball_x; by0=g_ball_y
    tx=g_travel_tx; ty=g_travel_ty
    for i in range(21):
        t=i/20
        cx=bx0+(tx-bx0)*t; cy=by0+(ty-by0)*t
        draw_map_no_aim()
        fill_rect(int(cx)-2,int(cy)-2,5,5,C_WHITE)
        time.sleep(0.04)
    if on_water(tx,ty):
        g_stroke+=2
        g_ball_x=g_prev_bx; g_ball_y=g_prev_by
        fill_rect(SW//2-50,SH//2-10,100,20,C_BLACK)
        draw_text("Water! +1",SW//2-40,SH//2-8,C_WATER,C_BLACK)
        time.sleep(1.0)
        g_phase="map"
    else:
        g_prev_bx=bx0; g_prev_by=by0
        g_ball_x=tx; g_ball_y=ty
        g_stroke+=1
        g_phase="green" if on_green(tx,ty) else "map"

# Green phase

def map_to_gs(mx,my):
    ox=(SW-GREEN_W*7)//2
    return ox+int((mx-g_green_x)*7), GV_Y+int((my-g_green_y)*7)

def draw_green_view(show_aim):
    zw=GREEN_W*7; zh=GREEN_H*7
    ox=(SW-zw)//2
    fill_rect(0,GV_Y,SW,GV_H,C_DARK_GREEN)
    fill_rect(ox,GV_Y,zw,zh,C_GREEN_PATCH)
    hsx,hsy=map_to_gs(g_pin_x,g_pin_y)
    fill_rect(hsx-3,hsy-3,7,7,C_BLACK)
    gsx,gsy=map_to_gs(g_ball_x,g_ball_y)
    fill_rect(gsx-3,gsy-3,7,7,C_WHITE)
    gdx=-int(round(math.cos(g_aim_angle)*7))
    gdy=-int(round(math.sin(g_aim_angle)*7))
    fill_rect(gsx+gdx-3,gsy+gdy-3,7,7,C_RED)
    if show_aim:
        ds=CLUB_DISTS[g_club_idx]*7
        ax=int(gsx+ds*math.cos(g_aim_angle))
        ay=int(gsy+ds*math.sin(g_aim_angle))
        draw_plus(ax,ay,C_AIM)
        for frac,col in ((0.25,C_RED),(0.50,C_GOLD),(0.75,C_YELLOW)):
            draw_plus(int(gsx+ds*frac*math.cos(g_aim_angle)),
                      int(gsy+ds*frac*math.sin(g_aim_angle)),col,size=3)
        if ay<SH-50 and (gsy<SH-50 or gsx>2*SW//3):
            fill_rect(0,SH-40,180,40,C_BLACK)
            draw_text("Hole %d, Par %d"%(g_hole_num,g_par),4,SH-38,C_WHITE,C_BLACK)
            draw_text("%d Strokes, %s"%(g_stroke,CLUB_NAMES[g_club_idx]),4,SH-20,C_YELLOW,C_BLACK)
        else:
            fill_rect(0,30,180,40,C_BLACK)
            draw_text("Hole %d, Par %d"%(g_hole_num,g_par),4,32,C_WHITE,C_BLACK)
            draw_text("%d Strokes, %s"%(g_stroke,CLUB_NAMES[g_club_idx]),4,50,C_YELLOW,C_BLACK)
    draw_meters_bar(None,None)

def green_phase():
    global g_phase,g_club_idx,g_aim_angle
    g_club_idx=PUTTER_IDX
    draw_green_view(True)
    while True:
        if ion.keydown(KEY_LEFT):
            g_aim_angle-=0.05; draw_green_view(True); time.sleep(0.05)
        elif ion.keydown(KEY_RIGHT):
            g_aim_angle+=0.05; draw_green_view(True); time.sleep(0.05)
        elif key_pressed_once(KEY_DOWN):
            g_club_idx=(g_club_idx+1)%NUM_CLUBS; draw_green_view(True)
        elif key_pressed_once(KEY_UP):
            g_club_idx=(g_club_idx-1)%NUM_CLUBS; draw_green_view(True)
        elif ion.keydown(KEY_OK) or ion.keydown(KEY_EXE):
            while ion.keydown(KEY_OK) or ion.keydown(KEY_EXE): pass
            g_phase="green_meters"; return

def green_meters_phase():
    global g_phase,g_last_acc,g_last_pwr
    draw_green_view(False)
    acc=0.0; d=1
    while True:
        acc+=d*0.12
        if acc>1.0: acc=1.0; d=-1
        elif acc<-1.0: acc=-1.0; d=1
        draw_meters_bar(acc,None)
        if ion.keydown(KEY_OK) or ion.keydown(KEY_EXE):
            while ion.keydown(KEY_OK) or ion.keydown(KEY_EXE): pass
            g_last_acc=acc; break
        time.sleep(0.02)
    pwr=0.0; d=1
    while True:
        pwr+=d*0.05625
        if pwr>=1.0: pwr=1.0; d=-1
        elif pwr<=0.0: pwr=0.0; d=1
        draw_meters_bar(g_last_acc,pwr)
        if ion.keydown(KEY_OK) or ion.keydown(KEY_EXE):
            while ion.keydown(KEY_OK) or ion.keydown(KEY_EXE): pass
            g_last_pwr=pwr; break
        time.sleep(0.02)
    g_phase="green_putt"

def green_putt_phase():
    global g_phase,g_ball_x,g_ball_y,g_stroke
    dist=CLUB_DISTS[g_club_idx]*g_last_pwr
    ang=g_aim_angle+g_last_acc*0.3
    bx0=g_ball_x; by0=g_ball_y
    nx=bx0+dist*math.cos(ang); ny=by0+dist*math.sin(ang)
    for i in range(21):
        t=i/20
        cx=bx0+(nx-bx0)*t; cy=by0+(ny-by0)*t
        draw_green_view(False)
        gsx,gsy=map_to_gs(cx,cy)
        fill_rect(gsx-2,gsy-2,5,5,C_WHITE)
        time.sleep(0.05)
    g_ball_x=nx; g_ball_y=ny
    g_stroke+=1
    g_phase="green" if on_green(nx,ny) else "map"

# Main loop

def reset_hole(idx):
    global g_hole_idx,g_hole_num,g_stroke,g_club_idx,g_aim_angle
    global g_ball_x,g_ball_y,g_prev_bx,g_prev_by,g_phase
    load_hole((H1,H2,H3)[idx])
    g_hole_idx=idx; g_hole_num=idx+1
    g_stroke=0; g_club_idx=0; g_aim_angle=-math.pi/4
    g_ball_x=float(TEE_X); g_ball_y=float(TEE_Y)
    g_prev_bx=float(TEE_X); g_prev_by=float(TEE_Y)
    g_phase="map"

def main():
    global g_phase, SCORE
    #gc.collect()
    reset_hole(0)
    while True:
        if   g_phase=="map":          map_phase()
        elif g_phase=="meters":       meters_phase()
        elif g_phase=="motion":       motion_phase()
        elif g_phase=="ball_travel":  ball_travel_phase()
        elif g_phase=="green":        green_phase()
        elif g_phase=="green_meters": green_meters_phase()
        elif g_phase=="green_putt":   green_putt_phase()
        # Win check: squared distance avoids sqrt
        dx=g_ball_x-g_pin_x; dy=g_ball_y-g_pin_y
        if dx*dx+dy*dy < 9:
            SCORE += g_stroke - g_par
            fill_rect(0,0,SW,SH,C_BLACK)
            if g_stroke == g_par + 2:
              draw_text("Double Bogey.",85,70,C_RED,C_BLACK)
            elif g_stroke == g_par + 1:
              draw_text("Bogey.",125,70,C_RED,C_BLACK)
            elif g_stroke == g_par:
              draw_text("Par!",130,70,C_WHITE,C_BLACK)
            elif g_stroke == g_par - 1:
              draw_text("Birdie!",120,70,C_FAIRWAY,C_BLACK)
            elif g_stroke == g_par - 2:
              draw_text("Eagle!",125,70,C_LGREEN,C_BLACK)
            draw_text("Hole %d: %d strokes"%(g_hole_num,g_stroke),50,90,C_YELLOW,C_BLACK)
            draw_text("Par %d"%g_par,120,110,C_WHITE,C_BLACK)
            draw_text("Score: %d"%SCORE,105,130,C_WHITE,C_BLACK)
            wait_for_ok()
            nxt=g_hole_idx+1
            if nxt>=3:
                fill_rect(0,0,SW,SH,C_BLACK)
                draw_text("Final Score: %d"%SCORE,80,100,C_YELLOW,C_BLACK)
                draw_text("Press OK to exit",70,120,C_WHITE,C_BLACK)
                wait_for_ok()
                break
            reset_hole(nxt)

main()
