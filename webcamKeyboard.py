"""Виртуальная клавиатура (диплом, раздел 3.5).

Клавиши рисуются поверх видео. Навести указательный палец на клавишу и «щипком»
свести большой и указательный пальцы: символ печатается туда, где стоит текстовый курсор.
Служебные клавиши: SH - регистр, LN - язык (RU/EN), EN - Enter, CL - очистить строку на экране, BS - стереть символ.
Подписи рисуются через Pillow, потому что cv2.putText не умеет русские буквы.
"""
import os
import time
from collections import Counter, deque

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from SystemInput import SystemInput

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_CANDIDATES = [
    os.path.join(BASE_DIR, "assets", "fonts", "DejaVuSans-Bold.ttf"),
    "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/segoeuib.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/Library/Fonts/Arial Bold.ttf",
]

# Раскладки (как в дипломе: буквы заглавными, регистр переключается клавишей SH)
_DIGITS = list("1234567890-=")
CONTROL_ROW = [" ", "SH", "LN", "EN", "CL", "BS"]
en_keys = [_DIGITS, list("QWERTYUIOP[]"), list("ASDFGHJKL;'*"), list("ZXCVBNM,./?$"), CONTROL_ROW]
ru_keys = [_DIGITS, list("ЙЦУКЕНГШЩЗХЪ"), list("ФЫВАПРОЛДЖЭ;"), list("ЯЧСМИТЬБЮ,.?"), CONTROL_ROW]
CONTROL_NAMES = ("SH", "LN", "EN", "CL", "BS")

KEY_COLOR = (175, 0, 175)     # BGR, малиновый как на рисунке 36 диплома
HOVER_COLOR = (175, 0, 175)
PRESS_COLOR = (0, 255, 0)
CORNER_COLOR = (0, 255, 0)
WHITE = (255, 255, 255)


def _load_font(px):
    for path in FONT_CANDIDATES:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, max(int(px), 8))
            except OSError:
                continue
    return ImageFont.load_default()


def apply_case(rows, upper):
    """Буквы и подписи служебных клавиш в нужном регистре."""
    return [[k.upper() if upper else k.lower() for k in row] for row in rows]


class Button:
    def __init__(self, pos, text, size=(85, 85)):
        self.pos = list(pos)
        self.size = list(size)
        self.text = text

    @property
    def is_control(self):
        return self.text.upper() in CONTROL_NAMES

    def contains(self, x, y):
        return self.pos[0] < x < self.pos[0] + self.size[0] and self.pos[1] < y < self.pos[1] + self.size[1]


def addButtonList(buttonList, keys, scale=1.0):
    """Расставить клавиши сеткой 100x100 (клавиша 85x85), умноженной на scale. Пробел занимает три клетки."""
    pitch, side = 100 * scale, 85 * scale
    for i, row in enumerate(keys):
        y = 50 * scale + pitch * i
        if i == len(keys) - 1:   # нижний ряд: широкий пробел и служебные клавиши
            cols = [(0, 3), (3, 1), (4, 1), (5, 1), (6, 1), (7, 1)]
        else:
            cols = [(j, 1) for j in range(len(row))]
        for key, (col, span) in zip(row, cols):
            buttonList.append(Button([50 * scale + pitch * col, y], key, [side + pitch * (span - 1), side]))
    return buttonList


def _center_text(draw, text, box, font, fill=(255, 255, 255)):
    x, y, w, h = box
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    draw.text((x + (w - (right - left)) / 2 - left, y + (h - (bottom - top)) / 2 - top), text, font=font, fill=fill)


def _key_label(button):
    return "␣" if button.text == " " else button.text


def drawAll(img, buttonList, scale=1.0):
    """Прозрачная клавиатура поверх кадра (без подсветки): используется как запасной вариант и в тестах."""
    return _KeyboardRenderer().blend(img, buttonList, scale)


class _KeyboardRenderer:
    """Рисует клавиши. Слой клавиш готовится один раз для размера кадра и раскладки, потом только накладывается."""

    def __init__(self):
        self._layer_key = None
        self._layer = None
        self._sprites = {}
        self._fonts = {}
        self._text_cache = (None, None)

    def font(self, px):
        px = int(px)
        if px not in self._fonts:
            self._fonts[px] = _load_font(px)
        return self._fonts[px]

    def _make_layer(self, buttonList, shape, scale):
        h, w = shape[:2]
        layer = np.zeros((h, w, 3), np.uint8)
        mask = np.zeros((h, w), np.uint8)
        t = max(int(4 * scale), 1)
        arm = max(int(20 * scale), 4)
        for b in buttonList:
            x, y = int(b.pos[0]), int(b.pos[1])
            bw, bh = int(b.size[0]), int(b.size[1])
            cv2.rectangle(layer, (x, y), (x + bw, y + bh), KEY_COLOR, cv2.FILLED)
            cv2.rectangle(mask, (x, y), (x + bw, y + bh), 255, cv2.FILLED)
            # зелёные уголки, как у cvzone.cornerRect
            for cx, cy, dx, dy in ((x, y, 1, 1), (x + bw, y, -1, 1), (x, y + bh, 1, -1), (x + bw, y + bh, -1, -1)):
                cv2.line(layer, (cx, cy), (cx + dx * arm, cy), CORNER_COLOR, t)
                cv2.line(layer, (cx, cy), (cx, cy + dy * arm), CORNER_COLOR, t)
        # подписи рисуем отдельным слоем и накладываем плотно (не полупрозрачно), чтобы буквы читались
        text = Image.new("L", (w, h), 0)
        draw = ImageDraw.Draw(text)
        for b in buttonList:
            self._label(draw, b, scale, 255)
        alpha = np.asarray(text)
        ys, xs = np.nonzero(mask)
        if len(ys) == 0:
            return layer, mask.astype(bool), (0, 0, 0, 0), None
        box = (int(ys.min()), int(ys.max()) + 1, int(xs.min()), int(xs.max()) + 1)
        part = alpha[box[0]:box[1], box[2]:box[3]]
        idx = np.nonzero(part)
        return layer, mask.astype(bool), box, (idx, (part[idx].astype(np.float32) / 255.0)[:, None])

    def _label(self, draw, b, scale, fill=WHITE):
        px = (34 if b.is_control else 48) * scale
        _center_text(draw, _key_label(b), (b.pos[0], b.pos[1], b.size[0], b.size[1]), self.font(px), fill)

    def blend(self, img, buttonList, scale):
        key = (img.shape[:2], tuple((b.text, tuple(b.pos)) for b in buttonList))
        if key != self._layer_key:
            self._layer = self._make_layer(buttonList, img.shape, scale)
            self._layer_key = key
        layer, mask, (y0, y1, x0, x1), text = self._layer
        out = img.copy()
        if y1 > y0:
            roi = out[y0:y1, x0:x1]
            blended = cv2.addWeighted(roi, 0.5, layer[y0:y1, x0:x1], 0.5, 0)
            np.copyto(roi, blended, where=mask[y0:y1, x0:x1, None])
            if text is not None:
                idx, a = text
                roi[idx] = (roi[idx] * (1.0 - a) + 255.0 * a).astype(np.uint8)
        return out

    def sprite(self, b, scale, color):
        """Сплошная клавиша (наведение или нажатие)."""
        w, h = int(b.size[0]), int(b.size[1])
        key = (b.text, w, h, color)
        if key not in self._sprites:
            pil = Image.new("RGB", (w, h), color[::-1])
            self._label(ImageDraw.Draw(pil), Button((0, 0), b.text, (w, h)), scale)
            self._sprites[key] = cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR)
        return self._sprites[key]

    def paste(self, img, sprite, x, y):
        h, w = sprite.shape[:2]
        x, y = int(x), int(y)
        x0, y0 = max(x, 0), max(y, 0)
        x1, y1 = min(x + w, img.shape[1]), min(y + h, img.shape[0])
        if x1 > x0 and y1 > y0:
            img[y0:y1, x0:x1] = sprite[y0 - y:y1 - y, x0 - x:x1 - x]

    def text_field(self, img, text, scale):
        """Строка с напечатанным текстом внизу (прямоугольник из диплома)."""
        x, y = int(50 * scale), int(560 * scale)
        w, h = int(1190 * scale), int(100 * scale)
        if self._text_cache[0] != (text, w, h):
            pil = Image.new("RGB", (w, h), KEY_COLOR[::-1])
            draw = ImageDraw.Draw(pil)
            font = self.font(56 * scale)
            shown = text
            while shown and draw.textlength(shown, font=font) > w - 20 * scale:   # показываем хвост строки
                shown = shown[1:]
            left, top, right, bottom = draw.textbbox((0, 0), shown or " ", font=font)
            draw.text((10 * scale - left, (h - (bottom - top)) / 2 - top), shown, font=font, fill=WHITE)
            self._text_cache = ((text, w, h), cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR))
        self.paste(img, self._text_cache[1], x, y)


class VirtualKeyboard:
    PINCH_CLOSE = 0.25   # большой и указательный сведены (в долях размера ладони)
    PINCH_OPEN = 0.33    # снова разведены
    PRESS_PAUSE = 0.30   # секунд между нажатиями (в дипломе time.sleep(0.3))
    FLASH = 0.25         # сколько секунд нажатая клавиша горит зелёной

    def __init__(self, os_input=None, clock=time.monotonic):
        self.os = os_input or SystemInput()
        self.clock = clock
        self.lang = "ru"
        self.upper = True
        self.finalText = ""
        self._pinched = False
        self._hist = deque(maxlen=6)
        self._last_press = -1e9
        self._flash = (None, 0.0)
        self._render = _KeyboardRenderer()

    @property
    def register(self):
        return "upper" if self.upper else "lower"

    def keys(self):
        return apply_case(ru_keys if self.lang == "ru" else en_keys, self.upper)

    def reset(self):
        """Вызывается при выходе из режима клавиатуры."""
        self._pinched = False
        self._hist.clear()

    # --- нажатие клавиши --------------------------------------------------
    def press(self, button):
        """Выполнить действие клавиши. Возвращает имя действия (для тестов и подсказок)."""
        name = button.text.upper()
        if name == "SH":
            self.upper = not self.upper
            return "shift"
        if name == "LN":
            self.lang = "en" if self.lang == "ru" else "ru"
            return "language"
        if name == "EN":
            self.os.press("enter")
            return "enter"
        if name == "CL":
            self.finalText = ""
            return "clear"
        if name == "BS":
            self.os.press("backspace")
            self.finalText = self.finalText[:-1]
            return "backspace"
        self.os.type_text(button.text)
        self.finalText += button.text
        return "char"

    # --- кадр -------------------------------------------------------------
    def main(self, img, lmList, detector):
        """Нарисовать клавиатуру и обработать один кадр. Возвращает новый кадр."""
        h, w = img.shape[:2]
        scale = w / 1280.0
        buttons = addButtonList([], self.keys(), scale)
        new_img = self._render.blend(img, buttons, scale)
        now = self.clock()

        hover = None
        if lmList and len(lmList) >= 21:
            px, py = lmList[8][1], lmList[8][2]
            for i, b in enumerate(buttons):
                if b.contains(px, py):
                    hover = i
                    break
            cv2.circle(new_img, (px, py), max(int(10 * scale), 4), PRESS_COLOR, cv2.FILLED)
        self._hist.append(hover)

        if lmList and len(lmList) >= 21:
            detector.findDistance(4, 8, new_img, draw=True)
            size = detector.handSize()
            ratio = detector._dist(4, 8) / size if size else 1.0
            pinch_start = False
            if self._pinched:
                if ratio > self.PINCH_OPEN:
                    self._pinched = False
            elif ratio < self.PINCH_CLOSE:
                self._pinched = True
                pinch_start = True
            if pinch_start and now - self._last_press > self.PRESS_PAUSE:
                target = self._target(hover)
                if target is not None:
                    self.press(buttons[target])
                    self._last_press = now
                    self._flash = (target, now + self.FLASH)
                    buttons = addButtonList([], self.keys(), scale)   # раскладка могла смениться
                    new_img = self._render.blend(img, buttons, scale)
        else:
            self._pinched = False

        flash_idx = self._flash[0] if now < self._flash[1] else None
        if hover is not None and hover < len(buttons) and hover != flash_idx:
            b = buttons[hover]
            self._render.paste(new_img, self._render.sprite(b, scale, HOVER_COLOR), b.pos[0], b.pos[1])
        if flash_idx is not None and flash_idx < len(buttons):
            b = buttons[flash_idx]
            self._render.paste(new_img, self._render.sprite(b, scale, PRESS_COLOR), b.pos[0], b.pos[1])
        self._render.text_field(new_img, self.finalText, scale)
        return new_img

    def _target(self, hover):
        """Какая клавиша нажата: палец при щипке чуть смещается, поэтому берём клавишу, на которой он стоял до щипка."""
        before = [k for k in list(self._hist)[:-2] if k is not None]
        if before:
            return Counter(before).most_common(1)[0][0]
        return hover
