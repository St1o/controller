"""Простой графический редактор («особое состояние», диплом, раздел 3.6).

Два пальца (указательный и средний) - режим выбора: поднесите их к цветной полосе сверху.
Один указательный палец - рисование. Чёрный цвет работает как ластик.
"""
import cv2
import numpy as np

# Цвета полосы (BGR): красный, малиновый, оранжевый, зелёный, синий, голубой, белый, чёрный (ластик)
PALETTE = [(0, 0, 255), (255, 0, 255), (0, 102, 255), (0, 255, 0), (255, 0, 0), (255, 255, 0),
           (255, 255, 255), (0, 0, 0)]
ERASER = (0, 0, 0)


class AiPainter:
    def __init__(self):
        self.drawColor = PALETTE[0]
        self.xp, self.yp = 0, 0
        self.imgCanvas = None

    def reset(self):
        self.xp, self.yp = 0, 0

    def clear(self):
        self.imgCanvas = None
        self.reset()

    @staticmethod
    def header_height(img):
        return int(img.shape[0] * 0.14)

    def draw_all(self, img):
        """Палитра красок сверху."""
        h, w = img.shape[:2]
        head = self.header_height(img)
        step = w / len(PALETTE)
        for i, color in enumerate(PALETTE):
            cv2.rectangle(img, (int(i * step), 0), (int((i + 1) * step), head), color, cv2.FILLED)
        cv2.rectangle(img, (0, 0), (w, head), (240, 240, 240), 1)
        return img

    def color_selection(self, x1, drawColor, width):
        """Цвет по координате x указательного пальца."""
        index = int(np.clip(x1 / width * len(PALETTE), 0, len(PALETTE) - 1))
        return PALETTE[index]

    def main(self, img, lmList, fingers):
        """Один кадр редактора. fingers - [большой, указательный, средний, безымянный, мизинец]."""
        h, w = img.shape[:2]
        if self.imgCanvas is None or self.imgCanvas.shape != img.shape:
            self.imgCanvas = np.zeros(img.shape, np.uint8)
        new_img = img
        head = self.header_height(img)
        scale = w / 1280.0

        if lmList and len(lmList) >= 21 and fingers is not None:
            x1, y1 = lmList[8][1:]
            x2, y2 = lmList[12][1:]
            if fingers[1:] == [1, 1, 0, 0]:        # режим выбора
                self.reset()
                cv2.rectangle(new_img, (x1, y1 - 15), (x2, y2 + 15), self.drawColor, cv2.FILLED)
                if y1 < head:
                    self.drawColor = self.color_selection(x1, self.drawColor, w)
            elif fingers[1:] == [1, 0, 0, 0]:      # рисование
                cv2.circle(new_img, (x1, y1), 15, self.drawColor, cv2.FILLED)
                if self.xp == 0 and self.yp == 0:
                    self.xp, self.yp = x1, y1
                thickness = int((40 if self.drawColor == ERASER else 15) * max(scale, 0.5))
                if y1 > head:    # на полосу цветов не рисуем
                    cv2.line(new_img, (self.xp, self.yp), (x1, y1), self.drawColor, thickness)
                    cv2.line(self.imgCanvas, (self.xp, self.yp), (x1, y1), self.drawColor, thickness)
                self.xp, self.yp = x1, y1
            else:
                self.reset()
        else:
            self.reset()

        # Накладываем холст на кадр: где на холсте что-то нарисовано, кадр заменяется рисунком
        imgGray = cv2.cvtColor(self.imgCanvas, cv2.COLOR_BGR2GRAY)
        _, imgInv = cv2.threshold(imgGray, 50, 255, cv2.THRESH_BINARY_INV)
        imgInv = cv2.cvtColor(imgInv, cv2.COLOR_GRAY2BGR)
        new_img = cv2.bitwise_and(new_img, imgInv)
        new_img = cv2.bitwise_or(new_img, self.imgCanvas)
        return self.draw_all(new_img)
