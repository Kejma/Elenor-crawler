# --- DISPLAY & CAMERA VIEWPORT SETTINGS ---
TILE_W = 16
TILE_H = 16
SPRITE_W = 16
SPRITE_H = 20

VIEW_COLS = 30                       # 30 tiles * 16 px = 480 px (x4 = 1920 px Full HD!)
VIEW_ROWS = 13                       # 13 tiles * 16 px = 208 px

MAP_COLS = 66
MAP_ROWS = 42

# River tiles shared by terrain generation, movement and fishing.
SHALLOW_WATER, DEEP_WATER, PIER, PEBBLE_SHORE = range(37, 41)

VIEW_W = VIEW_COLS * TILE_W          # 480 px native viewport width (16:9)
VIEW_H = VIEW_ROWS * TILE_H          # 208 px native viewport height

THOUGHT_ZONE_H = 38
CANVAS_H = VIEW_H + THOUGHT_ZONE_H   # 246 px total normal-mapped canvas height (246 * 4 = 984 px)

THOUGHT_BOX_W = 320
THOUGHT_BOX_H = 32
THOUGHT_BOX_X = (VIEW_W - THOUGHT_BOX_W) // 2
THOUGHT_BOX_Y = VIEW_H + (THOUGHT_ZONE_H - THOUGHT_BOX_H) // 2

SCALE = 4                            # Exact 4x integer scale -> 1920x1080 native Full HD!
HUD_HEIGHT = 96                      # Bottom HUD bar (984 + 96 = 1080 px)

SCREEN_W = VIEW_W * SCALE            # 1920 px
SCREEN_H = CANVAS_H * SCALE + HUD_HEIGHT  # 1080 px

# --- REALTIME, LOS & LIGHTING SETTINGS ---
LOS_MAX_RADIUS = 265.0               # Unobstructed sightline distance for wider 16:9 viewport
TORCH_BASE_RADIUS = 116.0            # Torch triples your effective vision distance!
DARK_VISION_RADIUS = 68.0            # Tight dark-vision radius (pitch black beyond this!)
TORCH_BURN_RATE = 0.85
TORCH_Z_HEIGHT = 24.0
RAY_COUNT = 280

PLAYER_BASE_SPEED = 4.7
TYPEWRITER_SPEED = 96.0

# --- ITEM RARITY COLORS & DROP WEIGHTS (50 / 24 / 15.5 / 7.5 / 3) ---
RARITY_COLORS = {
    "common": (215, 215, 220),       # White (50%)
    "uncommon": (85, 225, 105),      # Green (24%)
    "rare": (80, 165, 255),          # Blue (15.5%)
    "epic": (195, 105, 255),         # Purple (7.5%)
    "legendary": (255, 160, 45)      # Orange (3%)
}

# Base drop & perk weights at Luck = 1 (78% Common!)
RARITY_WEIGHTS = {
    "common": 78.0,
    "uncommon": 14.0,
    "rare": 5.5,
    "epic": 2.0,
    "legendary": 0.5,
}


def get_rarity_weights(luck=1):
    """Returns [common, uncommon, rare, epic, legendary] weights scaled by Player's Luck."""
    bonus = max(0, luck - 1)
    c = max(30.0, 78.0 - bonus * 5.5)
    u = 14.0 + bonus * 2.8
    r = 5.5 + bonus * 1.6
    e = 2.0 + bonus * 0.8
    l = 0.5 + bonus * 0.3
    return [c, u, r, e, l]

# --- FIXED PIXEL-RPG UI PALETTE ---
UI_BG_DARK = (20, 17, 24)
UI_PANEL_BG = (34, 29, 38)
UI_SLOT_BG = (24, 20, 28)
UI_BORDER_OUTER = (12, 10, 15)
UI_BORDER_WOOD = (92, 62, 46)
UI_BORDER_GOLD = (178, 138, 72)
UI_BORDER_HIGHLIGHT = (225, 190, 115)
UI_TEXT_MAIN = (236, 226, 208)
UI_TEXT_DIM = (152, 142, 132)

# Probability of reserving an ordinary dungeon room for the merchant.
MERCHANT_ROOM_CHANCE = 0.15
