import cv2
import numpy as np


def draw_all(img):
    return img  # Заглушка для функции отрисовки


def color_selection(x1, drawColor):
    return drawColor  # Заглушка для выбора цвета


def main(img, drawColor, lmList, fingers, xp, yp, imgCanvas):
    new_img = draw_all(img)

    if lmList:
        x1, y1 = lmList[8][1:]
        x2, y2 = lmList[12][1:]

        if fingers == [0, 1, 1, 0, 0]:
            xp, yp = 0, 0
            cv2.rectangle(new_img, (x1, y1 - 15), (x2, y2 + 15), drawColor, cv2.FILLED)
            if y1 < 100:
                drawColor = color_selection(x1, drawColor)

        if fingers == [0, 1, 0, 0, 0]:
            cv2.circle(new_img, (x1, y1), 15, drawColor, cv2.FILLED)

            if xp == 0 and yp == 0:
                xp, yp = x1, y1

            if drawColor == (0, 0, 0):
                thickness = 40
            else:
                thickness = 15

            cv2.line(new_img, (xp, yp), (x1, y1), drawColor, thickness)
            cv2.line(imgCanvas, (xp, yp), (x1, y1), drawColor, thickness)
            xp, yp = x1, y1

    imgGray = cv2.cvtColor(imgCanvas, cv2.COLOR_BGR2GRAY)
    _, imgInv = cv2.threshold(imgGray, 50, 255, cv2.THRESH_BINARY_INV)
    imgInv = cv2.cvtColor(imgInv, cv2.COLOR_GRAY2BGR)
    new_img = cv2.bitwise_and(new_img, imgInv)
    new_img = cv2.bitwise_or(new_img, imgCanvas)

    return new_img, drawColor, xp, yp