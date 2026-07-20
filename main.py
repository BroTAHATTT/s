import pygame
import random
import sys
import math

pygame.init()

info = pygame.display.Info()
DISPLAY_W, DISPLAY_H = info.current_w, info.current_h

# Рендерим в маленькое фиксированное разрешение — на слабом железе (телефоны через
# Pydroid используют программный рендер SDL, и полноразмерный FullHD+ экран без
# этого лагает жёстко). SCALED растягивает картинку на весь экран уже аппаратно.
WIDTH, HEIGHT = 400, 600
try:
    screen = pygame.display.set_mode(
        (WIDTH, HEIGHT), pygame.FULLSCREEN | pygame.SCALED, vsync=1
    )
except pygame.error:
    try:
        screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN | pygame.SCALED)
    except pygame.error:
        screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)
pygame.display.set_caption("Гонки: уклонись от машин")
clock = pygame.time.Clock()

SCALE = 1.0


def sc(v):
    return int(v * SCALE)


font = pygame.font.SysFont("arial", sc(28))
btn_font = pygame.font.SysFont("arial", sc(32), bold=True)
big_font = pygame.font.SysFont("arial", sc(56), bold=True)
title_font = pygame.font.SysFont("arial", sc(64), bold=True)

ROAD_WIDTH = sc(280)
ROAD_LEFT = WIDTH // 2 - ROAD_WIDTH // 2
ROAD_RIGHT = WIDTH // 2 + ROAD_WIDTH // 2
LANE_COUNT = 3
LANE_WIDTH = (ROAD_RIGHT - ROAD_LEFT) // LANE_COUNT

WHITE = (255, 255, 255)
BLACK = (20, 20, 20)
RED = (220, 40, 40)
BLUE = (40, 120, 220)
YELLOW = (240, 200, 40)
GREEN = (40, 180, 90)

TRACKS = [
    {
        "name": "Летний день",
        "grass": (40, 150, 60),
        "road": (60, 60, 60),
        "line": (240, 200, 40),
        "border": (255, 255, 255),
        "accent": (240, 200, 40),
    },
    {
        "name": "Ночной город",
        "grass": (20, 25, 45),
        "road": (35, 35, 40),
        "line": (240, 220, 80),
        "border": (120, 200, 255),
        "accent": (120, 200, 255),
    },
    {
        "name": "Пустыня",
        "grass": (196, 154, 88),
        "road": (90, 78, 66),
        "line": (250, 235, 210),
        "border": (255, 240, 200),
        "accent": (230, 140, 50),
    },
    {
        "name": "Зимняя трасса",
        "grass": (225, 235, 245),
        "road": (70, 78, 92),
        "line": (255, 255, 255),
        "border": (150, 190, 220),
        "accent": (140, 200, 240),
    },
    {
        "name": "Закат в горах",
        "grass": (120, 60, 90),
        "road": (55, 45, 60),
        "line": (255, 170, 80),
        "border": (255, 140, 100),
        "accent": (255, 140, 90),
    },
    {
        "name": "Неоновая трасса",
        "grass": (10, 10, 20),
        "road": (25, 15, 40),
        "line": (255, 60, 220),
        "border": (60, 255, 220),
        "accent": (255, 60, 220),
    },
    {
        "name": "Осенний лес",
        "grass": (110, 80, 35),
        "road": (65, 55, 50),
        "line": (240, 150, 60),
        "border": (220, 120, 40),
        "accent": (220, 120, 40),
    },
]
track_index = 0


def lane_x(lane):
    return ROAD_LEFT + lane * LANE_WIDTH + LANE_WIDTH // 2


def shade(c, k):
    return (max(0, min(255, int(c[0] * k))),
            max(0, min(255, int(c[1] * k))),
            max(0, min(255, int(c[2] * k))))


# ---------------------------------------------------------------------------
# Машины: спрайт кузова рисуется ОДИН РАЗ в кэш (Surface), в кадре только
# blit + отрисовка вращающихся колёс (единственное, что меняется).
# ---------------------------------------------------------------------------
_car_sprite_cache = {}


def _vertical_gradient_rect(surf, rect, color_top, color_bottom, border_radius=0):
    """Рисует прямоугольник с вертикальным градиентом (имитация покраски металликом)."""
    x, y, w, h = rect
    if h <= 0 or w <= 0:
        return
    grad = pygame.Surface((1, h), pygame.SRCALPHA)
    for i in range(h):
        t = i / max(1, h - 1)
        col = (
            int(color_top[0] + (color_bottom[0] - color_top[0]) * t),
            int(color_top[1] + (color_bottom[1] - color_top[1]) * t),
            int(color_top[2] + (color_bottom[2] - color_top[2]) * t),
        )
        grad.set_at((0, i), col)
    grad = pygame.transform.scale(grad, (w, h))
    if border_radius:
        mask = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, w, h), border_radius=border_radius)
        grad.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surf.blit(grad, (x, y))


def get_car_body_sprite(color, w, h):
    """Возвращает готовый Surface с кузовом машины (без колёс), кэшируется по цвету/размеру."""
    key = (color, w, h)
    cached = _car_sprite_cache.get(key)
    if cached is not None:
        return cached

    pad = 6
    surf = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)
    ox, oy = pad, pad
    cx = ox + w / 2

    top_c = shade(color, 1.25)
    bottom_c = shade(color, 0.65)

    # силуэт кузова: капот уже, "плечи" у дверей шире, багажник чуть сужен
    body_pts = [
        (ox + w * 0.16, oy),                    # перед капота, лево
        (ox + w - w * 0.16, oy),                 # перед капота, право
        (ox + w * 0.04, oy + h * 0.16),
        (ox + w - w * 0.04, oy + h * 0.16),
        (ox + w, oy + h * 0.30),                 # плечо право
        (ox + w, oy + h * 0.72),
        (ox + w - w * 0.06, oy + h * 0.90),
        (ox + w * 0.06, oy + h * 0.90),
        (ox, oy + h * 0.72),
        (ox, oy + h * 0.30),                     # плечо лево
    ]
    # используем bounding box для градиентной заливки, потом маскируем полигоном
    body_mask = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)
    pygame.draw.polygon(body_mask, (255, 255, 255, 255), body_pts)
    body_layer = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)
    _vertical_gradient_rect(body_layer, (0, 0, w + pad * 2, h + pad * 2), top_c, bottom_c)
    body_layer.blit(body_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surf.blit(body_layer, (0, 0))
    pygame.draw.polygon(surf, shade(color, 0.4), body_pts, 2)

    # боковой блик (тоньше и мягче)
    pygame.draw.polygon(surf, (255, 255, 255, 40), [
        (ox + w * 0.32, oy + h * 0.05),
        (ox + w * 0.40, oy + h * 0.05),
        (ox + w * 0.35, oy + h * 0.85),
        (ox + w * 0.29, oy + h * 0.85),
    ])

    # решётка радиатора спереди
    grille = pygame.Rect(0, 0, w * 0.5, 5)
    grille.center = (cx, oy + 3)
    pygame.draw.rect(surf, (25, 25, 25), grille, border_radius=2)
    for gx in range(3):
        gxp = grille.x + 4 + gx * (grille.w - 8) / 2
        pygame.draw.line(surf, (60, 60, 60), (gxp, grille.y + 1), (gxp, grille.bottom - 1), 1)

    # лобовое стекло со стойками
    windshield = pygame.Rect(0, 0, w - 14, h * 0.20)
    windshield.center = (cx, oy + h * 0.24)
    pygame.draw.rect(surf, (120, 190, 225), windshield, border_radius=4)
    pygame.draw.rect(surf, (200, 235, 250), (windshield.x + 3, windshield.y + 2, windshield.w - 6, windshield.h * 0.35), border_radius=3)
    pygame.draw.rect(surf, shade(color, 0.35), windshield, 2, border_radius=4)
    # стойки крыши (тонкие)
    pygame.draw.line(surf, shade(color, 0.4), (windshield.left + 2, windshield.top), (ox + 3, oy + h * 0.30), 3)
    pygame.draw.line(surf, shade(color, 0.4), (windshield.right - 2, windshield.top), (ox + w - 3, oy + h * 0.30), 3)

    # дворники
    pygame.draw.line(surf, (30, 30, 30), (cx - w * 0.18, windshield.bottom - 1), (cx - 2, windshield.bottom - 3), 2)
    pygame.draw.line(surf, (30, 30, 30), (cx + w * 0.18, windshield.bottom - 1), (cx + 2, windshield.bottom - 3), 2)

    # крыша (панель более тёмного тона по центру)
    roof = pygame.Rect(0, 0, w - 20, h * 0.32)
    roof.center = (cx, oy + h * 0.46)
    _vertical_gradient_rect(surf, roof, shade(color, 0.95), shade(color, 0.75), border_radius=6)
    pygame.draw.rect(surf, shade(color, 0.4), roof, 1, border_radius=6)

    # заднее стекло
    rear = pygame.Rect(0, 0, w - 18, h * 0.15)
    rear.center = (cx, oy + h - h * 0.20)
    pygame.draw.rect(surf, (100, 165, 200), rear, border_radius=4)
    pygame.draw.rect(surf, shade(color, 0.35), rear, 2, border_radius=4)

    # боковые окна (передняя и задняя дверь) - тонкие полосы под крышей
    side_win_y = oy + h * 0.30
    side_win_h = h * 0.16
    pygame.draw.rect(surf, (140, 195, 225), (ox + w * 0.10, side_win_y, w * 0.30, side_win_h), border_radius=3)
    pygame.draw.rect(surf, (140, 195, 225), (ox + w * 0.60, side_win_y, w * 0.30, side_win_h), border_radius=3)

    # боковые зеркала
    pygame.draw.rect(surf, shade(color, 0.55), (ox - 4, oy + h * 0.28, 5, 9), border_radius=2)
    pygame.draw.rect(surf, shade(color, 0.55), (ox + w - 1, oy + h * 0.28, 5, 9), border_radius=2)
    pygame.draw.rect(surf, (170, 210, 230), (ox - 3, oy + h * 0.29, 3, 5), border_radius=1)
    pygame.draw.rect(surf, (170, 210, 230), (ox + w, oy + h * 0.29, 3, 5), border_radius=1)

    # фары (с "отражением" - маленький белый блик внутри)
    for fx in (ox + 1, ox + w - 9):
        pygame.draw.rect(surf, (255, 253, 225), (fx, oy - 1, 8, 6), border_radius=2)
        pygame.draw.rect(surf, (255, 255, 255), (fx + 1, oy, 2, 2))
        pygame.draw.rect(surf, shade(color, 0.4), (fx, oy - 1, 8, 6), 1, border_radius=2)

    # стоп-сигналы
    for fx in (ox + 1, ox + w - 9):
        pygame.draw.rect(surf, (210, 30, 30), (fx, oy + h - 5, 8, 5), border_radius=2)
        pygame.draw.rect(surf, (255, 120, 120), (fx + 1, oy + h - 4, 2, 1))

    # бамперы с лёгким объёмом
    pygame.draw.rect(surf, (35, 35, 38), (ox + w * 0.08, oy - 2, w * 0.84, 4), border_radius=2)
    pygame.draw.rect(surf, (55, 55, 58), (ox + w * 0.08, oy - 2, w * 0.84, 1), border_radius=1)
    pygame.draw.rect(surf, (35, 35, 38), (ox + w * 0.08, oy + h - 2, w * 0.84, 4), border_radius=2)

    # финальный контур
    pygame.draw.polygon(surf, (20, 20, 20), body_pts, 2)

    _car_sprite_cache[key] = (surf, pad)
    return surf, pad


# Тень — тоже кэшируем как готовый Surface (форма не меняется, только позиция)
_shadow_cache = {}


def get_shadow_sprite(w):
    if w in _shadow_cache:
        return _shadow_cache[w]
    shadow = pygame.Surface((w + 14, 18), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 100), shadow.get_rect())
    pygame.draw.ellipse(shadow, (0, 0, 0, 60), shadow.get_rect().inflate(6, 6))
    _shadow_cache[w] = shadow
    return shadow


class Car:
    def __init__(self, lane, y, color, w=None, h=None):
        self.lane = lane
        self.w = w or sc(46)
        self.h = h or sc(78)
        self.x = lane_x(lane)
        self.y = y
        self.color = color
        self.wheel_angle = 0
        self.wheel_r = self.w * 0.17
        self.wheel_inset_x = self.w * 0.06

    def rect(self):
        return pygame.Rect(self.x - self.w // 2, self.y - self.h // 2, self.w, self.h)

    def update_wheels(self, distance):
        self.wheel_angle = (self.wheel_angle + distance * 6) % 360

    def _draw_wheel(self, cx, cy, radius):
        cx, cy = int(cx), int(cy)
        # шина с боковым профилем
        pygame.draw.circle(screen, (12, 12, 12), (cx, cy), radius)
        pygame.draw.circle(screen, (35, 35, 35), (cx, cy), radius, max(1, int(radius * 0.25)))
        # обод (диск)
        pygame.draw.circle(screen, (200, 200, 205), (cx, cy), radius * 0.55)
        pygame.draw.circle(screen, (150, 150, 155), (cx, cy), radius * 0.55, 1)
        # спицы диска, вращающиеся
        a = math.radians(self.wheel_angle)
        for i in range(5):
            ang = a + i * (2 * math.pi / 5)
            x2 = cx + math.cos(ang) * radius * 0.5
            y2 = cy + math.sin(ang) * radius * 0.5
            pygame.draw.line(screen, (120, 120, 125), (cx, cy), (x2, y2), 2)
        # центральная гайка
        pygame.draw.circle(screen, (80, 80, 85), (cx, cy), max(1, radius * 0.14))
        # блик на шине
        pygame.draw.circle(screen, (70, 70, 70), (cx - radius * 0.3, cy - radius * 0.3), max(1, radius * 0.15))

    def draw(self):
        r = self.rect()

        shadow = get_shadow_sprite(self.w)
        screen.blit(shadow, (r.x - 7, r.bottom - 10))

        self._draw_wheel(r.x + self.wheel_inset_x, r.y + self.h * 0.22, self.wheel_r)
        self._draw_wheel(r.right - self.wheel_inset_x, r.y + self.h * 0.22, self.wheel_r)
        self._draw_wheel(r.x + self.wheel_inset_x, r.y + self.h * 0.80, self.wheel_r)
        self._draw_wheel(r.right - self.wheel_inset_x, r.y + self.h * 0.80, self.wheel_r)

        sprite, pad = get_car_body_sprite(self.color, self.w, self.h)
        screen.blit(sprite, (r.x - pad, r.y - pad))


# ---------------------------------------------------------------------------
# Дорога: разметка (линии) кэшируется как повторяющаяся текстура-полоса,
# вместо пересчёта прямоугольников в цикле каждый кадр.
# ---------------------------------------------------------------------------
_road_cache = {}


def get_road_surface(track_name):
    """Статичная часть дороги (без движущейся разметки) - фон + асфальт + бордюры."""
    key = track_name
    if key in _road_cache:
        return _road_cache[key]
    track = next(t for t in TRACKS if t["name"] == track_name)
    surf = pygame.Surface((WIDTH, HEIGHT))
    surf.fill(track["grass"])
    pygame.draw.rect(surf, track["road"], (ROAD_LEFT, 0, ROAD_RIGHT - ROAD_LEFT, HEIGHT))
    pygame.draw.rect(surf, track["border"], (ROAD_LEFT - sc(4), 0, sc(4), HEIGHT))
    pygame.draw.rect(surf, track["border"], (ROAD_RIGHT, 0, sc(4), HEIGHT))
    _road_cache[key] = surf
    return surf


def draw_road(offset, track):
    screen.blit(get_road_surface(track["name"]), (0, 0))
    dash_len, gap = sc(30), sc(20)
    period = dash_len + gap
    start_y = -(offset % period)
    for lane in range(1, LANE_COUNT):
        x = ROAD_LEFT + lane * LANE_WIDTH
        y = start_y
        while y < HEIGHT:
            pygame.draw.rect(screen, track["line"], (x - sc(3), y, sc(6), dash_len))
            y += period


# ---------------------------------------------------------------------------
# UI: кнопка с кэшированной подложкой (полупрозрачный фон рисуется 1 раз)
# ---------------------------------------------------------------------------
class Button:
    def __init__(self, rect, text, font_obj=None):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.font = font_obj or btn_font
        self._bg = None
        self._text_surf = None
        self._last_text = None
        self._build_bg()

    def _build_bg(self):
        s = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        pygame.draw.rect(s, (255, 255, 255, 45), s.get_rect(), border_radius=sc(14))
        pygame.draw.rect(s, WHITE, s.get_rect(), 2, border_radius=sc(14))
        self._bg = s

    def set_text(self, text):
        self.text = text

    def draw(self, surf):
        surf.blit(self._bg, self.rect.topleft)
        if self._text_surf is None or self._last_text != self.text:
            self._text_surf = self.font.render(self.text, True, WHITE)
            self._last_text = self.text
        surf.blit(self._text_surf, self._text_surf.get_rect(center=self.rect.center))

    def clicked(self, pos):
        return self.rect.collidepoint(pos)


def get_event_pos(event):
    if event.type == pygame.FINGERDOWN:
        raw = (event.x * DISPLAY_W, event.y * DISPLAY_H)
    else:
        raw = event.pos
    # SCALED масштабирует автоматически и pygame сам пересчитывает event.pos
    # в системы координат внутреннего Surface для MOUSEBUTTONDOWN, но FINGERDOWN
    # даёt нормализованные 0..1 координаты реального экрана - переводим вручную.
    if event.type == pygame.FINGERDOWN:
        return (raw[0] * WIDTH / DISPLAY_W, raw[1] * HEIGHT / DISPLAY_H)
    return raw


def get_click_pos(events):
    """Возвращает координаты ОДНОГО клика/тапа за кадр (если был), убирая дубли
    FINGERDOWN+синтетический MOUSEBUTTONDOWN, которые SDL шлёт на один и тот же тап
    на мобильных устройствах — раньше это приводило к двойному срабатыванию кнопок
    (например, перелистыванию сразу на 2 трассы)."""
    for event in events:
        if event.type == pygame.FINGERDOWN:
            return get_event_pos(event)
    for event in events:
        if event.type == pygame.MOUSEBUTTONDOWN:
            return get_event_pos(event)
    return None


_dark_overlay = None


def get_dark_overlay(alpha):
    global _dark_overlay
    if _dark_overlay is None:
        _dark_overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        _dark_overlay.fill((0, 0, 0, alpha))
    return _dark_overlay


_tap_zone_surf = None


def get_tap_zone_surf(hint_h):
    global _tap_zone_surf
    if _tap_zone_surf is None:
        _tap_zone_surf = pygame.Surface((WIDTH // 2, hint_h), pygame.SRCALPHA)
        _tap_zone_surf.fill((255, 255, 255, 30))
    return _tap_zone_surf


_title_cache = {}


def render_title_with_outline(text, font_obj, fg, outline_col, outline_w=3):
    key = (text, id(font_obj), fg, outline_col, outline_w)
    cached = _title_cache.get(key)
    if cached is not None:
        return cached
    base = font_obj.render(text, True, fg)
    w, h = base.get_size()
    surf = pygame.Surface((w + outline_w * 2, h + outline_w * 2), pygame.SRCALPHA)
    outline = font_obj.render(text, True, outline_col)
    for dx in range(-outline_w, outline_w + 1):
        for dy in range(-outline_w, outline_w + 1):
            if dx * dx + dy * dy <= outline_w * outline_w:
                surf.blit(outline, (outline_w + dx, outline_w + dy))
    surf.blit(base, (outline_w, outline_w))
    _title_cache[key] = surf
    return surf


GAME_MODES = [
    {"key": "classic", "label": "Классика"},
    {"key": "levels", "label": "Уровни"},
    {"key": "endless", "label": "Бесконечный"},
]
mode_index = 0

# Предрасчитанные обводки для пульсации кнопки ИГРАТЬ (вместо draw.rect каждый кадр
# с новым inflate — рисуем один раз на каждый шаг анимации и просто blit'им)
_glow_frames_cache = {}


def get_glow_frames(base_rect, accent, steps=20):
    key = (base_rect.size, accent)
    cached = _glow_frames_cache.get(key)
    if cached is not None:
        return cached
    frames = []
    max_pad = sc(14)
    for i in range(steps):
        t = i / (steps - 1)
        pad = int(max_pad * t)
        w, h = base_rect.w + pad, base_rect.h + pad
        surf = pygame.Surface((w + sc(6), h + sc(6)), pygame.SRCALPHA)
        pygame.draw.rect(surf, accent, (sc(3), sc(3), w, h), max(2, sc(2)), border_radius=sc(18))
        frames.append(surf)
    _glow_frames_cache[key] = frames
    return frames


_track_card_cache = {}


def get_track_card(track, w, h):
    key = (track["name"], w, h)
    cached = _track_card_cache.get(key)
    if cached is not None:
        return cached
    accent = track.get("accent", WHITE)
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(surf, (255, 255, 255, 40), surf.get_rect(), border_radius=sc(14))
    pygame.draw.rect(surf, accent, surf.get_rect(), 2, border_radius=sc(14))
    name_surf = font.render(track["name"], True, WHITE)
    surf.blit(name_surf, name_surf.get_rect(center=(w // 2, h // 2 - sc(10))))
    _track_card_cache[key] = surf
    return surf


_mode_card_cache = {}


def get_mode_card(mode, w, h, accent):
    key = (mode["key"], w, h, accent)
    cached = _mode_card_cache.get(key)
    if cached is not None:
        return cached
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(surf, (255, 255, 255, 40), surf.get_rect(), border_radius=sc(14))
    pygame.draw.rect(surf, accent, surf.get_rect(), 2, border_radius=sc(14))
    name_surf = font.render(mode["label"], True, WHITE)
    surf.blit(name_surf, name_surf.get_rect(center=(w // 2, h // 2)))
    _mode_card_cache[key] = surf
    return surf


def menu():
    global track_index, mode_index
    btn_w, btn_h = sc(260), sc(74)
    play_btn = Button((WIDTH // 2 - btn_w // 2, HEIGHT // 2 - sc(60), btn_w, btn_h), "ИГРАТЬ")
    quit_btn = Button((WIDTH // 2 - btn_w // 2, HEIGHT // 2 + sc(240), btn_w, btn_h), "ВЫХОД")

    arrow_size = sc(52)
    card_w, card_h = sc(220), sc(58)

    mode_row_y = HEIGHT // 2 + sc(45)
    track_row_y = HEIGHT // 2 + sc(130)

    mode_left_btn = Button((WIDTH // 2 - card_w // 2 - arrow_size - sc(8), mode_row_y, arrow_size, card_h), "<")
    mode_right_btn = Button((WIDTH // 2 + card_w // 2 + sc(8), mode_row_y, arrow_size, card_h), ">")

    track_left_btn = Button((WIDTH // 2 - card_w // 2 - arrow_size - sc(8), track_row_y, arrow_size, card_h), "<")
    track_right_btn = Button((WIDTH // 2 + card_w // 2 + sc(8), track_row_y, arrow_size, card_h), ">")

    bg_offset = 0
    decorative_track = TRACKS[track_index]

    title_surf = render_title_with_outline("АВТО ГОНКИ", title_font, WHITE, (15, 15, 15), sc(3))
    subtitle_surf = font.render("Уклонись от машин", True, (225, 225, 225))
    hint_surf = font.render("Тапай слева/справа по экрану, чтобы менять полосу", True, (210, 210, 210))

    glow_frame_idx = 0
    glow_dir = 1

    while True:
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                pygame.quit()
                sys.exit()

        pos = get_click_pos(events)
        if pos is not None:
            if play_btn.clicked(pos):
                return
            elif mode_left_btn.clicked(pos):
                mode_index = (mode_index - 1) % len(GAME_MODES)
            elif mode_right_btn.clicked(pos):
                mode_index = (mode_index + 1) % len(GAME_MODES)
            elif track_left_btn.clicked(pos):
                track_index = (track_index - 1) % len(TRACKS)
                decorative_track = TRACKS[track_index]
            elif track_right_btn.clicked(pos):
                track_index = (track_index + 1) % len(TRACKS)
                decorative_track = TRACKS[track_index]
            elif quit_btn.clicked(pos):
                pygame.quit()
                sys.exit()

        bg_offset += 3
        accent = decorative_track.get("accent", WHITE)

        draw_road(bg_offset, decorative_track)
        screen.blit(get_dark_overlay(130), (0, 0))

        title_rect = title_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 - sc(230)))
        underline_w = title_rect.w * 0.7
        pygame.draw.rect(screen, accent,
                          (WIDTH // 2 - underline_w // 2, title_rect.bottom - sc(6), underline_w, sc(4)),
                          border_radius=sc(2))
        screen.blit(title_surf, title_rect)
        screen.blit(subtitle_surf, subtitle_surf.get_rect(center=(WIDTH // 2, title_rect.bottom + sc(22))))

        # Пульсация кнопки ИГРАТЬ через предрасчитанные кадры (без draw.rect в цикле)
        glow_frames = get_glow_frames(play_btn.rect, accent)
        glow_frame_idx += glow_dir
        if glow_frame_idx >= len(glow_frames) - 1 or glow_frame_idx <= 0:
            glow_dir *= -1
        glow = glow_frames[glow_frame_idx]
        screen.blit(glow, glow.get_rect(center=play_btn.rect.center))
        play_btn.draw(screen)

        # Режим игры
        mode_card_rect = pygame.Rect(0, 0, card_w, card_h)
        mode_card_rect.center = (WIDTH // 2, mode_row_y + card_h // 2)
        screen.blit(get_mode_card(GAME_MODES[mode_index], card_w, card_h, accent), mode_card_rect.topleft)
        mode_left_btn.draw(screen)
        mode_right_btn.draw(screen)

        # Трасса
        track_card_rect = pygame.Rect(0, 0, card_w, card_h)
        track_card_rect.center = (WIDTH // 2, track_row_y + card_h // 2)
        screen.blit(get_track_card(decorative_track, card_w, card_h), track_card_rect.topleft)
        track_left_btn.draw(screen)
        track_right_btn.draw(screen)

        dot_r = sc(4)
        dot_gap = sc(14)
        total_w = (len(TRACKS) - 1) * dot_gap
        start_x = track_card_rect.centerx - total_w // 2
        dots_y = track_card_rect.bottom + sc(14)
        for i in range(len(TRACKS)):
            col = accent if i == track_index else (150, 150, 150)
            pygame.draw.circle(screen, col, (start_x + i * dot_gap, dots_y), dot_r)

        quit_btn.draw(screen)
        screen.blit(hint_surf, hint_surf.get_rect(center=(WIDTH // 2, HEIGHT - sc(30))))

        pygame.display.flip()
        clock.tick(60)


# ---------------------------------------------------------------------------
# Режим "Уровни": набор уровней с нарастающей сложностью и фан-модификаторами.
# ---------------------------------------------------------------------------
LEVELS = [
    {"name": "Разминка", "target_score": 8, "base_speed": 6, "spawn_range": (40, 70), "gimmick": None},
    {"name": "Разгон", "target_score": 14, "base_speed": 7.5, "spawn_range": (35, 60), "gimmick": None},
    {"name": "Туман", "target_score": 18, "base_speed": 8, "spawn_range": (32, 55), "gimmick": "fog"},
    {"name": "Гололёд", "target_score": 22, "base_speed": 8.5, "spawn_range": (30, 52), "gimmick": "ice"},
    {"name": "Зеркалка", "target_score": 24, "base_speed": 9, "spawn_range": (30, 50), "gimmick": "mirror"},
    {"name": "Ночная гонка", "target_score": 28, "base_speed": 9.5, "spawn_range": (28, 48), "gimmick": "night"},
    {"name": "Ливень машин", "target_score": 34, "base_speed": 10, "spawn_range": (18, 34), "gimmick": "swarm"},
    {"name": "Финиш", "target_score": 42, "base_speed": 11, "spawn_range": (16, 30), "gimmick": "all"},
]

GIMMICK_LABELS = {
    "fog": "Туман — видно недалеко вперёд",
    "ice": "Гололёд — машину заносит",
    "mirror": "Зеркалка — управление инвертировано",
    "night": "Ночь — узкий фонарик",
    "swarm": "Ливень машин — враги сыплются чаще",
    "all": "Всё сразу!",
}

level_index = 0


def get_gimmicks(level):
    g = level.get("gimmick")
    if g == "all":
        return ["fog", "ice", "mirror", "night", "swarm"]
    if g is None:
        return []
    return [g]


_fog_overlay_cache = {}


def get_fog_overlay():
    if "fog" in _fog_overlay_cache:
        return _fog_overlay_cache["fog"]
    surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for i in range(HEIGHT):
        t = i / HEIGHT
        alpha = int(210 * (1 - t) ** 2.2)
        pygame.draw.line(surf, (210, 210, 220, alpha), (0, i), (WIDTH, i))
    _fog_overlay_cache["fog"] = surf
    return surf


_night_overlay_cache = {}


def get_night_overlay(radius):
    key = radius
    if key in _night_overlay_cache:
        return _night_overlay_cache[key]
    surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 235))
    # "прожигаем" мягкую дыру-фонарик через радиальный градиент
    hole = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    for r in range(radius, 0, -2):
        alpha = int(235 * (r / radius) ** 2)
        pygame.draw.circle(hole, (0, 0, 0, alpha), (radius, radius), r)
    surf.blit(hole, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
    _night_overlay_cache[key] = surf
    return surf


def play(mode="classic"):
    global level_index

    track = TRACKS[track_index]

    if mode == "levels":
        level = LEVELS[level_index]
        gimmicks = get_gimmicks(level)
        base_speed = sc(level["base_speed"])
        spawn_range = level["spawn_range"]
        target_score = level["target_score"]
    else:
        gimmicks = []
        base_speed = float(sc(6))
        spawn_range = (35, 65)
        target_score = None

    player = Car(1, HEIGHT - sc(120), RED)
    enemies = []
    spawn_timer = 0
    speed = float(base_speed)
    score = 0
    offset = 0.0
    game_over = False
    level_cleared = False
    move_target_lane = 1

    # Гололёд: у машины есть "инерция заноса" — целевая полоса не даёт мгновенно
    # долетать до центра, а слегка проскальзывает мимо и возвращается.
    ice_active = "ice" in gimmicks or "all" in gimmicks
    mirror_active = "mirror" in gimmicks
    fog_active = "fog" in gimmicks
    night_active = "night" in gimmicks
    swarm_active = "swarm" in gimmicks

    back_btn = Button((sc(14), sc(14), sc(120), sc(50)), "Меню", font)
    restart_btn = Button((WIDTH // 2 - sc(110), HEIGHT // 2 + sc(20), sc(220), sc(64)), "Заново")
    menu_btn_over = Button((WIDTH // 2 - sc(110), HEIGHT // 2 + sc(100), sc(220), sc(64)), "В меню")
    next_level_btn = Button((WIDTH // 2 - sc(110), HEIGHT // 2 + sc(20), sc(220), sc(64)), "Дальше")

    hint_h = sc(60)
    tap_zone = get_tap_zone_surf(hint_h)
    arrow_l = font.render("<", True, WHITE)
    arrow_r = font.render(">", True, WHITE)
    game_over_overlay = get_dark_overlay(160)
    crash_text = big_font.render("АВАРИЯ!", True, RED)
    win_text = big_font.render("УРОВЕНЬ ПРОЙДЕН!", True, GREEN)

    gimmick_banner = None
    if gimmicks:
        label = " · ".join(GIMMICK_LABELS[g] for g in gimmicks)
        gimmick_banner = font.render(label, True, YELLOW)
    level_title_surf = None
    if mode == "levels":
        level_title_surf = font.render(f"Уровень {level_index + 1}: {level['name']}", True, WHITE)
    banner_timer = 150

    score_cache_val = None
    score_surf = None

    while True:
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return
                if event.key == pygame.K_r:
                    return play(mode)
                elif not game_over and not level_cleared:
                    if event.key in (pygame.K_LEFT, pygame.K_a):
                        d = 1 if mirror_active else -1
                        move_target_lane = max(0, min(LANE_COUNT - 1, player.lane + d))
                    if event.key in (pygame.K_RIGHT, pygame.K_d):
                        d = -1 if mirror_active else 1
                        move_target_lane = max(0, min(LANE_COUNT - 1, player.lane + d))

        pos = get_click_pos(events)
        if pos is not None:
            tap_x, tap_y = pos
            if level_cleared:
                if next_level_btn.clicked(pos):
                    level_index = min(level_index + 1, len(LEVELS) - 1)
                    return play(mode)
                if menu_btn_over.clicked(pos):
                    level_index = 0
                    return
            elif game_over:
                if restart_btn.clicked(pos):
                    return play(mode)
                if menu_btn_over.clicked(pos):
                    if mode == "levels":
                        level_index = 0
                    return
            else:
                if back_btn.clicked(pos):
                    return
                elif tap_x < WIDTH / 2:
                    d = 1 if mirror_active else -1
                    move_target_lane = max(0, min(LANE_COUNT - 1, player.lane + d))
                else:
                    d = -1 if mirror_active else 1
                    move_target_lane = max(0, min(LANE_COUNT - 1, player.lane + d))

        if banner_timer > 0:
            banner_timer -= 1

        if not game_over and not level_cleared:
            player.lane = move_target_lane
            target_x = lane_x(player.lane)
            if ice_active:
                # заносит: догоняем цель медленнее и с "перелётом"
                player.x += (target_x - player.x) * 0.12
            else:
                player.x += (target_x - player.x) * 0.35

            offset += speed

            if mode == "endless":
                # Бесконечный режим усложняется с каждым набранным очком
                speed = base_speed + score * (sc(0.18))
            else:
                speed += 0.0015 * SCALE

            spawn_timer -= 1
            if spawn_timer <= 0:
                lane = random.randint(0, LANE_COUNT - 1)
                color = random.choice([BLUE, YELLOW, GREEN, (150, 60, 200)])
                enemies.append(Car(lane, -sc(80), color))
                lo, hi = spawn_range
                if mode == "endless":
                    # чем больше очков, тем чаще спавн (но не чаще предела)
                    shrink = min(20, score // 2)
                    lo, hi = max(12, lo - shrink), max(20, hi - shrink)
                if swarm_active and random.random() < 0.4:
                    other_lanes = [l for l in range(LANE_COUNT) if l != lane]
                    if other_lanes:
                        lane2 = random.choice(other_lanes)
                        color2 = random.choice([BLUE, YELLOW, GREEN, (150, 60, 200)])
                        enemies.append(Car(lane2, -sc(80), color2))
                spawn_timer = random.randint(lo, hi)

            player.update_wheels(speed)
            for e in enemies:
                e.y += speed
                e.update_wheels(speed)
            enemies = [e for e in enemies if e.y < HEIGHT + sc(100)]

            for e in enemies:
                if not hasattr(e, "scored") and e.y > player.y:
                    e.scored = True
                    score += 1

            player_rect = player.rect().inflate(-sc(8), -sc(8))
            for e in enemies:
                if player_rect.colliderect(e.rect()):
                    game_over = True

            if target_score is not None and score >= target_score:
                level_cleared = True

        draw_road(offset, track)
        for e in enemies:
            e.draw()
        player.draw()

        if fog_active:
            screen.blit(get_fog_overlay(), (0, 0))
        if night_active:
            screen.blit(get_night_overlay(sc(110)), (0, 0))

        if score_cache_val != score:
            score_surf = font.render(f"Очки: {score}", True, WHITE)
            score_cache_val = score
        screen.blit(score_surf, (sc(150), sc(24)))

        if mode == "levels" and level_title_surf is not None:
            screen.blit(level_title_surf, level_title_surf.get_rect(center=(WIDTH // 2, sc(30))))
            if target_score is not None:
                goal_surf = font.render(f"Цель: {score}/{target_score}", True, (220, 220, 220))
                screen.blit(goal_surf, goal_surf.get_rect(center=(WIDTH // 2, sc(60))))

        if gimmick_banner is not None and banner_timer > 0:
            alpha = min(255, banner_timer * 4)
            gb = gimmick_banner.copy()
            gb.set_alpha(alpha)
            screen.blit(gb, gb.get_rect(center=(WIDTH // 2, sc(90))))

        if level_cleared:
            screen.blit(game_over_overlay, (0, 0))
            screen.blit(win_text, win_text.get_rect(center=(WIDTH // 2, HEIGHT // 2 - sc(90))))
            final_score_surf = font.render(f"Очки: {score}", True, WHITE)
            screen.blit(final_score_surf, final_score_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 - sc(30))))
            if level_index < len(LEVELS) - 1:
                next_level_btn.draw(screen)
                menu_btn_over.draw(screen)
            else:
                done_surf = font.render("Все уровни пройдены!", True, YELLOW)
                screen.blit(done_surf, done_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 + sc(55))))
                menu_btn_over.draw(screen)
        elif not game_over:
            back_btn.draw(screen)
            screen.blit(tap_zone, (0, HEIGHT - hint_h))
            screen.blit(tap_zone, (WIDTH // 2, HEIGHT - hint_h))
            screen.blit(arrow_l, arrow_l.get_rect(center=(WIDTH // 4, HEIGHT - hint_h // 2)))
            screen.blit(arrow_r, arrow_r.get_rect(center=(3 * WIDTH // 4, HEIGHT - hint_h // 2)))
        else:
            screen.blit(game_over_overlay, (0, 0))
            screen.blit(crash_text, crash_text.get_rect(center=(WIDTH // 2, HEIGHT // 2 - sc(90))))
            final_score_surf = font.render(f"Очки: {score}", True, WHITE)
            screen.blit(final_score_surf, final_score_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 - sc(30))))
            restart_btn.draw(screen)
            menu_btn_over.draw(screen)

        pygame.display.flip()
        clock.tick(60)





def main():
    while True:
        menu()
        selected_mode = GAME_MODES[mode_index]["key"]
        play(selected_mode)


if __name__ == "__main__":
    main()
