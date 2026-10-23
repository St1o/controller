"""Управление мышью и клавиатурой операционной системы.

Все остальные модули не обращаются к pyautogui и pynput напрямую, а используют этот класс.
Благодаря этому логику жестов можно проверять тестами без экрана (подставляется
поддельный объект с теми же методами), а библиотеки подключаются только при первом действии.
"""
import sys


class SystemInput:
    def __init__(self):
        self.enabled = True        # False - жесты распознаются, но ОС не управляется (режим «пауза»)
        self._pg = None
        self._kb = None

    # --- подключение библиотек --------------------------------------------
    @property
    def pg(self):
        if self._pg is None:
            try:
                import pyautogui
            except SystemExit:   # pyautogui завершает программу, если в Python нет tkinter
                raise RuntimeError("pyautogui не запустился: в этой установке Python нет tkinter "
                                   "(переустановите Python с галочкой «tcl/tk and IDLE»)")
            pyautogui.FAILSAFE = False   # курсор часто уходит в угол экрана, это не авария
            pyautogui.PAUSE = 0          # без задержки 0,1 с после каждого действия
            self._pg = pyautogui
        return self._pg

    @property
    def kb(self):
        if self._kb is None:
            from pynput.keyboard import Controller
            self._kb = Controller()
        return self._kb

    # --- экран и курсор ---------------------------------------------------
    def screen_size(self):
        size = self.pg.size()
        return int(size[0]), int(size[1])

    def position(self):
        pos = self.pg.position()
        return int(pos[0]), int(pos[1])

    def move(self, x, y):
        if self.enabled:
            w, h = self.screen_size()
            self.pg.moveTo(int(min(max(x, 0), w - 1)), int(min(max(y, 0), h - 1)), _pause=False)

    # --- кнопки мыши ------------------------------------------------------
    def click(self, button="left", clicks=1):
        if self.enabled:
            self.pg.click(button=button, clicks=clicks, interval=0.05, _pause=False)

    def mouse_down(self, button="left"):
        if self.enabled:
            self.pg.mouseDown(button=button, _pause=False)

    def mouse_up(self, button="left"):
        # отпускаем кнопку всегда, даже на паузе: иначе кнопка может «залипнуть»
        self.pg.mouseUp(button=button, _pause=False)

    def scroll(self, amount):
        """Прокрутка: плюс - вверх, минус - вниз. В Windows amount измеряется в 1/120 щелчка колеса."""
        if not self.enabled or not amount:
            return
        if sys.platform != "win32":  # в других системах единица - целый щелчок
            amount = int(round(amount / 25.0)) or (1 if amount > 0 else -1)
        self.pg.scroll(int(amount), _pause=False)

    # --- клавиатура -------------------------------------------------------
    def type_text(self, text):
        """Напечатать символ(ы) в окно, где стоит текстовый курсор. Работает и с русскими буквами."""
        if self.enabled and text:
            self.kb.type(text)

    def press(self, key):
        """Нажать служебную клавишу: 'enter', 'backspace'."""
        if self.enabled:
            from pynput.keyboard import Key
            k = getattr(Key, key)
            self.kb.press(k)
            self.kb.release(k)
