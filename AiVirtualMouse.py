"""Распределительный модуль (диплом, раздел 3.3): жест -> действие, машина состояний.

Состояние хранится в old_combo, как в дипломе. Из каждого состояния можно перейти только
в некоторые другие (схема на рисунке 18), поэтому случайный жест не запустит чужую функцию:

    basic (раскрытая ладонь) - базовое состояние;
    move_mouse -> left_click / right_click / took (перетаскивание);
    scroll, volume_control, ai_painter (графический редактор).

Виртуальная клавиатура - не состояние, а окно поверх рабочего стола: жест «три пальца» просит окно
программы её показать (on_request), а рука при этом продолжает двигать курсор и нажимать клавиши.
Клавиатуру и редактор можно открыть из любого состояния, кроме «взятого» перетаскиваемого объекта.

Пальцы записываются как [большой, указательный, средний, безымянный, мизинец], 1 - поднят.
Положение большого пальца по камере определяется хуже остальных, поэтому там, где он не нужен
для отличия одного жеста от другого, он не учитывается (в таблице GESTURES стоит None).
Все выдержки времени заданы в секундах, а не в кадрах: на слабом компьютере камера даёт 10 кадров/с вместо 30.
"""
import time

import cv2

from AiPainter import AiPainter
from GestureFunction import CollectionGesture
from SystemInput import SystemInput
from WorkingHand import handDetector

HUD_COLOR = (255, 51, 102)   # BGR, сине-фиолетовый как у надписи «13 - basic» на рисунках диплома

# Жесты. None - положение этого пальца не важно.
GESTURES = {
    "palm":   [1, 1, 1, 1, 1],        # базовое состояние
    "open4":  [None, 1, 1, 1, 1],     # четыре пальца: выход из рисования
    "four":   [0, 1, 1, 1, 1],        # прокрутка страницы
    "peace":  [None, 1, 1, 0, 0],     # движение мыши, двойной клик
    "middle": [None, 0, 1, 0, 0],     # левая кнопка мыши
    "index":  [None, 1, 0, 0, 0],     # правая кнопка мыши
    "fist":   [None, 0, 0, 0, 0],     # «взять» (перетаскивание)
    "gun":    [1, 1, 0, 0, 0],        # громкость
    "three":  [None, 1, 1, 1, 0],     # виртуальная клавиатура
    "rock":   [None, 1, 0, 0, 1],     # графический редактор
}
# Сколько секунд жест должен продержаться, чтобы сработать (сверх того, что он уже принят без «мигания»)
HOLD = {"palm": 0.0, "open4": 0.5, "four": 0.4, "peace": 0.0, "middle": 0.15, "index": 0.15,
        "fist": 0.4, "gun": 0.3, "three": 0.6, "rock": 0.6}

MOVABLE = ("basic", "move_mouse", "left_click", "right_click", "took", "scroll", "volume_control")
NEUTRAL = ("basic", "scroll", "volume_control")
OPENABLE = ("basic", "move_mouse", "left_click", "right_click", "scroll", "volume_control")


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

    LOST_SECONDS = 0.5    # столько секунд без руки, и перетаскивание отпускается
    RESET_SECONDS = 0.15  # без руки дольше - жесты распознаются заново
    REQUEST_PAUSE = 2.0   # секунд между двумя просьбами показать клавиатуру

    def __init__(self, detector=None, os_input=None, mirror=True, clock=time.monotonic, on_request=None):
        self.os = os_input or SystemInput()
        self.detector = detector or handDetector(maxHands=1)
        self.gesture = CollectionGesture(os_input=self.os, clock=clock)
        self.painter = AiPainter(clock=clock)
        self.stabilizer = GestureStabilizer()
        self.mirror = mirror              # зеркальное изображение: рука вправо - курсор вправо
        self.clock = clock
        self.on_request = on_request      # функция(имя): окну нужно показать «keyboard»
        self.keyboard_visible = False     # окно клавиатуры сейчас на экране (сообщает окно программы)
        self.old_combo = "basic"
        self.basic_len = None
        self.fingers = None
        self._since = {name: None for name in GESTURES}
        self._lost_since = None
        self._wait_release = False   # после выхода из рисования жест «четыре пальца» надо сначала отпустить
        self._next_request = 0.0
        self._flash_label = ("", 0.0)
        self._pending = []           # команды из окна программы, выполняются в потоке жестов
        self._fps = 0.0
        self._last_time = None

    # --- управление из окна ----------------------------------------------
    def post(self, command, value=None):
        """Команда из другого потока (кнопки окна): 'painter' True/False, 'keyboard_visible' True/False, 'reach' 0.05..0.4."""
        self._pending.append((command, value))

    def _apply_pending(self):
        while self._pending:
            command, value = self._pending.pop(0)
            if command == "painter":
                if value:
                    self._enter("ai_painter")
                elif self.old_combo == "ai_painter":
                    self._enter("basic")
            elif command == "keyboard_visible":
                self.keyboard_visible = bool(value)
            elif command == "reach":
                self.gesture.frameR = min(max(float(value), 0.03), 0.45)

    def set_enabled(self, enabled):
        """Пауза: жесты видны на экране, но компьютером не управляют."""
        self.os.enabled = enabled
        if not enabled:
            self.gesture.drop()

    def shutdown(self):
        self.gesture.drop()
        self.detector.close()

    def _flash(self, label, now):
        """Показать в углу кадра, что сработало (двойной клик и правый клик сгибом состояния не меняют)."""
        self._flash_label = (label, now + 0.8)

    def _request(self, name):
        if self.on_request:
            self.on_request(name)

    def _enter(self, state):
        if state == self.old_combo:
            return
        if self.old_combo == "took":
            self.gesture.drop()
        if self.old_combo == "scroll":
            self.gesture.scroll_reset()
        if state == "ai_painter" or self.old_combo == "ai_painter":
            self.painter.reset()
        if state == "move_mouse":
            self.gesture.disarm_double_click()   # двойной клик только после того, как пальцы были разведены
            self.gesture.disarm_bend_click()     # правый клик сгибом - только после того, как палец был прямым
        self.old_combo = state

    # --- кадр -------------------------------------------------------------
    def process(self, img):
        self._apply_pending()
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
            self._lost_since = None
            fingers = self.stabilizer.update(self.detector.halfFingersUp())
        else:
            lmList = []
            if self._lost_since is None:
                self._lost_since = now
            lost = now - self._lost_since
            if lost >= self.RESET_SECONDS:
                self.stabilizer.reset()
            if lost >= self.LOST_SECONDS and self.old_combo == "took":
                self._enter("basic")
        self.fingers = fingers
        for name in GESTURES:
            if match(fingers, name):
                if self._since[name] is None:
                    self._since[name] = now
            else:
                self._since[name] = None

        img = self._step(img, lmList, fingers, now)
        self._hud(img, now)
        return img

    def _held(self, name, now):
        since = self._since[name]
        return since is not None and now - since >= HOLD[name]

    def _step(self, img, lmList, f, now):
        st = self.old_combo
        d = self.detector

        # --- графический редактор: у него своя отрисовка; выход - «Назад» или четыре пальца вверх
        if st == "ai_painter":
            if lmList and self._held("open4", now):
                self._enter("basic")
                self._wait_release = True
                return img
            img = self.painter.main(img, lmList, f, now)
            if self.painter.exit_requested:
                self.painter.exit_requested = False
                self._enter("basic")
            return img

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
        elif st in OPENABLE and not self.keyboard_visible and self._held("three", now) and now >= self._next_request:
            self.keyboard_visible = True         # окно подтвердит или сбросит это сообщением 'keyboard_visible'
            self._next_request = now + self.REQUEST_PAUSE
            self._request("keyboard")
        elif st in OPENABLE and self._held("rock", now):
            self._enter("ai_painter")
        elif st in ("basic", "volume_control") and self._held("gun", now):
            self._enter("volume_control")
            self.gesture.volume_control(img, lmList)
        elif st in NEUTRAL and self._held("four", now) and match(f, "four"):
            self._enter("scroll")
            self.gesture.hscroll(img, d)
        elif st == "scroll" and match(f, "four"):
            self.gesture.hscroll(img, d)
        elif match(f, "peace") and st in MOVABLE and self._finger_ok(img):
            self._enter("move_mouse")
            # пока указательный согнут (правый клик) или пальцы сведены (двойной клик), курсор стоит на месте
            still = self.gesture.index_bent(d) or self.gesture.fingers_closed(d)
            self.gesture.moveMouse(img, d, x1, y1, move=not still)
            if self.gesture.index_bend_click(d):
                self._flash("right_click", now)
            elif self.gesture.double_click(img, d, x1, y1):
                self._flash("double_click", now)
        elif st == "move_mouse" and self._held("middle", now) and match(f, "middle"):
            self.gesture.left_click()
            self._enter("left_click")
        elif st == "move_mouse" and self._held("index", now) and match(f, "index"):
            self.gesture.right_click()
            self._enter("right_click")
        elif st == "move_mouse" and self._held("fist", now):
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

    def _hud(self, img, now):
        scale = 3 * max(img.shape[1] / 1280.0, 0.6)
        label = self._flash_label[0] if now < self._flash_label[1] else self.old_combo
        cv2.putText(img, "%d - %s" % (int(self._fps), label), (5, int(13 * scale)),
                    cv2.FONT_HERSHEY_PLAIN, scale, HUD_COLOR, 2)


def main(cam_index=0):
    """Запуск без окна программы: обычное окно OpenCV, выход - клавиша q. Удобно для проверки камеры."""
    cap = cv2.VideoCapture(cam_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
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
