"""Функции жестов (диплом, раздел 3.4): движение мыши, клики, перетаскивание, прокрутка, громкость.

Класс CollectionGesture создаётся один раз в AiVirtualMouse.py. Сами методы ничего не знают
про то, какой жест показан: решение «что вызвать сейчас» принимает машина состояний.
"""
import math
import time

import cv2
import numpy as np

from overlay import fill_rect, put_text
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
    # Прокрутка по разведению четырёх пальцев (расстояние кончиков указательного и мизинца в долях ладони;
    # по скринам: вместе около 0,58, врозь около 1,09). Между порогами - покой.
    SPREAD_DOWN, SPREAD_DOWN_FAST = 0.95, 1.20     # врозь: страница вниз
    SPREAD_UP, SPREAD_UP_FAST = 0.70, 0.46         # вместе: страница вверх
    SCROLL_SLOW, SCROLL_FAST = 500, 1300           # единиц колеса в секунду (120 единиц = один щелчок)
    GAUGE_RANGE = (0.35, 1.30)                     # диапазон шкалы на кадре
    # Левый клик сгибом указательного (сумма изгибов двух суставов, градусов; по скринам: прямой около 6, согнутый около 58)
    BEND_ON, BEND_OFF, BEND_MAX = 35, 20, 110
    BEND_HOLD = 0.3             # секунд держать сгиб: быстрое складывание пальца для левого клика им не считается
    STRAIGHT_MAX = 30           # палец считается прямым, пока изгиб не больше
    BEND_REACH = 0.85           # согнутый указательный короче среднего (прямой около 0,9, по скрину согнутый около 0,66);
                                # рука, наклонённая к камере, укорачивает оба пальца сразу и сгибом не считается
    # Зона руки: поля растут с размером ладони, чтобы кончики пальцев и запястье оставались в кадре
    SIDE_PALM, TOP_PALM, BOTTOM_PALM = 0.7, 1.15, 0.9
    MIN_ZONE = 0.18             # зона не меньше этой доли кадра
    TOO_CLOSE = 0.30            # ладонь крупнее этой доли высоты кадра: просим отодвинуть руку

    SMOOTH_TIME = 0.09          # секунд: за это время курсор проходит около 63% пути до руки (не зависит от FPS)

    def __init__(self, basic_lenght_finger=50, plocX=0, plocY=0, old_vol=0,
                 os_input=None, smoothing=None, frameR=0.22, clock=time.monotonic):
        self.basic_lenght_finger = basic_lenght_finger
        self.plocX = plocX
        self.plocY = plocY
        self.old_vol = old_vol
        self.os = os_input or SystemInput()
        self.smooth_time = smoothing if smoothing is not None else self.SMOOTH_TIME   # больше - плавнее и медленнее
        self.frameR = frameR            # доля кадра по краям, которая не используется (зона руки = остальное)
        self.clock = clock
        self._last_move = None
        self.dragging = False
        self._screen = None
        self._seeded = False
        self._dc_armed = True
        self._dc_last = -1e9
        self._scroll_last = None
        self._volume = None
        self._palm = None
        self._bend_armed = True
        self._bend_since = None

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

    def hand_zone(self, w, h, palm):
        """Зона в кадре (слева, сверху, справа, снизу), по которой ходит основание ладони и которая соответствует всему экрану.

        Поля не меньше заданных ползунком, а у крупной кисти больше: чтобы, когда основание ладони у края зоны,
        кончики пальцев и запястье ещё были в кадре. Тогда любой угол экрана достижим без потери руки.
        """
        m = self.frameR
        side = max(m * w, self.SIDE_PALM * palm)
        top = max(m * h, self.TOP_PALM * palm)
        bottom = max(m * h, self.BOTTOM_PALM * palm)
        if w - 2 * side < self.MIN_ZONE * w:
            side = (w - self.MIN_ZONE * w) / 2
        if h - top - bottom < self.MIN_ZONE * h:      # очень крупная кисть: зона сжимается, но не исчезает
            half = self.MIN_ZONE * h / 2
            centre = min(max((top + h - bottom) / 2, half), h - half)
            top, bottom = centre - half, h - centre - half
        return side, top, w - side, h - bottom

    def moveMouse(self, img, detector, x1, y1, move=True):
        """Перенести положение руки в кадре на экран: курсор идёт плавно. move=False - только показать зону."""
        h, w = img.shape[:2]
        palm = detector.handSize() or (self._palm or 0.0)
        self._palm = palm if self._palm is None else self._palm * 0.9 + palm * 0.1   # плавно: рука то ближе, то дальше
        left, top, right, bottom = self.hand_zone(w, h, self._palm)
        cv2.rectangle(img, (int(left), int(top)), (int(right), int(bottom)), MAGENTA, 2)
        cv2.circle(img, (int(x1), int(y1)), 12, GREEN, cv2.FILLED)
        if self._palm > self.TOO_CLOSE * h:
            put_text(img, "Отодвиньте руку от камеры", (0, int(h * 0.9), w, int(h * 0.08)),
                     max(int(h * 0.045), 13), (60, 60, 255))
        if not move:
            return
        if not self.os.enabled:    # пауза: курсор не трогаем, а после паузы начнём с того места, где он стоит
            self._seeded = False
            return
        wScr, hScr = self.screen
        x3 = np.interp(x1, (left, right), (0, wScr))
        y3 = np.interp(y1, (top, bottom), (0, hScr))
        now = self.clock()
        if not self._seeded:   # начинаем с того места, где курсор стоит сейчас
            self.plocX, self.plocY = self.os.position()
            self._seeded = True
            self._last_move = None
        # сглаживание по времени, а не по кадрам: при 10 кадрах/с курсор не отстаёт в три раза сильнее, чем при 30
        dt = 1.0 / 30 if self._last_move is None else min(max(now - self._last_move, 0.0), 0.2)
        self._last_move = now
        alpha = 1.0 - math.exp(-dt / self.smooth_time)
        clocX = self.plocX + (x3 - self.plocX) * alpha
        clocY = self.plocY + (y3 - self.plocY) * alpha
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
        if ratio is None or self.index_bent(detector) or detector.fingerBend(2) > self.STRAIGHT_MAX:
            return False        # согнутый палец - это левый клик, а не сведение пальцев
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

    # --- левый клик сгибом указательного ---------------------------------------
    def index_bent(self, detector):
        """Указательный палец заметно согнут (идёт сгиб для левого клика): курсор в это время не двигаем."""
        return detector.fingerBend(1) > self.STRAIGHT_MAX

    def disarm_bend_click(self):
        """После перехода в движение левый клик сгибом заработает, только когда палец сначала выпрямлен."""
        self._bend_armed = False
        self._bend_since = None

    def index_bend_click(self, detector):
        """Левый клик, когда указательный согнут (средний остаётся прямым) и сгиб удерживается около 0,3 с.

        Срабатывает один раз; повторно - только после того, как палец снова выпрямлен.
        Палец, который быстро складывают, чтобы остался один средний (старый способ левого клика), сюда не попадает: слишком быстро и слишком сильно.
        """
        now = self.clock()
        bend, middle = detector.fingerBend(1), detector.fingerBend(2)
        if bend <= self.BEND_OFF:
            self._bend_armed = True
            self._bend_since = None
            return False
        shorter = detector.fingerReach(1) < self.BEND_REACH * max(detector.fingerReach(2), 1.0)
        if self.BEND_ON <= bend <= self.BEND_MAX and middle <= self.STRAIGHT_MAX and shorter and self._bend_armed:
            if self._bend_since is None:
                self._bend_since = now
            elif now - self._bend_since >= self.BEND_HOLD:
                self._bend_armed = False
                self._bend_since = None
                self.left_click()
                return True
        else:
            self._bend_since = None
        return False

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

    def hscroll(self, img, detector):
        """Прокрутка страницы по разведению четырёх пальцев: врозь - вниз, вместе - вверх, посередине - покой.

        Чем сильнее пальцы разведены или сведены, тем быстрее. На кадре внизу шкала с подписями.
        Возвращает отправленное значение (плюс - вверх, минус - вниз).
        """
        h, w = img.shape[:2]
        spread = detector.fingerSpread()
        now = self.clock()
        dt = 0.03 if self._scroll_last is None else min(now - self._scroll_last, 0.1)
        self._scroll_last = now
        amount = 0.0
        if spread >= self.SPREAD_DOWN:
            amount = -float(np.interp(spread, [self.SPREAD_DOWN, self.SPREAD_DOWN_FAST], [self.SCROLL_SLOW, self.SCROLL_FAST]))
        elif spread <= self.SPREAD_UP:
            amount = float(np.interp(-spread, [-self.SPREAD_UP, -self.SPREAD_UP_FAST], [self.SCROLL_SLOW, self.SCROLL_FAST]))
        sent = 0
        if amount:
            sent = int(amount * dt) or (1 if amount > 0 else -1)
            self.os.scroll(sent)
        self._draw_scroll_gauge(img, spread, sent)
        return sent

    def _draw_scroll_gauge(self, img, spread, sent):
        """Шкала внизу кадра: вверх | покой | вниз, и где сейчас пальцы."""
        h, w = img.shape[:2]
        lo, hi = self.GAUGE_RANGE
        x0, x1 = int(w * 0.18), int(w * 0.82)
        y0, bh = int(h * 0.80), max(int(h * 0.07), 20)

        def at(value):
            return int(x0 + (min(max(value, lo), hi) - lo) / (hi - lo) * (x1 - x0))
        fill_rect(img, (x0, y0, at(self.SPREAD_UP) - x0, bh), (220, 120, 40), 0.75)            # вверх
        fill_rect(img, (at(self.SPREAD_UP), y0, at(self.SPREAD_DOWN) - at(self.SPREAD_UP), bh), (90, 90, 90), 0.75)
        fill_rect(img, (at(self.SPREAD_DOWN), y0, x1 - at(self.SPREAD_DOWN), bh), (40, 40, 220), 0.75)  # вниз
        px = max(int(h * 0.04), 12)
        put_text(img, "ВВЕРХ (вместе)", (x0, y0 + bh, at(self.SPREAD_UP) - x0, int(px * 1.6)), px, (255, 255, 255))
        put_text(img, "стоп", (at(self.SPREAD_UP), y0 + bh, at(self.SPREAD_DOWN) - at(self.SPREAD_UP), int(px * 1.6)), px,
                 (255, 255, 255))
        put_text(img, "ВНИЗ (врозь)", (at(self.SPREAD_DOWN), y0 + bh, x1 - at(self.SPREAD_DOWN), int(px * 1.6)), px,
                 (255, 255, 255))
        mx = at(spread)
        cv2.rectangle(img, (mx - 3, y0 - 8), (mx + 3, y0 + bh + 8), (255, 255, 255), cv2.FILLED)
        if sent:
            cx, cy = w // 2, int(h * 0.25)
            cv2.arrowedLine(img, (cx, cy), (cx, cy - (70 if sent > 0 else -70)), RED, 6, tipLength=0.4)

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
