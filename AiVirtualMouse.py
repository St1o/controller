"""Распределительный модуль (диплом, раздел 3.3): жест -> действие, машина состояний.

Состояние хранится в old_combo, как в дипломе. Из каждого состояния можно перейти только
в некоторые другие (схема на рисунке 18), поэтому случайный жест не запустит чужую функцию:

    basic (раскрытая ладонь) - базовое состояние, из него идут все остальные;
    move_mouse -> left_click / right_click / took (перетаскивание);
    scroll, volume_control, ai_keyboard (виртуальная клавиатура), ai_painter (рисование).

Пальцы записываются как [большой, указательный, средний, безымянный, мизинец], 1 - поднят.
Положение большого пальца по камере определяется хуже остальных, поэтому там, где он не нужен
для отличия одного жеста от другого, он не учитывается (в таблице GESTURES стоит None).
"""
import time

import cv2

from AiPainter import AiPainter
from GestureFunction import CollectionGesture
from SystemInput import SystemInput
from WorkingHand import handDetector
from webcamKeyboard import VirtualKeyboard

HUD_COLOR = (255, 51, 102)   # BGR, сине-фиолетовый как у надписи «13 - basic» на рисунках диплома

# Жесты. None - положение этого пальца не важно.
GESTURES = {
    "palm":   [1, 1, 1, 1, 1],        # базовое состояние
    "open4":  [None, 1, 1, 1, 1],     # четыре пальца: выход из клавиатуры и рисования
    "four":   [0, 1, 1, 1, 1],        # прокрутка страницы
    "peace":  [None, 1, 1, 0, 0],     # движение мыши, двойной клик
    "middle": [None, 0, 1, 0, 0],     # левая кнопка мыши
    "index":  [None, 1, 0, 0, 0],     # правая кнопка мыши
    "fist":   [None, 0, 0, 0, 0],     # «взять» (перетаскивание)
    "gun":    [1, 1, 0, 0, 0],        # громкость
    "three":  [None, 1, 1, 1, 0],     # виртуальная клавиатура
    "rock":   [None, 1, 0, 0, 1],     # графический редактор
}
# Сколько кадров подряд жест должен продержаться, чтобы сработать (при 30 кадрах/с кадр - 33 мс)
HOLD = {"palm": 1, "open4": 10, "four": 8, "peace": 1, "middle": 3, "index": 3,
        "fist": 8, "gun": 6, "three": 8, "rock": 8}

MOVABLE = ("basic", "move_mouse", "left_click", "right_click", "took", "scroll", "volume_control")
NEUTRAL = ("basic", "scroll", "volume_control")
SPECIAL = ("ai_keyboard", "ai_painter")


def match(fingers, name):
    """Подходит ли набор пальцев под жест из таблицы GESTURES."""
    return fingers is not None and all(p is None or p == f for p, f in zip(GESTURES[name], fingers))


class GestureStabilizer:
    """Убирает мигание: жест принимается, когда четыре пальца не меняются несколько кадров подряд,
    а большой палец (самый неустойчивый) решается голосованием последних кадров."""

    def __init__(self, frames=3, thumb_frames=7):
        self.frames = frames
        self.thumb_frames = thumb_frames
        self.reset()

    def reset(self):
        self._candidate = None
        self._count = 0
        self._stable = None
        self._thumbs = []

    def update(self, fingers):
        four = tuple(fingers[1:])
        if four == self._candidate:
            self._count += 1
        else:
            self._candidate, self._count = four, 1
        if self._count >= self.frames:
            self._stable = four
        self._thumbs = (self._thumbs + [fingers[0]])[-self.thumb_frames:]
        if self._stable is None:
            return None
        return [1 if sum(self._thumbs) * 2 > len(self._thumbs) else 0] + list(self._stable)


class VirtualMouse:
    """Один экземпляр на программу. process(кадр) -> кадр с подписями, действия выполняются в ОС."""

    LOST_FRAMES = 15      # столько кадров без руки, и перетаскивание отпускается (полсекунды)
    RESET_FRAMES = 5      # без руки дольше - жесты распознаются заново

    def __init__(self, detector=None, os_input=None, mirror=True, clock=time.monotonic):
        self.os = os_input or SystemInput()
        self.detector = detector or handDetector(maxHands=1)
        self.gesture = CollectionGesture(os_input=self.os, clock=clock)
        self.keyboard = VirtualKeyboard(os_input=self.os, clock=clock)
        self.painter = AiPainter()
        self.stabilizer = GestureStabilizer()
        self.mirror = mirror              # зеркальное изображение: рука вправо - курсор вправо
        self.clock = clock
        self.old_combo = "basic"
        self.basic_len = None
        self.counts = {name: 0 for name in GESTURES}
        self.fingers = None
        self._lost = 0
        self._wait_release = False   # после выхода из клавиатуры/рисования жест «четыре пальца» надо сначала отпустить
        self._fps = 0.0
        self._last_time = None

    # --- управление -------------------------------------------------------
    def set_enabled(self, enabled):
        """Пауза: жесты видны на экране, но компьютером не управляют."""
        self.os.enabled = enabled
        if not enabled:
            self.gesture.drop()

    def shutdown(self):
        self.gesture.drop()
        self.detector.close()

    def _enter(self, state):
        if state == self.old_combo:
            return
        if self.old_combo == "took":
            self.gesture.drop()
        if self.old_combo == "scroll":
            self.gesture.scroll_reset()
        if self.old_combo == "ai_keyboard":
            self.keyboard.reset()
        if self.old_combo == "ai_painter":
            self.painter.reset()
        if state == "move_mouse":
            self.gesture.disarm_double_click()   # двойной клик только после того, как пальцы были разведены
        self.old_combo = state

    # --- кадр -------------------------------------------------------------
    def process(self, img):
        if self.mirror:
            img = cv2.flip(img, 1)
        now = self.clock()
        if self._last_time is not None and now > self._last_time:
            fps = 1.0 / (now - self._last_time)
            self._fps = fps if self._fps == 0 else self._fps * 0.9 + fps * 0.1
        self._last_time = now

        img = self.detector.findHands(img, draw=True)
        lmList, _ = self.detector.findPosition(img, draw=False)
        fingers = None
        if len(lmList) >= 21:
            self._lost = 0
            fingers = self.stabilizer.update(self.detector.halfFingersUp())
        else:
            lmList = []
            self._lost += 1
            if self._lost == self.RESET_FRAMES:
                self.stabilizer.reset()
            if self._lost == self.LOST_FRAMES and self.old_combo == "took":
                self._enter("basic")
        self.fingers = fingers
        for name in GESTURES:
            self.counts[name] = self.counts[name] + 1 if match(fingers, name) else 0

        img = self._step(img, lmList, fingers)
        self._hud(img)
        return img

    def _held(self, name):
        return self.counts[name] >= HOLD[name]

    def _step(self, img, lmList, f):
        st = self.old_combo
        d = self.detector

        # --- особые состояния: у них своя отрисовка, выход - четыре пальца вверх
        if st in SPECIAL:
            if lmList and self._held("open4"):
                self._enter("basic")
                self._wait_release = True
                return img
            if st == "ai_keyboard":
                return self.keyboard.main(img, lmList, d)
            return self.painter.main(img, lmList, f)

        if not lmList or f is None:
            return img
        if self._wait_release:
            if match(f, "open4"):
                return img
            self._wait_release = False

        x1, y1 = lmList[9][1], lmList[9][2]     # центр ладони: не смещается, когда пальцы сгибаются для клика

        if match(f, "palm"):                     # базовое состояние, запоминаем длину пальца
            self._enter("basic")
            self.basic_len = self.gesture.basic(img, d)
        elif st in ("basic", "volume_control") and self._held("gun"):
            self._enter("volume_control")
            self.gesture.volume_control(img, lmList)
        elif st in NEUTRAL and self._held("four") and match(f, "four"):
            self._enter("scroll")
            self.gesture.hscroll(img, y1)
        elif st == "scroll" and match(f, "four"):
            self.gesture.hscroll(img, y1)
        elif st in NEUTRAL and self._held("three"):
            self._enter("ai_keyboard")
        elif st in NEUTRAL and self._held("rock"):
            self._enter("ai_painter")
        elif match(f, "peace") and st in MOVABLE and self._finger_ok(img):
            self._enter("move_mouse")
            if not self.gesture.fingers_closed(d):
                self.gesture.moveMouse(img, d, x1, y1)
            self.gesture.double_click(img, d, x1, y1)
        elif st == "move_mouse" and self._held("middle") and match(f, "middle"):
            self.gesture.left_click()
            self._enter("left_click")
        elif st == "move_mouse" and self._held("index") and match(f, "index"):
            self.gesture.right_click()
            self._enter("right_click")
        elif st == "move_mouse" and self._held("fist"):
            self.gesture.drag_and_drop()
            self._enter("took")
            self.gesture.moveMouse(img, d, x1, y1)
        elif st == "took" and match(f, "fist"):
            self.gesture.moveMouse(img, d, x1, y1)
        return img

    def _finger_ok(self, img):
        """Рука не слишком далеко и не повёрнута: длина среднего пальца не меньше 70% от той, что была при раскрытой ладони."""
        length = self.detector.findDistance(11, 12, img, draw=False)[0]
        if self.basic_len is None:
            self.basic_len = length
        return length >= 0.7 * self.basic_len

    def _hud(self, img):
        scale = 3 * max(img.shape[1] / 1280.0, 0.6)
        cv2.putText(img, "%d - %s" % (int(self._fps), self.old_combo), (5, int(13 * scale)),
                    cv2.FONT_HERSHEY_PLAIN, scale, HUD_COLOR, 2)


def main(cam_index=0):
    """Запуск без окна программы: обычное окно OpenCV, выход - клавиша q. Удобно для проверки камеры."""
    cap = cv2.VideoCapture(cam_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    mouse = VirtualMouse()
    try:
        while True:
            success, img = cap.read()
            if not success:
                break
            cv2.imshow("Image", mouse.process(img))
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        mouse.shutdown()
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
