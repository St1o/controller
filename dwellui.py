"""Окна поверх рабочего стола, которыми управляют «наведи и подожди».

DwellWindow - окно без рамки поверх всех окон, которое НЕ забирает фокус (как экранная клавиатура Windows):
щёлкнуть по нему или навести курсор можно, а текстовый курсор в другой программе остаётся на месте,
поэтому напечатанное попадает именно туда. KeyWidget - кнопка с индикатором: пока курсор стоит на ней,
она заполняется, и когда заполнится, срабатывает. Обычный щелчок мышью срабатывает сразу.
"""
import time

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, pyqtSignal

from overlay import DwellTracker

COLORS = {          # kind -> (обычный, под курсором)
    "char": ("#8a1f8a", "#b02db0"),
    "ctrl": ("#4a4a8a", "#6666b0"),
    "back": ("#b03a2e", "#d0493a"),
    "tool": ("#2e6f73", "#3a8f94"),
}
FILL = "#00c853"    # цвет индикатора и вспышки нажатия


class KeyWidget(QtWidgets.QWidget):
    pressed = pyqtSignal(object)     # щелчок мышью

    def __init__(self, text, kind="char", parent=None):
        super().__init__(parent)
        self.text = text
        self.kind = kind
        self.progress = 0.0
        self.flash_until = 0.0
        self.hover = False
        self.setFocusPolicy(Qt.NoFocus)
        self.setAttribute(Qt.WA_Hover, True)

    def set_text(self, text):
        if text != self.text:
            self.text = text
            self.update()

    def set_progress(self, value):
        if abs(value - self.progress) > 0.01 or (value == 0.0) != (self.progress == 0.0):
            self.progress = value
            self.update()

    def flash(self, seconds=0.25):
        self.flash_until = time.monotonic() + seconds
        self.update()
        QtCore.QTimer.singleShot(int(seconds * 1000) + 40, self.update)

    def enterEvent(self, event):
        self.hover = True
        self.update()

    def leaveEvent(self, event):
        self.hover = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.pressed.emit(self)

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = QtCore.QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        normal, hot = COLORS.get(self.kind, COLORS["char"])
        flashing = time.monotonic() < self.flash_until
        path = QtGui.QPainterPath()
        path.addRoundedRect(rect, 9, 9)
        p.fillPath(path, QtGui.QColor(FILL if flashing else (hot if self.hover or self.progress > 0 else normal)))
        if self.progress > 0 and not flashing:       # индикатор: заливка снизу вверх
            p.save()
            p.setClipPath(path)
            height = rect.height() * self.progress
            p.fillRect(QtCore.QRectF(rect.left(), rect.bottom() - height, rect.width(), height), QtGui.QColor(FILL))
            p.restore()
        font = p.font()
        font.setBold(True)
        size = max(int(self.height() * (0.34 if len(self.text) > 3 else 0.46)), 10)
        font.setPixelSize(size)
        while size > 8 and QtGui.QFontMetrics(font).horizontalAdvance(self.text) > self.width() - 10:
            size -= 1                  # надпись не влезает в кнопку - уменьшаем шрифт
            font.setPixelSize(size)
        p.setFont(font)
        p.setPen(QtGui.QColor("#ffffff"))
        p.drawText(self.rect(), Qt.AlignCenter, self.text)


class DwellWindow(QtWidgets.QWidget):
    TITLE_HEIGHT = 48        # верхняя полоса, за которую окно можно перетащить

    def __init__(self, dwell=0.8, cursor_pos=None, clock=time.monotonic, dwell_allowed=None):
        flags = Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus
        super().__init__(None, flags)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.clock = clock
        self.cursor_pos = cursor_pos or QtGui.QCursor.pos      # подставляется в тестах
        self.dwell_allowed = dwell_allowed or (lambda: True)   # False - на паузе: только обычные щелчки мышью
        self.tracker = DwellTracker(dwell)
        self._drag = None
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self.poll)
        self._timer.start()

    # --- нажатие задержкой -------------------------------------------------
    def keys(self):
        return self.findChildren(KeyWidget)

    def key_at(self, global_pos):
        local = self.mapFromGlobal(global_pos)
        if not self.rect().contains(local):
            return None
        child = self.childAt(local)
        while child is not None and not isinstance(child, KeyWidget):
            child = child.parentWidget()
        return child

    def poll(self):
        """Вызывается по таймеру: что под курсором, сколько он там стоит, не пора ли нажимать."""
        if not self.isVisible():
            return
        now = self.clock()
        if not self.dwell_allowed():
            self.tracker.reset(ignore_current=True)
            for key in self.keys():
                key.set_progress(0.0)
            return
        key = self.key_at(self.cursor_pos())
        fired = self.tracker.update(key, now)
        progress = self.tracker.progress(now)
        for k in self.keys():
            k.set_progress(progress if k is self.tracker.target else 0.0)
        if fired is not None:
            fired.flash()
            self.on_key(fired)

    def on_key(self, key):
        """Переопределяется в наследниках: кнопка нажата (задержкой или щелчком)."""

    def connect_clicks(self):
        for key in self.keys():
            key.pressed.connect(self._clicked)

    def _clicked(self, key):
        key.flash()
        self.on_key(key)

    def showEvent(self, event):
        # то, что окажется под курсором в момент появления окна, сработает только после того, как его покинут
        self.tracker.reset(ignore_current=True)
        super().showEvent(event)

    # --- перетаскивание за верхнюю полосу -----------------------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.pos().y() < self.TITLE_HEIGHT:
            self._drag = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag)

    def mouseReleaseEvent(self, event):
        self._drag = None
