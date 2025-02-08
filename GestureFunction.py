import numpy as np
import autopy
import cv2
import math
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from comtypes import CLSCTX_ALL


class CollectionGesture:
    def __init__(self, basic_lenght_finger=50, plocX=0, plocY=0, old_vol=0):
        self.basic_lenght_finger = basic_lenght_finger
        self.plocX = plocX
        self.plocY = plocY
        self.old_vol = old_vol

        # Инициализация работы с громкостью
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        self.volume = interface.QueryInterface(IAudioEndpointVolume)
        self.minVol, self.maxVol = self.volume.GetVolumeRange()[:2]

    def basic(self, img, detector):
        # Рассчитываем базальную длину между пальцами
        self.basic_lenght_finger = detector.findDistance(11, 12, img, draw=False)[0]
        return self.basic_lenght_finger

    def moveMouse(self, img, detector, x1, y1):
        # Преобразуем координаты пальцев для перемещения мыши
        x3 = np.interp(x1, (100, 500), (0, autopy.screen.size()[0]))
        y3 = np.interp(y1, (100, 500), (0, autopy.screen.size()[1]))

        # Логика плавного движения мыши
        clocX = self.plocX + (x3 - self.plocX) / 5
        clocY = self.plocY + (y3 - self.plocY) / 5

        autopy.mouse.move(autopy.screen.size()[0] - clocX, clocY)
        self.plocX, self.plocY = clocX, clocY

    def left_click(self):
        autopy.mouse.click()
        return "left_click"

    def right_click(self):
        autopy.mouse.click(autopy.mouse.Button.RIGHT)
        return "right_click"

    def double_click(self, img, detector, x1, y1):
        # Двойной клик с использованием расстояния между пальцами
        length, img, lineInfo = detector.findDistance(8, 12, img, draw=True)
        if length < 55:
            autopy.mouse.click()
            autopy.mouse.click()

    def volume_control(self, img, lmList):
        # Управление громкостью через расстояние между большим и указательным пальцем
        x_thumb, y_thumb = lmList[4][1], lmList[4][2]
        x_forefinger, y_forefinger = lmList[8][1], lmList[8][2]

        # Рассчитываем расстояние между пальцами
        length = math.hypot(x_forefinger - x_thumb, y_forefinger - y_thumb)
        vol = np.interp(length, [50, 280], [self.minVol, self.maxVol])

        # Устанавливаем громкость, если она изменилась
        if abs(vol - self.old_vol) > 0.8:
            self.volume.SetMasterVolumeLevel(vol, None)
            self.old_vol = vol

    def drag_and_drop(self, img, detector, x1, y1, drag_start):
        # Логика перетаскивания объектов
        if drag_start:
            autopy.mouse.move(x1, y1)
            autopy.mouse.toggle(down=True)
        else:
            autopy.mouse.toggle(down=False)

    def hscroll(self, lmList):
        # Горизонтальная прокрутка экрана
        if lmList:
            x1, y1 = lmList[8][1:]
            x2, y2 = lmList[12][1:]
            dx = x2 - x1
            if abs(dx) > 50:
                if dx < 0:
                    pyautogui.hscroll(-1)
                else:
                    pyautogui.hscroll(1)
