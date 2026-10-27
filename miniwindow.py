"""Мини-окно: появляется, когда главное окно свёрнуто, и остаётся поверх всех окон.

В нём кадр с камеры (видно, что распознаётся рука и какое состояние) и три кнопки: пауза, клавиатура, развернуть.
Окно не забирает фокус и не мешает работать с рабочим столом; его можно перетащить за верхнюю полосу.
"""
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, pyqtSignal

from dwellui import DwellWindow, KeyWidget

STYLE = """
#mini { background-color: #1f1f2b; border: 2px solid #5f9ea0; border-radius: 10px; }
#mini_title { color: #ffffff; font-size: 11pt; font-weight: bold; background: transparent; }
#mini_video { background-color: #000000; color: #a8b3c2; }
"""
VIDEO_SIZE = (288, 216)      # 4:3, как кадр камеры


class MiniWindow(DwellWindow):
    restore_requested = pyqtSignal()
    pause_toggled = pyqtSignal(bool)       # True - поставили на паузу
    keyboard_requested = pyqtSignal()

    TITLE_HEIGHT = 30

    def __init__(self, dwell=1.0, **kwargs):
        super().__init__(dwell=dwell, **kwargs)
        self.setObjectName("mini")
        self.setStyleSheet(STYLE)
        self.paused = False
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 4, 8, 8)
        root.setSpacing(5)
        self.title = QtWidgets.QLabel("VMouse: жесты включены")
        self.title.setObjectName("mini_title")
        self.title.setFixedHeight(self.TITLE_HEIGHT - 6)
        root.addWidget(self.title)
        self.video = QtWidgets.QLabel("Камера запускается...")
        self.video.setObjectName("mini_video")
        self.video.setAlignment(Qt.AlignCenter)
        self.video.setFixedSize(*VIDEO_SIZE)
        root.addWidget(self.video)
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(5)
        self.pause_key = KeyWidget("⏸ Пауза", "tool")
        self.keyboard_key = KeyWidget("⌨ Клавиатура", "tool")
        self.restore_key = KeyWidget("⤢ Развернуть", "tool")
        for key in (self.pause_key, self.keyboard_key, self.restore_key):
            key.setFixedHeight(40)
            key.setMinimumWidth(90)
            row.addWidget(key)
        root.addLayout(row)
        self.connect_clicks()
        self.adjustSize()

    def show_frame(self, image):
        pixmap = QtGui.QPixmap.fromImage(image).scaled(self.video.size(), Qt.KeepAspectRatio, Qt.FastTransformation)
        self.video.setPixmap(pixmap)

    def set_paused(self, paused):
        self.paused = paused
        self.pause_key.set_text("▶ Включить" if paused else "⏸ Пауза")
        self.title.setText("VMouse: на паузе" if paused else "VMouse: жесты включены")

    def on_key(self, key):
        if key is self.pause_key:
            self.set_paused(not self.paused)
            self.pause_toggled.emit(self.paused)
        elif key is self.keyboard_key:
            self.keyboard_requested.emit()
        elif key is self.restore_key:
            self.restore_requested.emit()

    def move_to_corner(self):
        g = QtWidgets.QApplication.primaryScreen().availableGeometry()
        self.adjustSize()
        self.move(g.right() - self.width() - 12, g.bottom() - self.height() - 12)
