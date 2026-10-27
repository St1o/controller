"""Экранная клавиатура поверх рабочего стола (диплом, раздел 3.5, переработана).

Это отдельное окно без рамки: оно не забирает фокус, поэтому нажатые клавиши печатаются в ту программу,
где стоит текстовый курсор (сначала щёлкните жестом по полю ввода). Рука двигает курсор как обычно
(два пальца буквой V); чтобы нажать клавишу, подержите курсор на ней: клавиша заполняется, и символ печатается.
Защита от случайных нажатий: нужно подержать курсор на клавише около секунды, повторно клавиша срабатывает
только после того, как курсор её покинул, а на паузе и в момент появления окна нажатия задержкой выключены.
"""
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, pyqtSignal

from dwellui import DwellWindow, KeyWidget
from SystemInput import SystemInput
from webcamKeyboard import KeyboardModel, is_control

TITLE = "Виртуальная клавиатура"
HINT = "Наведите курсор на клавишу и подержите: символ напечатается там, где стоит текстовый курсор"
DWELL_CHOICES = (0.5, 0.8, 1.2, 1.8)    # секунд удержания; переключается кнопкой справа вверху
STYLE = """
#osk { background-color: #1f1f2b; border: 2px solid #5f9ea0; border-radius: 12px; }
#osk_title { color: #ffffff; font-size: 15pt; font-weight: bold; background: transparent; }
#osk_hint { color: #a8b3c2; font-size: 9pt; background: transparent; }
#osk_text { color: #ffffff; background-color: #8a1f8a; border-radius: 9px; padding: 0 12px; font-size: 17pt; font-weight: bold; }
"""


class OnScreenKeyboard(DwellWindow):
    closed = pyqtSignal()       # нажали «Назад»

    def __init__(self, os_input=None, dwell=0.8, screen_width=None, **kwargs):
        super().__init__(dwell=dwell, **kwargs)
        self.setObjectName("osk")
        self.setStyleSheet(STYLE)
        self.os = os_input or SystemInput()
        self.model = KeyboardModel(self.os)
        screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
        self.screen_rect = screen
        unit = max(min(int((screen_width or screen.width()) / 21), 80), 50)
        self.unit = unit
        self._build()
        self.connect_clicks()
        self._placed = False

    # --- построение окна -----------------------------------------------------
    def _build(self):
        unit, gap = self.unit, 6
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 12)
        root.setSpacing(6)

        bar = QtWidgets.QHBoxLayout()
        self.back_key = KeyWidget("← Назад", "back")
        self.back_key.setFixedSize(unit * 2, 44)
        title = QtWidgets.QLabel(TITLE)
        title.setObjectName("osk_title")
        title.setAlignment(Qt.AlignCenter)
        self.dwell_key = KeyWidget("", "tool")
        self.dwell_key.setFixedSize(unit * 2, 44)
        self._show_dwell()
        bar.addWidget(self.back_key)
        bar.addWidget(title, 1)
        bar.addWidget(self.dwell_key)
        root.addLayout(bar)

        hint = QtWidgets.QLabel(HINT)
        hint.setObjectName("osk_hint")
        hint.setAlignment(Qt.AlignCenter)
        root.addWidget(hint)

        grid = QtWidgets.QGridLayout()
        grid.setSpacing(gap)
        self.rows = []
        for r, row in enumerate(self.model.keys()):
            widgets = []
            col = 0
            for c, label in enumerate(row):
                span = 1
                if r == len(self.model.keys()) - 1 and c == 0:
                    span = 7                    # пробел занимает семь клеток нижнего ряда
                key = KeyWidget(self._label(label), "ctrl" if is_control(label) else "char")
                key.setMinimumSize(unit, int(unit * 0.85))
                key.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
                grid.addWidget(key, r, col, 1, span)
                widgets.append(key)
                col += span
            self.rows.append(widgets)
        for c in range(12):
            grid.setColumnStretch(c, 1)
        root.addLayout(grid)

        self.text_label = QtWidgets.QLabel("")
        self.text_label.setObjectName("osk_text")
        self.text_label.setFixedHeight(int(unit * 0.85))
        root.addWidget(self.text_label)
        self.setFixedWidth(12 * unit + 11 * gap + 24)
        self.adjustSize()
        self.refresh()

    @staticmethod
    def _label(text):
        return "␣" if text == " " else text      # пробел подписан знаком пробела

    def _show_dwell(self):
        self.dwell_key.set_text("⏱ %s с" % ("%.1f" % self.tracker.seconds).replace(".", ","))

    # --- обновление ------------------------------------------------------------
    def refresh(self):
        """Подписи клавиш по языку и регистру и строка с напечатанным."""
        for widgets, row in zip(self.rows, self.model.keys()):
            for key, label in zip(widgets, row):
                key.set_text(self._label(label))
        metrics = QtGui.QFontMetrics(self.text_label.font())
        text = self.model.finalText.replace("\n", " ")
        width = max(self.text_label.width() - 40, 100)
        self.text_label.setText(metrics.elidedText(text, Qt.ElideLeft, width))

    def on_key(self, key):
        if key is self.back_key:
            self.hide_keyboard()
            return
        if key is self.dwell_key:
            index = (DWELL_CHOICES.index(self.tracker.seconds) + 1) % len(DWELL_CHOICES) \
                if self.tracker.seconds in DWELL_CHOICES else 1
            self.tracker.seconds = DWELL_CHOICES[index]
            self._show_dwell()
            return
        for r, widgets in enumerate(self.rows):
            if key in widgets:
                label = self.model.keys()[r][widgets.index(key)]
                self.model.press(label)
                self.refresh()
                return

    # --- показать и спрятать -------------------------------------------------------
    def show_keyboard(self):
        if not self._placed:     # первый раз: по центру внизу экрана; потом окно остаётся там, куда его перетащили
            g = self.screen_rect
            self.adjustSize()
            self.move(g.left() + (g.width() - self.width()) // 2, g.bottom() - self.height() - 8)
            self._placed = True
        self.show()

    def hide_keyboard(self):
        self.hide()
        self.closed.emit()
