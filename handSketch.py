"""Нарисованная рука для вкладки «Инструкция» и для тестов.

Вместо фотографий (в дипломе были гифки с рукой автора) строим руку из тех же 21 точек,
что выдаёт mediapipe, и рисуем её тем же скелетом, который видно на экране при работе.
"""
import math

import cv2
import numpy as np

from WorkingHand import draw_hand

SKIN = (120, 150, 205)       # BGR
BACKGROUND = (28, 33, 43)    # тёмный фон, как у кадра с камеры на рисунках диплома
HUD_COLOR = (255, 51, 102)

# Основания пальцев (x, y) относительно запястья; y вверх отрицательный. Ладонью к камере, большой слева.
_MCP = {5: (-24, -95), 9: (0, -100), 13: (24, -94), 17: (46, -80)}
_LENGTHS = {5: (38, 24, 20), 9: (42, 26, 22), 13: (38, 24, 20), 17: (30, 20, 18)}
_FAN = {5: -4, 9: 0, 13: 4, 17: 10}   # градусов: пальцы чуть веером
_VEE = {5: -18, 9: 18}                # указательный и средний подняты вдвоём: разводим буквой V


def make_hand(fingers, scale=1.0, thumb_tucked_tip=(-12, -52), vee=True):
    """21 точка руки (x, y) для набора пальцев [большой, указательный, средний, безымянный, мизинец].

    Запястье в (0, 0), рука смотрит вверх; масштаб 1.0 - ладонь длиной 100 пикселей.
    vee=False: указательный и средний подняты вместе (поза двойного клика), иначе разведены буквой V.
    """
    pts = [None] * 21
    pts[0] = (0.0, 0.0)
    pts[1], pts[2] = (-26, -22), (-44, -44)
    if fingers[0]:
        pts[3], pts[4] = (-58, -62), (-72, -80)
    else:
        pts[3], pts[4] = (-28, -50), thumb_tucked_tip
    vee = vee and fingers[1] and fingers[2]
    for k, (mcp, up) in enumerate(zip((5, 9, 13, 17), fingers[1:])):
        x0, y0 = _MCP[mcp]
        pts[mcp] = (x0, y0)
        pip_len, dip_len, tip_len = _LENGTHS[mcp]
        if up:
            a = math.radians(_VEE[mcp] if vee and mcp in _VEE else _FAN[mcp])
            dx, dy = math.sin(a), -math.cos(a)
            pts[mcp + 1] = (x0 + dx * pip_len, y0 + dy * pip_len)
            pts[mcp + 2] = (x0 + dx * (pip_len + dip_len), y0 + dy * (pip_len + dip_len))
            pts[mcp + 3] = (x0 + dx * (pip_len + dip_len + tip_len), y0 + dy * (pip_len + dip_len + tip_len))
        else:   # палец согнут: кончик возвращается к ладони
            pts[mcp + 1] = (x0, y0 - 26)
            pts[mcp + 2] = (x0 + 1, y0 - 6)
            pts[mcp + 3] = (x0 + 2, y0 + 14)
    return [(x * scale, y * scale) for x, y in pts]


def place(points, index, x, y):
    """Сдвинуть руку так, чтобы точка index оказалась в (x, y)."""
    dx, dy = x - points[index][0], y - points[index][1]
    return [(px + dx, py + dy) for px, py in points]


def _skin(img, pts, scale):
    """Кожа: ладонь и пальцы толстыми линиями, чтобы рука выглядела рукой."""
    palm = np.array([pts[0], pts[1], pts[2], pts[5], pts[9], pts[13], pts[17]], np.int32)
    cv2.fillPoly(img, [palm], SKIN, cv2.LINE_AA)
    width = max(int(20 * scale), 3)
    for chain in ((1, 2, 3, 4), (5, 6, 7, 8), (9, 10, 11, 12), (13, 14, 15, 16), (17, 18, 19, 20)):
        for a, b in zip(chain, chain[1:]):
            cv2.line(img, tuple(int(v) for v in pts[a]), tuple(int(v) for v in pts[b]), SKIN, width, cv2.LINE_AA)
    cv2.fillPoly(img, [palm], SKIN, cv2.LINE_AA)


def gesture_picture(fingers, label, size=(375, 225), vee=True):
    """Картинка-подсказка для вкладки «Инструкция»: рука, скелет и надпись состояния, как в окне программы."""
    w, h = size
    img = np.zeros((h, w, 3), np.uint8)
    top, bottom = np.array(BACKGROUND, np.float32) * 1.25, np.array(BACKGROUND, np.float32) * 0.7
    for y in range(h):    # лёгкий градиент фона
        img[y, :] = (top + (bottom - top) * y / h).clip(0, 255)
    scale = h / 255.0
    pts = make_hand(fingers, scale, vee=vee)
    pts = place(pts, 0, w * 0.5, h * 0.93)
    _skin(img, pts, scale)
    draw_hand(img, pts)
    cv2.putText(img, label, (8, 28), cv2.FONT_HERSHEY_PLAIN, 1.8, HUD_COLOR, 2, cv2.LINE_AA)
    return img
