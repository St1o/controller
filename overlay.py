"""Общие детали для кнопок «наведи и подожди» и для русского текста на кадре с камеры.

DwellTracker - нажатие задержкой: кнопка срабатывает, когда палец (или курсор) пробыл на ней нужное время.
Защита от случайных нажатий встроена: после срабатывания кнопку нужно покинуть, чтобы она сработала снова,
а при смене кнопки отсчёт начинается заново.
"""
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_CANDIDATES = [
    os.path.join(BASE_DIR, "assets", "fonts", "DejaVuSans-Bold.ttf"),
    "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/segoeuib.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/Library/Fonts/Arial Bold.ttf",
]


class DwellTracker:
    def __init__(self, seconds=0.8):
        self.seconds = seconds
        self.reset()

    def reset(self, ignore_current=False):
        """Начать заново. ignore_current=True: то, что под пальцем в момент сброса, сработает, только когда его покинут и вернутся."""
        self.target = None
        self.since = 0.0
        self.armed = True
        self._ignore_first = ignore_current

    def update(self, target, now):
        """target - что сейчас под пальцем (любой объект) или None. Возвращает target в момент нажатия, иначе None."""
        if self._ignore_first:
            self._ignore_first = False
            if target is not None:
                self.target, self.since, self.armed = target, now, False
                return None
        if target != self.target:
            self.target, self.since, self.armed = target, now, True
            return None
        if target is None or not self.armed:
            return None
        if now - self.since >= self.seconds:
            self.armed = False
            return target
        return None

    def progress(self, now):
        """Доля пройденного ожидания 0..1 для текущей кнопки (для индикатора)."""
        if self.target is None or not self.armed or self.seconds <= 0:
            return 0.0
        return min(max((now - self.since) / self.seconds, 0.0), 1.0)


# --- русский текст на кадре (cv2.putText русских букв не рисует) -------------
_fonts = {}
_masks = {}


def _font(px):
    px = int(max(px, 8))
    if px not in _fonts:
        font = None
        for path in FONT_CANDIDATES:
            if os.path.isfile(path):
                try:
                    font = ImageFont.truetype(path, px)
                    break
                except OSError:
                    continue
        _fonts[px] = font or ImageFont.load_default()
    return _fonts[px]


def text_mask(text, px):
    """Прозрачность букв (0..255) и размер надписи; результат кешируется."""
    key = (text, int(px))
    if key not in _masks:
        font = _font(px)
        probe = ImageDraw.Draw(Image.new("L", (1, 1)))
        left, top, right, bottom = probe.textbbox((0, 0), text, font=font)
        w, h = max(right - left, 1), max(bottom - top, 1)
        img = Image.new("L", (w, h), 0)
        ImageDraw.Draw(img).text((-left, -top), text, font=font, fill=255)
        if len(_masks) > 300:
            _masks.clear()
        _masks[key] = np.asarray(img)
    return _masks[key]


def put_text(img, text, rect, px, color=(255, 255, 255), align="center"):
    """Написать text в прямоугольнике rect=(x, y, w, h) на кадре BGR (на месте)."""
    mask = text_mask(text, px)
    mh, mw = mask.shape
    x, y, w, h = [int(v) for v in rect]
    ox = x + (w - mw) // 2 if align == "center" else x + 8
    oy = y + (h - mh) // 2
    x0, y0 = max(ox, 0), max(oy, 0)
    x1, y1 = min(ox + mw, img.shape[1]), min(oy + mh, img.shape[0])
    if x1 <= x0 or y1 <= y0:
        return img
    a = mask[y0 - oy:y1 - oy, x0 - ox:x1 - ox].astype(np.float32)[:, :, None] / 255.0
    roi = img[y0:y1, x0:x1]
    roi[:] = (roi * (1.0 - a) + np.array(color, np.float32) * a).astype(np.uint8)
    return img


def fill_rect(img, rect, color, alpha=1.0):
    """Залить прямоугольник цветом (alpha < 1 - полупрозрачно)."""
    x, y, w, h = [int(v) for v in rect]
    x0, y0 = max(x, 0), max(y, 0)
    x1, y1 = min(x + w, img.shape[1]), min(y + h, img.shape[0])
    if x1 <= x0 or y1 <= y0:
        return img
    roi = img[y0:y1, x0:x1]
    if alpha >= 1.0:
        roi[:] = color
    else:
        roi[:] = (roi * (1.0 - alpha) + np.array(color, np.float32) * alpha).astype(np.uint8)
    return img


def inside(rect, point):
    x, y, w, h = rect
    return point is not None and x <= point[0] <= x + w and y <= point[1] <= y + h
