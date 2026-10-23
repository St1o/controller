"""Модуль для работы с руками (диплом, раздел 3.2).

Класс handDetector находит руку в кадре, переводит точки руки в пиксели
и отвечает на вопросы «какие пальцы подняты» и «какое расстояние между точками».

Для поиска руки нужен mediapipe. У него две версии интерфейса:
  * новая (HandLandmarker, mediapipe 0.10 и выше, файл модели models/hand_landmarker.task);
  * старая (mp.solutions.hands, mediapipe до 0.10.x), на ней был написан диплом.
Выбирается та, что есть в установленном mediapipe, ничего настраивать не нужно.
"""
import math
import os
import time
import urllib.request

import cv2
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "models", "hand_landmarker.task")
MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
             "hand_landmarker/float16/latest/hand_landmarker.task")

# Пары точек, которые соединяет скелет руки (нумерация mediapipe, 21 точка)
HAND_CONNECTIONS = [
    (1, 2), (2, 3), (3, 4),                    # большой
    (5, 6), (6, 7), (7, 8),                    # указательный
    (9, 10), (10, 11), (11, 12),               # средний
    (13, 14), (14, 15), (15, 16),              # безымянный
    (17, 18), (18, 19), (19, 20),              # мизинец
    (0, 1), (0, 5), (5, 9), (9, 13), (13, 17), (0, 17),  # ладонь
]
# Цвета пальцев (BGR), как на рисунках диплома: большой синий, указательный зелёный, средний жёлтый, остальные фиолетовые
_FINGER_COLORS = {
    "thumb": (255, 128, 30),
    "index": (60, 220, 60),
    "middle": (0, 205, 255),
    "ring": (200, 70, 160),
    "pinky": (200, 70, 160),
    "palm": (230, 230, 230),
}
_JOINT_GROUP = {}
for _ids, _name in (((1, 2, 3, 4), "thumb"), ((5, 6, 7, 8), "index"), ((9, 10, 11, 12), "middle"),
                    ((13, 14, 15, 16), "ring"), ((17, 18, 19, 20), "pinky")):
    for _i in _ids:
        _JOINT_GROUP[_i] = _name


def draw_hand(img, points, dots=True):
    """Нарисовать скелет руки. points: список из 21 пары (x, y) в пикселях."""
    for a, b in HAND_CONNECTIONS:
        group = _JOINT_GROUP.get(a)
        if group is None or group != _JOINT_GROUP.get(b):
            group = "palm"  # линии ладони: запястье и основания пальцев
        cv2.line(img, tuple(int(v) for v in points[a]), tuple(int(v) for v in points[b]),
                 _FINGER_COLORS[group], 2, cv2.LINE_AA)
    if dots:
        for x, y in points:
            cv2.circle(img, (int(x), int(y)), 4, (40, 40, 235), cv2.FILLED)
    return img


def ensure_model(path=MODEL_PATH):
    """Файл модели лежит в репозитории; если его удалили, скачиваем заново."""
    if os.path.isfile(path) and os.path.getsize(path) > 1_000_000:
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".part"
    try:
        with urllib.request.urlopen(MODEL_URL, timeout=60) as resp, open(tmp, "wb") as out:
            out.write(resp.read())
        os.replace(tmp, path)
    except Exception as exc:  # noqa: BLE001 - нужна понятная ошибка, а не трассировка сети
        if os.path.exists(tmp):
            os.remove(tmp)
        raise RuntimeError(
            "Нет файла модели руки %s и скачать его не удалось (%s). "
            "Скачайте его вручную по адресу %s" % (path, exc, MODEL_URL))
    return path


class _TasksBackend:
    """Новый интерфейс mediapipe (HandLandmarker)."""
    name = "tasks"

    def __init__(self, maxHands, detectionCon, trackCon, static, model_path=None):
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision
        self._mp = mp
        self._static = static
        # Модель читаем сами и передаём байтами: путь с русскими буквами (папка пользователя) mediapipe не открывает
        with open(ensure_model(model_path or MODEL_PATH), "rb") as f:
            buffer = f.read()
        options = vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_buffer=buffer),
            running_mode=vision.RunningMode.IMAGE if static else vision.RunningMode.VIDEO,
            num_hands=maxHands,
            min_hand_detection_confidence=detectionCon,
            min_hand_presence_confidence=detectionCon,
            min_tracking_confidence=trackCon)
        self._landmarker = vision.HandLandmarker.create_from_options(options)
        self._last_ts = 0

    def detect(self, img_rgb):
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=np.ascontiguousarray(img_rgb))
        if self._static:
            result = self._landmarker.detect(image)
        else:
            ts = int(time.monotonic() * 1000)
            if ts <= self._last_ts:  # метки времени для видео обязаны расти
                ts = self._last_ts + 1
            self._last_ts = ts
            result = self._landmarker.detect_for_video(image, ts)
        return [[(p.x, p.y, p.z) for p in hand] for hand in result.hand_landmarks]

    def close(self):
        self._landmarker.close()


class _LegacyBackend:
    """Старый интерфейс mediapipe (mp.solutions.hands), как в дипломе."""
    name = "solutions"

    def __init__(self, maxHands, detectionCon, trackCon, static):
        import mediapipe as mp
        self.hands = mp.solutions.hands.Hands(static_image_mode=static, max_num_hands=maxHands,
                                              min_detection_confidence=detectionCon,
                                              min_tracking_confidence=trackCon)

    def detect(self, img_rgb):
        result = self.hands.process(img_rgb)
        if not result.multi_hand_landmarks:
            return []
        return [[(p.x, p.y, p.z) for p in hand.landmark] for hand in result.multi_hand_landmarks]

    def close(self):
        self.hands.close()


def _make_backend(maxHands, detectionCon, trackCon, static):
    try:
        from mediapipe.tasks.python import vision
        has_tasks = hasattr(vision, "HandLandmarker")
    except Exception:  # noqa: BLE001 - старый mediapipe без tasks
        has_tasks = False
    if has_tasks:
        return _TasksBackend(maxHands, detectionCon, trackCon, static)
    return _LegacyBackend(maxHands, detectionCon, trackCon, static)


class handDetector:
    # Большой палец «отведён», если его кончик дальше этого значения (в долях длины ладони)
    # от линии «запястье - основание указательного» в сторону от мизинца.
    # Два порога дают гистерезис: палец не мигает на границе.
    THUMB_OUT = -0.12
    THUMB_IN = -0.04

    def __init__(self, mode=False, maxHands=1, detectionCon=0.5, trackCon=0.5, backend=None):
        self.mode = mode
        self.maxHands = maxHands
        self.detectionCon = detectionCon
        self.trackCon = trackCon
        # backend можно подставить готовый (в тестах); обычно создаётся настоящий mediapipe
        self.backend = backend or _make_backend(maxHands, detectionCon, trackCon, mode)
        self.tipIds = [4, 8, 12, 16, 20]
        self.results = []
        self.lmList = []
        self._thumb_out = False

    # --- поиск руки -------------------------------------------------------
    def findHands(self, img, draw=True):
        """Найти руки в кадре (BGR) и при необходимости нарисовать скелет."""
        imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        self.results = self.backend.detect(imgRGB)
        if draw and self.results:
            h, w = img.shape[:2]
            for hand in self.results:
                draw_hand(img, [(p[0] * w, p[1] * h) for p in hand])
        return img

    def findPosition(self, img, handNo=0, draw=True):
        """Координаты 21 точки руки в пикселях: [[номер, x, y], ...] и рамка руки."""
        self.lmList = []
        bbox = []
        if not self.results or handNo >= len(self.results):
            return self.lmList, bbox
        h, w = img.shape[:2]
        xList, yList = [], []
        for idx, p in enumerate(self.results[handNo]):
            cx, cy = int(p[0] * w), int(p[1] * h)
            xList.append(cx)
            yList.append(cy)
            self.lmList.append([idx, cx, cy])
            if draw:
                cv2.circle(img, (cx, cy), 5, (255, 0, 255), cv2.FILLED)
        bbox = min(xList), min(yList), max(xList), max(yList)
        if draw:
            cv2.rectangle(img, (bbox[0] - 20, bbox[1] - 20), (bbox[2] + 20, bbox[3] + 20), (0, 255, 0), 2)
        return self.lmList, bbox

    # --- размеры и расстояния --------------------------------------------
    def _dist(self, a, b):
        return math.hypot(self.lmList[a][1] - self.lmList[b][1], self.lmList[a][2] - self.lmList[b][2])

    def handSize(self):
        """Размер ладони в пикселях (запястье - основание среднего пальца). Не зависит от согнутых пальцев."""
        if len(self.lmList) < 21:
            return 0.0
        return max(self._dist(0, 9), 1.0)

    def findDistance(self, p1, p2, img, draw=True):
        x1, y1 = self.lmList[p1][1], self.lmList[p1][2]
        x2, y2 = self.lmList[p2][1], self.lmList[p2][2]
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        length = int(math.hypot(x2 - x1, y2 - y1))
        if draw:
            cv2.line(img, (x1, y1), (x2, y2), (255, 0, 255), 3)
            cv2.circle(img, (x1, y1), 8, (255, 0, 255), cv2.FILLED)
            cv2.circle(img, (x2, y2), 8, (255, 0, 255), cv2.FILLED)
            cv2.circle(img, (cx, cy), 5, (0, 0, 255), cv2.FILLED)
        return length, img, [x1, y1, x2, y2, cx, cy]

    # --- какие пальцы подняты ---------------------------------------------
    def _thumb_side(self):
        """Насколько кончик большого пальца выступает за ладонь (в долях её длины).

        Меньше нуля - палец отведён в сторону, больше нуля - прижат к ладони.
        Считается относительно линии «запястье - основание указательного»
        и стороны мизинца, поэтому не зависит ни от того, правая рука или левая,
        ни от поворота руки.
        """
        w, idx, pinky, tip = self.lmList[0], self.lmList[5], self.lmList[17], self.lmList[4]

        def cross(o, a, b):
            return (a[1] - o[1]) * (b[2] - o[2]) - (a[2] - o[2]) * (b[1] - o[1])

        line = math.hypot(idx[1] - w[1], idx[2] - w[2]) or 1.0
        sign = 1.0 if cross(w, idx, pinky) >= 0 else -1.0
        return cross(w, idx, tip) / line / self.handSize() * sign

    def _fingers(self, margin):
        if len(self.lmList) < 21:
            return [0, 0, 0, 0, 0]
        side = self._thumb_side()
        if self._thumb_out:
            self._thumb_out = side < self.THUMB_IN
        else:
            self._thumb_out = side < self.THUMB_OUT
        fingers = [1 if self._thumb_out else 0]
        for i in range(1, 5):
            tip = self.tipIds[i]
            # палец поднят, если кончик дальше от запястья, чем средний сустав
            up = self._dist(tip, 0) > self._dist(tip - 2, 0) * margin
            fingers.append(1 if up else 0)
        return fingers

    def fingersUp(self):
        """[большой, указательный, средний, безымянный, мизинец]: 1 - поднят, 0 - опущен."""
        return self._fingers(1.05)

    def halfFingersUp(self):
        """То же, но палец считается поднятым и когда он поднят не до конца (гибче)."""
        return self._fingers(0.95)

    def close(self):
        try:
            self.backend.close()
        except Exception:  # noqa: BLE001 - при выходе ошибки закрытия не важны
            pass
