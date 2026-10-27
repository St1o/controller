"""Простой графический редактор («особое состояние», диплом, раздел 3.6).

Два пальца (указательный и средний) - режим выбора: поднесите их к цветной полосе сверху.
Один указательный палец - рисование. Чёрный цвет работает как ластик.
Под палитрой подписана панель: «← Назад» (выход), название режима и «Очистить».
Кнопки панели нажимаются «навести и подождать»: подержите кончик указательного пальца на кнопке.
"""
import time

import cv2
import numpy as np

from overlay import DwellTracker, fill_rect, inside, put_text

# Цвета полосы (BGR): красный, малиновый, оранжевый, зелёный, синий, голубой, белый, чёрный (ластик)
PALETTE = [(0, 0, 255), (255, 0, 255), (0, 102, 255), (0, 255, 0), (255, 0, 0), (255, 255, 0),
           (255, 255, 255), (0, 0, 0)]
ERASER = (0, 0, 0)
TITLE = "Графический редактор"
BUTTON_COLOR = (175, 0, 175)
PROGRESS_COLOR = (0, 200, 0)


class AiPainter:
    DWELL = 1.0     # секунд удержания пальца на кнопке «Назад» или «Очистить»

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.drawColor = PALETTE[0]
        self.xp, self.yp = 0, 0
        self.imgCanvas = None
        self.exit_requested = False
        self.tracker = DwellTracker(self.DWELL)

    def reset(self):
        """Прервать текущую линию и заново начать отсчёт нажатий (при входе и выходе из режима)."""
        self.xp, self.yp = 0, 0
        self.tracker.reset(ignore_current=True)

    def clear(self):
        self.imgCanvas = None
        self.xp, self.yp = 0, 0

    # --- разметка ---------------------------------------------------------
    @staticmethod
    def header_height(img):
        return int(img.shape[0] * 0.14)

    @staticmethod
    def strip_height(img):
        return max(int(img.shape[0] * 0.09), 36)

    def buttons(self, img):
        """Прямоугольники кнопок панели: (x, y, w, h)."""
        h, w = img.shape[:2]
        y = self.header_height(img) + 4
        bh = self.strip_height(img) - 8
        bw = max(int(w * 0.2), 110)
        return {"back": (6, y, bw, bh), "clear": (w - bw - 6, y, bw, bh)}

    def draw_all(self, img):
        """Палитра красок сверху и панель с названием режима."""
        h, w = img.shape[:2]
        head = self.header_height(img)
        step = w / len(PALETTE)
        for i, color in enumerate(PALETTE):
            cv2.rectangle(img, (int(i * step), 0), (int((i + 1) * step), head), color, cv2.FILLED)
            if color == self.drawColor:     # выбранный цвет обведён
                cv2.rectangle(img, (int(i * step) + 3, 3), (int((i + 1) * step) - 3, head - 3), (255, 51, 102), 4)
        px = max(int(h * 0.05), 14)
        fill_rect(img, (0, head, w, self.strip_height(img)), (30, 30, 30), 0.6)
        put_text(img, TITLE.upper(), (0, head, w, self.strip_height(img)), px, (255, 255, 255))
        return img

    def _draw_button(self, img, name, rect, label, progress):
        fill_rect(img, rect, BUTTON_COLOR, 0.85)
        if progress > 0:
            x, y, w, h = rect
            fill_rect(img, (x, y, w * progress, h), PROGRESS_COLOR, 0.8)
        put_text(img, label, rect, max(int(img.shape[0] * 0.045), 13), (255, 255, 255))

    # --- кадр -------------------------------------------------------------
    def main(self, img, lmList, fingers, now=None):
        """Один кадр редактора. fingers - [большой, указательный, средний, безымянный, мизинец]."""
        now = self.clock() if now is None else now
        h, w = img.shape[:2]
        if self.imgCanvas is None or self.imgCanvas.shape != img.shape:
            self.imgCanvas = np.zeros(img.shape, np.uint8)
        new_img = img
        head = self.header_height(img)
        top = head + self.strip_height(img)       # ниже этой линии можно рисовать
        scale = w / 1280.0
        have_hand = bool(lmList) and len(lmList) >= 21

        # кнопки панели: нажимаются удержанием кончика указательного пальца
        rects = self.buttons(img)
        tip = (lmList[8][1], lmList[8][2]) if have_hand else None
        target = next((name for name, rect in rects.items() if inside(rect, tip)), None)
        pressed = self.tracker.update(target, now)
        if pressed == "back":
            self.exit_requested = True
        elif pressed == "clear":
            self.clear()
            self.imgCanvas = np.zeros(img.shape, np.uint8)

        if have_hand and fingers is not None:
            x1, y1 = lmList[8][1:]
            x2, y2 = lmList[12][1:]
            if fingers[1:] == [1, 1, 0, 0]:        # режим выбора
                self.xp, self.yp = 0, 0
                cv2.rectangle(new_img, (x1, y1 - 15), (x2, y2 + 15), self.drawColor, cv2.FILLED)
                if y1 < head:
                    index = int(np.clip(x1 / w * len(PALETTE), 0, len(PALETTE) - 1))
                    self.drawColor = PALETTE[index]
            elif fingers[1:] == [1, 0, 0, 0]:      # рисование
                cv2.circle(new_img, (x1, y1), 15, self.drawColor, cv2.FILLED)
                if self.xp == 0 and self.yp == 0:
                    self.xp, self.yp = x1, y1
                thickness = int((40 if self.drawColor == ERASER else 15) * max(scale, 0.5))
                if y1 > top:    # на палитру и панель не рисуем
                    cv2.line(new_img, (self.xp, self.yp), (x1, y1), self.drawColor, thickness)
                    cv2.line(self.imgCanvas, (self.xp, self.yp), (x1, y1), self.drawColor, thickness)
                self.xp, self.yp = x1, y1
            else:
                self.xp, self.yp = 0, 0
        else:
            self.xp, self.yp = 0, 0

        # Накладываем холст на кадр: где на холсте что-то нарисовано, кадр заменяется рисунком
        imgGray = cv2.cvtColor(self.imgCanvas, cv2.COLOR_BGR2GRAY)
        _, imgInv = cv2.threshold(imgGray, 50, 255, cv2.THRESH_BINARY_INV)
        imgInv = cv2.cvtColor(imgInv, cv2.COLOR_GRAY2BGR)
        new_img = cv2.bitwise_and(new_img, imgInv)
        new_img = cv2.bitwise_or(new_img, self.imgCanvas)

        self.draw_all(new_img)
        progress = self.tracker.progress(now)
        self._draw_button(new_img, "back", rects["back"], "← Назад", progress if target == "back" else 0)
        self._draw_button(new_img, "clear", rects["clear"], "Очистить", progress if target == "clear" else 0)
        hint = "Палец - рисовать, два пальца у цветов - цвет, «Назад» - выход"
        bar = (0, h - max(int(h * 0.06), 24), w, max(int(h * 0.06), 24))
        fill_rect(new_img, bar, (30, 30, 30), 0.6)
        put_text(new_img, hint, bar, max(int(h * 0.03), 11), (255, 255, 255), align="left")
        return new_img
