# Ludo King style game V11 - Python 3 + pygame (works in Pydroid 3, on a laptop, desktop and TV)
# Install pygame first: Pydroid 3 menu > Pip > pygame   (computer: pip install pygame)

import pygame
import random
import sys
import math
import array
import os
import json
import time

pygame.mixer.pre_init(22050, -16, 1, 512)
pygame.init()

# ---------- Screen ----------
IS_ANDROID = 'ANDROID_ROOT' in os.environ or 'ANDROID_DATA' in os.environ
info = pygame.display.Info()
DW, DH = info.current_w, info.current_h
MAX_SIDE = 1800          # the game never draws more than this on its long side; very big screens (4K TVs) are scaled up smoothly
rs = min(1.0, MAX_SIDE / float(max(DW, DH)))
screen = None
if rs < 1.0 and (rs < 0.6 or not IS_ANDROID):
    try:
        screen = pygame.display.set_mode((int(DW * rs), int(DH * rs)), pygame.SCALED)
    except Exception:
        screen = None
if screen is None:
    screen = pygame.display.set_mode((DW, DH))
W, H = screen.get_size()
pygame.display.set_caption('Ludo')
clock = pygame.time.Clock()
FS = 1.0                 # length of the last frame in 1/60 second units: keeps every animation smooth on slow or fast devices
text_cache = {}
jobs = []                # slow jobs (sounds, pictures) that run a little bit in every frame, so nothing freezes


def render_text(fnt, text, colour):
    key = (id(fnt), text, colour)
    s = text_cache.get(key)
    if s is None:
        if len(text_cache) > 400:
            text_cache.clear()
        s = text_cache[key] = fnt.render(text, True, colour)
    return s


def pump_jobs(budget=0.005):
    t0 = time.perf_counter()
    while jobs and time.perf_counter() - t0 < budget:
        try:
            next(jobs[0])
        except StopIteration:
            jobs.pop(0)
        except Exception:
            jobs.pop(0)


# ---------- Layout: board a bit lower, one separate dice for every colour ----------
def layout(cell):
    ds = int(cell * 2.4)                      # size of every dice pad
    gap = int(cell * 0.4)
    bw = cell * 15
    ox = (W - bw) // 2
    if ox >= ds + 2 * gap:
        # wide screen: the dice stand beside the board, next to their own corner
        free = H - bw
        oy = int(min(max(cell * 2.6, free * 0.7), free - cell * 0.2))
        lx, rx = ox - ds - gap, ox + bw + gap
        ty = oy + int(cell * 0.8)
        by = oy + bw - ds - int(cell * 0.8)
        my = (ty + by) // 2
        pos4 = [(lx, ty), (rx, ty), (rx, by), (lx, by)]
        pos6 = [(lx, ty), (rx, ty), (rx, my), (rx, by), (lx, by), (lx, my)]
        msg = (W // 2, int(oy - cell * 0.85), bw)
        msg4 = msg6 = msg
        ok = oy >= cell * 1.8 and oy + bw < H
    else:
        # tall screen (phone): dice above and below the board
        top_need = int(cell * 5.2)
        bot_need = ds + gap + int(cell * 2.8)
        spare = H - bw - top_need - bot_need
        oy = top_need + int(max(0, spare) * 0.35)
        lx, rx = ox, ox + bw - ds
        cx = ox + (bw - ds) // 2
        top_y = oy - ds - gap
        bot_y = oy + bw + gap
        pos4 = [(lx, top_y), (rx, top_y), (rx, bot_y), (lx, bot_y)]
        pos6 = [(lx, top_y), (cx, top_y), (rx, top_y), (rx, bot_y), (cx, bot_y), (lx, bot_y)]
        msg4 = (W // 2, bot_y + ds // 2, bw - 2 * (ds + gap))
        msg6 = (W // 2, bot_y + ds + int(cell * 1.7), bw)
        ok = spare >= 0
    return ox, oy, ds, pos4, pos6, msg4, msg6, ok


CELL = int(min(W * 0.98, H * 0.85) // 15)      # biggest board that fits the screen
while True:
    OX, OY, DS, POS4, POS6, MSG4, MSG6, fits = layout(CELL)
    if fits or CELL <= 20:
        break
    CELL -= 1
SIDE_LAYOUT = OX >= DS + 2 * int(CELL * 0.4)     # dice beside the board (wide screen) or above and below it (phone)
K = CELL / 72.0                  # size factor for sparkles and confetti

font = pygame.font.SysFont(None, int(CELL * 0.9))
small_font = pygame.font.SysFont(None, int(CELL * 0.7))
tiny_font = pygame.font.SysFont(None, int(CELL * 0.5))
tag_font = pygame.font.SysFont(None, int(CELL * 0.62))
big_font = pygame.font.SysFont(None, int(CELL * 1.6))
title_font = pygame.font.SysFont(None, int(CELL * 2.8))
overlay_surf = pygame.Surface((W, H))
overlay_surf.fill((0, 0, 0))
flash_surf = pygame.Surface((W, H))
flash_surf.fill((255, 255, 255))

# ---------- Colours (six players) ----------
RED = (225, 50, 50)
GREEN = (45, 175, 80)
YELLOW = (250, 205, 40)
BLUE = (50, 100, 225)
PURPLE = (150, 80, 205)
ORANGE = (255, 140, 30)
WHITE = (255, 255, 255)
BLACK = (20, 20, 20)
GOLD = (255, 215, 0)
BOARD_BG = (250, 245, 230)
COLOURS = [RED, GREEN, YELLOW, BLUE, PURPLE, ORANGE]
LIGHT = [(255, 170, 170), (170, 235, 190), (255, 240, 170), (170, 200, 255), (222, 190, 245), (255, 210, 160)]
DEFAULT_NAMES = ['Red', 'Green', 'Yellow', 'Blue', 'Purple', 'Orange']
NAMES = list(DEFAULT_NAMES)        # the first name becomes the player's own name during a game
# players that are not playing keep their own colour, only darker (never black)
DARK = [tuple(int(c * 0.55) for c in col) for col in COLOURS]
DARK_LIGHT = [tuple(int(c * 0.55) for c in col) for col in LIGHT]
RAINBOW = [(255, 80, 80), (255, 170, 40), (255, 230, 60), (90, 220, 110), (80, 170, 255), (190, 110, 255)]
TRI = [(28, 168, 96), (255, 96, 172), (214, 38, 64)]     # welcome page: green, pink, red

# ---------- The 4-colour board (2, 3 and 4 players) ----------
CLASSIC_PATH = [
    (1,6),(2,6),(3,6),(4,6),(5,6),
    (6,5),(6,4),(6,3),(6,2),(6,1),(6,0),
    (7,0),(8,0),
    (8,1),(8,2),(8,3),(8,4),(8,5),
    (9,6),(10,6),(11,6),(12,6),(13,6),(14,6),
    (14,7),(14,8),
    (13,8),(12,8),(11,8),(10,8),(9,8),
    (8,9),(8,10),(8,11),(8,12),(8,13),(8,14),
    (7,14),(6,14),
    (6,13),(6,12),(6,11),(6,10),(6,9),
    (5,8),(4,8),(3,8),(2,8),(1,8),(0,8),
    (0,7),(0,6),
]
CLASSIC_HOME = [
    [(1,7),(2,7),(3,7),(4,7),(5,7)],
    [(7,1),(7,2),(7,3),(7,4),(7,5)],
    [(13,7),(12,7),(11,7),(10,7),(9,7)],
    [(7,13),(7,12),(7,11),(7,10),(7,9)],
]
CLASSIC_BASE = [
    [(1.5,1.5),(3.5,1.5),(1.5,3.5),(3.5,3.5)],
    [(10.5,1.5),(12.5,1.5),(10.5,3.5),(12.5,3.5)],
    [(10.5,10.5),(12.5,10.5),(10.5,12.5),(12.5,12.5)],
    [(1.5,10.5),(3.5,10.5),(1.5,12.5),(3.5,12.5)],
]
# Every colour has its own 4 parking spots in its own triangle of the centre,
# so finished stick men never overlap or merge (offsets from the centre, in boxes)
CLASSIC_SLOTS = [
    [(-1.15, -0.32), (-1.15, 0.32), (-0.62, -0.3), (-0.62, 0.3)],    # Red (left triangle)
    [(-0.3, -1.0), (0.3, -1.0), (-0.25, -0.4), (0.25, -0.4)],        # Green (top triangle)
    [(1.15, -0.32), (1.15, 0.32), (0.62, -0.3), (0.62, 0.3)],        # Yellow (right triangle)
    [(-0.3, 1.3), (0.3, 1.3), (-0.25, 0.7), (0.25, 0.7)],            # Blue (bottom triangle)
]

# ---------- The 6-arm star board (5 and 6 players) ----------
HEX_N, HEX_TH0, HEX_T0, HEX_U = 6, 210.0, 3.0, 0.84


def hex_arm(k):
    return math.radians(HEX_TH0 + 360.0 / HEX_N * k)


def hex_point(k, t, lane):
    # a spot on arm k: t boxes out from the middle, lane -1 / 0 / +1 across the arm
    th = hex_arm(k)
    dx, dy = math.cos(th), math.sin(th)
    return (round(7 + (t * dx - lane * dy) * HEX_U, 6), round(7 + (t * dy + lane * dx) * HEX_U, 6))


def build_hex_board():
    n, t0, u = HEX_N, HEX_T0, HEX_U
    path, ang = [], []
    for q in range(n):                              # the same 13-box pattern for every arm
        a, b = q, (q + 1) % n
        for j in range(4, -1, -1):
            path.append(hex_point(a, t0 + j, 1))
            ang.append(hex_arm(a))
        for j in range(6):
            path.append(hex_point(b, t0 + j, -1))
            ang.append(hex_arm(b))
        path.append(hex_point(b, t0 + 5, 0))
        ang.append(hex_arm(b))
        path.append(hex_point(b, t0 + 5, 1))
        ang.append(hex_arm(b))
    home = [[hex_point(k, t0 + j, 0) for j in range(4, -1, -1)] for k in range(n)]
    base, base_c, slots = [], [], []
    for k in range(n):
        phi = hex_arm(k) + math.pi / n               # the gap between arm k and the next arm
        rx, ry = math.cos(phi), math.sin(phi)
        tx, ty = -ry, rx
        bc = (7 + rx * 6.5 * u, 7 + ry * 6.5 * u)
        base_c.append(bc)
        base.append([(bc[0] + (a * rx + b * tx) * 0.62 * u, bc[1] + (a * ry + b * ty) * 0.62 * u)
                     for a, b in ((-1, -1), (1, -1), (-1, 1), (1, 1))])
        th = hex_arm(k)
        ox, oy = math.cos(th), math.sin(th)
        px, py = -oy, ox
        slots.append([((r * ox + l * px) * u, (r * oy + l * py) * u)
                      for r, l in ((1.9, -0.5), (1.9, 0.5), (1.0, -0.25), (1.0, 0.25))])
    return {'kind': 'hex', 'nc': n, 'path': path, 'ang': ang, 'start': [13 * k for k in range(n)],
            'safe': [13 * k + o for k in range(n) for o in (0, 8)], 'home': home, 'base': base,
            'base_c': base_c, 'slots': slots, 'track': 13 * n}


BOARDS = {
    4: {'kind': 'classic', 'nc': 4, 'path': CLASSIC_PATH, 'ang': [0.0] * 52, 'start': [0, 13, 26, 39],
        'safe': [0, 8, 13, 21, 26, 34, 39, 47], 'home': CLASSIC_HOME, 'base': CLASSIC_BASE,
        'base_c': [], 'slots': CLASSIC_SLOTS, 'track': 52},
    6: build_hex_board(),
}
NC = 4
PATH, PATH_ANG, START, SAFE, HOME_COL, BASE, BASE_CENTRE, FINISH_SLOTS = [], [], [], [], [], [], [], []
TRACK, FINISH, BOARD_KIND = 52, 57, 'classic'
DICE_POS, MSG = POS4, MSG4


def set_board(nc):
    # 2, 3 and 4 players use the classic board; 5 and 6 players use the 6-arm star board
    global NC, PATH, PATH_ANG, START, SAFE, HOME_COL, BASE, BASE_CENTRE, FINISH_SLOTS
    global TRACK, FINISH, BOARD_KIND, DICE_POS, MSG
    b = BOARDS[6 if nc > 4 else 4]
    NC = b['nc']
    PATH, PATH_ANG, START, SAFE = b['path'], b['ang'], b['start'], b['safe']
    HOME_COL, BASE, BASE_CENTRE, FINISH_SLOTS = b['home'], b['base'], b['base_c'], b['slots']
    TRACK = b['track']
    FINISH = TRACK + 5                 # 5 boxes of the home column, then the finish
    BOARD_KIND = b['kind']
    DICE_POS = POS6 if NC == 6 else POS4
    MSG = MSG6 if NC == 6 else MSG4


set_board(4)

HOP_FRAMES = 14
ROLL_SEC = 1.45        # the dice flies, bounces and rolls for this long (seconds)
ROLL_TIME = 1700       # whole roll in milliseconds (the last moment shows the result clearly)
DICE_EDGE = 0.5        # dice size compared to its pad
SINA, COSA = 0.906, 0.423          # the camera looks down at the table from above
LX, LY, LZ = -0.35, -0.45, 0.82    # where the light comes from
T_HIT = 500            # kill animation: hit effect length (milliseconds)
HS_MS = 2800           # handshake length (milliseconds)
HS_SCALE = 1.3         # stick men size during handshake
ACTIVE_SCALE = 2.0     # the rolling team's stick men grow to this size (then shrink back to 1.0)
FIN_SCALE = 0.75       # size of stick men parked at the finish
COMPUTER_OPPONENTS = 1 # Computer mode: how many computer players (1 to 3)
EXACT_FINISH = False   # True = a stick man needs the exact number to enter the finish
YAWS = (0.14, -0.12, 0.1, -0.16, 0.08, -0.1)


def cell_to_px(c, r):
    return OX + c * CELL + CELL / 2, OY + r * CELL + CELL / 2


def ease_in_out(t):
    return t * t * (3 - 2 * t)


def ease_out3(t):
    return 1 - (1 - t) ** 3


def ease_out_back(t):
    return 1 + 2.70158 * (t - 1) ** 3 + 1.70158 * (t - 1) ** 2


def ease_out_bounce(t):
    n1, d1 = 7.5625, 2.75
    if t < 1 / d1:
        return n1 * t * t
    if t < 2 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    if t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    t -= 2.625 / d1
    return n1 * t * t + 0.984375


def clamp01(v):
    return max(0.0, min(1.0, v))


# ---------- Saved data (only on this device): name, coins, wins ----------
try:
    SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ludo_save.json')
except Exception:
    SAVE_PATH = 'ludo_save.json'
save = {'name': '', 'coins': 0, 'wins': 0, 'games': 0, 'board': {}, 'code': '', 'daily': '', 'sound': True,
        'names': ['', '', '', '', '', '']}


def write_save():
    try:
        with open(SAVE_PATH, 'w') as f:
            json.dump(save, f)
    except Exception:
        pass


def load_save():
    try:
        with open(SAVE_PATH) as f:
            data = json.load(f)
        for key in save:
            if key in data:
                save[key] = data[key]
    except Exception:
        pass
    if not isinstance(save['names'], list) or len(save['names']) != 6:
        save['names'] = ['', '', '', '', '', '']
    if not save['code']:
        save['code'] = ''.join(random.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(6))
        write_save()


load_save()
SOUND_ON = bool(save.get('sound', True))        # can be switched in Settings


# ---------- Rules: CLASSIC = traditional Ludo, MASTER = kill an opponent before going home ----------
GAME_RULES = 'classic'
pending_rules = 'classic'
kills = [0] * 6                     # how many opponents each colour has knocked out


def home_open(p):
    # CLASSIC: the home path is always open. MASTER: only after a kill.
    return GAME_RULES == 'classic' or kills[p] > 0


# ---------- 3D maths for the dice ----------
def mmul(A, B):
    return [[sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def mvec(M, v):
    return (M[0][0] * v[0] + M[0][1] * v[1] + M[0][2] * v[2],
            M[1][0] * v[0] + M[1][1] * v[1] + M[1][2] * v[2],
            M[2][0] * v[0] + M[2][1] * v[1] + M[2][2] * v[2])


def transpose(M):
    return [[M[j][i] for j in range(3)] for i in range(3)]


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return [[1, 0, 0], [0, c, -s], [0, s, c]]


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return [[c, 0, s], [0, 1, 0], [-s, 0, c]]


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]


def rot_axis(ax, th):
    x, y, z = ax
    c, s = math.cos(th), math.sin(th)
    t = 1 - c
    return [[t * x * x + c, t * x * y - s * z, t * x * z + s * y],
            [t * x * y + s * z, t * y * y + c, t * y * z - s * x],
            [t * x * z - s * y, t * y * z + s * x, t * z * z + c]]


def axis_angle(M):
    tr = M[0][0] + M[1][1] + M[2][2]
    th = math.acos(max(-1.0, min(1.0, (tr - 1) / 2)))
    if th < 1e-6:
        return (0.0, 0.0, 1.0), 0.0
    if th > math.pi - 1e-4:
        ax = [math.sqrt(max(0.0, (M[i][i] + 1) / 2)) for i in range(3)]
        i = max(range(3), key=lambda k: ax[k])
        for j in range(3):
            if j != i and M[i][j] < 0:
                ax[j] = -ax[j]
        norm = math.sqrt(sum(v * v for v in ax)) or 1.0
        return tuple(v / norm for v in ax), math.pi
    s = 2 * math.sin(th)
    return ((M[2][1] - M[1][2]) / s, (M[0][2] - M[2][0]) / s, (M[1][0] - M[0][1]) / s), th


# a real dice: opposite sides add up to 7. face number: (outward direction, u axis, v axis)
FACES = {
    1: ((0, 0, 1), (1, 0, 0), (0, 1, 0)),
    6: ((0, 0, -1), (1, 0, 0), (0, -1, 0)),
    2: ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    5: ((-1, 0, 0), (0, 1, 0), (0, 0, -1)),
    3: ((0, 1, 0), (0, 0, 1), (1, 0, 0)),
    4: ((0, -1, 0), (0, 0, 1), (-1, 0, 0)),
}
PIPS = {
    1: [(0, 0)],
    2: [(-0.25, -0.25), (0.25, 0.25)],
    3: [(-0.25, -0.25), (0, 0), (0.25, 0.25)],
    4: [(-0.25, -0.25), (0.25, -0.25), (-0.25, 0.25), (0.25, 0.25)],
    5: [(-0.25, -0.25), (0.25, -0.25), (0, 0), (-0.25, 0.25), (0.25, 0.25)],
    6: [(-0.25, -0.28), (0.25, -0.28), (-0.25, 0), (0.25, 0), (-0.25, 0.28), (0.25, 0.28)],
}
# turns the dice so that this number faces up
FACE_ROT = {
    1: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
    6: rot_x(math.pi),
    2: rot_y(-math.pi / 2),
    5: rot_y(math.pi / 2),
    3: rot_x(math.pi / 2),
    4: rot_x(-math.pi / 2),
}


def move_steps(t, d):
    # the boxes a stick man walks through with a roll of d. Returns (list of steps, wrapped round again?)
    if t.steps == -1:
        return [0], False
    path, s, wrapped = [], t.steps, False
    for _ in range(d):
        s += 1
        if s >= TRACK and not home_open(t.player):
            s -= TRACK                              # MASTER: no kill yet, so it goes round the board again
            wrapped = True
        if s > FINISH:
            break
        path.append(s)
        if s == FINISH:
            break
    return path, wrapped


class Token:
    def __init__(self, player, no):
        self.player = player
        self.no = no
        self.steps = -1
        self.slot = 0              # which parking spot it gets at the finish
        self.px, self.py = self.target_pixel()
        self.height = 0.0
        self.scale = 1.0
        self.phase = random.random() * 6.28
        self.dx = 0.0              # side by side offset when sharing a box
        self.dscale = 1.0          # size: grows when it is the rolling team, smaller when sharing
        self.facing = 1            # handshake: which way it looks
        self.turn = 0.0            # handshake: 0 = front, 1 = fully turned
        self.paired = False        # already shook hands
        self.win_from = (0, 0)
        self.from_pos = (0, 0)
        self.dead = False          # knocked out: X eyes
        self.flash = False         # knocked out: white flash
        self.origin = (0, 0)
        self.back_pts = []         # the path home, walked backwards
        self.back_len = []
        self.fly_ms = 900

    def square(self):
        if 0 <= self.steps < TRACK:
            return (START[self.player] + self.steps) % TRACK
        return None

    def grid_pos_for(self, steps):
        if steps == -1:
            return BASE[self.player][self.no]
        if steps == FINISH:
            sx, sy = FINISH_SLOTS[self.player][self.slot]
            return (7 + sx, 7 + sy)
        if steps >= TRACK:
            return HOME_COL[self.player][steps - TRACK]
        return PATH[(START[self.player] + steps) % TRACK]

    def target_pixel(self):
        c, r = self.grid_pos_for(self.steps)
        return cell_to_px(c, r)

    def can_move(self, dice):
        if self.steps == FINISH:
            return False
        if self.steps == -1:
            return dice == 6
        if EXACT_FINISH and home_open(self.player):
            return self.steps + dice <= FINISH
        return True


tokens = [[Token(p, i) for i in range(4)] for p in range(NC)]
active_players = [0, 1, 2, 3]
ai_players = []
screen_state = 'login'         # login, auth, name, home, modes or game
modes_hover = -1
profile = None                 # who is logged in: {'name', 'method', 'id'}
current = 0
dice = 0
last_dice = [0, 0, 0, 0, 0, 0]       # the number every colour's own dice shows
dice_orient = [mmul(rot_z(y), FACE_ROT[1]) for y in YAWS]
roll_data = None
state = 'roll'     # roll, rolling, choose, moving, capture, handshake, won, confirm_quit
prev_state = 'roll'
confirm_action = 'quit'
message = "Red's turn: tap the dice"
roll_timer = 0
pending_dice = 1
roll_sounds_done = 0
ai_seen_state = ''
ai_seen_at = 0
result_counted = False

moving_token = None
move_path = []
hop_start = (0, 0)
hop_end = (0, 0)
hop_frame = 0
hop_t0 = 0
pause_until = 0
confirm_open_t = 0
captured_flag = False

team_dancing = False      # True from the dice roll until the turn is over
shadow_level = [0.0] * 6   # shadow under each team (fades in and out)
hs_pair = ()
hs_start = 0
hs_stage = ((0, 0), (0, 0))
hs_shaking = False
hs_burst_done = False
hs_spark_time = 0
win_mode = False
win_start = 0
last_rocket = 0
win_cheer_done = False
win_land_done = False
particles = []
rockets = []
balloons = []
cap_victims = []
cap_mover = None
cap_start = 0
cap_phase = 0
cap_fly_start = 0
toast_text = ''
toast_until = 0


def toast(text, secs=2.4):
    global toast_text, toast_until
    toast_text = text
    toast_until = pygame.time.get_ticks() + int(secs * 1000)


def draw_toast(y):
    now = pygame.time.get_ticks()
    if now >= toast_until:
        return
    txt = small_font.render(toast_text, True, WHITE)
    maxw = W * 0.88
    if txt.get_width() > maxw:
        txt = pygame.transform.smoothscale(txt, (int(maxw), max(2, int(txt.get_height() * maxw / txt.get_width()))))
    r = txt.get_rect(center=(W / 2, y)).inflate(int(CELL * 1.2), int(CELL * 0.7))
    pygame.draw.rect(screen, (0, 0, 0), r.move(0, 4), border_radius=int(r.h * 0.5))
    pygame.draw.rect(screen, (40, 14, 60), r, border_radius=int(r.h * 0.5))
    pygame.draw.rect(screen, GOLD, r, 3, border_radius=int(r.h * 0.5))
    screen.blit(txt, txt.get_rect(center=r.center))


# ---------- Sound effects (made by the code, no files needed) ----------
snd_thud = snd_rattle = snd_kill = snd_whoosh = snd_fanfare = snd_pop = snd_cheer = None


def sound_gen():
    # builds the sound effects a little at a time, so the game never freezes while it starts
    global snd_thud, snd_rattle, snd_kill, snd_whoosh, snd_fanfare, snd_pop, snd_cheer
    try:
        init = pygame.mixer.get_init()
        if not init or init[1] != -16 or init[2] > 2:
            return
        rate, chans = init[0], init[2]

        def make(samples):
            vals = [int(max(-1.0, min(1.0, s)) * 28000) for s in samples]
            if chans == 2:
                vals = [v for v in vals for _ in (0, 1)]
            return pygame.mixer.Sound(buffer=array.array('h', vals).tobytes())

        # wooden knock when the dice hits the table
        out = []
        for i in range(int(rate * 0.13)):
            t = i / rate
            tone = math.sin(2 * math.pi * 190 * t) * math.exp(-t * 38)
            tone += 0.5 * math.sin(2 * math.pi * 380 * t) * math.exp(-t * 55)
            click = (random.random() * 2 - 1) * math.exp(-t * 160)
            out.append(0.6 * tone + 0.5 * click)
            if i % 900 == 0:
                yield
        snd_thud = make(out)
        yield

        # rattle when the dice leaves the hand
        n = int(rate * 0.4)
        out = [0.0] * n
        for _ in range(14):
            start = int(random.random() * rate * 0.34)
            amp = random.uniform(0.3, 0.7)
            for j in range(int(rate * 0.012)):
                if start + j < n:
                    t = j / rate
                    tick = (random.random() * 2 - 1) + 0.6 * math.sin(2 * math.pi * 900 * t)
                    out[start + j] += amp * tick * math.exp(-t * 350)
            yield
        snd_rattle = make(out)
        yield

        # knock-out: boom + crack + falling zap
        out = []
        ph = 0.0
        for i in range(int(rate * 0.7)):
            t = i / rate
            boom = math.sin(2 * math.pi * 95 * t) * math.exp(-t * 11)
            crack = (random.random() * 2 - 1) * math.exp(-t * 45)
            ph += 2 * math.pi * (120 + 900 * math.exp(-t * 4.5)) / rate
            out.append(0.7 * boom + 0.5 * crack + 0.28 * math.sin(ph) * math.exp(-t * 4.0))
            if i % 1200 == 0:
                yield
        snd_kill = make(out)
        yield

        # whoosh when the defeated stick man flies back home
        out = []
        n = int(rate * 0.55)
        ph = 0.0
        for i in range(n):
            env = math.sin(math.pi * i / n) ** 1.5
            ph += 2 * math.pi * (300 + 1100 * i / n) / rate
            out.append(env * (0.22 * (random.random() * 2 - 1) + 0.12 * math.sin(ph)))
            if i % 1200 == 0:
                yield
        snd_whoosh = make(out)
        yield

        # winning fanfare: three short notes, then a long bright chord
        out = []
        for f, d in ((523.25, 0.14), (659.25, 0.14), (783.99, 0.14), (1046.5, 0.8)):
            for i in range(int(rate * d)):
                t = i / rate
                env = min(1.0, t * 80) * math.exp(-t * (1.6 if d > 0.5 else 5.0))
                if d > 0.5:
                    v = sum(math.sin(2 * math.pi * ff * t) for ff in (f, f * 1.26, f * 1.5))
                else:
                    v = math.sin(2 * math.pi * f * t) + 0.5 * math.sin(4 * math.pi * f * t)
                out.append(0.3 * env * v)
                if i % 1000 == 0:
                    yield
        snd_fanfare = make(out)
        yield

        # firework pop
        out = []
        for i in range(int(rate * 0.5)):
            t = i / rate
            thump = math.sin(2 * math.pi * 70 * t) * math.exp(-t * 14)
            bang = (random.random() * 2 - 1) * math.exp(-t * 22)
            crackle = 0.0
            if t > 0.12 and random.random() < 0.08:
                crackle = (random.random() * 2 - 1) * 0.25 * math.exp(-t * 5)
            out.append(0.6 * thump + 0.55 * bang + crackle)
            if i % 1200 == 0:
                yield
        snd_pop = make(out)
        yield

        # crowd cheering
        out = []
        lp = 0.0
        for i in range(int(rate * 1.6)):
            t = i / rate
            lp += 0.3 * ((random.random() * 2 - 1) - lp)
            env = min(1.0, t * 5) * math.exp(-max(0.0, t - 0.5) * 1.8)
            out.append(1.4 * lp * env * (0.7 + 0.3 * math.sin(2 * math.pi * 7 * t)))
            if i % 1200 == 0:
                yield
        snd_cheer = make(out)
    except Exception:
        pass


def play(snd, vol=1.0):
    try:
        if SOUND_ON and snd is not None:
            snd.set_volume(vol)
            snd.play()
    except Exception:
        pass




# ---------- Sparkles, fireworks, confetti, rockets and balloons ----------
class Particle:
    def __init__(self, x, y, vx, vy, life, colour, size, kind='spark'):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.life = self.maxlife = life
        self.colour = colour
        self.size = size
        self.kind = kind
        self.rot = random.random() * 6.28
        self.vr = (random.random() - 0.5) * 0.4

    def update(self, f=1.0):
        self.x += self.vx * f
        self.y += self.vy * f
        if self.kind in ('confetti', 'streamer'):
            self.vy = min(self.vy + 0.03 * K * f, 4 * K)
            self.vx += math.sin(self.y * 0.03 + self.rot) * 0.03 * K * f
            self.rot += self.vr * f
        else:
            self.vy += 0.07 * K * f
            self.vx *= 0.985 ** f
            self.life -= f

    def alive(self):
        return self.life > 0 and self.y < H + 40

    def draw(self):
        if self.kind in ('confetti', 'streamer'):
            if self.kind == 'confetti':
                w, h = self.size, self.size * 0.5
            else:
                w, h = self.size * 1.8, self.size * 0.2
            ca, sa = math.cos(self.rot), math.sin(self.rot)
            pts = [(self.x + dx * ca - dy * sa, self.y + dx * sa + dy * ca)
                   for dx, dy in ((-w, -h), (w, -h), (w, h), (-w, h))]
            pygame.draw.polygon(screen, self.colour, pts)
        elif self.kind == 'star':
            draw_star(self.x, self.y, max(2, self.size * self.life / self.maxlife), self.colour)
        else:
            pygame.draw.circle(screen, self.colour, (self.x, self.y),
                               max(1, self.size * self.life / self.maxlife))


def spawn_confetti(n):
    for _ in range(n):
        if len(particles) > 240:
            return
        kind = 'streamer' if random.random() < 0.25 else 'confetti'
        particles.append(Particle(random.uniform(0, W), random.uniform(-H * 0.1, 0),
                                  random.uniform(-1, 1) * K, random.uniform(2, 4) * K, 9999,
                                  random.choice(COLOURS + [WHITE, GOLD]),
                                  random.uniform(5, 9) * K, kind))


def spawn_sparkles(x, y, colour, n):
    for _ in range(n):
        ang = random.random() * 2 * math.pi
        sp = random.uniform(1, 3.5) * K
        particles.append(Particle(x, y, math.cos(ang) * sp, math.sin(ang) * sp - 1.5 * K,
                                  random.randint(25, 45), random.choice([colour, GOLD, WHITE]),
                                  random.uniform(6, 10) * K, 'star'))


def spawn_impact(x, y, colour):
    for _ in range(30):
        ang = random.random() * 2 * math.pi
        sp = random.uniform(2, 7) * K
        particles.append(Particle(x, y - CELL * 0.3, math.cos(ang) * sp, math.sin(ang) * sp - 2 * K,
                                  random.randint(18, 34), random.choice([colour, WHITE, GOLD]),
                                  random.uniform(3, 6) * K))
    spawn_sparkles(x, y - CELL * 0.4, colour, 8)


def explode(x, y, colour):
    # a firework in one of four styles
    style = random.choice(('ring', 'burst', 'double', 'willow'))
    c2 = random.choice(COLOURS + [GOLD, WHITE])
    if style in ('ring', 'double'):
        for i in range(40):
            ang = 2 * math.pi * i / 40
            particles.append(Particle(x, y, math.cos(ang) * 5.5 * K, math.sin(ang) * 5.5 * K,
                                      50, colour, 4 * K))
        if style == 'double':
            for i in range(20):
                ang = 2 * math.pi * i / 20 + 0.1
                particles.append(Particle(x, y, math.cos(ang) * 3 * K, math.sin(ang) * 3 * K,
                                          45, c2, 4 * K))
    elif style == 'burst':
        for _ in range(70):
            ang = random.random() * 2 * math.pi
            sp = random.uniform(1.5, 7) * K
            particles.append(Particle(x, y, math.cos(ang) * sp, math.sin(ang) * sp,
                                      random.randint(35, 65), random.choice([colour, c2, WHITE]),
                                      random.uniform(3, 5) * K))
    else:
        for _ in range(36):
            ang = random.random() * 2 * math.pi
            sp = random.uniform(1, 4) * K
            particles.append(Particle(x, y, math.cos(ang) * sp, math.sin(ang) * sp,
                                      random.randint(70, 100), GOLD, 3 * K))
    play(snd_pop, random.uniform(0.35, 0.6))


class Rocket:
    def __init__(self):
        self.x = random.uniform(W * 0.1, W * 0.9)
        self.y = float(H + 10)
        self.ty = random.uniform(H * 0.08, H * 0.4)
        self.vy = -H * random.uniform(0.0095, 0.012)
        self.colour = random.choice(COLOURS + [GOLD, WHITE])
        self.done = False

    def update(self, f=1.0):
        self.y += self.vy * f
        particles.append(Particle(self.x + random.uniform(-2, 2) * K, self.y, 0, 0.5 * K, 12, GOLD, 3.5 * K))
        if self.y <= self.ty:
            explode(self.x, self.y, self.colour)
            self.done = True


def make_balloon(first):
    r = CELL * random.uniform(0.45, 0.7)
    y = H + r * 3 + (random.uniform(0, H * 0.9) if first else 0)
    return {'x': random.uniform(W * 0.05, W * 0.95), 'y': y, 'vy': -random.uniform(1.2, 2.6) * K,
            'r': r, 'c': random.choice(COLOURS + [GOLD]), 'ph': random.random() * 6.28}


def update_balloon(b):
    b['y'] += b['vy'] * FS
    if b['y'] < -b['r'] * 4:
        b['y'] = H + b['r'] * 3
        b['x'] = random.uniform(W * 0.05, W * 0.95)


def draw_balloon(b, ts):
    x = b['x'] + math.sin(ts * 1.5 + b['ph']) * CELL * 0.25
    y, r = b['y'], b['r']
    pts = [(x + math.sin(ts * 3 + b['ph'] + i * 0.8) * r * 0.12, y + r * 1.2 + i * r * 0.35) for i in range(6)]
    pygame.draw.lines(screen, (220, 220, 220), False, pts, 2)
    pygame.draw.ellipse(screen, b['c'], (x - r * 0.8, y - r, r * 1.6, r * 2))
    pygame.draw.ellipse(screen, WHITE, (x - r * 0.45, y - r * 0.7, r * 0.3, r * 0.5))
    pygame.draw.polygon(screen, b['c'], [(x, y + r), (x - r * 0.15, y + r * 1.2), (x + r * 0.15, y + r * 1.2)])


def update_particles():
    for p in particles:
        p.update(FS)
    particles[:] = [p for p in particles if p.alive()]


def draw_particles():
    for p in particles:
        p.draw()


def build_glow():
    g = pygame.Surface((128, 128), pygame.SRCALPHA)
    for r in range(64, 0, -2):
        a = int(150 * (1 - r / 64.0) ** 2)
        pygame.draw.circle(g, (255, 215, 90, a), (64, 64), r)
    return g


glow_surf = build_glow()


# ---------- Ludo wallpaper (game and home screen background) ----------
def radial_glow(size, col, peak):
    n = 48
    s = pygame.Surface((n, n), pygame.SRCALPHA)
    for r in range(n // 2, 0, -1):
        a = int(peak * (1 - r / (n / 2.0)) ** 2)
        pygame.draw.circle(s, col + (a,), (n // 2, n // 2), r)
    return pygame.transform.smoothscale(s, (size, size))


def build_wallpaper():
    small = pygame.Surface((2, 32))
    for y in range(32):                            # deep night-blue gradient
        f = y / 31.0
        for x in range(2):
            small.set_at((x, y), (int(16 + 14 * f), int(14 + 26 * f), int(48 + 30 * f)))
    surf = pygame.transform.smoothscale(small, (W, H))
    rng = random.Random(11)
    big = int(max(W, H) * 1.1)
    for gx, gy, col in ((0, 0, RED), (W, 0, GREEN), (W, H, YELLOW), (0, H, BLUE)):
        surf.blit(radial_glow(big, col, 90), (gx - big // 2, gy - big // 2))
    # faint Ludo symbols: dice, pawns, stars and the cross-shaped track
    sym = pygame.Surface((W, H), pygame.SRCALPHA)
    s = int(CELL * 3)
    for i in range(18):
        x, y = rng.randint(0, W), rng.randint(0, H)
        tile = pygame.Surface((s, s), pygame.SRCALPHA)
        white = (255, 255, 255, 36)
        tint = COLOURS[i % 4] + (52,)
        kind = i % 4
        if kind == 0:                              # dice
            pygame.draw.rect(tile, white, (int(s * 0.2), int(s * 0.2), int(s * 0.6), int(s * 0.6)), 4,
                             border_radius=int(s * 0.1))
            for fx, fy in PIPS[rng.randint(1, 6)]:
                pygame.draw.circle(tile, white, (int(s * 0.5 + fx * s * 0.6), int(s * 0.5 + fy * s * 0.6)),
                                   int(s * 0.05))
        elif kind == 1:                            # pawn
            pygame.draw.circle(tile, tint, (int(s * 0.5), int(s * 0.3)), int(s * 0.13), 4)
            pygame.draw.polygon(tile, tint, [(s * 0.4, s * 0.42), (s * 0.6, s * 0.42),
                                             (s * 0.74, s * 0.8), (s * 0.26, s * 0.8)], 4)
            pygame.draw.ellipse(tile, tint, (int(s * 0.22), int(s * 0.74), int(s * 0.56), int(s * 0.16)), 4)
        elif kind == 2:                            # star
            pts = []
            for k in range(10):
                ang = math.pi / 2 + k * math.pi / 5
                rad = s * 0.36 if k % 2 == 0 else s * 0.16
                pts.append((s * 0.5 + rad * math.cos(ang), s * 0.5 - rad * math.sin(ang)))
            pygame.draw.polygon(tile, tint, pts, 4)
        else:                                      # the cross-shaped Ludo track
            for cx, cy in ((1, 0), (0, 1), (1, 1), (2, 1), (1, 2)):
                pygame.draw.rect(tile, white, (int(s * (0.16 + cx * 0.22)), int(s * (0.16 + cy * 0.22)),
                                               int(s * 0.2), int(s * 0.2)), 3)
        tile = pygame.transform.rotate(tile, rng.randint(-35, 35))
        sym.blit(tile, (x - tile.get_width() // 2, y - tile.get_height() // 2))
    surf.blit(sym, (0, 0))
    return surf


wallpaper = build_wallpaper()


# ---------- Quit / Home buttons, confirm box, rules badge ----------
def quit_rect():
    return pygame.Rect(10, 10, CELL * 2.2, CELL * 1.1)


def home_btn_rect():
    return pygame.Rect(10 + CELL * 2.2 + 10, 10, CELL * 2.2, CELL * 1.1)


def yes_rect():
    return pygame.Rect(W / 2 - CELL * 3, H / 2 + CELL * 0.4, CELL * 2.5, CELL * 1.3)


def no_rect():
    return pygame.Rect(W / 2 + CELL * 0.5, H / 2 + CELL * 0.4, CELL * 2.5, CELL * 1.3)


def draw_quit_button():
    r = quit_rect()
    pygame.draw.rect(screen, (200, 40, 40), r, border_radius=12)
    pygame.draw.rect(screen, WHITE, r, 3, border_radius=12)
    txt = small_font.render('QUIT', True, WHITE)
    screen.blit(txt, txt.get_rect(center=r.center))


def draw_rules_badge():
    label = 'MASTER' if GAME_RULES == 'master' else 'CLASSIC'
    txt = small_font.render(label, True, WHITE)
    r = pygame.Rect(0, 0, txt.get_width() + int(CELL * 0.9), int(CELL * 1.1))
    r.topright = (W - 10, 10)
    pygame.draw.rect(screen, (130, 70, 220) if GAME_RULES == 'master' else (230, 120, 40), r, border_radius=12)
    pygame.draw.rect(screen, WHITE, r, 3, border_radius=12)
    screen.blit(txt, txt.get_rect(center=r.center))


def draw_confirm_box():
    if 'dim160' not in panel_cache:
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        s.fill((0, 0, 0, 160))
        panel_cache['dim160'] = s
    screen.blit(panel_cache['dim160'], (0, 0))
    box = pygame.Rect(W / 2 - CELL * 4.6, H / 2 - CELL * 2.2, CELL * 9.2, CELL * 4.6)
    pygame.draw.rect(screen, WHITE, box, border_radius=16)
    pygame.draw.rect(screen, BLACK, box, 3, border_radius=16)
    for k, line in enumerate(('Quit this match and go', 'to the home screen?')):
        txt = render_text(small_font, line, BLACK)
        screen.blit(txt, txt.get_rect(center=(W / 2, H / 2 - CELL * (1.3 - 0.8 * k))))
    for rect, label, colour in ((yes_rect(), 'YES', (200, 40, 40)), (no_rect(), 'NO', (45, 175, 80))):
        pygame.draw.rect(screen, colour, rect, border_radius=12)
        t = font.render(label, True, WHITE)
        screen.blit(t, t.get_rect(center=rect.center))


# ---------- Drawing the board ----------
def draw_star(cx, cy, r, colour):
    pts = []
    for i in range(10):
        ang = math.pi / 2 + i * math.pi / 5
        rad = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rad * math.cos(ang), cy - rad * math.sin(ang)))
    pygame.draw.polygon(screen, colour, pts)


def draw_classic_board():
    board_rect = pygame.Rect(OX - 6, OY - 6, CELL * 15 + 12, CELL * 15 + 12)
    pygame.draw.rect(screen, (90, 60, 30), board_rect, border_radius=14)
    pygame.draw.rect(screen, BOARD_BG, (OX, OY, CELL * 15, CELL * 15))

    corners = [(0, 0), (9, 0), (9, 9), (0, 9)]
    for i, (c, r) in enumerate(corners):
        on = i in active_players                    # colours that are not playing stay visible, but darker
        col = COLOURS[i] if on else DARK[i]
        lt = LIGHT[i] if on else DARK_LIGHT[i]
        rect = pygame.Rect(OX + c * CELL, OY + r * CELL, CELL * 6, CELL * 6)
        pygame.draw.rect(screen, col, rect)
        inner = rect.inflate(-CELL * 1.6, -CELL * 1.6)
        pygame.draw.rect(screen, lt, inner, border_radius=18)
        for (bc, br) in BASE[i]:
            x, y = cell_to_px(bc, br)
            pygame.draw.circle(screen, WHITE if on else (190, 190, 190), (x, y), CELL * 0.45)
            pygame.draw.circle(screen, col, (x, y), CELL * 0.45, 3)

    for idx, (c, r) in enumerate(PATH):
        rect = pygame.Rect(OX + c * CELL, OY + r * CELL, CELL, CELL)
        colour = WHITE
        for p in range(4):
            if idx == START[p]:
                colour = COLOURS[p] if p in active_players else DARK[p]
        pygame.draw.rect(screen, colour, rect)
        pygame.draw.rect(screen, (120, 120, 120), rect, 1)
        if idx in SAFE and idx not in START:
            draw_star(rect.centerx, rect.centery, CELL * 0.35, (150, 150, 150))

    for p in range(4):
        for (c, r) in HOME_COL[p]:
            rect = pygame.Rect(OX + c * CELL, OY + r * CELL, CELL, CELL)
            pygame.draw.rect(screen, COLOURS[p] if p in active_players else DARK[p], rect)
            pygame.draw.rect(screen, (120, 120, 120), rect, 1)

    x0, y0 = OX + 6 * CELL, OY + 6 * CELL
    s = CELL * 3
    centre = (x0 + s / 2, y0 + s / 2)
    tl, tr = (x0, y0), (x0 + s, y0)
    br, bl = (x0 + s, y0 + s), (x0, y0 + s)
    tri = [COLOURS[p] if p in active_players else DARK[p] for p in range(4)]
    pygame.draw.polygon(screen, tri[0], [tl, bl, centre])
    pygame.draw.polygon(screen, tri[1], [tl, tr, centre])
    pygame.draw.polygon(screen, tri[2], [tr, br, centre])
    pygame.draw.polygon(screen, tri[3], [bl, br, centre])
    pygame.draw.rect(screen, BLACK, (x0, y0, s, s), 2)


def cell_poly(c, r, ang, size):
    # a square box of the star board, turned to face along its arm
    h = size / 2.0
    ca, sa = math.cos(ang), math.sin(ang)
    return [cell_to_px(c + x * ca - y * sa, r + x * sa + y * ca)
            for x, y in ((-h, -h), (h, -h), (h, h), (-h, h))]


def draw_hex_board():
    u = HEX_U
    cx, cy = cell_to_px(7, 7)
    rad = CELL * 8.9 * u
    pygame.draw.circle(screen, (90, 60, 30), (cx, cy), rad + 6)
    pygame.draw.circle(screen, BOARD_BG, (cx, cy), rad)

    for k in range(NC):                              # the six home bases
        on = k in active_players
        col = COLOURS[k] if on else DARK[k]
        lt = LIGHT[k] if on else DARK_LIGHT[k]
        bx, by = cell_to_px(*BASE_CENTRE[k])
        pygame.draw.circle(screen, col, (bx, by), CELL * 1.58 * u)
        pygame.draw.circle(screen, lt, (bx, by), CELL * 1.3 * u)
        for (c, r) in BASE[k]:
            x, y = cell_to_px(c, r)
            pygame.draw.circle(screen, WHITE if on else (190, 190, 190), (x, y), CELL * 0.4 * u)
            pygame.draw.circle(screen, col, (x, y), CELL * 0.4 * u, 3)

    for idx, (c, r) in enumerate(PATH):
        pts = cell_poly(c, r, PATH_ANG[idx], 0.95 * u)
        colour = WHITE
        for p in range(NC):
            if idx == START[p]:
                colour = COLOURS[p] if p in active_players else DARK[p]
        pygame.draw.polygon(screen, colour, pts)
        pygame.draw.polygon(screen, (120, 120, 120), pts, 1)
        if idx in SAFE and idx not in START:
            sx, sy = cell_to_px(c, r)
            draw_star(sx, sy, CELL * 0.32 * u, (150, 150, 150))

    for p in range(NC):
        for i, (c, r) in enumerate(HOME_COL[p]):
            pts = cell_poly(c, r, hex_arm(p), 0.95 * u)
            pygame.draw.polygon(screen, COLOURS[p] if p in active_players else DARK[p], pts)
            pygame.draw.polygon(screen, (120, 120, 120), pts, 1)

    rc = (HEX_T0 - 0.5) * u / math.cos(math.pi / HEX_N)     # the middle star: one wedge per colour
    for k in range(NC):
        a1, a2 = hex_arm(k) - math.pi / HEX_N, hex_arm(k) + math.pi / HEX_N
        pts = [(cx, cy),
               cell_to_px(7 + rc * math.cos(a1), 7 + rc * math.sin(a1)),
               cell_to_px(7 + rc * math.cos(a2), 7 + rc * math.sin(a2))]
        pygame.draw.polygon(screen, COLOURS[k] if k in active_players else DARK[k], pts)
        pygame.draw.polygon(screen, BLACK, pts, 2)


board_cache = None
name_tags = {}
shadow_cache = {}


def invalidate_board():
    global board_cache
    board_cache = None


def draw_board():
    # the board never changes during a game, so it is drawn only once and copied in every frame
    global board_cache, screen
    if board_cache is None:
        real = screen
        board_cache = pygame.Surface((W, H))
        screen = board_cache
        try:
            screen.blit(wallpaper, (0, 0))
            if BOARD_KIND == 'classic':
                draw_classic_board()
            else:
                draw_hex_board()
        finally:
            screen = real
    screen.blit(board_cache, (0, 0))


def get_shadow(w, h, alpha):
    key = (w, h, alpha)
    s = shadow_cache.get(key)
    if s is None:
        if len(shadow_cache) > 160:
            shadow_cache.clear()
        s = pygame.Surface((w + 2, h + 2), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (0, 0, 0, alpha), s.get_rect())
        shadow_cache[key] = s
    return s


def build_name_tags():
    # one name tag for every player, in the colour of that player (drawn next to the player's dice pad)
    name_tags.clear()
    for p in active_players:
        txt = tag_font.render(NAMES[p], True, WHITE)
        dark = tag_font.render(NAMES[p], True, (20, 10, 30))
        maxw = CELL * 5.2
        if txt.get_width() > maxw:
            f = maxw / float(txt.get_width())
            txt = pygame.transform.smoothscale(txt, (int(maxw), max(2, int(txt.get_height() * f))))
            dark = pygame.transform.smoothscale(dark, (int(maxw), max(2, int(dark.get_height() * f))))
        h = int(CELL * 0.95)
        w = txt.get_width() + int(h * 1.35)
        s = pygame.Surface((w + 4, h + 6), pygame.SRCALPHA)
        r = pygame.Rect(0, 0, w, h)
        pygame.draw.rect(s, (0, 0, 0, 90), r.move(2, 4), border_radius=int(h * 0.5))
        pygame.draw.rect(s, COLOURS[p] + (255,), r, border_radius=int(h * 0.5))
        pygame.draw.rect(s, (255, 255, 255, 255), r, 3, border_radius=int(h * 0.5))
        pygame.draw.circle(s, (255, 255, 255, 255), (int(h * 0.5), h // 2), int(h * 0.2))
        tx = int(h * 0.95)
        s.blit(dark, (tx + 2, (h - dark.get_height()) // 2 + 2))
        s.blit(txt, (tx, (h - txt.get_height()) // 2))
        name_tags[p] = s


def draw_name_tags():
    for p in active_players:
        s = name_tags.get(p)
        if s is None:
            continue
        r = dice_rect(p)
        ph = DS * SINA
        if SIDE_LAYOUT or r.y < OY:
            y = r.centery - ph / 2 - CELL * 0.45 - s.get_height()
        else:
            y = r.centery + ph / 2 + CELL * 0.45
        screen.blit(s, (r.centerx - s.get_width() / 2, y))


# ---------- Stick man drawing ----------
def draw_stickman(t, mode):
    # mode: 'idle', 'dance', 'still' (parked at the finish), 'move', 'shake' (handshake) or 'win'
    if t.flash:
        colour = WHITE
    elif t.player in active_players:
        colour = COLOURS[t.player]
    else:
        colour = DARK[t.player]                     # not playing: same colour, but darker
    s = CELL * 0.5 * t.scale * t.dscale
    x = t.px + t.dx
    base_y = t.py - t.height
    now = pygame.time.get_ticks() / 1000.0

    # The shadow only shows under the team that is rolling (it fades in and out)
    level = shadow_level[t.player]
    if level > 0.03:
        sh_w = s * 1.1 * max(0.5, 1 - t.height / (CELL * 1.5))
        sw, shh = int(sh_w * 2) // 4 * 4 + 4, int(s * 0.5) // 4 * 4 + 4
        screen.blit(get_shadow(sw, shh, int(90 * level) // 12 * 12), (x - sw / 2, t.py + s * 0.55))

    if mode == 'dance':
        sway = math.sin(now * 9 + t.phase)
        bounce = abs(math.sin(now * 9 + t.phase)) * s * 0.25
        arm_l = math.sin(now * 9 + t.phase) * 1.0
        arm_r = -math.sin(now * 9 + t.phase) * 1.0
        leg_l = math.sin(now * 9 + t.phase + 1.5) * 0.6
        leg_r = -math.sin(now * 9 + t.phase + 1.5) * 0.6
        sway_x = sway * s * 0.15
    elif mode == 'move':
        bounce = 0
        arm_l, arm_r = -1.3, 1.3
        leg_l, leg_r = 0.5, -0.5
        sway_x = 0
    elif mode == 'shake':
        bounce = abs(math.sin(now * 8)) * s * 0.06 if hs_shaking else 0
        arm_l = arm_r = 0
        leg_l, leg_r = 0.25, -0.25
        sway_x = 0
    elif mode == 'win':
        bounce = 0
        arm_l = arm_r = 0
        leg_l = math.sin(now * 12 + t.phase) * 0.5
        leg_r = -leg_l
        sway_x = math.sin(now * 6 + t.phase) * s * 0.1
    elif mode == 'still':
        bounce = 0
        arm_l, arm_r = 0.25, -0.25
        leg_l, leg_r = 0.2, -0.2
        sway_x = 0
    else:
        bounce = 0
        arm_l = 0.25 + math.sin(now * 2 + t.phase) * 0.08
        arm_r = -0.25 - math.sin(now * 2 + t.phase) * 0.08
        leg_l, leg_r = 0.2, -0.2
        sway_x = 0

    y = base_y - bounce
    cx = x + sway_x

    head_r = s * 0.28
    head_y = y - s * 0.75
    neck_y = head_y + head_r
    hip_y = y - s * 0.05
    w = max(3, int(s * 0.14))

    pygame.draw.line(screen, colour, (cx, neck_y), (cx, hip_y), w)

    sh_y = neck_y + s * 0.15
    arm_len = s * 0.5
    if mode == 'shake':
        # front arm reaches toward the partner and pumps up and down
        pump = math.sin(now * 16) * s * 0.12 if hs_shaking else 0
        hx = cx + t.facing * arm_len * 1.1 * t.turn
        hy = sh_y + (1 - t.turn) * arm_len * 0.8 + pump * t.turn
        pygame.draw.line(screen, colour, (cx, sh_y), (hx, hy), w)
        # back arm waves happily in the air
        bx = cx - t.facing * arm_len * 0.7
        by = sh_y - arm_len * (0.2 + 0.7 * t.turn) + math.sin(now * 10 + t.phase) * s * 0.12 * t.turn
        pygame.draw.line(screen, colour, (cx, sh_y), (bx, by), w)
    elif mode == 'win':
        wave = math.sin(now * 10 + t.phase) * s * 0.18
        pygame.draw.line(screen, colour, (cx, sh_y), (cx - arm_len * 0.9, sh_y - arm_len * 1.1 + wave), w)
        pygame.draw.line(screen, colour, (cx, sh_y), (cx + arm_len * 0.9, sh_y - arm_len * 1.1 - wave), w)
    else:
        for a in (arm_l, arm_r):
            ex = cx + math.sin(a) * arm_len * 1.0
            ey = sh_y + math.cos(a) * arm_len * 0.9 if abs(a) < 1.1 else sh_y - abs(math.cos(a)) * arm_len
            pygame.draw.line(screen, colour, (cx, sh_y), (ex, ey), w)

    leg_len = s * 0.6
    for a in (leg_l, leg_r):
        ex = cx + math.sin(a) * leg_len
        ey = hip_y + math.cos(a) * leg_len
        pygame.draw.line(screen, colour, (cx, hip_y), (ex, ey), w)

    # Head and face (the face turns sideways during the handshake)
    fx = t.facing * t.turn if mode == 'shake' else 0
    pygame.draw.circle(screen, WHITE, (cx, head_y), head_r)
    pygame.draw.circle(screen, colour, (cx, head_y), head_r, w)
    face_cx = cx + fx * head_r * 0.45
    gap = head_r * 0.35 * (1 - abs(fx) * 0.6)
    if t.dead:
        # knocked out: X eyes and a flat mouth
        e = head_r * 0.18
        for sgn in (-1, 1):
            ox, oy = face_cx + sgn * gap, head_y - head_r * 0.1
            pygame.draw.line(screen, BLACK, (ox - e, oy - e), (ox + e, oy + e), 2)
            pygame.draw.line(screen, BLACK, (ox - e, oy + e), (ox + e, oy - e), 2)
        pygame.draw.line(screen, BLACK, (face_cx - head_r * 0.3, head_y + head_r * 0.45),
                         (face_cx + head_r * 0.3, head_y + head_r * 0.45), 2)
    else:
        eye = max(1, int(head_r * 0.15))
        pygame.draw.circle(screen, BLACK, (face_cx - gap, head_y - head_r * 0.1), eye)
        pygame.draw.circle(screen, BLACK, (face_cx + gap, head_y - head_r * 0.1), eye)
        sm = 1 - abs(fx) * 0.3
        pygame.draw.arc(screen, BLACK,
                        (face_cx - head_r * 0.45 * sm, head_y - head_r * 0.1, head_r * 0.9 * sm, head_r * 0.7),
                        math.pi * 1.1, math.pi * 1.9, 2)

    if mode == 'win':
        # the winners wear a golden crown
        hw = head_r * 0.85
        cb = head_y - head_r * 0.8
        ch = head_r * 1.0
        pts = [(cx - hw, cb), (cx - hw, cb - ch * 0.55), (cx - hw * 0.5, cb - ch * 0.25), (cx, cb - ch),
               (cx + hw * 0.5, cb - ch * 0.25), (cx + hw, cb - ch * 0.55), (cx + hw, cb)]
        pygame.draw.polygon(screen, GOLD, pts)
        pygame.draw.polygon(screen, (200, 140, 20), pts, 2)
        pygame.draw.circle(screen, colour, (cx, cb - ch), max(2, int(head_r * 0.14)))


# ---------- Stick men: size, standing side by side, drawing ----------
def want_scale(t):
    if t.steps == FINISH:
        return FIN_SCALE                           # parked at the finish
    if team_dancing and t.player == current and not win_mode:
        return ACTIVE_SCALE                        # the rolling team grows
    return 1.0                                     # everybody else: exactly the original size


def glide(t, tdx, tsc):
    k = 1 - 0.8 ** FS
    t.dx += (tdx - t.dx) * k
    t.dscale += (tsc - t.dscale) * k
    if abs(tdx - t.dx) < 0.5:
        t.dx = tdx
    if abs(tsc - t.dscale) < 0.004:
        t.dscale = tsc                             # lands on the exact size, no leftovers


def update_sharing():
    # Stick men in the same box stand side by side (smaller if needed) so they never merge
    groups = {}
    for p in active_players:
        for t in tokens[p]:
            if win_mode and p == current:
                t.dx, t.dscale = 0.0, 1.0
            elif t is moving_token:
                glide(t, 0.0, want_scale(t))
            elif t in hs_pair or t in cap_victims:
                glide(t, 0.0, 1.0)
            else:
                groups.setdefault((round(t.px), round(t.py)), []).append(t)
    for grp in groups.values():
        grp.sort(key=lambda t: (t.player, t.no))
        n = len(grp)
        spacing = CELL * 0.9 / n
        fit = 99.0 if n == 1 else max(0.5, 1.8 / n)
        for i, t in enumerate(grp):
            glide(t, (i - (n - 1) / 2) * spacing, min(want_scale(t), fit))


def draw_tokens(highlight):
    items = []
    for p in range(NC):
        for t in tokens[p]:
            if p not in active_players:
                items.append((t.py, t, 'still'))   # players that are not playing wait quietly, in darker colours
                continue
            if t is moving_token or t in hs_pair or t in cap_victims:
                continue
            if win_mode and p == current:
                continue
            if t.steps == FINISH:
                mode = 'still'                     # a stick man at the finish never dances
            elif team_dancing and p == current:
                mode = 'dance'
            else:
                mode = 'idle'
            items.append((t.py, t, mode))
    items.sort(key=lambda it: it[0])               # lower ones in front
    for _, t, mode in items:
        if t in highlight:
            pulse = 3 + 2 * math.sin(pygame.time.get_ticks() / 150)
            pygame.draw.circle(screen, WHITE, (t.px + t.dx, t.py), CELL * 0.45 * t.dscale + pulse, 3)
        draw_stickman(t, mode)
    if hs_pair:
        draw_handshake_stage()
        for t in hs_pair:
            draw_stickman(t, 'shake')
        if hs_pair[0].turn > 0.95:
            hx, hy = shake_hand_pos()
            pygame.draw.circle(screen, (255, 230, 120), (hx, hy), CELL * 0.07)
    if moving_token:
        draw_stickman(moving_token, 'move')
    for v in cap_victims:
        draw_stickman(v, 'move')
    draw_capture_fx()


# ---------- Handshake ----------
def shake_hand_pos():
    a, b = hs_pair
    now = pygame.time.get_ticks() / 1000.0
    s = CELL * 0.5 * a.scale * a.dscale
    bounce = abs(math.sin(now * 8)) * s * 0.06 if hs_shaking else 0
    pump = math.sin(now * 16) * s * 0.12 if hs_shaking else 0
    return (a.px + b.px) / 2, a.py - a.height - bounce - s * 0.32 + pump


def draw_handshake_stage():
    a, b = hs_pair
    turn = a.turn
    if turn <= 0:
        return
    cx = (hs_stage[0][0] + hs_stage[1][0]) / 2
    cy = hs_stage[0][1] + CELL * 0.4
    now = pygame.time.get_ticks() / 1000.0
    R = CELL * (1.0 + 0.04 * math.sin(now * 6)) * turn
    pygame.draw.ellipse(screen, WHITE, (cx - R, cy - R * 0.4, R * 2, R * 0.8), 4)
    pygame.draw.ellipse(screen, COLOURS[a.player], (cx - R * 0.8, cy - R * 0.32, R * 1.6, R * 0.64), 3)
    if hs_shaking:
        txt = small_font.render('Great teamwork!', True, COLOURS[a.player])
        pos = txt.get_rect(center=(cx, hs_stage[0][1] - CELL * 1.4))
        pygame.draw.rect(screen, WHITE, pos.inflate(20, 10), border_radius=10)
        screen.blit(txt, pos)


def start_handshake(a, b):
    global state, hs_pair, hs_start, hs_stage, hs_shaking, hs_burst_done
    if a.px > b.px:
        a, b = b, a
    state = 'handshake'
    a.facing, b.facing = 1, -1
    a.turn = b.turn = 0.0
    a.from_pos = (a.px, a.py)
    b.from_pos = (b.px, b.py)
    hs_pair = (a, b)
    hs_start = pygame.time.get_ticks()
    hs_shaking = False
    hs_burst_done = False
    cx, cy = cell_to_px(7, 7)
    sep = 2 * 1.1 * (CELL * 0.5 * HS_SCALE * 0.5)     # hands meet exactly in the middle
    hs_stage = ((cx - sep / 2, cy + CELL * 0.3), (cx + sep / 2, cy + CELL * 0.3))


def update_handshake():
    global hs_shaking, hs_burst_done, hs_spark_time
    a, b = hs_pair
    now = pygame.time.get_ticks()
    p = (now - hs_start) / HS_MS
    if p >= 1.0:
        finish_handshake()
        return
    hopping = False
    if p < 0.2:                      # hop to the centre and turn to face each other
        q = ease_in_out(p / 0.2)
        pos_q, turn, hopping = q, q, True
        hs_shaking = False
    elif p < 0.8:                    # face to face, shake hands
        pos_q, turn = 1.0, 1.0
        hs_shaking = 0.28 <= p <= 0.72
    else:                            # turn back and walk to the finish spots
        q = ease_in_out((p - 0.8) / 0.2)
        pos_q, turn, hopping = 1 - q, 1 - q, True
        hs_shaking = False
    for t, stage in ((a, hs_stage[0]), (b, hs_stage[1])):
        t.px = t.from_pos[0] + (stage[0] - t.from_pos[0]) * pos_q
        t.py = t.from_pos[1] + (stage[1] - t.from_pos[1]) * pos_q
        t.turn = turn
        t.scale = 1 + (HS_SCALE - 1) * turn
        t.height = math.sin(pos_q * math.pi) * CELL * 0.25 if hopping else 0
    if hs_shaking:
        hx, hy = shake_hand_pos()
        if not hs_burst_done:
            hs_burst_done = True
            spawn_sparkles(hx, hy, COLOURS[a.player], 28)
        if now - hs_spark_time > 160:
            hs_spark_time = now
            spawn_sparkles(hx, hy, COLOURS[a.player], 4)


def finish_handshake():
    global hs_pair, hs_shaking
    for t in hs_pair:
        t.px, t.py = t.target_pixel()
        t.height = 0
        t.scale = 1.0
        t.turn = 0.0
    hs_pair = ()
    hs_shaking = False
    end_of_move()


# ---------- Winning celebration ----------
def draw_text_outline(text, fnt, colour, centre, scale=1.0):
    base = fnt.render(text, True, colour)
    shad = fnt.render(text, True, BLACK)
    if scale != 1.0:
        base = pygame.transform.rotozoom(base, 0, scale)
        shad = pygame.transform.rotozoom(shad, 0, scale)
    rect = base.get_rect(center=centre)
    for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3)):
        screen.blit(shad, rect.move(dx, dy))
    screen.blit(base, rect)


def draw_trophy(cx, cy, s):
    gold, dark = (255, 200, 40), (200, 140, 20)
    pygame.draw.arc(screen, gold, (cx - s * 0.95, cy - s * 0.55, s * 0.7, s * 0.7), math.pi * 0.5, math.pi * 1.5, 6)
    pygame.draw.arc(screen, gold, (cx + s * 0.25, cy - s * 0.55, s * 0.7, s * 0.7), math.pi * 1.5, math.pi * 2.5, 6)
    pygame.draw.polygon(screen, gold, [(cx - s * 0.6, cy - s * 0.65), (cx + s * 0.6, cy - s * 0.65),
                                       (cx + s * 0.35, cy + s * 0.1), (cx - s * 0.35, cy + s * 0.1)])
    pygame.draw.ellipse(screen, gold, (cx - s * 0.35, cy - s * 0.05, s * 0.7, s * 0.3))
    pygame.draw.rect(screen, dark, (cx - s * 0.08, cy + s * 0.15, s * 0.16, s * 0.35))
    pygame.draw.rect(screen, dark, (cx - s * 0.4, cy + s * 0.5, s * 0.8, s * 0.15), border_radius=4)
    draw_star(cx, cy - s * 0.3, s * 0.22, COLOURS[current])
    pygame.draw.line(screen, WHITE, (cx - s * 0.4, cy - s * 0.55), (cx - s * 0.25, cy - s * 0.05), 4)


def draw_win_screen():
    now = pygame.time.get_ticks()
    e = (now - win_start) / 1000.0
    ts = now / 1000.0
    overlay_surf.set_alpha(int(min(1.0, e / 0.8) * 215))
    screen.blit(overlay_surf, (0, 0))
    cx, cy = W / 2, H / 2 - CELL * 1.7

    # spinning rays of light
    grow = max(0.0, min(1.0, (e - 0.2) / 0.7))
    if grow > 0:
        R = min(W, H) * 0.95 * grow
        dark = tuple(int(c * 0.4) for c in COLOURS[current])
        for i in range(12):
            a = ts * 0.45 + i * 2 * math.pi / 12
            pts = [(cx, cy), (cx + R * math.cos(a), cy + R * math.sin(a)),
                   (cx + R * math.cos(a + 0.24), cy + R * math.sin(a + 0.24))]
            pygame.draw.polygon(screen, dark if i % 2 == 0 else (75, 66, 28), pts)

    # glowing light behind the trophy
    gs = int(CELL * 8 * (1 + 0.06 * math.sin(ts * 3)))
    g = pygame.transform.smoothscale(glow_surf, (gs, gs))
    screen.blit(g, g.get_rect(center=(cx, cy)))

    for b in balloons:
        draw_balloon(b, ts)

    # the trophy rises from below with a bounce, golden stars circle around it
    pt = max(0.0, min(1.0, (e - 0.35) / 1.0))
    if pt > 0:
        draw_trophy(cx, cy + (1 - ease_out_back(pt)) * H * 0.6, CELL * 1.9)
        if pt >= 1.0:
            for i in range(8):
                a = ts * 1.6 + i * math.pi / 4
                draw_star(cx + math.cos(a) * CELL * 2.6, cy + math.sin(a) * CELL * 1.5,
                          CELL * (0.18 + 0.08 * math.sin(ts * 6 + i)), GOLD)

    for t in tokens[current]:
        draw_stickman(t, 'win')

    # WINNER! letters pop in one by one and wave
    word = 'WINNER!'
    widths = [big_font.size(ch)[0] for ch in word]
    x = W / 2 - (sum(widths) + CELL * 0.15 * (len(word) - 1)) / 2
    for i, ch in enumerate(word):
        q = max(0.0, min(1.0, (e - 1.0 - i * 0.1) / 0.4))
        if q > 0:
            col = RAINBOW[(i + int(ts * 4)) % len(RAINBOW)]
            draw_text_outline(ch, big_font, col,
                              (x + widths[i] / 2, H / 2 - CELL * 6.4 + math.sin(ts * 4 + i * 0.7) * CELL * 0.12),
                              max(0.05, ease_out_back(q)))
        x += widths[i] + CELL * 0.15
    if e > 1.9:
        q = min(1.0, (e - 1.9) / 0.4)
        draw_text_outline(NAMES[current].upper(), big_font, COLOURS[current],
                          (W / 2, H / 2 - CELL * 4.85), max(0.05, ease_out_back(q)))
        draw_text_outline('WINS THE GAME!', font, WHITE, (W / 2, H / 2 - CELL * 3.7), max(0.05, q))
    if e > 3.8 and int(ts * 2) % 2 == 0:
        draw_text_outline('Tap to continue', font, WHITE, (W / 2, H / 2 + CELL * 5.0))

    # shockwave rings and a white flash at the very start
    bx, by = cell_to_px(7, 7)
    for k in range(3):
        qq = e * 1.4 - k * 0.25
        if 0 < qq < 1:
            pygame.draw.circle(screen, (WHITE, GOLD, COLOURS[current])[k], (bx, by),
                               CELL * (1 + 14 * qq), max(1, int(8 * (1 - qq))))
    if e < 0.45:
        flash_surf.set_alpha(int(255 * (1 - e / 0.45)))
        screen.blit(flash_surf, (0, 0))


def count_result():
    # keeps the score on this device (the first colour is the person who logged in)
    global result_counted
    if result_counted:
        return
    result_counted = True
    save['games'] += 1
    if current == 0:
        save['wins'] += 1
        who = (profile['name'] if profile and profile['name'] else 'Guest')
        save['board'][who] = save['board'].get(who, 0) + 1
    write_save()


def start_win():
    global state, win_mode, win_start, last_rocket, message, win_cheer_done, win_land_done
    state = 'won'
    win_mode = True
    win_start = last_rocket = pygame.time.get_ticks()
    win_cheer_done = win_land_done = False
    message = NAMES[current] + ' WINS!'
    count_result()
    for t in tokens[current]:
        t.win_from = (t.px, t.py)
        t.phase = t.no * 0.9
    rockets[:] = []
    balloons[:] = [make_balloon(True) for _ in range(12)]
    bx, by = cell_to_px(7, 7)
    for _ in range(80):                            # big burst from the middle of the board
        ang = random.random() * 2 * math.pi
        sp = random.uniform(2, 11) * K
        particles.append(Particle(bx, by, math.cos(ang) * sp, math.sin(ang) * sp, random.randint(40, 80),
                                  random.choice(COLOURS + [WHITE, GOLD]), random.uniform(3, 6) * K))
    spawn_confetti(90)
    play(snd_fanfare)
    play(snd_pop)


def update_win():
    global last_rocket, win_cheer_done, win_land_done
    now = pygame.time.get_ticks()
    e = (now - win_start) / 1000.0
    fly = max(0.0, min(1.0, (e - 0.25) / 1.1))
    q = ease_in_out(fly)
    for t in tokens[current]:
        # the four winners fly in a curve to the podium
        sx, sy = t.win_from
        tx = W / 2 + (t.no - 1.5) * CELL * 2.3
        ty = H / 2 + CELL * 2.9
        mx, my = (sx + tx) / 2, min(sy, ty) - CELL * 6
        t.px = (1 - q) ** 2 * sx + 2 * (1 - q) * q * mx + q * q * tx
        t.py = (1 - q) ** 2 * sy + 2 * (1 - q) * q * my + q * q * ty
        t.scale = 1 + 1.4 * q
        if fly < 1.0:
            t.height = 0
            if fly > 0 and random.random() < 0.7:
                particles.append(Particle(t.px, t.py - CELL * 0.3, random.uniform(-1, 1) * K,
                                          random.uniform(-1, 1) * K, 20, COLOURS[t.player],
                                          random.uniform(5, 8) * K, 'star'))
        else:
            t.height = abs(math.sin(e * 6 + t.no * 0.8)) * CELL * 0.8
    if fly >= 1.0 and not win_land_done:
        win_land_done = True
        play(snd_thud)
        for t in tokens[current]:
            spawn_sparkles(t.px, t.py, COLOURS[t.player], 14)
    if e > 0.6 and not win_cheer_done:
        win_cheer_done = True
        play(snd_cheer, 0.7)
    if e > 0.8 and now - last_rocket > 520:
        last_rocket = now
        rockets.append(Rocket())
    for rk in rockets:
        rk.update()
    rockets[:] = [rk for rk in rockets if not rk.done]
    for b in balloons:
        update_balloon(b)
    spawn_confetti(3)


# ---------- Knock-out (kill) animation ----------
def point_along(pts, lens, d):
    for i in range(1, len(pts)):
        if d <= lens[i] or i == len(pts) - 1:
            seg = lens[i] - lens[i - 1]
            f = 0.0 if seg == 0 else max(0.0, min(1.0, (d - lens[i - 1]) / seg))
            return (pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * f,
                    pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * f)
    return pts[-1]


def start_capture(mover, victims):
    global state, cap_victims, cap_mover, cap_start, cap_phase, message
    state = 'capture'
    cap_mover = mover
    cap_victims = victims
    cap_start = pygame.time.get_ticks()
    cap_phase = 0
    message = NAMES[mover.player] + ' knocked out ' + NAMES[victims[0].player] + '!'
    if GAME_RULES == 'master':
        if kills[mover.player] == 0:
            toast(NAMES[mover.player] + ': home path unlocked!', 2.8)
        kills[mover.player] += len(victims)        # MASTER: this colour may now enter the home path
    play(snd_kill)
    for v in victims:
        v.dead = True
        v.flash = True
        v.origin = (v.px, v.py)
        # the way home: the same boxes it walked, in reverse, down to its base
        pts = [v.origin]
        for s in range(v.steps - 1, -2, -1):
            c, r = v.grid_pos_for(s)
            pts.append(cell_to_px(c, r))
        lens = [0.0]
        for i in range(1, len(pts)):
            lens.append(lens[-1] + math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]))
        v.back_pts, v.back_len = pts, lens
        v.fly_ms = min(2200, max(900, 45 * len(pts)))
    spawn_impact(mover.px, mover.py, COLOURS[mover.player])


def update_capture():
    global cap_phase, cap_fly_start
    now = pygame.time.get_ticks()
    m = cap_mover
    if cap_phase == 0:
        # hit effect: the winner hops with joy, the loser is knocked into the air
        q = min(1.0, (now - cap_start) / T_HIT)
        m.height = math.sin(q * math.pi) * CELL * 0.35
        for i, v in enumerate(cap_victims):
            v.flash = q < 0.22
            v.height = math.sin(q * math.pi) * CELL * 1.3
            v.px = v.origin[0] + (1 if i % 2 == 0 else -1) * CELL * 0.5 * math.sin(q * math.pi)
        if q >= 1.0:
            cap_phase = 1
            cap_fly_start = now
            play(snd_whoosh)
            m.height = 0
            for v in cap_victims:
                v.flash = False
                v.px, v.py = v.origin
                v.height = 0
        return
    # fly back along the same path, smoothly, all the way to the base
    done = True
    for v in cap_victims:
        q = min(1.0, (now - cap_fly_start) / v.fly_ms)
        e = ease_in_out(q)
        v.px, v.py = point_along(v.back_pts, v.back_len, e * v.back_len[-1])
        v.height = math.sqrt(max(0.0, math.sin(q * math.pi))) * CELL * 0.35
        if q < 1.0:
            done = False
            particles.append(Particle(v.px, v.py - v.height - CELL * 0.25,
                                      random.uniform(-0.5, 0.5) * K, random.uniform(-0.5, 0.5) * K,
                                      14, COLOURS[v.player], 6 * K))
    if done:
        finish_capture()


def finish_capture():
    global cap_victims, cap_mover
    for v in cap_victims:
        v.steps = -1
        v.px, v.py = v.target_pixel()
        v.height = 0
        v.scale = 1.0
        v.dead = False
        v.flash = False
        spawn_sparkles(v.px, v.py - CELL * 0.3, COLOURS[v.player], 10)
    mover = cap_mover
    mover.height = 0
    cap_victims = []
    cap_mover = None
    after_landing(mover)


def draw_capture_fx():
    if cap_phase != 0 or cap_mover is None:
        return
    q = min(1.0, (pygame.time.get_ticks() - cap_start) / T_HIT)
    m = cap_mover
    gx, gy = m.px + m.dx, m.py + CELL * 0.3
    for k in range(2):                              # shockwave rings
        qq = max(0.0, q - k * 0.18)
        R = CELL * (0.3 + 1.8 * qq)
        wd = max(1, int(5 * (1 - qq)))
        pygame.draw.ellipse(screen, WHITE if k == 0 else COLOURS[m.player],
                            (gx - R, gy - R * 0.4, R * 2, R * 0.8), wd)
    sc = 0.4 + 1.0 * ease_out3(min(1.0, q * 2))      # KO text pops up
    draw_text_outline('KO!', font, GOLD, (m.px, m.py - CELL * (1.5 + 0.6 * q)), sc)


# ---------- Dice: a real 3D dice, thrown on a table pad that belongs to its colour ----------
def dice_rect(p):
    x, y = DICE_POS[p]
    return pygame.Rect(x, y, DS, DS)


def make_roll(p, face):
    # Plays the whole throw in advance: it flies up, falls, bounces three times and rolls to a stop.
    a = DS * DICE_EDGE
    h0 = 1.5 * a
    t1 = 0.42                                      # time of the first flight
    g = 8 * h0 / (t1 * t1)
    vz = g * t1 / 2
    vz0 = vz
    ang = random.uniform(0, 2 * math.pi)
    sp = DS * random.uniform(0.7, 1.0)
    vx, vy = math.cos(ang) * sp, math.sin(ang) * sp * 0.5
    x = y = h = 0.0
    dt = 1.0 / 120
    n = int(ROLL_SEC / dt)
    xs, ys, hs, imp = [], [], [], []
    for i in range(n + 1):
        xs.append(x)
        ys.append(y)
        hs.append(h)
        vz -= g * dt
        h += vz * dt
        x += vx * dt
        y += vy * dt
        drag = 6.0 if h <= 0 else 1.0
        vx -= vx * drag * dt
        vy -= vy * drag * dt
        if h <= 0:
            h = 0.0
            if vz < -0.12 * vz0:
                imp.append((i * dt, min(1.0, -vz / vz0)))   # the dice hits the table here
                vz = -vz * 0.5
                vx *= 0.8
                vy *= 0.8
            else:
                vz = 0.0
    ex, ey = xs[-1], ys[-1]
    for i in range(n + 1):                         # it comes to rest in the middle of the pad
        k = i / float(n)
        s = k * k * (3 - 2 * k)
        xs[i] -= ex * s
        ys[i] -= ey * s
    fx = min(1.0, DS * 0.26 / (max(abs(v) for v in xs) or 1.0))
    fy = min(1.0, DS * 0.14 / (max(abs(v) for v in ys) or 1.0))
    xs = [v * fx for v in xs]
    ys = [v * fy for v in ys]
    Rf = mmul(rot_z(random.uniform(-0.3, 0.3)), FACE_ROT[face])     # the chosen number ends on top
    axis, th = axis_angle(mmul(transpose(Rf), dice_orient[p]))
    return {'xs': xs, 'ys': ys, 'hs': hs, 'imp': imp, 'Rf': Rf, 'axis': axis, 'th': th,
            'n': [random.choice((-1, 1)) * random.randint(2, 4) for _ in range(3)]}


def roll_pose(t):
    # orientation, offset and height of the dice t seconds after the throw
    D = roll_data
    if t >= ROLL_SEC:
        return D['Rf'], 0.0, 0.0, 0.0
    u = t / ROLL_SEC
    f = 1 - (1 - u) ** 2                           # turning fast at first, slower and slower, then still
    G = rot_axis(D['axis'], D['th'] * (1 - f))
    E = mmul(rot_x(D['n'][0] * 2 * math.pi * f), mmul(rot_y(D['n'][1] * 2 * math.pi * f),
                                                      rot_z(D['n'][2] * 2 * math.pi * f)))
    i = min(int(t * 120), len(D['xs']) - 1)
    return mmul(D['Rf'], mmul(G, E)), D['xs'][i], D['ys'][i], D['hs'][i]


def draw_cube(gx, gy, a, R, hg, shade=1.0):
    # gx, gy: where the dice stands on the table; hg: height of its lowest corner above the table
    half = a / 2.0
    low = min(R[2][0] * sx + R[2][1] * sy + R[2][2] * sz
              for sx in (-half, half) for sy in (-half, half) for sz in (-half, half))
    zc = hg - low
    pr = a * 0.085
    for n, (nrm, u, v) in FACES.items():
        nw = mvec(R, nrm)
        if -nw[1] * COSA + nw[2] * SINA <= 0.03:
            continue                               # this side faces away from the camera
        uw, vw = mvec(R, u), mvec(R, v)
        lit = max(0.0, nw[0] * LX + nw[1] * LY + nw[2] * LZ)
        sf = (0.5 + 0.5 * lit) * shade
        col = (int(255 * sf), int(252 * sf), int(244 * sf))
        c0 = (nw[0] * half, nw[1] * half, nw[2] * half + zc)
        pts = []
        for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            X = c0[0] + (uw[0] * su + vw[0] * sv) * half
            Y = c0[1] + (uw[1] * su + vw[1] * sv) * half
            Z = c0[2] + (uw[2] * su + vw[2] * sv) * half
            pts.append((gx + X, gy - (Y * SINA + Z * COSA)))
        pygame.draw.polygon(screen, col, pts)
        pygame.draw.polygon(screen, (int(120 * sf), int(120 * sf), int(126 * sf)), pts, 2)
        for pu, pv in PIPS[n]:
            ring = []
            for k in range(10):
                an = k * 0.6283
                du = pu * a + math.cos(an) * pr
                dv = pv * a + math.sin(an) * pr
                X = c0[0] + uw[0] * du + vw[0] * dv
                Y = c0[1] + uw[1] * du + vw[1] * dv
                Z = c0[2] + uw[2] * du + vw[2] * dv
                ring.append((gx + X, gy - (Y * SINA + Z * COSA)))
            pygame.draw.polygon(screen, (28, 28, 34), ring)


def draw_dice_shadow(gx, gy, a, h):
    k = min(1.0, h / (2.0 * a))
    w = int(a * (1.25 + 0.35 * k)) // 4 * 4 + 4
    hh = int(a * (0.55 + 0.15 * k)) // 4 * 4 + 4
    screen.blit(get_shadow(w, hh, int(120 * (1 - 0.6 * k)) // 12 * 12), (gx - w / 2 + h * 0.15, gy - hh / 2 + a * 0.05))


def draw_lock(p, rect):
    # MASTER mode: a padlock on the pad. Red = home path still locked, green = open (a kill was made)
    opened = kills[p] > 0
    s = DS * 0.2
    x, y = rect.right - s * 1.1, rect.y + s * 0.15
    col = (60, 200, 110) if opened else (225, 60, 60)
    body = pygame.Rect(int(x), int(y + s * 0.45), int(s * 0.9), int(s * 0.65))
    sx = x + s * (0.62 if opened else 0.45)
    pygame.draw.arc(screen, WHITE, (sx - s * 0.3, y - s * 0.05, s * 0.6, s * 0.7), 0, math.pi, 3)
    pygame.draw.rect(screen, col, body, border_radius=4)
    pygame.draw.rect(screen, WHITE, body, 2, border_radius=4)
    pygame.draw.circle(screen, WHITE, (body.centerx, body.centery), max(2, int(s * 0.1)))


def gst():
    # the state of the game (a game that waits behind the Quit question keeps its own state)
    return prev_state if state == 'confirm_quit' else state


def draw_pad(p, r, now_ms):
    # the table the dice is thrown on, in the colour of its player
    ph = DS * SINA
    rect = pygame.Rect(r.x, r.centery - ph / 2, DS, ph)
    rad = int(DS * 0.16)
    is_cur = (p == current)
    if is_cur and gst() != 'won':
        glow = 4 + 3 * math.sin(now_ms / 200)
        pygame.draw.rect(screen, COLOURS[p], rect.inflate(glow * 2, glow * 2), border_radius=rad + 4)
    pygame.draw.rect(screen, (8, 12, 16), rect.move(0, 4), border_radius=rad)
    pygame.draw.rect(screen, (22, 96, 64) if is_cur else (16, 66, 46), rect, border_radius=rad)
    pygame.draw.rect(screen, COLOURS[p] if is_cur else DARK[p], rect, 4, border_radius=rad)
    if GAME_RULES == 'master':
        draw_lock(p, rect)


def draw_dice():
    now_ms = confirm_open_t if state == 'confirm_quit' else pygame.time.get_ticks()
    a = DS * DICE_EDGE
    for p in active_players:
        r = dice_rect(p)
        draw_pad(p, r, now_ms)
        gx, gy = r.centerx, r.centery + DS * 0.08
        if p == current and gst() == 'rolling' and roll_data is not None:
            t = (now_ms - roll_timer) / 1000.0
            R, x, y, h = roll_pose(max(0.0, t))
            gx2, gy2 = gx + x, gy - y * SINA
            draw_dice_shadow(gx2, gy2, a, h)
            draw_cube(gx2, gy2, a, R, h, 1.0)
            if t > ROLL_SEC:                       # the dice has stopped: the number pulses so it is clear
                q = min(1.0, (t - ROLL_SEC) / (ROLL_TIME / 1000.0 - ROLL_SEC))
                rr = DS * (0.35 + 0.2 * q)
                pygame.draw.ellipse(screen, COLOURS[p], (r.centerx - rr, r.centery - rr * 0.8,
                                                         rr * 2, rr * 1.6), max(1, int(5 * (1 - q))))
        else:
            draw_dice_shadow(gx, gy, a, 0.0)
            draw_cube(gx, gy, a, dice_orient[p], 0.0, 1.0 if p == current else 0.72)
        if p == current and gst() == 'roll' and p not in ai_players:
            draw_text_outline('TAP', small_font, WHITE, (r.centerx, r.centery + DS * 0.38),
                              1 + 0.06 * math.sin(now_ms / 150))


def draw_message():
    if not message:
        return                                     # nothing to say (for example while the dice rolls)
    mx, my, maxw = MSG
    txt = small_font.render(message, True, COLOURS[current])
    maxw = max(maxw, CELL * 4)
    if txt.get_width() > maxw:
        txt = pygame.transform.smoothscale(txt, (int(maxw), max(2, int(txt.get_height() * maxw / txt.get_width()))))
    pos = txt.get_rect(center=(mx, my))
    pygame.draw.rect(screen, WHITE, pos.inflate(20, 10), border_radius=10)
    screen.blit(txt, pos)


def draw_all(highlight):
    draw_board()
    draw_tokens(highlight)
    draw_dice()
    draw_name_tags()
    draw_message()
    if win_mode:
        draw_win_screen()
    draw_particles()
    draw_quit_button()
    draw_rules_badge()
    draw_toast(OY + CELL * 7.5)
    if state == 'confirm_quit':
        draw_confirm_box()
    pygame.display.flip()


# ======================================================================
#  HD ICONS (drawn 4 times bigger, then shrunk, so the edges are smooth and sharp)
# ======================================================================
icon_cache = {}


def sector(surf, col, cx, cy, r_out, r_in, a0, a1):
    n = max(6, int(abs(a1 - a0) / 3))
    pts = []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        pts.append((cx + math.cos(a) * r_out, cy + math.sin(a) * r_out))
    for i in range(n, -1, -1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        pts.append((cx + math.cos(a) * r_in, cy + math.sin(a) * r_in))
    pygame.draw.polygon(surf, col, pts)


def round_mask(w, h, r):
    m = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(m, (255, 255, 255, 255), (0, 0, w, h), border_radius=int(r))
    return m


def circle_mask(n):
    m = pygame.Surface((n, n), pygame.SRCALPHA)
    pygame.draw.circle(m, (255, 255, 255, 255), (n // 2, n // 2), n // 2)
    return m


def gradient_surface(w, h, c1, c2):
    s = pygame.Surface((w, h))
    for y in range(0, h, 2):
        f = y / float(h)
        pygame.draw.rect(s, tuple(int(c1[i] + (c2[i] - c1[i]) * f) for i in range(3)), (0, y, w, 2))
    return s


def hd_icon(kind, size):
    key = (kind, size)
    if key in icon_cache:
        return icon_cache[key]
    N = size * 4
    big = pygame.Surface((N, N), pygame.SRCALPHA)
    c = N / 2.0
    if kind == 'google':
        pygame.draw.circle(big, (255, 255, 255, 255), (c, c), N * 0.49)
        pygame.draw.circle(big, (226, 228, 236, 255), (c, c), N * 0.49, max(2, int(N * 0.012)))
        ro, ri = N * 0.30, N * 0.18
        sector(big, (234, 67, 53), c, c, ro, ri, 215, 330)
        sector(big, (251, 188, 5), c, c, ro, ri, 145, 215)
        sector(big, (52, 168, 83), c, c, ro, ri, 45, 145)
        sector(big, (66, 133, 244), c, c, ro, ri, 0, 45)
        pygame.draw.rect(big, (66, 133, 244), (c - N * 0.005, c - (ro - ri) * 0.5, ro + N * 0.005, ro - ri))
    elif kind == 'facebook':
        pygame.draw.circle(big, (24, 119, 242, 255), (c, c), N * 0.49)
        f = pygame.font.SysFont(None, int(N * 1.05))
        g = f.render('f', True, WHITE)
        for ox, oy in ((0, 0), (N * 0.012, 0), (-N * 0.012, 0), (0, N * 0.012)):
            big.blit(g, g.get_rect(center=(c + N * 0.06 + ox, c + N * 0.13 + oy)))
    elif kind == 'phone':
        pygame.draw.circle(big, (37, 170, 90, 255), (c, c), N * 0.49)
        body = pygame.Rect(0, 0, N * 0.34, N * 0.58)
        body.center = (c - N * 0.03, c)
        pygame.draw.rect(big, (255, 255, 255, 255), body, max(3, int(N * 0.04)), border_radius=int(N * 0.06))
        pygame.draw.rect(big, (255, 255, 255, 70), body.inflate(-N * 0.08, -N * 0.14), border_radius=int(N * 0.03))
        pygame.draw.line(big, WHITE, (body.centerx - N * 0.05, body.y + N * 0.045), (body.centerx + N * 0.05, body.y + N * 0.045), max(2, int(N * 0.025)))
        pygame.draw.circle(big, WHITE, (body.centerx, body.bottom - N * 0.045), max(2, int(N * 0.02)))
        for k in (1, 2):
            pygame.draw.arc(big, WHITE, (c + N * 0.16 - N * 0.07 * k, c - N * 0.22 - N * 0.07 * k, N * 0.14 * k + N * 0.1, N * 0.14 * k + N * 0.1),
                            -0.9, 0.9, max(2, int(N * 0.028)))
    elif kind == 'guest':
        pygame.draw.circle(big, (112, 122, 168, 255), (c, c), N * 0.49)
        body = pygame.Surface((N, N), pygame.SRCALPHA)
        pygame.draw.circle(body, (255, 255, 255, 255), (c, N * 0.38), N * 0.14)
        pygame.draw.ellipse(body, (255, 255, 255, 255), (N * 0.22, N * 0.56, N * 0.56, N * 0.56))
        body.blit(circle_mask(N), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        big.blit(body, (0, 0))
    elif kind == 'coin':
        pygame.draw.circle(big, (255, 190, 30, 255), (c, c), N * 0.49)
        pygame.draw.circle(big, (255, 226, 110, 255), (c, c), N * 0.42)
        pygame.draw.circle(big, (240, 150, 10, 255), (c, c), N * 0.36, max(2, int(N * 0.04)))
        pts = []
        for k in range(10):
            ang = math.pi / 2 + k * math.pi / 5
            rad = N * 0.22 if k % 2 == 0 else N * 0.09
            pts.append((c + rad * math.cos(ang), c - rad * math.sin(ang) + N * 0.01))
        pygame.draw.polygon(big, (230, 140, 10, 255), pts)
        pygame.draw.arc(big, (255, 255, 255, 220), (N * 0.12, N * 0.12, N * 0.76, N * 0.76), 1.9, 2.8, max(2, int(N * 0.03)))
    elif kind == 'plus':
        pygame.draw.rect(big, (52, 200, 110, 255), (0, 0, N, N), border_radius=int(N * 0.28))
        pygame.draw.rect(big, (255, 255, 255, 120), (0, 0, N, N), max(2, int(N * 0.04)), border_radius=int(N * 0.28))
        t = N * 0.14
        pygame.draw.rect(big, WHITE, (c - t / 2, N * 0.24, t, N * 0.52), border_radius=int(t * 0.4))
        pygame.draw.rect(big, WHITE, (N * 0.24, c - t / 2, N * 0.52, t), border_radius=int(t * 0.4))
    elif kind == 'gear':
        for k in range(8):
            a = math.radians(k * 45)
            ca, sa = math.cos(a), math.sin(a)
            pts = []
            for dr, dt in ((0.28, -0.09), (0.47, -0.065), (0.47, 0.065), (0.28, 0.09)):
                pts.append((c + (ca * dr - sa * dt) * N, c + (sa * dr + ca * dt) * N))
            pygame.draw.polygon(big, (255, 255, 255, 255), pts)
        pygame.draw.circle(big, (255, 255, 255, 255), (c, c), N * 0.34)
        pygame.draw.circle(big, (0, 0, 0, 0), (c, c), N * 0.14)
    elif kind == 'trophy':
        gold, dark = (255, 205, 50, 255), (215, 150, 20, 255)
        pygame.draw.ellipse(big, gold, (N * 0.07, N * 0.16, N * 0.3, N * 0.3), max(3, int(N * 0.05)))
        pygame.draw.ellipse(big, gold, (N * 0.63, N * 0.16, N * 0.3, N * 0.3), max(3, int(N * 0.05)))
        pygame.draw.polygon(big, gold, [(N * 0.25, N * 0.1), (N * 0.75, N * 0.1), (N * 0.68, N * 0.42), (N * 0.56, N * 0.56), (N * 0.44, N * 0.56), (N * 0.32, N * 0.42)])
        pygame.draw.polygon(big, (255, 240, 170, 255), [(N * 0.31, N * 0.14), (N * 0.4, N * 0.14), (N * 0.4, N * 0.4), (N * 0.34, N * 0.38)])
        pygame.draw.rect(big, dark, (N * 0.45, N * 0.55, N * 0.1, N * 0.2))
        pygame.draw.rect(big, dark, (N * 0.28, N * 0.74, N * 0.44, N * 0.12), border_radius=int(N * 0.03))
        pygame.draw.rect(big, gold, (N * 0.2, N * 0.84, N * 0.6, N * 0.09), border_radius=int(N * 0.03))
    elif kind == 'addfriend':
        pygame.draw.circle(big, (255, 255, 255, 255), (N * 0.4, N * 0.33), N * 0.17)
        pygame.draw.ellipse(big, (255, 255, 255, 255), (N * 0.08, N * 0.56, N * 0.64, N * 0.5))
        t = N * 0.1
        pygame.draw.rect(big, (255, 214, 70, 255), (N * 0.83 - t / 2, N * 0.22, t, N * 0.4), border_radius=int(t * 0.4))
        pygame.draw.rect(big, (255, 214, 70, 255), (N * 0.68, N * 0.37, N * 0.3, t), border_radius=int(t * 0.4))
    elif kind == 'avatar':
        big.blit(gradient_surface(N, N, (96, 150, 255), (150, 90, 230)), (0, 0))
        pygame.draw.circle(big, (255, 255, 255, 235), (c, N * 0.37), N * 0.17)
        pygame.draw.ellipse(big, (255, 255, 255, 235), (N * 0.17, N * 0.58, N * 0.66, N * 0.66))
        big.blit(round_mask(N, N, N * 0.22), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        pygame.draw.rect(big, (255, 255, 255, 255), (0, 0, N, N), max(3, int(N * 0.04)), border_radius=int(N * 0.22))
    out = pygame.transform.smoothscale(big, (size, size))
    icon_cache[key] = out
    return out


# ======================================================================
#  WELCOME + LOGIN PAGE  (green, pink and red background)
# ======================================================================
LOGIN_LABELS = ['Login with Google (Gmail)', 'Login with Facebook', 'Login Using Mobile Number', 'Login as Guest']
LOGIN_METHODS = ['google', 'facebook', 'mobile', 'guest']
LOGIN_ICONS = ['google', 'facebook', 'phone', 'guest']
WELCOME_LINES = ['WELCOME TO', 'OUR GAME']
login_t0 = None
login_hover = -1
login_assets = {}
bokeh_cache = {}
panel_cache = {}


def tri_colour(f):
    # smoothly blends green -> pink -> red -> green
    f = (f % 1.0) * 3
    i = int(f) % 3
    k = f - int(f)
    k = k * k * (3 - 2 * k)
    a, b = TRI[i], TRI[(i + 1) % 3]
    return tuple(int(a[j] + (b[j] - a[j]) * k) for j in range(3))


def render_fancy(text, size):
    # gold letters with a dark red line and a white outline
    f = pygame.font.SysFont(None, size)
    widths = [f.size(ch)[0] for ch in text]
    sp = size * 0.04
    pad = int(size * 0.16)
    total = sum(widths) + sp * (len(text) - 1)
    hgt = f.size('W')[1]
    surf = pygame.Surface((int(total) + 2 * pad, int(hgt) + 2 * pad), pygame.SRCALPHA)
    ro, ri = max(3, int(size * 0.05)), max(2, int(size * 0.025))
    x = float(pad)
    for ch, w in zip(text, widths):
        white = f.render(ch, True, WHITE)
        dark = f.render(ch, True, (110, 14, 50))
        gold = f.render(ch, True, (255, 207, 48))
        light = f.render(ch, True, (255, 244, 170))
        shade = f.render(ch, True, (60, 0, 20))
        surf.blit(shade, (x + ro * 0.6, pad + ro * 1.1))
        for k in range(8):
            a = k * math.pi / 4
            surf.blit(white, (x + math.cos(a) * ro, pad + math.sin(a) * ro))
        for k in range(8):
            a = k * math.pi / 4
            surf.blit(dark, (x + math.cos(a) * ri, pad + math.sin(a) * ri))
        surf.blit(gold, (x, pad))
        surf.blit(light, (x - 1, pad - 2))
        surf.blit(gold, (x, pad + 1))
        x += w + sp
    return surf


def make_sprite(kind, size, col):
    s = int(size)
    surf = pygame.Surface((s, s), pygame.SRCALPHA)
    if kind == 'dice':
        rr = int(s * 0.16)
        pygame.draw.rect(surf, (0, 0, 0, 55), (int(s * 0.12), int(s * 0.14), int(s * 0.78), int(s * 0.78)), border_radius=rr)
        pygame.draw.rect(surf, (255, 255, 255, 240), (int(s * 0.08), int(s * 0.08), int(s * 0.78), int(s * 0.78)), border_radius=rr)
        pygame.draw.rect(surf, col + (255,), (int(s * 0.08), int(s * 0.08), int(s * 0.78), int(s * 0.78)), 3, border_radius=rr)
        for fx, fy in PIPS[random.randint(1, 6)]:
            pygame.draw.circle(surf, (30, 30, 40, 255), (int(s * 0.47 + fx * s * 0.62), int(s * 0.47 + fy * s * 0.62)),
                               max(2, int(s * 0.06)))
    elif kind == 'pawn':
        pygame.draw.ellipse(surf, (0, 0, 0, 60), (int(s * 0.2), int(s * 0.78), int(s * 0.64), int(s * 0.16)))
        pygame.draw.polygon(surf, col + (255,), [(s * 0.38, s * 0.42), (s * 0.62, s * 0.42), (s * 0.78, s * 0.8), (s * 0.22, s * 0.8)])
        pygame.draw.ellipse(surf, col + (255,), (int(s * 0.18), int(s * 0.7), int(s * 0.64), int(s * 0.18)))
        pygame.draw.circle(surf, col + (255,), (int(s * 0.5), int(s * 0.3)), int(s * 0.18))
        pygame.draw.circle(surf, (255, 255, 255, 200), (int(s * 0.44), int(s * 0.25)), max(2, int(s * 0.05)))
        pygame.draw.polygon(surf, (255, 255, 255, 235), [(s * 0.38, s * 0.42), (s * 0.62, s * 0.42), (s * 0.78, s * 0.8), (s * 0.22, s * 0.8)], 3)
    elif kind == 'star':
        pts = []
        for k in range(10):
            ang = math.pi / 2 + k * math.pi / 5
            rad = s * 0.46 if k % 2 == 0 else s * 0.2
            pts.append((s * 0.5 + rad * math.cos(ang), s * 0.52 - rad * math.sin(ang)))
        pygame.draw.polygon(surf, (255, 214, 60, 255), pts)
        pygame.draw.polygon(surf, (255, 255, 255, 230), pts, 3)
    else:
        pygame.draw.circle(surf, (255, 205, 50, 255), (s // 2, s // 2), int(s * 0.42))
        pygame.draw.circle(surf, (210, 150, 20, 255), (s // 2, s // 2), int(s * 0.42), 4)
        pygame.draw.circle(surf, (255, 235, 140, 255), (s // 2, s // 2), int(s * 0.28), 3)
    return surf


def login_geometry():
    bw = int(min(W * 0.86, CELL * 13))
    bh = int(CELL * 1.7)
    gap = int(CELL * 0.3)
    total = 4 * bh + 3 * gap
    top = int(H / 2 + CELL * 0.1)                  # a little lower than the middle of the screen
    if top + total > H - CELL * 1.0:
        top = int(H - CELL * 1.0 - total)
    x = (W - bw) // 2
    rects = [pygame.Rect(x, top + i * (bh + gap), bw, bh) for i in range(4)]
    heading_y = top - CELL * 0.85
    sub_y = heading_y - CELL * 1.45
    return rects, heading_y, sub_y


def build_login_assets():
    A = login_assets
    if A:
        return
    n = 72                                           # green -> pink -> red, blended smoothly and drawn only once
    small = pygame.Surface((n, n))
    for yy in range(n):
        for xx in range(n):
            small.set_at((xx, yy), tri_colour((xx + yy) / float(n)))
    A['tile'] = pygame.transform.smoothscale(small, (W, H))
    # floating Ludo things: dice, pawns, stars and coins
    rng = random.Random(5)
    deco = []
    for i in range(20):
        kind = ('dice', 'pawn', 'star', 'coin')[i % 4]
        size = CELL * rng.uniform(0.9, 2.0)
        spr = make_sprite(kind, size, rng.choice(COLOURS))
        frames = [pygame.transform.rotate(spr, a * 22.5) for a in range(16)]     # turned copies, made only once
        deco.append({'frames': frames, 'x': rng.uniform(0, W),
                     'y0': rng.uniform(0, H + 300), 'v': rng.uniform(18, 55), 'ph': rng.uniform(0, 6.28),
                     'rot': rng.uniform(-3, 3), 'sway': rng.uniform(10, 40) * K, 'size': size})
    A['deco'] = deco
    A['bokeh'] = [(rng.uniform(0, W), rng.uniform(0, H), rng.randint(int(CELL * 0.4), int(CELL * 1.6)),
                   rng.uniform(8, 22), rng.uniform(0, 6.28)) for _ in range(16)]
    # the big title, "LUDO" over "GAME"
    ref = pygame.font.SysFont(None, 100)
    w4 = sum(ref.size(ch)[0] for ch in 'LUDO') + 6 * 3
    s1 = int(max(30, min(100 * W * 0.78 / w4, CELL * 4.8)))
    l1, l2 = render_fancy('LUDO', s1), render_fancy('GAME', int(s1 * 0.8))
    ov = int(s1 * 0.12)
    tw = max(l1.get_width(), l2.get_width())
    th = l1.get_height() + l2.get_height() - ov
    title = pygame.Surface((tw, th), pygame.SRCALPHA)
    title.blit(l1, ((tw - l1.get_width()) // 2, 0))
    title.blit(l2, ((tw - l2.get_width()) // 2, l1.get_height() - ov))
    rects, heading_y, sub_y = login_geometry()
    allowed = sub_y - CELL * 1.0 - CELL * 0.6
    if th > allowed:
        f = allowed / float(th)
        title = pygame.transform.smoothscale(title, (max(2, int(tw * f)), max(2, int(th * f))))
    A['title'] = title
    A['title_cy'] = min(H * 0.26, sub_y - CELL * 1.0 - title.get_height() / 2.0)
    # the letters of WELCOME TO OUR GAME
    widest = max(sum(ref.size(ch)[0] for ch in ln) + 6 * (len(ln) - 1) for ln in WELCOME_LINES)
    size = int(max(20, min(100 * (W * 0.9) / widest, CELL * 3.6)))
    f = pygame.font.SysFont(None, size)
    lh = f.size('W')[1]
    sp = size * 0.06
    letters = []
    idx = 0
    for li, line in enumerate(WELCOME_LINES):
        widths = [f.size(ch)[0] for ch in line]
        x = W / 2 - (sum(widths) + sp * (len(line) - 1)) / 2
        y = H / 2 + (li - (len(WELCOME_LINES) - 1) / 2) * lh * 1.1
        for ch, w in zip(line, widths):
            if ch != ' ':
                col = WHITE if idx % 2 == 0 else (255, 235, 120)
                letters.append({'x': x + w / 2, 'y': y, 'i': idx,
                                'base': f.render(ch, True, col), 'shad': f.render(ch, True, (90, 10, 45))})
                idx += 1
            x += w + sp
    A['letters'] = letters
    A['stars'] = [(rng.random() * W, rng.random() * H, rng.uniform(0.5, 1.0) * CELL * 0.14, rng.random() * 6.28)
                  for _ in range(30)]


def draw_login_bg(ts):
    t = login_assets['tile']
    ox, oy = int(ts * 34) % W, int(ts * 24) % H
    screen.blit(t, (-ox, -oy))
    screen.blit(t, (W - ox, -oy))
    screen.blit(t, (-ox, H - oy))
    screen.blit(t, (W - ox, H - oy))


def get_bokeh(r):
    if r not in bokeh_cache:
        s = pygame.Surface((2 * r + 4, 2 * r + 4), pygame.SRCALPHA)
        pygame.draw.circle(s, (255, 255, 255, 30), (r + 2, r + 2), r)
        pygame.draw.circle(s, (255, 255, 255, 60), (r + 2, r + 2), r, 3)
        bokeh_cache[r] = s
    return bokeh_cache[r]


def draw_login_deco(ts):
    A = login_assets
    for x, y, r, sp, ph in A['bokeh']:
        s = get_bokeh(r)
        screen.blit(s, (x + math.sin(ts * 0.3 + ph) * 30 * K - r, (y - ts * sp) % (H + 2 * r) - r))
    for d in A['deco']:
        span = H + 2 * d['size']
        y = (d['y0'] - ts * d['v']) % span - d['size']
        x = d['x'] + math.sin(ts * 0.8 + d['ph']) * d['sway']
        fr = d['frames'][int(ts * d['rot'] * 1.5 + d['ph'] * 10) % 16]
        screen.blit(fr, fr.get_rect(center=(x, y)))


def draw_login_button(rect, i, hover):
    lift = -4 if hover else 0
    r = rect.move(0, lift)
    rad = int(r.h * 0.3)
    pygame.draw.rect(screen, (60, 10, 30), r.move(0, 7), border_radius=rad)
    pygame.draw.rect(screen, (252, 252, 255) if not hover else (255, 246, 250), r, border_radius=rad)
    pygame.draw.rect(screen, (255, 214, 70) if i == 3 else (255, 255, 255), r, 3, border_radius=rad)
    ic = int(r.h * 0.72)
    screen.blit(hd_icon(LOGIN_ICONS[i], ic), (r.x + int(r.h * 0.2), r.y + (r.h - ic) // 2))
    txt = small_font.render(LOGIN_LABELS[i], True, (50, 40, 60))
    maxw = r.w - r.h * 1.5 - CELL * 0.4
    if txt.get_width() > maxw:
        txt = pygame.transform.smoothscale(txt, (int(maxw), max(2, int(txt.get_height() * maxw / txt.get_width()))))
    screen.blit(txt, txt.get_rect(center=(r.x + r.h * 1.2 + maxw / 2, r.centery)))
    ax = r.right - int(r.h * 0.42)
    pygame.draw.polygon(screen, (200, 60, 110), [(ax - 6, r.centery - 9), (ax + 6, r.centery), (ax - 6, r.centery + 9)])


def blit_letter(L, s, alpha, dy=0.0):
    base, shad = L['base'], L['shad']
    if abs(s - 1.0) > 0.01:
        base = pygame.transform.rotozoom(base, 0, s)
        shad = pygame.transform.rotozoom(shad, 0, s)
    elif alpha < 255:
        base, shad = base.copy(), shad.copy()
    if alpha < 255:
        base.set_alpha(alpha)
        shad.set_alpha(alpha)
    rect = base.get_rect(center=(L['x'], L['y'] + dy))
    off = max(2, int(3 * s))
    for ox, oy in ((-off, 0), (off, 0), (0, -off), (0, off)):
        screen.blit(shad, rect.move(ox, oy))
    screen.blit(base, rect)


def draw_login():
    global login_t0
    now = pygame.time.get_ticks()
    if login_t0 is None:
        login_t0 = now
    build_login_assets()
    A = login_assets
    t = (now - login_t0) / 1000.0
    ts = now / 1000.0
    rects, heading_y, sub_y = login_geometry()
    draw_login_bg(ts)
    draw_login_deco(ts)

    # 1) WELCOME TO OUR GAME: letters drop in and pop up, stay, then shrink and fade away
    if t < 3.4:
        for L in A['letters']:
            i = L['i']
            ta, td = 0.1 + 0.06 * i, 1.9 + 0.045 * i
            if t < ta:
                continue
            if t < td:
                q = min(1.0, (t - ta) / 0.45)
                blit_letter(L, max(0.05, ease_out_back(q)), 255, -(1 - ease_out3(q)) * CELL * 1.2)
            else:
                q = (t - td) / 0.7
                if q < 1.0:
                    blit_letter(L, max(0.05, 1 - 0.95 * ease_in_out(q)), int(255 * (1 - q)))

    # 2) LUDO GAME grows from small on the same screen, then settles up at the top
    if t > 2.3:
        q = clamp01((t - 2.3) / 1.5)
        sc = max(0.05, 0.05 + 0.95 * ease_out_back(q))
        g = ease_in_out(clamp01((t - 3.9) / 0.8))
        cy = H / 2 + (A['title_cy'] - H / 2) * g
        if t > 4.7:
            cy += math.sin(ts * 2.2) * CELL * 0.07
        tit = A['title']
        gs = max(2, int(tit.get_width() * 1.5 * sc))
        gl = pygame.transform.smoothscale(glow_surf, (gs, gs))
        screen.blit(gl, gl.get_rect(center=(W / 2, cy)))
        img = tit if abs(sc - 1.0) < 0.005 else pygame.transform.rotozoom(tit, 0, sc)
        screen.blit(img, img.get_rect(center=(W / 2, cy)))
        if q >= 1.0:
            for k in range(6):                      # little stars circle around the title
                a = ts * 1.1 + k * math.pi / 3
                draw_star(W / 2 + math.cos(a) * tit.get_width() * 0.56, cy + math.sin(a) * tit.get_height() * 0.52,
                          CELL * (0.16 + 0.07 * math.sin(ts * 5 + k)), GOLD)
        if random.random() < 0.35:
            spawn_sparkles(W / 2 + random.uniform(-0.5, 0.5) * img.get_width(),
                           cy + random.uniform(-0.5, 0.5) * img.get_height(), random.choice([GOLD, WHITE]), 1)

    # 3) subtitle, heading and the four login buttons
    if t > 4.3:
        q = clamp01((t - 4.3) / 0.5)
        band = pygame.Rect(0, 0, int(min(W * 0.8, CELL * 12)), int(CELL * 0.95))
        band.center = (W / 2, sub_y - (1 - ease_out3(q)) * CELL)
        pygame.draw.rect(screen, (120, 18, 56), band, border_radius=int(band.h * 0.5))
        pygame.draw.rect(screen, (255, 215, 90), band, 3, border_radius=int(band.h * 0.5))
        sub = tiny_font.render('THE CLASSIC BOARD GAME', True, (255, 236, 160))
        screen.blit(sub, sub.get_rect(center=band.center))
        draw_text_outline('Login to play', small_font, WHITE, (W / 2, heading_y - (1 - ease_out3(q)) * CELL))
        for i, r in enumerate(rects):
            qi = clamp01((t - 4.3 - i * 0.16) / 0.5)
            if qi > 0:
                off = (1 - ease_out_back(qi)) * CELL * 4
                draw_login_button(r.move(0, int(off)), i, i == login_hover)
    update_particles()
    draw_particles()
    pygame.display.flip()


def login_tap(pos):
    global login_t0
    now = pygame.time.get_ticks()
    if login_t0 is None:
        return
    t = (now - login_t0) / 1000.0
    if t < 5.3:
        login_t0 = now - 6000                       # a tap skips the intro and shows everything
        return
    rects, _, _ = login_geometry()
    for i, r in enumerate(rects):
        if r.collidepoint(pos):
            play(snd_thud, 0.6)
            begin_auth(LOGIN_METHODS[i])
            return


# ======================================================================
#  TEXT INPUT: always the normal keyboard of the device (no keyboard is drawn by the game)
# ======================================================================
HAS_TI = hasattr(pygame, 'TEXTINPUT') and hasattr(pygame.key, 'start_text_input')
TEXT_EVENT = getattr(pygame, 'TEXTINPUT', -1)
field_kind = ''                 # gmail, fbname, phone, otp or name
field_text = ''
field_error = ''
field_rect = pygame.Rect(0, 0, 10, 10)


kb_request_at = 0
kb_wanted = False
pending_kd = None               # a key press that waits to see if a TEXTINPUT event follows (so a letter is never typed twice)


def open_keyboard(delay=0):
    # asks the device to show its normal keyboard (the phone keyboard, or the physical keyboard of a laptop)
    global kb_request_at
    kb_request_at = pygame.time.get_ticks() + delay


def service_keyboard():
    # always switches the text input off and on again, so the keyboard also comes back if it was hidden earlier
    global kb_request_at
    if kb_request_at and pygame.time.get_ticks() >= kb_request_at:
        kb_request_at = 0
        for fn, arg in ((pygame.key.stop_text_input, None), (pygame.key.set_text_input_rect, field_rect),
                        (pygame.key.start_text_input, None)):
            try:
                fn() if arg is None else fn(arg)
            except Exception:
                pass


def close_keyboard():
    global kb_request_at
    kb_request_at = 0
    try:
        pygame.key.stop_text_input()
    except Exception:
        pass


def field_limit():
    return {'gmail': 40, 'fbname': 40, 'phone': 12, 'otp': 4, 'name': 14}.get(field_kind, 30)


def input_char(ch):
    global field_text, field_error
    if not ch or not ch.isprintable():
        return
    if screen_state == 'modes':                     # the name of a player
        if 0 <= field_active < len(name_fields) and not name_fields[field_active]['ai']:
            f = name_fields[field_active]
            if len(f['text']) < 14:
                f['text'] += ch
        return
    if auth_step in ('busy', 'done') and screen_state == 'auth':
        return
    if field_kind in ('phone', 'otp') and not ch.isdigit():
        return
    if field_kind == 'gmail' and ch == ' ':
        return
    if len(field_text) >= field_limit():
        return
    field_text += ch
    field_error = ''


def input_backspace():
    global field_text, field_error
    if screen_state == 'modes':
        if 0 <= field_active < len(name_fields) and not name_fields[field_active]['ai']:
            f = name_fields[field_active]
            f['text'] = f['text'][:-1]
        return
    field_text = field_text[:-1]
    field_error = ''


def input_enter():
    if screen_state == 'auth':
        auth_submit()
    elif screen_state == 'name':
        name_next()
    elif screen_state == 'modes':
        modes_enter_key()


def key_down(event):
    global pending_kd
    if event.key == pygame.K_BACKSPACE:
        input_backspace()
    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
        input_enter()
    elif event.key == pygame.K_ESCAPE:
        if screen_state == 'auth':
            auth_back()
        elif screen_state == 'name':
            name_back()
        elif screen_state == 'modes':
            modes_back()
    else:
        ch = getattr(event, 'unicode', '')
        if ch and ch.isprintable():
            if HAS_TI:
                pending_kd = (ch, pygame.time.get_ticks())   # a TEXTINPUT event normally follows; if not, the key itself is used
            else:
                input_char(ch)


def draw_field(rect, shown_text, hint, now_ms, active=True, centered=False, big=False):
    # a rounded box with a blinking cursor
    global field_rect
    field_rect = rect
    rad = int(min(rect.w, rect.h) * (0.16 if big else 0.28))
    pygame.draw.rect(screen, (0, 0, 0), rect.move(0, 5), border_radius=rad)
    pygame.draw.rect(screen, WHITE, rect, border_radius=rad)
    pygame.draw.rect(screen, (255, 110, 160), rect, 4, border_radius=rad)
    fnt = big_font if big else small_font
    cur = '|' if (active and int(now_ms / 500) % 2 == 0) else ' '
    if shown_text == '':
        tx = fnt.render(hint, True, (170, 160, 175))
        screen.blit(tx, tx.get_rect(center=rect.center) if centered else tx.get_rect(midleft=(rect.x + rect.h * 0.3, rect.centery)))
        cx = rect.centerx if centered else rect.x + rect.h * 0.3
        pygame.draw.line(screen, (255, 110, 160), (cx, rect.centery - fnt.get_height() * 0.4),
                         (cx, rect.centery + fnt.get_height() * 0.4), 3) if cur == '|' else None
        return
    tx = fnt.render(shown_text, True, (40, 30, 50))
    maxw = rect.w - rect.h * 0.6
    if tx.get_width() > maxw:
        f = maxw / float(tx.get_width())
        tx = pygame.transform.smoothscale(tx, (int(maxw), max(2, int(tx.get_height() * f))))
    pos = tx.get_rect(center=rect.center) if centered else tx.get_rect(midleft=(rect.x + rect.h * 0.3, rect.centery))
    screen.blit(tx, pos)
    if cur == '|':
        pygame.draw.line(screen, (255, 110, 160), (pos.right + 3, rect.centery - fnt.get_height() * 0.4),
                         (pos.right + 3, rect.centery + fnt.get_height() * 0.4), 3)


# ======================================================================
#  LOGIN SCREENS (a demo: nothing is sent anywhere; only your name is saved on this device)
# ======================================================================
auth_method = ''
auth_step = 'input'             # input, otp, busy, done
auth_phone = ''
auth_otp = ''
auth_t0 = 0
auth_ident = ''
auth_enter = 0
name_enter = 0
name_prefill = ''


def begin_auth(method):
    global screen_state, auth_method, auth_step, field_text, field_error, auth_enter, field_kind, profile
    if method == 'guest':                          # guests go straight to "Add Your Name"
        profile = {'name': '', 'method': 'guest', 'id': ''}
        go_name('')
        return
    screen_state = 'auth'
    auth_method = method
    auth_step = 'input'
    field_kind = {'google': 'gmail', 'facebook': 'fbname', 'mobile': 'phone'}[method]
    field_text = ''
    field_error = ''
    auth_enter = pygame.time.get_ticks()
    open_keyboard(250)


def valid_gmail(s):
    s = s.strip().lower()
    if s.count('@') != 1:
        return False
    local, dom = s.split('@')
    return (dom in ('gmail.com', 'googlemail.com') and len(local) >= 3
            and all(c.isalnum() or c in '._-' for c in local))


def valid_facebook(s):
    s = s.strip()
    if len(s) < 3:
        return False
    if '@' in s:
        local, _, dom = s.partition('@')
        return len(local) >= 1 and '.' in dom and len(dom) >= 3
    return True


def make_profile(method, ident):
    if method == 'google':
        base = ident.split('@')[0]
        words = [w for w in base.replace('.', ' ').replace('_', ' ').replace('-', ' ').split() if w]
        name = ' '.join(w.capitalize() for w in words[:2])
    elif method == 'facebook':
        base = ident.split('@')[0] if '@' in ident else ident
        name = ' '.join(w.capitalize() for w in base.replace('.', ' ').replace('_', ' ').split()[:2])
    else:
        name = ''
    return {'name': name[:14], 'method': method, 'id': ident}


def auth_back():
    global screen_state, login_t0, auth_step, field_text, field_error, field_kind
    if auth_step in ('busy', 'done'):
        return
    if auth_step == 'otp':
        auth_step, field_text, field_error, field_kind = 'input', '', '', 'phone'
        open_keyboard(150)
        return
    close_keyboard()
    screen_state = 'login'
    login_t0 = pygame.time.get_ticks() - 6000


def auth_submit():
    global auth_step, field_error, auth_phone, auth_otp, field_text, auth_t0, auth_ident, field_kind
    if auth_step in ('busy', 'done'):
        return
    txt = field_text.strip()
    if auth_step == 'otp':
        if txt == auth_otp:
            auth_ident = auth_phone
            auth_step, auth_t0 = 'busy', pygame.time.get_ticks()
            close_keyboard()
        else:
            field_error = 'Wrong code, please try again'
            field_text = ''
        return
    if auth_method == 'google':
        if not valid_gmail(txt):
            field_error = 'Enter your full Gmail address (name@gmail.com)'
            return
        auth_ident = txt.lower()
    elif auth_method == 'facebook':
        if not valid_facebook(txt):
            field_error = 'Enter your Facebook name or email (3+ letters)'
            return
        auth_ident = txt
    else:
        if not (10 <= len(txt) <= 12):
            field_error = 'Enter a valid mobile number (10 digits)'
            return
        auth_phone = txt
        auth_otp = str(random.randint(1000, 9999))
        auth_step, field_text, field_error, field_kind = 'otp', '', '', 'otp'
        open_keyboard(150)
        return
    auth_step, auth_t0 = 'busy', pygame.time.get_ticks()
    close_keyboard()


def finish_auth():
    global profile, auth_step, auth_t0
    profile = make_profile(auth_method, auth_ident)
    auth_step, auth_t0 = 'done', pygame.time.get_ticks()
    play(snd_fanfare, 0.5)
    spawn_sparkles(W / 2, H * 0.4, GOLD, 40)


def auth_geom():
    field = pygame.Rect(0, 0, int(min(W * 0.86, CELL * 12)), int(CELL * 1.8))
    field.midtop = (W // 2, int(H * 0.30))
    off = 2.5 if auth_step == 'otp' else 1.35
    cont = pygame.Rect(0, 0, int(min(W * 0.86, CELL * 11)), int(CELL * 1.7))
    cont.midtop = (W // 2, int(field.bottom + CELL * off))
    resend = pygame.Rect(0, 0, int(CELL * 5), int(CELL * 0.9))
    resend.midtop = (W // 2, int(cont.bottom + CELL * 0.4))
    back = pygame.Rect(10, 10, int(CELL * 2.6), int(CELL * 1.1))
    return field, cont, resend, back


def auth_tap(pos):
    field, cont, resend, back = auth_geom()
    if auth_step == 'done':
        return
    if back.collidepoint(pos):
        auth_back()
        return
    if auth_step == 'busy':
        return
    if field.collidepoint(pos):
        open_keyboard()                            # tap the box: the normal keyboard opens
        return
    if cont.collidepoint(pos):
        play(snd_thud, 0.5)
        auth_submit()
        return
    if auth_step == 'otp' and resend.collidepoint(pos):
        global auth_otp, field_text, field_error
        auth_otp = str(random.randint(1000, 9999))
        field_text, field_error = '', ''


def draw_auth():
    global screen_state
    now = pygame.time.get_ticks()
    ts = now / 1000.0
    build_login_assets()
    draw_login_bg(ts)
    draw_login_deco(ts)
    field, cont, resend, back = auth_geom()

    pygame.draw.rect(screen, WHITE, back, border_radius=14)
    bt = small_font.render('< Back', True, (120, 20, 60))
    screen.blit(bt, bt.get_rect(center=back.center))
    ic = int(CELL * 2.6)
    screen.blit(hd_icon({'google': 'google', 'facebook': 'facebook', 'mobile': 'phone'}[auth_method], ic),
                (W // 2 - ic // 2, int(H * 0.115)))
    head = {'google': 'Login with Google', 'facebook': 'Login with Facebook', 'mobile': 'Login with Mobile'}[auth_method]
    draw_text_outline(head, big_font, WHITE, (W // 2, int(H * 0.115 + ic + CELL * 0.9)))

    if auth_method == 'google':
        label = 'Gmail address'
    elif auth_method == 'facebook':
        label = 'Facebook name or email'
    else:
        label = 'Mobile number' if auth_step == 'input' else 'Enter the 4 digit code'
    lt = small_font.render(label, True, WHITE)
    screen.blit(lt, lt.get_rect(midleft=(field.x + CELL * 0.2, field.y - CELL * 0.55)))
    hint = {'gmail': 'yourname@gmail.com', 'fbname': 'Your name', 'phone': '10 digit number', 'otp': '4 digit code'}[field_kind]
    draw_field(field, field_text, hint, now, auth_step in ('input', 'otp'))

    if auth_step == 'otp':
        pill = pygame.Rect(0, 0, int(CELL * 8.2), int(CELL * 0.95))
        pill.midtop = (W // 2, int(field.bottom + CELL * 0.35))
        pygame.draw.rect(screen, (255, 214, 70), pill, border_radius=int(pill.h * 0.5))
        pt = small_font.render('Demo code: ' + auth_otp, True, (90, 20, 40))
        screen.blit(pt, pt.get_rect(center=pill.center))
        nt = tiny_font.render('(no SMS is sent in this demo)', True, (255, 240, 245))
        screen.blit(nt, nt.get_rect(center=(W // 2, int(pill.bottom + CELL * 0.4))))
    if field_error:
        et = tiny_font.render(field_error, True, (255, 244, 150))
        screen.blit(et, et.get_rect(center=(W // 2, int(field.bottom + CELL * (0.55 if auth_step == 'input' else 2.2)))))

    pygame.draw.rect(screen, (60, 10, 30), cont.move(0, 5), border_radius=int(cont.h * 0.3))
    pygame.draw.rect(screen, (255, 214, 70), cont, border_radius=int(cont.h * 0.3))
    ct = font.render('Verify' if auth_step == 'otp' else ('Send code' if auth_method == 'mobile' else 'Continue'),
                     True, (90, 20, 40))
    screen.blit(ct, ct.get_rect(center=cont.center))
    if auth_step == 'otp':
        rt = tiny_font.render('Send a new code', True, WHITE)
        screen.blit(rt, rt.get_rect(center=resend.center))
    note = tiny_font.render('Tap the box to open your keyboard. Demo sign-in: nothing is sent anywhere.', True, (255, 240, 245))
    if note.get_width() > W * 0.94:
        note = pygame.transform.smoothscale(note, (int(W * 0.94), max(2, int(note.get_height() * W * 0.94 / note.get_width()))))
    screen.blit(note, note.get_rect(center=(W // 2, int(resend.bottom + CELL * 1.0))))

    # signing in ... and the welcome check mark
    if auth_step in ('busy', 'done'):
        shade = pygame.Surface((W, H), pygame.SRCALPHA)
        shade.fill((20, 0, 20, 170))
        screen.blit(shade, (0, 0))
        el = (now - auth_t0) / 1000.0
        cx, cy = W // 2, int(H * 0.4)
        if auth_step == 'busy':
            r = int(CELL * 1.2)
            pygame.draw.circle(screen, (255, 255, 255), (cx, cy), r, 4)
            pygame.draw.arc(screen, (255, 214, 70), (cx - r, cy - r, 2 * r, 2 * r), ts * 6, ts * 6 + 2.2, 10)
            draw_text_outline('Signing in...', font, WHITE, (cx, cy + int(CELL * 2.4)))
            if el > 1.3:
                finish_auth()
        else:
            q = clamp01(el / 0.45)
            r = int(CELL * 1.5 * ease_out_back(q))
            pygame.draw.circle(screen, (60, 190, 110), (cx, cy), max(2, r))
            pygame.draw.circle(screen, WHITE, (cx, cy), max(2, r), 5)
            if q >= 1.0:
                pygame.draw.lines(screen, WHITE, False, [(cx - r * 0.45, cy), (cx - r * 0.1, cy + r * 0.35),
                                                         (cx + r * 0.5, cy - r * 0.35)], 10)
            draw_text_outline('Logged in!', big_font, GOLD, (cx, cy + int(CELL * 2.6)))
            if el > 1.5:
                particles[:] = []
                go_name(profile['name'])
    update_particles()
    draw_particles()
    fade = (now - auth_enter) / 400.0
    if fade < 1.0:
        overlay_surf.set_alpha(int(255 * (1 - max(0.0, fade))))
        screen.blit(overlay_surf, (0, 0))
    pygame.display.flip()


# ======================================================================
#  ADD YOUR NAME PAGE
# ======================================================================
def go_name(prefill):
    global screen_state, field_kind, field_text, field_error, name_enter
    screen_state = 'name'
    field_kind = 'name'
    field_text = (prefill or save['name'] or '')[:14]
    field_error = ''
    name_enter = pygame.time.get_ticks()
    open_keyboard(250)


def name_geom():
    side = int(min(W * 0.62, CELL * 8.4, H * 0.32))
    box = pygame.Rect(0, 0, side, side)
    box.midtop = (W // 2, int(H * 0.2))
    nxt = pygame.Rect(0, 0, side, int(CELL * 1.8))
    nxt.midtop = (W // 2, int(box.bottom + CELL * 0.45))
    back = pygame.Rect(10, 10, int(CELL * 2.6), int(CELL * 1.1))
    return box, nxt, back


def name_next():
    global profile
    name = ''.join(ch for ch in field_text if ch.isprintable()).strip()
    if not name:
        global field_error
        field_error = 'Please type a name first'
        return
    if profile is None:
        profile = {'name': name, 'method': 'guest', 'id': ''}
    profile['name'] = name[:14]
    save['name'] = profile['name']
    write_save()
    close_keyboard()
    go_home(True)


def name_back():
    global screen_state, login_t0
    close_keyboard()
    screen_state = 'login'
    login_t0 = pygame.time.get_ticks() - 6000


def name_tap(pos):
    box, nxt, back = name_geom()
    if back.collidepoint(pos):
        name_back()
    elif box.collidepoint(pos):
        open_keyboard()                            # tap the box: the normal keyboard opens
    elif nxt.collidepoint(pos):
        play(snd_thud, 0.5)
        name_next()


def draw_home_bg(ts):
    build_login_assets()
    screen.blit(wallpaper, (0, 0))
    draw_login_deco(ts)


def draw_name():
    now = pygame.time.get_ticks()
    ts = now / 1000.0
    box, nxt, back = name_geom()
    draw_home_bg(ts)
    pygame.draw.rect(screen, WHITE, back, border_radius=14)
    bt = small_font.render('< Back', True, (60, 30, 100))
    screen.blit(bt, bt.get_rect(center=back.center))
    draw_text_outline('Add Your Name', big_font, WHITE, (W // 2, int(box.y - CELL * 2.0)))
    draw_field(box, field_text, 'Your name', now, True, True, True)
    if field_error:
        et = small_font.render(field_error, True, (255, 244, 150))
        screen.blit(et, et.get_rect(center=(W // 2, int(box.bottom + CELL * 0.45 + nxt.h + CELL * 0.8))))
    ok = field_text.strip() != ''
    pygame.draw.rect(screen, (40, 10, 60), nxt.move(0, 6), border_radius=int(nxt.h * 0.3))
    pygame.draw.rect(screen, (255, 200, 50) if ok else (150, 150, 165), nxt, border_radius=int(nxt.h * 0.3))
    pygame.draw.rect(screen, WHITE, nxt, 3, border_radius=int(nxt.h * 0.3))
    t = font.render('Next', True, (90, 25, 45) if ok else (230, 230, 240))
    screen.blit(t, t.get_rect(center=nxt.center))
    fade = (now - name_enter) / 400.0
    if fade < 1.0:
        overlay_surf.set_alpha(int(255 * (1 - max(0.0, fade))))
        screen.blit(overlay_surf, (0, 0))
    pygame.display.flip()


# ======================================================================
#  HOME SCREEN: profile, coins, four game boxes with entrance animations and a liquid glass effect
# ======================================================================
home_t0 = 0
home_assets = {}
home_job = None
panel = None                    # None, 'coins', 'friends', 'settings' or 'board'
panel_buttons = []
ALL_DONE = 1.8                  # all four boxes have arrived
RIPPLE_T = 2.8                  # the water ripple plays once and then stops
GLASS_T = RIPPLE_T


def ease_out_quart(t):
    return 1 - (1 - t) ** 4


def art_text(s, text, size, centre, colour=WHITE, outline=(40, 20, 70)):
    f = pygame.font.SysFont(None, int(size))
    base = f.render(text, True, colour)
    shad = f.render(text, True, outline)
    r = base.get_rect(center=centre)
    o = max(2, int(size * 0.06))
    for dx, dy in ((-o, 0), (o, 0), (0, -o), (0, o), (-o, -o), (o, o), (-o, o), (o, -o)):
        s.blit(shad, r.move(dx, dy))
    s.blit(base, r)


def rot_poly(pts, ang, cx, cy):
    ca, sa = math.cos(ang), math.sin(ang)
    return [(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in pts]


def heart(s, x, y, r, col):
    pygame.draw.circle(s, col, (x - r * 0.5, y), r * 0.55)
    pygame.draw.circle(s, col, (x + r * 0.5, y), r * 0.55)
    pygame.draw.polygon(s, col, [(x - r * 1.02, y + r * 0.2), (x + r * 1.02, y + r * 0.2), (x, y + r * 1.25)])


def art_online(s, N):
    # a glowing globe with an orbit and signal waves
    cx, cy, R = N * 0.5, N * 0.40, N * 0.19
    for k in range(7, 0, -1):
        pygame.draw.circle(s, (70, 190, 255, 16), (cx, cy), R + k * N * 0.014)
    pygame.draw.circle(s, (12, 40, 125, 255), (cx, cy), R)
    pygame.draw.circle(s, (120, 225, 255, 255), (cx, cy), R, max(3, int(N * 0.014)))
    for k in (0.38, 0.72):
        pygame.draw.ellipse(s, (120, 225, 255, 230), (cx - R * k, cy - R, 2 * R * k, 2 * R), max(2, int(N * 0.009)))
    for dy in (-0.5, 0.0, 0.5):
        w = math.sqrt(1 - dy * dy) * R
        pygame.draw.line(s, (120, 225, 255, 200), (cx - w, cy + dy * R), (cx + w, cy + dy * R), max(2, int(N * 0.008)))
    orb = pygame.Rect(0, 0, R * 3.3, R * 0.95)
    orb.center = (cx, cy + R * 0.1)
    pygame.draw.ellipse(s, (255, 255, 255, 240), orb, max(3, int(N * 0.012)))
    pygame.draw.circle(s, (255, 220, 80, 255), (orb.right - R * 0.15, orb.centery), N * 0.028)
    pygame.draw.circle(s, (255, 255, 255, 255), (orb.right - R * 0.15, orb.centery), N * 0.012)
    for k in (1, 2, 3):
        rr = N * 0.035 * k
        pygame.draw.arc(s, (255, 255, 255, 255), (cx - rr, cy - R * 1.2 - rr, 2 * rr, 2 * rr),
                        math.pi * 0.28, math.pi * 0.72, max(3, int(N * 0.012)))


def art_friends(s, N):
    # two stick friends giving a high five, with hearts
    cx, cy = N * 0.5, N * 0.44
    lw = max(4, int(N * 0.022))
    for sgn, col in ((-1, (255, 255, 255, 255)), (1, (255, 240, 170, 255))):
        hx, hy = cx + sgn * N * 0.13, cy - N * 0.06
        pygame.draw.circle(s, col, (hx, hy), N * 0.068)
        pygame.draw.circle(s, (120, 20, 90, 255), (hx - N * 0.022, hy - N * 0.008), max(2, N * 0.008))
        pygame.draw.circle(s, (120, 20, 90, 255), (hx + N * 0.022, hy - N * 0.008), max(2, N * 0.008))
        pygame.draw.arc(s, (120, 20, 90, 255), (hx - N * 0.03, hy - N * 0.02, N * 0.06, N * 0.045), math.pi * 1.1, math.pi * 1.9, 3)
        pygame.draw.line(s, col, (hx, hy + N * 0.068), (hx, hy + N * 0.19), lw)
        pygame.draw.line(s, col, (hx, hy + N * 0.19), (hx - N * 0.05, hy + N * 0.27), lw)
        pygame.draw.line(s, col, (hx, hy + N * 0.19), (hx + N * 0.05, hy + N * 0.27), lw)
        pygame.draw.line(s, col, (hx, hy + N * 0.1), (cx - sgn * N * 0.012, cy - N * 0.2), lw)
        pygame.draw.line(s, col, (hx, hy + N * 0.1), (hx + sgn * N * 0.085, hy + N * 0.17), lw)
    heart(s, cx, cy - N * 0.26, N * 0.04, (255, 255, 255, 255))
    heart(s, cx - N * 0.2, cy - N * 0.17, N * 0.025, (255, 235, 150, 255))
    heart(s, cx + N * 0.2, cy - N * 0.19, N * 0.028, (255, 235, 150, 255))


def art_classic(s, N):
    # a little Ludo board with a dice
    cx, cy = N * 0.48, N * 0.42
    side = N * 0.44
    r = pygame.Rect(0, 0, side, side)
    r.center = (cx, cy)
    pygame.draw.rect(s, (110, 60, 20, 120), r.move(N * 0.012, N * 0.016), border_radius=int(N * 0.04))
    pygame.draw.rect(s, (255, 250, 235, 255), r, border_radius=int(N * 0.04))
    q = side * 0.38
    for (dx, dy), col in (((0, 0), RED), ((1, 0), GREEN), ((1, 1), YELLOW), ((0, 1), BLUE)):
        pygame.draw.rect(s, col + (255,), (r.x + dx * (side - q), r.y + dy * (side - q), q, q), border_radius=int(N * 0.02))
        pygame.draw.circle(s, (255, 255, 255, 255), (r.x + dx * (side - q) + q / 2, r.y + dy * (side - q) + q / 2), q * 0.22)
    for k in range(1, 4):
        pygame.draw.line(s, (205, 205, 215, 255), (r.x + side * 0.38, r.y + side * k / 4.0), (r.x + side * 0.62, r.y + side * k / 4.0), 2)
        pygame.draw.line(s, (205, 205, 215, 255), (r.x + side * k / 4.0, r.y + side * 0.38), (r.x + side * k / 4.0, r.y + side * 0.62), 2)
    pygame.draw.polygon(s, (70, 60, 90, 255), [(cx, cy - q * 0.4), (cx + q * 0.4, cy), (cx, cy + q * 0.4), (cx - q * 0.4, cy)])
    d = N * 0.19
    dr = pygame.Rect(0, 0, d, d)
    dr.center = (r.right - N * 0.01, r.bottom)
    pygame.draw.rect(s, (255, 255, 255, 255), dr, border_radius=int(d * 0.22))
    pygame.draw.rect(s, (70, 60, 90, 255), dr, max(3, int(N * 0.012)), border_radius=int(d * 0.22))
    for fx, fy in PIPS[5]:
        pygame.draw.circle(s, (40, 30, 60, 255), (dr.centerx + fx * d * 0.9, dr.centery + fy * d * 0.9), d * 0.075)


def art_master(s, N):
    # a golden crown in front of two swords and a lightning bolt
    cx, cy = N * 0.5, N * 0.42
    for k in range(6, 0, -1):
        pygame.draw.circle(s, (255, 200, 60, 14), (cx, cy), N * 0.12 + k * N * 0.02)
    for sgn in (-1, 1):
        blade = rot_poly([(-N * 0.022, -N * 0.27), (N * 0.022, -N * 0.27), (N * 0.03, N * 0.15), (-N * 0.03, N * 0.15)], sgn * 0.75, cx, cy + N * 0.03)
        pygame.draw.polygon(s, (225, 230, 245, 255), blade)
        pygame.draw.polygon(s, (255, 255, 255, 255), blade, max(2, int(N * 0.008)))
        guard = rot_poly([(-N * 0.07, N * 0.14), (N * 0.07, N * 0.14), (N * 0.07, N * 0.17), (-N * 0.07, N * 0.17)], sgn * 0.75, cx, cy + N * 0.03)
        pygame.draw.polygon(s, (255, 200, 60, 255), guard)
    bolt = [(cx + N * 0.2, cy - N * 0.3), (cx + N * 0.15, cy - N * 0.18), (cx + N * 0.19, cy - N * 0.18), (cx + N * 0.14, cy - N * 0.06),
            (cx + N * 0.235, cy - N * 0.2), (cx + N * 0.19, cy - N * 0.2)]
    pygame.draw.polygon(s, (255, 240, 120, 255), bolt)
    crown = [(-0.17, 0.12), (-0.2, -0.1), (-0.095, 0.0), (0.0, -0.15), (0.095, 0.0), (0.2, -0.1), (0.17, 0.12)]
    pts = [(cx + x * N, cy + y * N) for x, y in crown]
    pygame.draw.polygon(s, (255, 200, 40, 255), pts)
    pygame.draw.polygon(s, (255, 244, 170, 255), pts, max(3, int(N * 0.012)))
    pygame.draw.rect(s, (230, 150, 20, 255), (cx - N * 0.17, cy + N * 0.095, N * 0.34, N * 0.04), border_radius=int(N * 0.01))
    for dx, dy, col in ((-0.2, -0.1, (255, 80, 110)), (0.0, -0.15, (90, 200, 255)), (0.2, -0.1, (120, 230, 140))):
        pygame.draw.circle(s, col + (255,), (cx + dx * N, cy + dy * N), N * 0.022)
        pygame.draw.circle(s, (255, 255, 255, 220), (cx + dx * N - N * 0.006, cy + dy * N - N * 0.006), N * 0.008)


BOX_INFO = [
    ('ONLINE', (10, 36, 120), (0, 160, 230), art_online, (90, 225, 255)),
    ('FRIENDS', (255, 70, 140), (255, 150, 60), art_friends, (255, 235, 160)),
    ('CLASSIC', (255, 205, 60), (235, 95, 40), art_classic, (255, 250, 220)),
    ('MASTER', (90, 40, 170), (20, 8, 48), art_master, (255, 205, 70)),
]


def make_box_art(kind, S):
    # a compact square box with rounded corners, drawn twice as big and shrunk (HD look). Every box has its own style.
    N = S * 2
    label, c1, c2, art, accent = BOX_INFO[kind]
    big = pygame.Surface((N, N), pygame.SRCALPHA)
    big.blit(gradient_surface(N, N, c1, c2), (0, 0))
    pat = pygame.Surface((N, N), pygame.SRCALPHA)
    rng = random.Random(kind + 3)
    if kind == 0:                                    # dots, like a map of a network
        step = int(N * 0.07)
        for x in range(step // 2, N, step):
            for y in range(step // 2, N, step):
                pygame.draw.circle(pat, (120, 225, 255, 28), (x, y), max(2, int(N * 0.006)))
    elif kind == 1:                                  # tiny hearts
        for _ in range(16):
            heart(pat, rng.uniform(0.05, 0.95) * N, rng.uniform(0.05, 0.7) * N, N * rng.uniform(0.018, 0.04), (255, 255, 255, 42))
    elif kind == 2:                                  # a checker board
        step = int(N * 0.125)
        for gx in range(0, N, step):
            for gy in range(0, N, step):
                if (gx // step + gy // step) % 2 == 0:
                    pygame.draw.rect(pat, (255, 255, 255, 24), (gx, gy, step, step))
    else:                                            # rays of golden light
        for k in range(14):
            a = k * math.pi / 7
            pygame.draw.polygon(pat, (255, 205, 70, 28), [(N * 0.5, N * 0.42),
                                                          (N * 0.5 + math.cos(a) * N, N * 0.42 + math.sin(a) * N),
                                                          (N * 0.5 + math.cos(a + 0.12) * N, N * 0.42 + math.sin(a + 0.12) * N)])
    big.blit(pat, (0, 0))
    pygame.draw.ellipse(big, (255, 255, 255, 30), (-N * 0.1, -N * 0.5, N * 1.2, N * 0.85))
    art(big, N)
    plate = pygame.Rect(0, 0, N * 0.78, N * 0.16)
    plate.center = (N * 0.5, N * 0.85)
    pygame.draw.rect(big, (0, 0, 0, 120), plate, border_radius=int(plate.h * 0.5))
    pygame.draw.rect(big, accent + (255,), plate, max(3, int(N * 0.01)), border_radius=int(plate.h * 0.5))
    art_text(big, label, N * 0.13, plate.center, WHITE, (20, 10, 40))
    if kind < 2:                                     # these two need an internet server
        pill = pygame.Rect(0, 0, N * 0.27, N * 0.085)
        pill.topright = (N * 0.93, N * 0.06)
        pygame.draw.rect(big, (255, 214, 70, 255), pill, border_radius=int(pill.h * 0.5))
        art_text(big, 'SOON', N * 0.058, pill.center, (90, 20, 40), (255, 214, 70))
    lw = max(3, int(N * 0.014))
    if kind == 0:                                    # neon corner brackets
        m, L = N * 0.045, N * 0.15
        for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
            x0, y0 = (m if sx > 0 else N - m), (m if sy > 0 else N - m)
            pygame.draw.line(big, accent + (255,), (x0, y0), (x0 + sx * L, y0), lw)
            pygame.draw.line(big, accent + (255,), (x0, y0), (x0, y0 + sy * L), lw)
    elif kind == 1:                                  # a dotted border
        for k in range(0, int(N), int(N * 0.06)):
            for px, py in ((k, N * 0.03), (k, N * 0.97), (N * 0.03, k), (N * 0.97, k)):
                pygame.draw.circle(big, (255, 255, 255, 230), (px, py), max(2, int(N * 0.01)))
    elif kind == 2:                                  # thick white frame with a brown line inside
        pygame.draw.rect(big, (255, 255, 255, 255), (int(N * 0.01), int(N * 0.01), N - int(N * 0.02), N - int(N * 0.02)), int(N * 0.022), border_radius=int(N * 0.19))
        pygame.draw.rect(big, (120, 60, 20, 170), (int(N * 0.045), int(N * 0.045), N - int(N * 0.09), N - int(N * 0.09)), max(2, int(N * 0.008)), border_radius=int(N * 0.16))
    else:                                            # a double golden frame
        pygame.draw.rect(big, (255, 205, 70, 255), (int(N * 0.01), int(N * 0.01), N - int(N * 0.02), N - int(N * 0.02)), int(N * 0.018), border_radius=int(N * 0.19))
        pygame.draw.rect(big, (255, 235, 150, 200), (int(N * 0.04), int(N * 0.04), N - int(N * 0.08), N - int(N * 0.08)), max(2, int(N * 0.006)), border_radius=int(N * 0.16))
    big.blit(round_mask(N, N, N * 0.2), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return pygame.transform.smoothscale(big, (S, S))


def start_home_job(side):
    global home_job
    home_job = home_assets_job(side)
    jobs.append(home_job)


def home_assets_job(S):
    # the pictures of the home screen are made a little at a time while the welcome animation plays
    A = {'side': S}
    boxes = []
    for k in range(4):
        boxes.append(make_box_art(k, S))
        yield
    A['boxes'] = boxes
    A['mask'] = round_mask(S, S, S * 0.2)
    sh = pygame.Surface((S + 40, S + 40), pygame.SRCALPHA)
    pygame.draw.rect(sh, (0, 0, 0, 90), (20, 30, S, S), border_radius=int(S * 0.2))
    A['shadow'] = sh
    sheen = pygame.Surface((S, S), pygame.SRCALPHA)        # clear glass: bright top, light streaks, shiny edge
    pygame.draw.ellipse(sheen, (255, 255, 255, 70), (-S * 0.15, -S * 0.62, S * 1.3, S * 1.15))
    for k, a in enumerate((58, 36, 20)):
        x0 = S * (0.3 + k * 0.28)
        pygame.draw.polygon(sheen, (255, 255, 255, a), [(x0, 0), (x0 + S * 0.12, 0), (x0 - S * 0.3, S), (x0 - S * 0.42, S)])
    pygame.draw.rect(sheen, (255, 255, 255, 160), (0, 0, S, S), 3, border_radius=int(S * 0.2))
    pygame.draw.rect(sheen, (255, 255, 255, 55), (6, 6, S - 12, S - 12), 6, border_radius=int(S * 0.18))
    sheen.blit(A['mask'], (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    A['sheen'] = sheen
    yield
    zoom = []
    for k in (2, 3):                                       # a slightly bigger copy: seen through the ripples it looks bent
        z = pygame.transform.smoothscale(boxes[k], (int(S * 1.07), int(S * 1.07)))
        o = (z.get_width() - S) // 2
        zoom.append(z.subsurface((o, o, S, S)).copy())
        yield
    A['zoom'] = zoom
    A['layers'] = [pygame.Surface((S, S), pygame.SRCALPHA) for _ in range(2)]
    A['lens'] = [pygame.Surface((S, S), pygame.SRCALPHA) for _ in range(2)]
    A['tmp'] = [pygame.Surface((S, S), pygame.SRCALPHA) for _ in range(2)]
    A['final'] = {}
    home_assets.update(A)
    home_assets['ready'] = True


def ripple_layer(A, i, tg):
    # ONE water drop falls on the glass of CLASSIC (i = 2) and MASTER (i = 3), makes rings that spread out, then it is over
    S = A['side']
    j = i - 2
    layer = A['layers'][j]
    layer.fill((0, 0, 0, 0))
    sh = A['sheen']
    sh.set_alpha(int(255 * clamp01(tg / 0.5)))
    layer.blit(sh, (0, 0))
    cx, cy = S * 0.5, S * 0.52
    t_drop = 0.5 + (0.12 if i == 3 else 0.0)
    if tg < t_drop:                                        # the drop falls
        f = tg / t_drop
        y = -S * 0.08 + (cy + S * 0.08) * f * f
        r = S * 0.032
        pygame.draw.polygon(layer, (255, 255, 255, 150), [(cx - r * 0.8, y), (cx + r * 0.8, y), (cx, y - r * 2.4)])
        pygame.draw.circle(layer, (255, 255, 255, 170), (cx, y), r)
        pygame.draw.circle(layer, (255, 255, 255, 235), (cx - r * 0.3, y - r * 0.3), max(1, r * 0.35))
    else:
        age = tg - t_drop
        rings = []
        for k in range(4):                                 # four rings, one after the other, each weaker than the last
            a = age - k * 0.2
            if a <= 0:
                continue
            rad = S * 0.5 * (a ** 0.85)
            fade = math.exp(-a * 1.25) * clamp01(1.0 - rad / (S * 0.8))
            if fade >= 0.03 and rad >= 3:
                rings.append((rad, fade))
        if rings:
            lens = A['lens'][j]
            lens.fill((0, 0, 0, 0))
            wb = max(4, int(S * 0.05))
            for rad, fade in rings:
                pygame.draw.circle(lens, (255, 255, 255, int(255 * fade)), (cx, cy), int(rad), min(wb, int(rad)))
            tmp = A['tmp'][j]
            tmp.fill((0, 0, 0, 0))
            tmp.blit(A['zoom'][j], (0, 0))
            tmp.blit(lens, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            layer.blit(tmp, (0, 0))                        # the picture looks bent where a wave passes
            for rad, fade in rings:
                pygame.draw.circle(layer, (255, 255, 255, int(150 * fade)), (cx, cy), int(rad + wb * 0.5), 2)
                pygame.draw.circle(layer, (10, 30, 70, int(90 * fade)), (cx, cy), int(max(2, rad - wb * 0.5)), 2)
        if age < 0.6:                                      # a tiny splash
            for k in range(7):
                ang = -math.pi * (0.12 + 0.76 * k / 6.0)
                sp = S * (0.55 + 0.12 * (k % 3))
                px, py = cx + math.cos(ang) * sp * age, cy + math.sin(ang) * sp * age + S * 1.9 * age * age
                pygame.draw.circle(layer, (255, 255, 255, int(220 * (1 - age / 0.6))), (px, py), max(1, S * 0.011 * (1 - age)))
            pygame.draw.circle(layer, (255, 255, 255, int(120 * (1 - age / 0.6))), (cx, cy), S * 0.03 + age * S * 0.05, 3)
    layer.blit(A['mask'], (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return layer


def home_layout():
    mx = max(int(CELL * 0.45), int(min(W, H) * 0.03))
    ty = max(int(CELL * 0.45), int(H * 0.025))
    prof = pygame.Rect(mx, ty, int(min(CELL * 7.0, W * 0.52)), int(CELL * 2.0))
    av = pygame.Rect(prof.x + int(CELL * 0.25), prof.y + int(CELL * 0.25), int(CELL * 1.5), int(CELL * 1.5))
    friends = pygame.Rect(mx, prof.bottom + int(CELL * 0.35), int(min(CELL * 5.6, W * 0.46)), int(CELL * 1.3))
    cw = int(min(CELL * 5.4, W * 0.4))
    coins = pygame.Rect(W - mx - cw, ty, cw, int(CELL * 1.7))
    plus = pygame.Rect(0, 0, int(coins.h * 0.7), int(coins.h * 0.7))
    plus.midright = (coins.right - int(CELL * 0.2), coins.centery)
    nw, nh = int(min(CELL * 5.6, W * 0.42)), int(CELL * 1.9)
    ny = H - max(int(CELL * 1.7), int(H * 0.07)) - nh          # Settings and Leaderboard sit well above the bottom edge
    settings = pygame.Rect(mx, ny, nw, nh)
    board = pygame.Rect(W - mx - nw, ny, nw, nh)
    gap = int(CELL * 0.5)
    top = friends.bottom + int(CELL * 0.7)
    bottom = ny - int(CELL * 0.7)
    side = int(max(60, min((bottom - top - gap) / 2.0, (W - 3 * gap) / 2.0, CELL * 7.6)))
    x0 = (W - (2 * side + gap)) // 2
    y0 = top + int((bottom - top - (2 * side + gap)) / 2.0)
    boxes = [pygame.Rect(x0 + (i % 2) * (side + gap), y0 + (i // 2) * (side + gap), side, side) for i in range(4)]
    return prof, av, friends, coins, plus, settings, board, boxes, side


def box_anim(i, rect, t):
    # ONLINE and FRIENDS come down from the top; CLASSIC comes from the left and MASTER from the right (these two together)
    if i in (0, 1):
        start = 0.15 if i == 0 else 0.3
        if t < start:
            return None
        q = ease_out_quart(clamp01((t - start) / 0.75))
        return rect.x, rect.y - (rect.bottom + 20) * (1 - q)
    if t < 1.0:
        return None
    q = ease_out_quart(clamp01((t - 1.0) / 0.8))
    if i == 2:
        return rect.x - (rect.right + 20) * (1 - q), rect.y
    return rect.x + (W - rect.x + 20) * (1 - q), rect.y


def go_home(replay):
    global screen_state, home_t0, panel
    NAMES[:] = DEFAULT_NAMES
    set_board(4)
    screen_state = 'home'
    panel = None
    home_t0 = pygame.time.get_ticks() - (0 if replay else int((ALL_DONE + RIPPLE_T + 0.5) * 1000))


def draw_pill(rect, fill, border, radius=None):
    rad = int(rect.h * 0.4) if radius is None else radius
    pygame.draw.rect(screen, (0, 0, 0), rect.move(0, 5), border_radius=rad)
    pygame.draw.rect(screen, fill, rect, border_radius=rad)
    pygame.draw.rect(screen, border, rect, 3, border_radius=rad)


def draw_home():
    now = pygame.time.get_ticks()
    ts = now / 1000.0
    t = (now - home_t0) / 1000.0
    prof, av, friends, coins, plus, settings, board, boxes, side = home_layout()
    if not home_assets.get('ready'):
        if home_job is None:
            start_home_job(side)
        for _ in home_job:
            pass
    A = home_assets
    draw_home_bg(ts)

    q = ease_out_quart(clamp01(t / 0.6))                     # the bars slide in from their own edges
    dxl, dxr, dyb = -(1 - q) * (prof.w + CELL), (1 - q) * (coins.w + CELL), (1 - q) * (CELL * 4)
    # profile card: square picture with soft corners, and the name
    card = prof.move(int(dxl), 0)
    pygame.draw.rect(screen, (0, 0, 0), card.move(0, 6), border_radius=int(CELL * 0.6))
    pygame.draw.rect(screen, (46, 24, 84), card, border_radius=int(CELL * 0.6))
    pygame.draw.rect(screen, WHITE, card, 3, border_radius=int(CELL * 0.6))
    avr = av.move(int(dxl), 0)
    screen.blit(hd_icon('avatar', avr.w), avr.topleft)
    method = profile['method'] if profile else 'guest'
    if method in ('google', 'facebook', 'mobile'):           # a tiny badge shows how you logged in
        bi = int(avr.w * 0.42)
        screen.blit(hd_icon({'google': 'google', 'facebook': 'facebook', 'mobile': 'phone'}[method], bi),
                    (avr.right - bi * 0.7, avr.bottom - bi * 0.7))
    name = profile['name'] if profile and profile['name'] else 'Guest'
    nt = render_text(font, name, WHITE)
    maxw = card.right - avr.right - CELL * 0.5
    if nt.get_width() > maxw:
        nt = pygame.transform.smoothscale(nt, (int(maxw), max(2, int(nt.get_height() * maxw / nt.get_width()))))
    screen.blit(nt, nt.get_rect(midleft=(avr.right + int(CELL * 0.3), avr.centery)))
    # Add Friends: a separate button of its own
    fr = friends.move(int(dxl), 0)
    draw_pill(fr, (255, 120, 40), WHITE, int(fr.h * 0.5))
    fi = int(fr.h * 0.8)
    screen.blit(hd_icon('addfriend', fi), (fr.x + int(fr.h * 0.35), fr.y + (fr.h - fi) // 2))
    ft = render_text(small_font, 'Add Friends', WHITE)
    screen.blit(ft, ft.get_rect(center=(fr.centerx + fi * 0.5, fr.centery)))
    # coins: a clear coin picture, the number and a small plus button (top right, separate)
    cr = coins.move(int(dxr), 0)
    draw_pill(cr, (60, 34, 110), (255, 215, 80), int(cr.h * 0.5))
    ci = int(cr.h * 0.98)
    screen.blit(hd_icon('coin', ci), (cr.x + int(cr.h * 0.04), cr.y + (cr.h - ci) // 2))
    bt = render_text(font, str(save['coins']), GOLD)
    screen.blit(bt, bt.get_rect(center=(cr.x + cr.h * 1.05 + (cr.w - cr.h * 1.05 - plus.w) / 2, cr.centery)))
    screen.blit(hd_icon('plus', plus.w), plus.move(int(dxr), 0).topleft)
    # Settings (left) and Leaderboard (right)
    for rect, kind, label, col in ((settings, 'gear', 'Settings', (60, 120, 230)), (board, 'trophy', 'Leaderboard', (230, 120, 40))):
        r = rect.move(0, int(dyb))
        draw_pill(r, col, WHITE)
        ii = int(r.h * 0.74)
        screen.blit(hd_icon(kind, ii), (r.x + int(r.h * 0.2), r.y + (r.h - ii) // 2))
        lt = render_text(small_font, label, WHITE)
        if lt.get_width() > r.w - r.h * 1.3:
            lt = pygame.transform.smoothscale(lt, (int(r.w - r.h * 1.3), max(2, int(lt.get_height() * (r.w - r.h * 1.3) / lt.get_width()))))
        screen.blit(lt, lt.get_rect(center=(r.x + r.h * 1.0 + (r.w - r.h * 1.0) / 2, r.centery)))

    # the four game boxes (2 x 2)
    for i, rect in enumerate(boxes):
        pos = box_anim(i, rect, t)
        if pos is None:
            continue
        x, y = int(pos[0]), int(pos[1])
        screen.blit(A['shadow'], (x - 20, y - 20))
        screen.blit(A['boxes'][i], (x, y))
        if i >= 2 and t >= ALL_DONE:                         # the water ripple starts when CLASSIC and MASTER have arrived
            tg = t - ALL_DONE
            if tg >= RIPPLE_T:                               # finished: from now on only a calm, clear glass look stays
                if i not in A['final']:
                    f = A['boxes'][i].copy()
                    A['sheen'].set_alpha(255)
                    f.blit(A['sheen'], (0, 0))
                    A['final'][i] = f
                screen.blit(A['final'][i], (x, y))
            else:
                screen.blit(ripple_layer(A, i, tg), (x, y))
    if panel:
        draw_panel(now)
    update_particles()
    draw_particles()
    draw_toast(int(H * 0.5))
    pygame.display.flip()


# ---------- Panels: coins, friends, settings, leaderboard ----------
def today():
    return time.strftime('%Y-%m-%d')


def panel_frame(title):
    global panel_buttons
    panel_buttons = []
    if 'shade' not in panel_cache:
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        s.fill((10, 4, 24, 190))
        panel_cache['shade'] = s
    screen.blit(panel_cache['shade'], (0, 0))
    w, h = int(min(W * 0.9, CELL * 13)), int(min(H * 0.72, CELL * 17))
    r = pygame.Rect((W - w) // 2, (H - h) // 2, w, h)
    pygame.draw.rect(screen, (0, 0, 0), r.move(0, 8), border_radius=int(CELL * 0.7))
    pygame.draw.rect(screen, (50, 26, 92), r, border_radius=int(CELL * 0.7))
    pygame.draw.rect(screen, GOLD, r, 4, border_radius=int(CELL * 0.7))
    draw_text_outline(title, big_font, WHITE, (r.centerx, r.y + int(CELL * 1.3)))
    close = pygame.Rect(0, 0, int(CELL * 1.2), int(CELL * 1.2))
    close.topright = (r.right - int(CELL * 0.3), r.y + int(CELL * 0.3))
    pygame.draw.rect(screen, (225, 60, 70), close, border_radius=int(close.h * 0.3))
    pygame.draw.line(screen, WHITE, (close.x + close.w * 0.3, close.y + close.h * 0.3), (close.right - close.w * 0.3, close.bottom - close.h * 0.3), 5)
    pygame.draw.line(screen, WHITE, (close.x + close.w * 0.3, close.bottom - close.h * 0.3), (close.right - close.w * 0.3, close.y + close.h * 0.3), 5)
    panel_buttons.append(('close', close))
    return r


def panel_button(r, label, name, col=(255, 200, 50), tcol=(90, 25, 45), enabled=True):
    pygame.draw.rect(screen, (0, 0, 0), r.move(0, 4), border_radius=int(r.h * 0.3))
    pygame.draw.rect(screen, col if enabled else (130, 130, 150), r, border_radius=int(r.h * 0.3))
    t = small_font.render(label, True, tcol if enabled else (225, 225, 235))
    if t.get_width() > r.w - 20:
        t = pygame.transform.smoothscale(t, (int(r.w - 20), max(2, int(t.get_height() * (r.w - 20) / t.get_width()))))
    screen.blit(t, t.get_rect(center=r.center))
    if enabled:
        panel_buttons.append((name, r))


def draw_panel(now):
    if panel == 'coins':
        r = panel_frame('Coins')
        ci = int(CELL * 3.2)
        screen.blit(hd_icon('coin', ci), (r.centerx - ci // 2, r.y + int(CELL * 2.3)))
        draw_text_outline(str(save['coins']), big_font, GOLD, (r.centerx, r.y + int(CELL * 6.2)))
        claimed = (save['daily'] == today())
        b = pygame.Rect(0, 0, int(r.w * 0.8), int(CELL * 1.6))
        b.midtop = (r.centerx, r.y + int(CELL * 7.4))
        panel_button(b, 'Come back tomorrow' if claimed else 'Claim 50 free coins', 'daily', enabled=not claimed)
        for k, (amt, lab) in enumerate((('100', 'Coin pack'), ('500', 'Big pack'), ('1000', 'Mega pack'))):
            pr = pygame.Rect(0, 0, int(r.w * 0.27), int(CELL * 3.8))
            pr.topleft = (r.x + int(r.w * 0.06) + k * int(r.w * 0.31), r.y + int(CELL * 9.6))
            pygame.draw.rect(screen, (70, 44, 120), pr, border_radius=int(CELL * 0.4))
            pygame.draw.rect(screen, (150, 120, 200), pr, 2, border_radius=int(CELL * 0.4))
            ii = int(CELL * 1.2)
            screen.blit(hd_icon('coin', ii), (pr.centerx - ii // 2, pr.y + int(CELL * 0.3)))
            t1 = small_font.render(amt, True, GOLD)
            screen.blit(t1, t1.get_rect(center=(pr.centerx, pr.y + int(CELL * 2.1))))
            t2 = tiny_font.render('Soon', True, (210, 200, 235))
            screen.blit(t2, t2.get_rect(center=(pr.centerx, pr.y + int(CELL * 3.1))))
    elif panel == 'friends':
        r = panel_frame('Add Friends')
        screen.blit(hd_icon('addfriend', int(CELL * 3)), (r.centerx - int(CELL * 1.5), r.y + int(CELL * 2.4)))
        lt = small_font.render('Your friend code', True, (230, 220, 250))
        screen.blit(lt, lt.get_rect(center=(r.centerx, r.y + int(CELL * 6.4))))
        cb = pygame.Rect(0, 0, int(r.w * 0.6), int(CELL * 2.0))
        cb.midtop = (r.centerx, r.y + int(CELL * 7.2))
        pygame.draw.rect(screen, WHITE, cb, border_radius=int(cb.h * 0.3))
        draw_text_outline(save['code'], big_font, (214, 38, 64), cb.center)
        for k, line in enumerate(('Share this code with your friends.', 'Playing together online needs an', 'internet server, so it is coming soon.')):
            t = tiny_font.render(line, True, (230, 220, 250))
            screen.blit(t, t.get_rect(center=(r.centerx, r.y + int(CELL * (10.2 + 0.8 * k)))))
    elif panel == 'settings':
        r = panel_frame('Settings')
        b1 = pygame.Rect(0, 0, int(r.w * 0.8), int(CELL * 1.7))
        b1.midtop = (r.centerx, r.y + int(CELL * 3.0))
        panel_button(b1, 'Sound: ON' if SOUND_ON else 'Sound: OFF', 'sound', (60, 190, 110) if SOUND_ON else (225, 90, 90), WHITE)
        b2 = b1.move(0, int(CELL * 2.3))
        panel_button(b2, 'Change my name', 'rename', (255, 200, 50))
        b3 = b2.move(0, int(CELL * 2.3))
        panel_button(b3, 'Logout', 'logout', (225, 60, 90), WHITE)
        t = tiny_font.render('Your name, coins and wins are saved only on this device.', True, (230, 220, 250))
        if t.get_width() > r.w - 20:
            t = pygame.transform.smoothscale(t, (int(r.w - 20), max(2, int(t.get_height() * (r.w - 20) / t.get_width()))))
        screen.blit(t, t.get_rect(center=(r.centerx, r.bottom - int(CELL * 1.0))))
    elif panel == 'board':
        r = panel_frame('Leaderboard')
        rows = sorted(save['board'].items(), key=lambda kv: -kv[1])[:8]
        t = small_font.render('Games: %d     Wins: %d' % (save['games'], save['wins']), True, GOLD)
        screen.blit(t, t.get_rect(center=(r.centerx, r.y + int(CELL * 2.8))))
        if not rows:
            t = small_font.render('No winners yet. Win a game to be listed!', True, WHITE)
            if t.get_width() > r.w - 20:
                t = pygame.transform.smoothscale(t, (int(r.w - 20), max(2, int(t.get_height() * (r.w - 20) / t.get_width()))))
            screen.blit(t, t.get_rect(center=(r.centerx, r.centery)))
        for k, (nm, wn) in enumerate(rows):
            row = pygame.Rect(r.x + int(CELL * 0.6), r.y + int(CELL * 4.0) + k * int(CELL * 1.4), r.w - int(CELL * 1.2), int(CELL * 1.2))
            pygame.draw.rect(screen, (70, 44, 120) if k % 2 == 0 else (60, 36, 106), row, border_radius=int(row.h * 0.3))
            col = GOLD if k == 0 else WHITE
            a = small_font.render('%d.  %s' % (k + 1, nm), True, col)
            screen.blit(a, a.get_rect(midleft=(row.x + int(CELL * 0.4), row.centery)))
            b = small_font.render('%d wins' % wn, True, col)
            screen.blit(b, b.get_rect(midright=(row.right - int(CELL * 0.4), row.centery)))


def panel_tap(pos):
    global panel, SOUND_ON
    for name, r in panel_buttons:
        if r.collidepoint(pos):
            play(snd_thud, 0.5)
            if name == 'close':
                panel = None
            elif name == 'daily':
                save['coins'] += 50
                save['daily'] = today()
                write_save()
                toast('+50 coins!')
                spawn_sparkles(W / 2, H / 2, GOLD, 30)
            elif name == 'sound':
                SOUND_ON = not SOUND_ON
                save['sound'] = SOUND_ON
                write_save()
            elif name == 'rename':
                panel = None
                go_name(profile['name'] if profile else '')
            elif name == 'logout':
                logout()
            return
    w, h = int(min(W * 0.9, CELL * 13)), int(min(H * 0.72, CELL * 17))
    if not pygame.Rect((W - w) // 2, (H - h) // 2, w, h).collidepoint(pos):
        panel = None                               # a tap outside closes the panel


def logout():
    global profile, screen_state, login_t0, panel
    profile = None
    panel = None
    screen_state = 'login'
    login_t0 = pygame.time.get_ticks() - 6000


def home_tap(pos):
    global panel, home_t0, pending_rules, screen_state
    if panel:
        panel_tap(pos)
        return
    now = pygame.time.get_ticks()
    t = (now - home_t0) / 1000.0
    prof, av, friends, coins, plus, settings, board, boxes, side = home_layout()
    if t < ALL_DONE + 0.3:
        home_t0 = now - int((ALL_DONE + GLASS_T) * 1000)      # a tap finishes the animations at once
        return
    if friends.collidepoint(pos):
        panel = 'friends'
    elif coins.collidepoint(pos):
        panel = 'coins'
    elif settings.collidepoint(pos):
        panel = 'settings'
    elif board.collidepoint(pos):
        panel = 'board'
    else:
        for i, r in enumerate(boxes):
            if r.collidepoint(pos):
                play(snd_thud, 0.6)
                if i < 2:
                    toast('Coming soon! Online play needs an internet server.')
                else:
                    pending_rules = 'classic' if i == 2 else 'master'
                    go_modes()
                return


# ======================================================================
#  GAME MODES (players) screen after CLASSIC or MASTER, with a name for every player
# ======================================================================
MODES = [('2', '2 Players'), ('3', '3 Players'), ('4', '4 Players'),
         ('cpu', 'Computer'), ('5', '5 Players'), ('6', '6 Players')]
ACCENTS = [RED, GREEN, BLUE, GOLD, PURPLE, ORANGE]
MODE_ICONS = [[0, 2], [0, 1, 2], [0, 1, 2, 3], [0, None], [0, 1, 2, 3, 4], [0, 1, 2, 3, 4, 5]]
menu_tokens = [Token(i, 0) for i in range(4)]
modes_enter = 0
modes_hover = -1
modes_sel = None                # which player count was tapped
name_fields = []                # one entry per player: {'p': colour number, 'text': name, 'ai': computer?}
field_active = -1
modes_scroll = 0.0


def build_menu_bg():
    small = pygame.Surface((2, 32))
    for y in range(32):
        f = y / 31.0
        for x in range(2):
            small.set_at((x, y), (int(18 + 24 * f), int(18 + 14 * f), int(42 + 40 * f)))
    return pygame.transform.smoothscale(small, (W, H))


menu_bg = build_menu_bg()


def mode_info(mode):
    if mode == '2':
        return [0, 2], [], 4
    if mode == '3':
        return [0, 1, 2], [], 4
    if mode == '4':
        return [0, 1, 2, 3], [], 4
    if mode == '5':
        return [0, 1, 2, 3, 4], [], 6
    if mode == '6':
        return [0, 1, 2, 3, 4, 5], [], 6
    ai = [2, 1, 3][:max(1, min(3, COMPUTER_OPPONENTS))]          # you against the computer
    return sorted([0] + ai), ai, 4


def go_modes():
    global screen_state, modes_enter, modes_sel, name_fields, field_active, modes_scroll, kb_wanted
    screen_state = 'modes'
    modes_enter = pygame.time.get_ticks()
    modes_sel = None
    name_fields = []
    field_active = -1
    kb_wanted = False
    modes_scroll = 0.0


def select_mode(i):
    # shows one name box for every player of the chosen game, each in the colour of that player
    global modes_sel, name_fields, field_active, kb_wanted
    players, ai, nc = mode_info(MODES[i][0])
    fields = []
    for p in players:
        if p in ai:
            fields.append({'p': p, 'text': 'Computer', 'ai': True})
        else:
            txt = save['names'][p]
            if p == players[0] and profile and profile['name']:
                txt = profile['name']                            # the first colour is the person who logged in
            fields.append({'p': p, 'text': txt[:14], 'ai': False})
    modes_sel, name_fields, field_active, kb_wanted = i, fields, -1, False


def modes_buttons():
    n = len(MODES)
    gap = int(CELL * 0.3)
    bw1 = (W - gap * (n + 1)) / float(n)
    if bw1 >= CELL * 3.2:                          # wide screen: all six in one line
        bw = int(min(bw1, CELL * 4.6))
        bh = int(CELL * 3.4)
        x0 = (W - (bw * n + gap * (n - 1))) // 2
        y0 = H // 2 - bh // 2
        return [pygame.Rect(x0 + i * (bw + gap), y0, bw, bh) for i in range(n)]
    per = 3                                        # narrow screen: two rows of three, around the middle
    bw = int(min((W - gap * (per + 1)) / float(per), CELL * 5))
    bh = int(CELL * 3.0)
    x0 = (W - (bw * per + gap * (per - 1))) // 2
    y0 = H // 2 - bh - gap // 2
    return [pygame.Rect(x0 + (i % per) * (bw + gap), y0 + (i // per) * (bh + gap), bw, bh) for i in range(n)]


def modes_geom():
    rects = modes_buttons()
    fields, start = [], None
    n = len(name_fields)
    if n:
        grid_bottom = max(r.bottom for r in rects)
        cols = 2 if (W >= H * 1.2 and n > 3) else 1
        rows = (n + cols - 1) // cols
        gap = int(CELL * 0.35)
        fw = int(min(W * 0.9, CELL * 12)) if cols == 1 else int(min(W * 0.45, CELL * 11))
        fh = int(CELL * 1.5)
        x0 = (W - (fw * cols + gap * (cols - 1))) // 2
        y0 = grid_bottom + int(CELL * 0.9)
        for i in range(n):
            fields.append(pygame.Rect(x0 + (i % cols) * (fw + gap), y0 + (i // cols) * (fh + gap), fw, fh))
        start = pygame.Rect(0, 0, int(min(W * 0.8, CELL * 9)), int(CELL * 1.8))
        start.midtop = (W // 2, y0 + rows * (fh + gap) + int(CELL * 0.2))
    return rects, fields, start


def modes_scroll_target():
    rects, fields, start = modes_geom()
    if not fields:
        return 0.0
    tgt = 0.0
    over = start.bottom + int(CELL * 0.5) - H                    # everything must fit: the screen moves up a little
    if over > 0:
        tgt = -float(over)
    if kb_wanted and 0 <= field_active < len(fields):             # the typing box stays above the phone keyboard
        tgt = min(tgt, H * 0.3 - fields[field_active].y)
    return tgt


def modes_back_rect():
    return pygame.Rect(10, 10, int(CELL * 2.6), int(CELL * 1.1))


def modes_back():
    close_keyboard()
    go_home(False)


def modes_enter_key():
    global field_active
    nxt = field_active + 1
    while nxt < len(name_fields) and name_fields[nxt]['ai']:
        nxt += 1
    if nxt < len(name_fields):
        field_active = nxt
        open_keyboard(0)
    else:
        modes_start()


def modes_start():
    if modes_sel is None:
        return
    names = {}
    ai_n = 0
    for f in name_fields:
        p = f['p']
        if f['ai']:
            ai_n += 1
            names[p] = 'Computer' if COMPUTER_OPPONENTS == 1 else 'Computer %d' % ai_n
        else:
            txt = f['text'].strip()
            names[p] = txt if txt else DEFAULT_NAMES[p]
            save['names'][p] = txt
    close_keyboard()
    write_save()
    start_game(MODES[modes_sel][0], names)


def draw_mini_player(cx, cy, colour, s):
    lw = max(2, int(s * 0.1))
    pygame.draw.circle(screen, WHITE, (cx, cy - s * 0.9), s * 0.3)
    pygame.draw.circle(screen, colour, (cx, cy - s * 0.9), s * 0.3, lw)
    pygame.draw.line(screen, colour, (cx, cy - s * 0.6), (cx, cy), lw)
    pygame.draw.line(screen, colour, (cx - s * 0.4, cy - s * 0.4), (cx + s * 0.4, cy - s * 0.4), lw)
    pygame.draw.line(screen, colour, (cx, cy), (cx - s * 0.3, cy + s * 0.6), lw)
    pygame.draw.line(screen, colour, (cx, cy), (cx + s * 0.3, cy + s * 0.6), lw)


def draw_mini_robot(cx, cy, s):
    body = pygame.Rect(0, 0, s * 1.3, s * 1.0)
    body.center = (cx, cy - s * 0.2)
    pygame.draw.rect(screen, (170, 180, 205), body, border_radius=8)
    pygame.draw.circle(screen, (30, 30, 50), (body.centerx - s * 0.28, body.centery - s * 0.05), max(2, int(s * 0.12)))
    pygame.draw.circle(screen, (30, 30, 50), (body.centerx + s * 0.28, body.centery - s * 0.05), max(2, int(s * 0.12)))
    pygame.draw.line(screen, (30, 30, 50), (body.centerx - s * 0.25, body.centery + s * 0.25),
                     (body.centerx + s * 0.25, body.centery + s * 0.25), 2)
    pygame.draw.line(screen, (170, 180, 205), (cx, body.top), (cx, body.top - s * 0.3), 3)
    pygame.draw.circle(screen, RED, (cx, body.top - s * 0.35), max(2, int(s * 0.1)))


def draw_modes():
    global modes_scroll, field_rect
    now = pygame.time.get_ticks()
    ts = now / 1000.0
    target = modes_scroll_target()
    modes_scroll += (target - modes_scroll) * (1 - 0.82 ** FS)
    if abs(target - modes_scroll) < 0.5:
        modes_scroll = target
    sy = int(modes_scroll)
    screen.blit(menu_bg, (0, 0))
    rects, fields, start = modes_geom()
    top_y = min(r.y for r in rects) + sy
    rule = 'MASTER' if pending_rules == 'master' else 'CLASSIC'
    col = (170, 110, 255) if pending_rules == 'master' else (255, 160, 60)
    draw_text_outline(rule, title_font, col, (W / 2, top_y - CELL * 4.6 + math.sin(ts * 3) * CELL * 0.15))
    for i, t in enumerate(menu_tokens):                       # four dancing stick men
        t.px = W / 2 + (i - 1.5) * CELL * 2.4
        t.py = top_y - CELL * 1.7
        t.scale = 1.6
        t.height = 0
        draw_stickman(t, 'dance')
    sub = render_text(small_font, 'Choose a game mode', (220, 220, 235))
    screen.blit(sub, sub.get_rect(center=(W / 2, top_y - CELL * 0.65)))
    line = 'Kill an opponent before you can enter home!' if pending_rules == 'master' else 'Traditional Ludo rules'
    rl = render_text(tiny_font, line, col)
    if rl.get_width() > W * 0.94:
        rl = pygame.transform.smoothscale(rl, (int(W * 0.94), max(2, int(rl.get_height() * W * 0.94 / rl.get_width()))))
    screen.blit(rl, rl.get_rect(center=(W / 2, top_y - CELL * 3.3)))
    for i, r in enumerate(rects):
        hov = (i == modes_hover)
        sel = (i == modes_sel)
        rr = r.move(0, sy - (6 if hov else 0))
        pygame.draw.rect(screen, (0, 0, 0), rr.move(0, 8), border_radius=18)
        pygame.draw.rect(screen, (94, 84, 140) if sel else ((74, 74, 116) if hov else (50, 50, 82)), rr, border_radius=18)
        pygame.draw.rect(screen, WHITE if sel else ACCENTS[i], rr, 6 if sel else 4, border_radius=18)
        who = MODE_ICONS[i]
        s = min(rr.w * 0.11, rr.w * 0.62 / (len(who) + 1) * 0.9)
        icon_y = rr.y + rr.h * 0.48
        for k, pl in enumerate(who):
            px = rr.x + rr.w * (k + 1) / (len(who) + 1)
            if pl is None:
                draw_mini_robot(px, icon_y, s)
            else:
                draw_mini_player(px, icon_y, COLOURS[pl], s)
        lab = render_text(small_font, MODES[i][1], WHITE)
        if lab.get_width() > rr.w - CELL * 0.3:
            lab = pygame.transform.smoothscale(lab, (int(rr.w - CELL * 0.3),
                                                     max(2, int(lab.get_height() * (rr.w - CELL * 0.3) / lab.get_width()))))
        screen.blit(lab, lab.get_rect(center=(rr.centerx, rr.bottom - rr.h * 0.17)))
    # a name box for every player, below the chosen button
    for i, (f, r) in enumerate(zip(name_fields, fields)):
        rr = r.move(0, sy)
        c = COLOURS[f['p']]
        active = (i == field_active)
        rad = int(rr.h * 0.3)
        pygame.draw.rect(screen, (0, 0, 0), rr.move(0, 4), border_radius=rad)
        pygame.draw.rect(screen, (205, 210, 225) if f['ai'] else WHITE, rr, border_radius=rad)
        pygame.draw.rect(screen, c, rr, 6 if active else 3, border_radius=rad)
        sw = int(rr.h * 0.62)
        pygame.draw.circle(screen, c, (rr.x + int(rr.h * 0.5), rr.centery), sw // 2)
        pygame.draw.circle(screen, WHITE, (rr.x + int(rr.h * 0.5), rr.centery), sw // 2, 3)
        shown = f['text']
        if shown:
            tx = render_text(small_font, shown, (40, 30, 50))
        else:
            tx = render_text(small_font, DEFAULT_NAMES[f['p']] + ' player', (170, 160, 175))
        maxw = rr.w - rr.h * 1.3
        if tx.get_width() > maxw:
            tx = pygame.transform.smoothscale(tx, (int(maxw), max(2, int(tx.get_height() * maxw / tx.get_width()))))
        pos = tx.get_rect(midleft=(rr.x + rr.h * 1.0, rr.centery))
        screen.blit(tx, pos)
        if active:
            field_rect = rr
            if int(now / 500) % 2 == 0:
                cxp = pos.right + 4 if shown else rr.x + rr.h * 1.0
                pygame.draw.line(screen, c, (cxp, rr.centery - rr.h * 0.25), (cxp, rr.centery + rr.h * 0.25), 3)
    if start is not None:
        sr = start.move(0, sy)
        pygame.draw.rect(screen, (60, 10, 30), sr.move(0, 6), border_radius=int(sr.h * 0.3))
        pygame.draw.rect(screen, (255, 200, 50), sr, border_radius=int(sr.h * 0.3))
        pygame.draw.rect(screen, WHITE, sr, 3, border_radius=int(sr.h * 0.3))
        st = render_text(font, 'Start Game', (90, 25, 45))
        screen.blit(st, st.get_rect(center=sr.center))
    b = modes_back_rect()
    pygame.draw.rect(screen, WHITE, b, border_radius=14)
    bt = render_text(small_font, '< Back', (60, 30, 100))
    screen.blit(bt, bt.get_rect(center=b.center))
    fade = (now - modes_enter) / 500.0
    if fade < 1.0:
        overlay_surf.set_alpha(int(255 * (1 - max(0.0, fade))))
        screen.blit(overlay_surf, (0, 0))
    pygame.display.flip()


def modes_tap(pos):
    global modes_sel, field_active, kb_wanted
    if modes_back_rect().collidepoint(pos):
        modes_back()
        return
    p2 = (pos[0], pos[1] - int(modes_scroll))
    rects, fields, start = modes_geom()
    for i, r in enumerate(fields):
        if r.collidepoint(p2) and not name_fields[i]['ai']:
            field_active, kb_wanted = i, True
            open_keyboard(0)                       # tap a name box: the normal keyboard opens
            return
    if start is not None and start.collidepoint(p2):
        play(snd_thud, 0.6)
        modes_start()
        return
    for i, r in enumerate(rects):
        if r.collidepoint(p2):
            play(snd_thud, 0.6)
            close_keyboard()
            select_mode(i)
            return
    field_active, kb_wanted = -1, False
    close_keyboard()


def start_game(mode, names):
    global active_players, ai_players, screen_state, GAME_RULES, result_counted
    players, ai, nc = mode_info(mode)
    GAME_RULES = pending_rules
    set_board(nc)
    NAMES[:] = DEFAULT_NAMES
    for p, nm in names.items():
        NAMES[p] = nm
    active_players, ai_players = players, ai
    reset()
    screen_state = 'game'


# ---------- Computer player ----------
def ai_pick(options):
    best, best_score = options[0], -1e9
    for t in options:
        path, _ = move_steps(t, dice)
        dest = path[-1]
        score = dest * 0.5 + random.random()
        if t.steps == -1:
            score += 60                            # bring a new stick man out
        if dest == FINISH:
            score += 80                            # reach the finish
        if dest < TRACK:
            sq = (START[t.player] + dest) % TRACK
            if sq in SAFE:
                score += 25
            else:
                for p in range(NC):
                    if p != t.player:
                        score += 100 * sum(1 for o in tokens[p] if o.square() == sq)   # knock somebody out
        if score > best_score:
            best, best_score = t, score
    return best


def ai_update():
    global ai_seen_state, ai_seen_at
    now = pygame.time.get_ticks()
    if state != ai_seen_state:
        ai_seen_state = state
        ai_seen_at = now
    if current not in ai_players or win_mode:
        return
    if state == 'roll' and now - ai_seen_at > 900:
        start_roll()
    elif state == 'choose' and now - ai_seen_at > 900:
        start_move(ai_pick(movable()))


# ---------- Game logic ----------
def movable():
    return [t for t in tokens[current] if t.can_move(dice)]


def turn_msg():
    if current in ai_players:
        return NAMES[current] + ' (computer) is playing'
    return NAMES[current] + "'s turn: tap the dice"


def next_player():
    global current, dice, state, message, team_dancing
    current = active_players[(active_players.index(current) + 1) % len(active_players)]
    dice = 0
    state = 'roll'
    team_dancing = False          # the turn is over: the team shrinks back, stops dancing, shadow fades
    message = turn_msg()


def start_roll():
    global state, message, roll_timer, pending_dice, roll_sounds_done, team_dancing, roll_data
    state = 'rolling'
    team_dancing = True           # the rolling team grows, dances and gets its shadow
    roll_timer = pygame.time.get_ticks()
    pending_dice = random.randint(1, 6)
    roll_sounds_done = 0
    roll_data = make_roll(current, pending_dice)
    message = ''                  # no text at all while the dice rolls
    play(snd_rattle)


def start_move(t):
    global state, moving_token, move_path
    move_path, wrapped = move_steps(t, dice)
    if wrapped and GAME_RULES == 'master':
        toast('MASTER: kill an opponent first, then go home!')
    if move_path[-1] == FINISH:
        t.slot = sum(1 for o in tokens[t.player] if o is not t and o.steps == FINISH)
    moving_token = t
    state = 'moving'
    begin_next_hop()


def begin_next_hop():
    global hop_start, hop_end, hop_t0
    t = moving_token
    c, r = t.grid_pos_for(move_path[0])
    hop_start = (t.px, t.py)
    hop_end = cell_to_px(c, r)
    hop_t0 = pygame.time.get_ticks()


def finish_move():
    global moving_token, captured_flag
    t = moving_token
    moving_token = None
    t.height = 0
    t.scale = 1.0

    victims = []
    sq = t.square()
    if sq is not None and sq not in SAFE:
        for p in range(NC):
            if p == t.player:
                continue
            for o in tokens[p]:
                if o.square() == sq:
                    victims.append(o)
    captured_flag = len(victims) > 0
    if victims:
        start_capture(t, victims)
        return
    after_landing(t)


def after_landing(t):
    # Two stick men of the same team at the finish shake hands
    if t.steps == FINISH:
        for o in tokens[t.player]:
            if o is not t and o.steps == FINISH and not o.paired:
                o.paired = t.paired = True
                start_handshake(o, t)
                return
    end_of_move()


def end_of_move():
    global state, message, dice
    if all(x.steps == FINISH for x in tokens[current]):
        start_win()
    elif dice == 6 or captured_flag:
        dice = 0
        state = 'roll'
        message = NAMES[current] + ': roll again!'
    else:
        next_player()


HOP_MS = 233                   # one hop takes this long, on every device


def update_move():
    t = moving_token
    p = min(1.0, (pygame.time.get_ticks() - hop_t0) / float(HOP_MS))
    e = ease_in_out(p)
    t.px = hop_start[0] + (hop_end[0] - hop_start[0]) * e
    t.py = hop_start[1] + (hop_end[1] - hop_start[1]) * e
    t.height = math.sin(p * math.pi) * CELL * 0.55
    t.scale = 1.0 + math.sin(p * math.pi) * 0.15
    if p >= 1.0:
        t.px, t.py = hop_end
        t.steps = move_path.pop(0)
        t.height = 0
        t.scale = 1.0
        if move_path:
            begin_next_hop()
        else:
            finish_move()


def reset():
    global tokens, current, dice, state, message, win_mode, team_dancing, result_counted
    global hs_pair, hs_shaking, particles, cap_victims, cap_mover, moving_token, roll_data
    tokens = [[Token(p, i) for i in range(4)] for p in range(NC)]
    current = active_players[0]
    dice = 0
    state = 'roll'
    win_mode = False
    result_counted = False
    team_dancing = False
    moving_token = None
    roll_data = None
    hs_pair = ()
    hs_shaking = False
    particles = []
    rockets[:] = []
    balloons[:] = []
    cap_victims = []
    cap_mover = None
    kills[:] = [0] * 6
    last_dice[:] = [0] * 6
    dice_orient[:] = [mmul(rot_z(y), FACE_ROT[1]) for y in YAWS]
    shadow_level[:] = [0.0] * 6
    message = turn_msg()
    invalidate_board()
    build_name_tags()


def handle_tap(pos):
    global state, prev_state, confirm_open_t, roll_timer, hs_start, cap_start, cap_fly_start, hop_t0, pause_until, ai_seen_at, last_rocket

    if state == 'confirm_quit':
        if yes_rect().collidepoint(pos):
            go_home(False)                         # leave this match and show the home screen (the app stays open)
        elif no_rect().collidepoint(pos):
            d = pygame.time.get_ticks() - confirm_open_t     # the game continues exactly where it was
            roll_timer += d
            hs_start += d
            cap_start += d
            cap_fly_start += d
            hop_t0 += d
            pause_until += d
            ai_seen_at += d
            last_rocket += d
            state = prev_state
        return

    if quit_rect().collidepoint(pos):                # the QUIT button works at any moment
        prev_state, state, confirm_open_t = state, 'confirm_quit', pygame.time.get_ticks()
        return

    if state in ('handshake', 'capture', 'nomove'):
        return
    if state == 'won':
        if pygame.time.get_ticks() - win_start > 3800:
            go_home(False)                         # back to the home screen
        return
    if current in ai_players:
        return                                     # the computer plays its own turn
    if state == 'roll':
        if dice_rect(current).inflate(CELL * 0.6, CELL * 0.6).collidepoint(pos):
            start_roll()
    elif state == 'choose':
        best, best_d = None, 0.0
        for t in movable():          # the nearest stick man to your finger is chosen
            d = math.hypot(pos[0] - (t.px + t.dx), pos[1] - (t.py - CELL * 0.3 * t.dscale))
            reach = CELL * (0.35 + 0.45 * t.dscale)
            if d <= reach and (best is None or d < best_d):
                best, best_d = t, d
        if best is not None:
            start_move(best)


def update_rolling():
    global dice, state, message, roll_sounds_done, pause_until
    el = (pygame.time.get_ticks() - roll_timer) / 1000.0
    imp = roll_data['imp']
    while roll_sounds_done < len(imp) and el >= imp[roll_sounds_done][0]:
        play(snd_thud, 0.3 + 0.6 * imp[roll_sounds_done][1])     # a knock every time it hits the table
        roll_sounds_done += 1
    if el * 1000 < ROLL_TIME:
        return
    dice = pending_dice
    dice_orient[current] = roll_data['Rf']
    last_dice[current] = dice
    options = movable()
    if not options:
        message = NAMES[current] + ' rolled ' + str(dice) + ': no move'
        state = 'nomove'                           # a short pause that never freezes the animations
        pause_until = pygame.time.get_ticks() + 900
    elif len(options) == 1 and options[0].steps != -1:
        message = NAMES[current] + ' rolled ' + str(dice)
        start_move(options[0])
    else:
        state = 'choose'
        if current in ai_players:
            message = NAMES[current] + ' rolled ' + str(dice)
        else:
            message = NAMES[current] + ' rolled ' + str(dice) + ': tap a stick man'


# ---------- Main loop ----------
def step_game():
    now = pygame.time.get_ticks()
    if state == 'rolling':
        update_rolling()
    elif state == 'moving':
        update_move()
    elif state == 'handshake':
        update_handshake()
    elif state == 'capture':
        update_capture()
    elif state == 'nomove' and now >= pause_until:
        next_player()
    ai_update()
    if win_mode:
        update_win()
    k = 1 - 0.82 ** FS
    for p in range(6):                      # shadows fade in and out with the turn
        target = 1.0 if (team_dancing and p == current) else 0.0
        shadow_level[p] += (target - shadow_level[p]) * k
    update_sharing()
    update_particles()
    highlight = movable() if (state == 'choose' and current not in ai_players) else []
    draw_all(highlight)


jobs.append(sound_gen())
start_home_job(home_layout()[-1])

running = True
while running:
    dt = clock.tick(60)
    FS = max(0.25, min(3.0, dt / 16.667))
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if screen_state == 'login':
                login_tap(event.pos)
            elif screen_state == 'auth':
                auth_tap(event.pos)
            elif screen_state == 'name':
                name_tap(event.pos)
            elif screen_state == 'home':
                home_tap(event.pos)
            elif screen_state == 'modes':
                modes_tap(event.pos)
            else:
                handle_tap(event.pos)
        elif event.type == pygame.MOUSEMOTION:
            if screen_state == 'modes':
                modes_hover = -1
                for i, r in enumerate(modes_buttons()):
                    if r.collidepoint((event.pos[0], event.pos[1] - int(modes_scroll))):
                        modes_hover = i
            elif screen_state == 'login':
                login_hover = -1
                for i, r in enumerate(login_geometry()[0]):
                    if r.collidepoint(event.pos):
                        login_hover = i
        elif event.type == TEXT_EVENT and screen_state in ('auth', 'name', 'modes'):
            pending_kd = None
            for ch in event.text:
                input_char(ch)
        elif event.type == pygame.KEYDOWN and screen_state in ('auth', 'name', 'modes'):
            key_down(event)
    if pending_kd is not None and pygame.time.get_ticks() - pending_kd[1] > 60:
        input_char(pending_kd[0])
        pending_kd = None

    if screen_state == 'login':
        draw_login()
    elif screen_state == 'auth':
        draw_auth()
    elif screen_state == 'name':
        draw_name()
    elif screen_state == 'home':
        draw_home()
    elif screen_state == 'modes':
        draw_modes()
    else:
        step_game()
    service_keyboard()
    pump_jobs()

pygame.quit()
sys.exit()
