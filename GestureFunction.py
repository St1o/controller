"""Функции жестов (диплом, раздел 3.4): движение мыши, клики, перетаскивание, прокрутка, громкость.

Класс CollectionGesture создаётся один раз в AiVirtualMouse.py. Сами методы ничего не знают
про то, какой жест показан: решение «что вызвать сейчас» принимает машина состояний.
"""
import math
import time

import cv2
import numpy as np

from SystemInput import SystemInput

MAGENTA = (255, 0, 255)
GREEN = (0, 255, 0)
RED = (0, 0, 255)


class _Volume:
    """Громкость Windows через pycaw. Если pycaw нет или звук недоступен, жест просто отключается."""

    def __init__(self):
        self.endpoint = None
        self.error = None
        try:
            from ctypes import POINTER, cast
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            speakers = AudioUtilities.GetSpeakers()
            if hasattr(speakers, "EndpointVolume"):       # новые версии pycaw
                self.endpoint = speakers.EndpointVolume
            else:                                          # версии, на которых писался диплом
                interface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                self.endpoint = cast(interface, POINTER(IAudioEndpointVolume))
        except Exception as exc:  # noqa: BLE001 - любая причина означает «громкости нет»
            self.error = str(exc)

    def set_level(self, level):
        if self.endpoint is None:
            return False
        try:
            self.endpoint.SetMasterVolumeLevelScalar(float(min(max(level, 0.0), 1.0)), None)
            return True
        except Exception as exc:  # noqa: BLE001
            self.error = str(exc)
            self.endpoint = None
            return False


class CollectionGesture:
    # Расстояния считаются в долях размера ладони, поэтому не зависят от камеры и от удаления руки
    DOUBLE_CLICK_CLOSE = 0.50   # пальцы сведены: двойной клик
    DOUBLE_CLICK_OPEN = 0.70    # пальцы снова разведены: можно кликать опять
    DOUBLE_CLICK_PAUSE = 0.7    # секунд между двойными кликами
    SCROLL_BAND = (0.40, 0.60)  # середина кадра по высоте: здесь прокрутки нет
    SCROLL_FAR = 0.15           # дальше этого от середины прокрутка быстрая
    SCROLL_SLOW, SCROLL_FAST = 600, 1200   # единиц колеса в секунду (120 единиц = один щелчок)

    def __init__(self, basic_lenght_finger=50, plocX=0, plocY=0, old_vol=0,
                 os_input=None, smoothing=5, frameR=0.15, clock=time.monotonic):
        self.basic_lenght_finger = basic_lenght_finger
        self.plocX = plocX
        self.plocY = plocY
        self.old_vol = old_vol
        self.os = os_input or SystemInput()
        self.smoothing = smoothing      # чем больше, тем плавнее и медленнее курсор
        self.frameR = frameR            # доля кадра по краям, которая не используется
        self.clock = clock
        self.dragging = False
        self._screen = None
        self._seeded = False
        self._dc_armed = True
        self._dc_last = -1e9
        self._scroll_last = None
        self._volume = None

    # --- базовое состояние -----------------------------------------------
    def basic(self, img, detector):
        """Запомнить длину пальца при раскрытой ладони, чтобы потом понимать, не отодвинута ли рука."""
        self.basic_lenght_finger = detector.findDistance(11, 12, img, draw=False)[0]
        return self.basic_lenght_finger

    # --- движение мыши ----------------------------------------------------
    @property
    def screen(self):
        if self._screen is None:
            self._screen = self.os.screen_size()
        return self._screen

    def moveMouse(self, img, detector, x1, y1):
        """Перенести положение руки в кадре на экран: курсор идёт плавно, края кадра не используются."""
        h, w = img.shape[:2]
        fx, fy = w * self.frameR, h * self.frameR
        cv2.rectangle(img, (int(fx), int(fy)), (int(w - fx), int(h - fy)), MAGENTA, 2)
        cv2.circle(img, (int(x1), int(y1)), 12, GREEN, cv2.FILLED)
        if not self.os.enabled:    # пауза: курсор не трогаем, а после паузы начнём с того места, где он стоит
            self._seeded = False
            return
        wScr, hScr = self.screen
        x3 = np.interp(x1, (fx, w - fx), (0, wScr))
        y3 = np.interp(y1, (fy, h - fy), (0, hScr))
        if not self._seeded:   # начинаем с того места, где курсор стоит сейчас
            self.plocX, self.plocY = self.os.position()
            self._seeded = True
        clocX = self.plocX + (x3 - self.plocX) / self.smoothing
        clocY = self.plocY + (y3 - self.plocY) / self.smoothing
        if abs(clocX - self.plocX) >= 1 or abs(clocY - self.plocY) >= 1:   # дрожание меньше пикселя не передаём
            self.os.move(clocX, clocY)
            self.plocX, self.plocY = clocX, clocY

    # --- клики ------------------------------------------------------------
    def left_click(self):
        self.os.click("left")
        return "left_click"

    def right_click(self):
        self.os.click("right")
        return "right_click"

    def double_click_pose(self, detector):
        """Сведены ли указательный и средний пальцы (в долях ладони). None, если руки нет."""
        size = detector.handSize()
        if not size:
            return None
        return detector._dist(8, 12) / size

    def double_click(self, img, detector, x1, y1):
        """Двойной клик, когда указательный и средний пальцы сводятся вместе.

        Срабатывает один раз при сведении и снова только после того, как пальцы разведены
        и прошла пауза. Возвращает True, если клик сделан.
        """
        ratio = self.double_click_pose(detector)
        if ratio is None:
            return False
        length, img, line = detector.findDistance(8, 12, img, draw=True)
        done = False
        now = self.clock()
        if ratio > self.DOUBLE_CLICK_OPEN:
            self._dc_armed = True
        elif ratio < self.DOUBLE_CLICK_CLOSE and self._dc_armed and now - self._dc_last > self.DOUBLE_CLICK_PAUSE:
            self.os.click("left", clicks=2)
            self._dc_armed = False
            self._dc_last = now
            done = True
        if ratio < self.DOUBLE_CLICK_CLOSE:
            cv2.circle(img, (line[4], line[5]), 15, GREEN, cv2.FILLED)
        return done

    def disarm_double_click(self):
        """Двойной клик снова заработает только после того, как пальцы будут разведены."""
        self._dc_armed = False

    def fingers_closed(self, detector):
        """Пальцы сведены (идёт двойной клик): курсор в это время не двигаем, чтобы клик попал куда целились."""
        ratio = self.double_click_pose(detector)
        return ratio is not None and ratio < self.DOUBLE_CLICK_OPEN * 0.85

    # --- перетаскивание ---------------------------------------------------
    def drag_and_drop(self):
        """«Взять»: зажать левую кнопку. Дальше рука двигает курсор, как при обычном движении."""
        if not self.dragging:
            self.os.mouse_down("left")
            self.dragging = True

    def drop(self):
        """«Отпустить»: отжать левую кнопку. Безопасно вызывать в любое время."""
        if self.dragging:
            self.os.mouse_up("left")
            self.dragging = False

    # --- прокрутка --------------------------------------------------------
    def scroll_reset(self):
        self._scroll_last = None

    def hscroll(self, img, y1):
        """Прокрутка страницы по высоте руки: выше середины кадра вверх, ниже вниз.

        В середине (красный прямоугольник) прокрутки нет. Чем дальше рука от середины, тем быстрее.
        Возвращает отправленное значение (плюс - вверх).
        """
        h, w = img.shape[:2]
        top, bottom = h * self.SCROLL_BAND[0], h * self.SCROLL_BAND[1]
        cv2.rectangle(img, (int(w * 0.25), int(top)), (int(w * 0.75), int(bottom)), RED, 2)
        now = self.clock()
        dt = 0.03 if self._scroll_last is None else min(now - self._scroll_last, 0.1)
        self._scroll_last = now
        far = h * self.SCROLL_FAR
        amount = 0
        if y1 < top:
            amount = self.SCROLL_FAST if y1 < top - far else self.SCROLL_SLOW
        elif y1 > bottom:
            amount = -(self.SCROLL_FAST if y1 > bottom + far else self.SCROLL_SLOW)
        if amount:
            amount = int(amount * dt) or (1 if amount > 0 else -1)
            self.os.scroll(amount)
            cv2.arrowedLine(img, (w // 2, int((top + bottom) / 2)),
                            (w // 2, int((top + bottom) / 2) - (60 if amount > 0 else -60)), RED, 4, tipLength=0.4)
        return amount

    # --- громкость --------------------------------------------------------
    def volume_control(self, img, lmList):
        """Громкость по расстоянию между большим и указательным пальцами (только Windows с pycaw)."""
        x_thumb, y_thumb = lmList[4][1], lmList[4][2]
        x_forefinger, y_forefinger = lmList[8][1], lmList[8][2]
        cx_vol, cy_vol = (x_thumb + x_forefinger) // 2, (y_thumb + y_forefinger) // 2
        cv2.line(img, (x_thumb, y_thumb), (x_forefinger, y_forefinger), MAGENTA, 3)
        cv2.circle(img, (cx_vol, cy_vol), 15, GREEN, cv2.FILLED)
        palm = max(math.hypot(lmList[0][1] - lmList[9][1], lmList[0][2] - lmList[9][2]), 1.0)
        length = math.hypot(x_forefinger - x_thumb, y_forefinger - y_thumb) / palm
        vol = float(np.interp(length, [0.3, 1.8], [0.0, 1.0]))
        bar_h = img.shape[0] // 3
        cv2.rectangle(img, (30, 100), (60, 100 + bar_h), MAGENTA, 2)
        cv2.rectangle(img, (30, 100 + int(bar_h * (1 - vol))), (60, 100 + bar_h), MAGENTA, cv2.FILLED)
        if abs(vol - self.old_vol) > 0.02 and self.os.enabled:   # проверка на дрожание пальцев
            if self._volume is None:
                self._volume = _Volume()    # создаём здесь, в потоке жестов: COM привязан к потоку
            self._volume.set_level(vol)
            self.old_vol = vol
        if self._volume is not None and self._volume.endpoint is None:
            cv2.putText(img, "volume: needs Windows + pycaw", (70, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.7, MAGENTA, 2)
        return vol

    @property
    def volume_error(self):
        return self._volume.error if self._volume is not None else None
