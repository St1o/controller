"""Окно программы VMouse (диплом, раздел 3.7).

В дипломе окно рисовалось в Qt Designer и переводилось в код командой pyuic5. Здесь оно собрано кодом,
с теми же именами элементов (webcam_btn, instruction_btn, about_btn, pushButton, stackedWidget, ...),
поэтому main.py остаётся таким же, как в дипломе.
"""
import os

import cv2
from PyQt5 import QtCore, QtGui, QtSvg, QtWidgets
from PyQt5.QtCore import Qt

import instruction
from handSketch import gesture_picture

ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icons")

TEAL = "#b8d8d8"        # шапка, меню и подвал
PAGE = "#f0f0f0"        # рабочее поле

STYLE = """
QWidget { font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif; font-size: 10pt; }
QMainWindow, #centralwidget, #top_frame, #left_menu_cont_frame, #bottom_frame { background-color: %(teal)s; }
#stackedWidget, #webcam_page, #instruction_page, #about_page, #instruction_content { background-color: %(page)s; }
QLabel { color: #000; background: transparent; }
#bottom_label, #logo_text { color: #000; }
#logo_text { font-family: "Segoe UI Light", "Segoe UI", "Helvetica Neue", Arial, sans-serif; font-size: 28pt; font-weight: 300; }
#about_label { font-size: 13pt; }
#status_label { color: #a02020; }
#stats_label { color: #707070; font-size: 9pt; }
QPushButton#pushButton { font-size: 12pt; }
QPushButton#menu_item, QPushButton#pushButton { border: none; background: transparent; color: #000; text-align: left; }
QPushButton#menu_item:hover, QPushButton#pushButton:hover { background-color: rgba(255, 255, 255, 90); }
QPushButton#menu_item:pressed, QPushButton#pushButton:pressed { background-color: rgba(255, 255, 255, 150); }
QPushButton#control_btn { border: 1px solid #8fb4b4; background: %(teal)s; padding: 4px 14px; color: #000; }
QPushButton#control_btn:hover { background: #cfe6e6; }
QPushButton#control_btn:checked { background: #e8b4b4; border-color: #b57a7a; }
QComboBox { color: #000; background: #ffffff; border: 1px solid #8fb4b4; padding: 2px 10px; min-width: 36px; }
QComboBox QAbstractItemView { background: #ffffff; color: #000; selection-background-color: %(teal)s; selection-color: #000; }
QCheckBox { color: #000; background: transparent; spacing: 6px; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #6b8f8f; background: #ffffff; }
QCheckBox::indicator:checked { background: #5f9ea0; }
QScrollArea { border: none; background: %(page)s; }
""" % {"teal": TEAL, "page": PAGE}


def svg_icon(name, size=64):
    """Иконка из assets/icons/<name>.svg в нужном размере (с запасом на экраны с масштабированием)."""
    renderer = QtSvg.QSvgRenderer(os.path.join(ICON_DIR, name + ".svg"))
    pixmap = QtGui.QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    renderer.render(painter)
    painter.end()
    return QtGui.QIcon(pixmap)


def numpy_to_pixmap(img_bgr):
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    h, w, _ = rgb.shape
    return QtGui.QPixmap.fromImage(QtGui.QImage(rgb.data, w, h, 3 * w, QtGui.QImage.Format_RGB888).copy())


class Ui_MainWindow(object):
    MENU_WIDE, MENU_NARROW = 190, 60       # ширина левого меню: развёрнуто / свёрнуто (в дипломе 160 и 60, у нас шрифт крупнее)

    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1366, 768)
        MainWindow.setMinimumSize(900, 600)
        MainWindow.setWindowTitle("VMouse")
        MainWindow.setWindowIcon(svg_icon("logo"))
        MainWindow.setStyleSheet(STYLE)

        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        root = QtWidgets.QVBoxLayout(self.centralwidget)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- шапка: кнопка «Меню» слева, логотип по центру ---------------
        self.top_frame = QtWidgets.QFrame(self.centralwidget)
        self.top_frame.setObjectName("top_frame")
        self.top_frame.setFixedHeight(74)
        top = QtWidgets.QHBoxLayout(self.top_frame)
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(0)

        self.pushButton = QtWidgets.QPushButton(self.top_frame)
        self.pushButton.setObjectName("pushButton")
        self.pushButton.setText("  Меню")
        self.pushButton.setIcon(svg_icon("menu"))
        self.pushButton.setIconSize(QtCore.QSize(36, 36))
        self.pushButton.setFixedSize(self.MENU_WIDE, 74)
        self.pushButton.setCursor(Qt.PointingHandCursor)
        top.addWidget(self.pushButton)
        top.addStretch(1)

        self.logo_icon = QtWidgets.QLabel(self.top_frame)
        self.logo_icon.setPixmap(svg_icon("logo").pixmap(56, 56))
        self.logo_icon.setFixedSize(60, 60)
        self.logo_text = QtWidgets.QLabel("VMouse", self.top_frame)
        self.logo_text.setObjectName("logo_text")
        top.addWidget(self.logo_icon)
        top.addWidget(self.logo_text)
        top.addStretch(1)
        top.addSpacing(self.MENU_WIDE)          # чтобы логотип стоял по центру окна
        root.addWidget(self.top_frame)

        # --- середина: меню слева и страницы -----------------------------
        middle = QtWidgets.QHBoxLayout()
        middle.setContentsMargins(0, 0, 0, 0)
        middle.setSpacing(0)

        self.left_menu_cont_frame = QtWidgets.QFrame(self.centralwidget)
        self.left_menu_cont_frame.setObjectName("left_menu_cont_frame")
        self.left_menu_cont_frame.setMinimumWidth(self.MENU_WIDE)
        self.left_menu_cont_frame.setMaximumWidth(self.MENU_WIDE)
        menu = QtWidgets.QVBoxLayout(self.left_menu_cont_frame)
        menu.setContentsMargins(0, 8, 0, 0)
        menu.setSpacing(2)
        self.webcam_btn = self._menu_button("webcam", "ВебКамера")
        self.instruction_btn = self._menu_button("instruction", "Инструкция")
        self.about_btn = self._menu_button("info", "Информация")
        for button in (self.webcam_btn, self.instruction_btn, self.about_btn):
            menu.addWidget(button)
        menu.addStretch(1)
        middle.addWidget(self.left_menu_cont_frame)

        self.stackedWidget = QtWidgets.QStackedWidget(self.centralwidget)
        self.stackedWidget.setObjectName("stackedWidget")
        self._setup_webcam_page()
        self._setup_instruction_page()
        self._setup_about_page()
        middle.addWidget(self.stackedWidget, 1)
        root.addLayout(middle, 1)

        # --- подвал ----------------------------------------------------------
        self.bottom_frame = QtWidgets.QFrame(self.centralwidget)
        self.bottom_frame.setObjectName("bottom_frame")
        self.bottom_frame.setFixedHeight(40)
        bottom = QtWidgets.QHBoxLayout(self.bottom_frame)
        self.bottom_label = QtWidgets.QLabel(instruction.FOOTER, self.bottom_frame)
        self.bottom_label.setObjectName("bottom_label")
        self.bottom_label.setAlignment(Qt.AlignCenter)
        bottom.addWidget(self.bottom_label)
        root.addWidget(self.bottom_frame)

        MainWindow.setCentralWidget(self.centralwidget)

    # --- части окна -------------------------------------------------------
    def _menu_button(self, icon, text):
        button = QtWidgets.QPushButton("   " + text, self.left_menu_cont_frame)
        button.setObjectName("menu_item")
        button.setIcon(svg_icon(icon))
        button.setIconSize(QtCore.QSize(34, 34))
        button.setFixedHeight(50)
        button.setCursor(Qt.PointingHandCursor)
        button.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)  # меню сворачивается, текст обрезается
        button.setStyleSheet("padding-left: 10px;")
        return button

    def _tool_button(self, text, checkable=False, tip=""):
        button = QtWidgets.QPushButton(text, self.webcam_page)
        button.setObjectName("control_btn")
        button.setCheckable(checkable)
        button.setToolTip(tip)
        return button

    def _setup_webcam_page(self):
        self.webcam_page = QtWidgets.QWidget()
        self.webcam_page.setObjectName("webcam_page")
        layout = QtWidgets.QVBoxLayout(self.webcam_page)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(6)

        bar = QtWidgets.QHBoxLayout()
        bar.setSpacing(8)
        self.camera_label = QtWidgets.QLabel("Камера:", self.webcam_page)
        self.camera_box = QtWidgets.QComboBox(self.webcam_page)
        self.camera_box.addItems(["0", "1", "2", "3"])
        self.camera_box.setToolTip("Номер камеры. Если видео не появилось, выберите другой номер.")
        self.control_btn = self._tool_button("Остановить управление", checkable=True,
                                             tip="Пауза: жесты видны на экране, но компьютером не управляют.")
        self.keyboard_btn = self._tool_button("Клавиатура", tip="Показать экранную клавиатуру поверх рабочего стола "
                                                                "(то же делает жест «три пальца»).")
        self.painter_btn = self._tool_button("Графический редактор", tip="Рисовать пальцем на картинке с камеры "
                                                                         "(то же делает жест «указательный и мизинец»).")
        self.mini_btn = self._tool_button("Свернуть в мини-окно", tip="Свернуть программу: останется маленькое окно "
                                                                      "поверх всех окон, жесты продолжают работать.")
        bar.addWidget(self.camera_label)
        bar.addWidget(self.camera_box)
        bar.addSpacing(6)
        for widget in (self.control_btn, self.keyboard_btn, self.painter_btn, self.mini_btn):
            bar.addWidget(widget)
        bar.addStretch(1)
        layout.addLayout(bar)

        bar2 = QtWidgets.QHBoxLayout()
        bar2.setSpacing(8)
        self.top_check = QtWidgets.QCheckBox("Поверх всех окон", self.webcam_page)
        self.top_check.setToolTip("Окно программы останется видно над другими программами.")
        self.reach_label = QtWidgets.QLabel("Чувствительность: 5", self.webcam_page)
        self.reach_slider = QtWidgets.QSlider(Qt.Horizontal, self.webcam_page)
        self.reach_slider.setRange(1, 10)
        self.reach_slider.setValue(5)
        self.reach_slider.setFixedWidth(150)
        self.reach_slider.setToolTip("Чем больше, тем меньше нужно двигать рукой, чтобы дойти до краёв экрана.\n"
                                     "Розовая рамка на видео - зона, в которой рука управляет курсором.")
        self.status_label = QtWidgets.QLabel("", self.webcam_page)
        self.status_label.setObjectName("status_label")
        self.status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.stats_label = QtWidgets.QLabel("", self.webcam_page)
        self.stats_label.setObjectName("stats_label")
        bar2.addWidget(self.top_check)
        bar2.addSpacing(10)
        bar2.addWidget(self.reach_label)
        bar2.addWidget(self.reach_slider)
        bar2.addStretch(1)
        bar2.addWidget(self.status_label)
        bar2.addWidget(self.stats_label)
        layout.addLayout(bar2)

        self.img_label = QtWidgets.QLabel(self.webcam_page)
        self.img_label.setObjectName("img_label")
        self.img_label.setAlignment(Qt.AlignCenter)
        self.img_label.setMinimumSize(320, 180)
        self.img_label.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Ignored)
        self.img_label.setText("Камера запустится, когда откроется эта вкладка")
        layout.addWidget(self.img_label, 1)
        self.stackedWidget.addWidget(self.webcam_page)

    def _setup_instruction_page(self):
        self.instruction_page = QtWidgets.QWidget()
        self.instruction_page.setObjectName("instruction_page")
        outer = QtWidgets.QVBoxLayout(self.instruction_page)
        outer.setContentsMargins(0, 0, 0, 0)
        self.instruction_scroll = QtWidgets.QScrollArea(self.instruction_page)
        self.instruction_scroll.setWidgetResizable(True)
        self.instruction_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QtWidgets.QWidget()
        content.setObjectName("instruction_content")
        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)
        for line in instruction.HEADER:
            label = QtWidgets.QLabel(line, content)
            label.setAlignment(Qt.AlignCenter)
            label.setWordWrap(True)
            layout.addWidget(label)
        layout.addSpacing(10)

        self.instruction_pictures = []
        for fingers, tag, title, gesture, description, vee in instruction.ENTRIES:
            row = QtWidgets.QHBoxLayout()
            row.setSpacing(14)
            picture = QtWidgets.QLabel(content)
            picture.setPixmap(numpy_to_pixmap(gesture_picture(fingers, "30 - " + tag, vee=vee)))
            picture.setFixedSize(375, 225)
            self.instruction_pictures.append(picture)
            row.addWidget(picture, 0, Qt.AlignTop)
            text = QtWidgets.QVBoxLayout()
            text.setSpacing(8)
            text.addStretch(1)
            heading = QtWidgets.QLabel("<b>%s</b>" % title, content)
            heading.setTextFormat(Qt.RichText)
            text.addWidget(heading)
            for line in ("Жест - " + gesture, "Описание - " + description):
                label = QtWidgets.QLabel(line, content)
                label.setWordWrap(True)
                text.addWidget(label)
            text.addStretch(1)
            row.addLayout(text, 1)
            layout.addLayout(row)
        layout.addStretch(1)
        self.instruction_scroll.setWidget(content)
        outer.addWidget(self.instruction_scroll)
        self.stackedWidget.addWidget(self.instruction_page)

    def _setup_about_page(self):
        self.about_page = QtWidgets.QWidget()
        self.about_page.setObjectName("about_page")
        layout = QtWidgets.QVBoxLayout(self.about_page)
        self.about_label = QtWidgets.QLabel("\n".join(instruction.ABOUT), self.about_page)
        self.about_label.setObjectName("about_label")
        self.about_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.about_label)
        self.stackedWidget.addWidget(self.about_page)
