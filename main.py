"""VMouse - управление компьютером жестами (диплом, раздел 3.7). Запуск: python main.py

Окно с тремя вкладками (ВебКамера, Инструкция, Информация). Камера и распознавание жестов работают в отдельном
потоке, поэтому окно не зависает. Окно можно свернуть: тогда появится мини-окно поверх всех окон, а жесты
продолжают управлять компьютером. Экранная клавиатура - отдельное окно поверх рабочего стола.
"""
import sys
import time

import cv2
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, QThread, pyqtSignal

from goodGui import Ui_MainWindow
from SystemInput import SystemInput

wCam, hCam = 640, 480  # разрешение камеры: чем меньше кадр, тем быстрее обработка и выше FPS (рука распознаётся и так)


def open_camera(index):
    """Открыть камеру с нужным разрешением. Возвращает cv2.VideoCapture или None."""
    backends = [cv2.CAP_DSHOW, cv2.CAP_ANY] if sys.platform == "win32" else [cv2.CAP_ANY]
    for backend in backends:
        for mjpg in (True, False):   # MJPG даёт больше кадров/с почти на любой камере, но есть и такие, где он не идёт
            cap = cv2.VideoCapture(index, backend)
            if not cap.isOpened():
                cap.release()
                break
            if mjpg:
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, wCam)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, hCam)
            ok, _ = cap.read()
            if ok:
                return cap
            cap.release()
    return None


def reach_to_margin(value):
    """Чувствительность 1..10 -> доля кадра по краям, которая не используется (зона руки = остальное)."""
    return 0.05 + 0.035 * value


class VideoWorker(QThread):
    """Читает камеру, распознаёт жесты (AiVirtualMouse) и отправляет готовые кадры в окно."""
    frame_ready = pyqtSignal(QtGui.QImage)
    message = pyqtSignal(str)
    request = pyqtSignal(str)       # жест просит окно что-то показать: 'keyboard'
    stats = pyqtSignal(str)

    def __init__(self, camera=0, control=True, reach=0.225, capture_factory=open_camera, mouse_factory=None,
                 parent=None):
        super().__init__(parent)
        self.camera = camera
        self.control = control
        self.reach = reach
        self.capture_factory = capture_factory
        self.mouse_factory = mouse_factory
        self._commands = []
        self._last_error = None

    def set_control(self, enabled):
        self.control = enabled

    def post(self, command, value=None):
        """Команда потоку жестов из окна (например, 'painter', True)."""
        self._commands.append((command, value))

    def stop(self):
        self.requestInterruption()
        self.wait(8000)

    def run(self):
        mouse = None
        cap = None
        try:
            self.message.emit("Загрузка модели руки...")
            if self.mouse_factory is None:
                from AiVirtualMouse import VirtualMouse   # mediapipe импортируем здесь: окно успевает открыться
                self.mouse_factory = VirtualMouse
            mouse = self.mouse_factory()
            mouse.on_request = self.request.emit
            mouse.post("reach", self.reach)
            self.message.emit("Запуск камеры %d..." % self.camera)
            cap = self.capture_factory(self.camera)
            if cap is None:
                self.message.emit("Камера %d не найдена или занята другой программой.\n"
                                  "Выберите другой номер камеры сверху." % self.camera)
                return
            fails, applied = 0, None
            frames, t_read, t_proc, t_stats = 0, 0.0, 0.0, time.perf_counter()
            while not self.isInterruptionRequested():
                t0 = time.perf_counter()
                ok, frame = cap.read()
                t1 = time.perf_counter()
                if not ok:
                    fails += 1
                    if fails > 60:
                        self.message.emit("Камера перестала отдавать видео.")
                        return
                    self.msleep(20)
                    continue
                fails = 0
                while self._commands:
                    mouse.post(*self._commands.pop(0))
                if applied != self.control:
                    mouse.set_enabled(self.control)
                    applied = self.control
                try:
                    frame = mouse.process(frame)
                except Exception as exc:  # noqa: BLE001 - ошибка одного кадра не должна останавливать видео
                    text = "%s: %s" % (type(exc).__name__, exc)
                    if text != self._last_error:     # одну и ту же ошибку показываем один раз
                        self._last_error = text
                        print("Ошибка обработки кадра -", text, file=sys.stderr)
                        self.message.emit("Ошибка: " + text)
                    frame = cv2.flip(frame, 1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w = rgb.shape[:2]
                self.frame_ready.emit(QtGui.QImage(rgb.data, w, h, 3 * w, QtGui.QImage.Format_RGB888).copy())
                t2 = time.perf_counter()
                frames += 1
                t_read += t1 - t0
                t_proc += t2 - t1
                if t2 - t_stats >= 2.0:     # раз в две секунды: где уходит время (подсказка, если программа тормозит)
                    self.stats.emit("%d кадров/с (камера %d мс, обработка %d мс)" % (
                        frames / (t2 - t_stats), 1000 * t_read / frames, 1000 * t_proc / frames))
                    frames, t_read, t_proc, t_stats = 0, 0.0, 0.0, t2
        except Exception as exc:  # noqa: BLE001
            print("Не удалось запустить:", exc, file=sys.stderr)
            self.message.emit("Не удалось запустить распознавание жестов:\n%s" % exc)
        finally:
            if mouse is not None:
                mouse.shutdown()    # отпускает зажатую кнопку мыши и закрывает mediapipe
            if cap is not None:
                cap.release()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, capture_factory=open_camera, mouse_factory=None, input_factory=SystemInput):
        QtWidgets.QMainWindow.__init__(self)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.capture_factory = capture_factory
        self.mouse_factory = mouse_factory
        self.input = input_factory()      # для экранной клавиатуры (она работает в потоке окна)
        self.worker = None
        self.animation = None
        self.osk = None
        self.mini = None
        self._pixmap = None

        self.ui.webcam_btn.clicked.connect(self.show_webcam_page)
        self.ui.instruction_btn.clicked.connect(self.show_instruction_page)
        self.ui.about_btn.clicked.connect(self.show_about_page)
        self.ui.pushButton.clicked.connect(self.slideLeftMenu)
        self.ui.camera_box.activated.connect(self.change_camera)
        self.ui.control_btn.toggled.connect(self.toggle_control)
        self.ui.top_check.toggled.connect(self.toggle_on_top)
        self.ui.keyboard_btn.clicked.connect(self.show_keyboard)
        self.ui.painter_btn.clicked.connect(self.open_painter)
        self.ui.mini_btn.clicked.connect(self.showMinimized)
        self.ui.reach_slider.valueChanged.connect(self.set_reach)

        self.ui.stackedWidget.setCurrentWidget(self.ui.about_page)
        self.show()

    @property
    def paused(self):
        return self.ui.control_btn.isChecked()

    # --- камера ------------------------------------------------------------
    def start_camera(self):
        if self.worker is not None and self.worker.isRunning():
            return
        self.worker = VideoWorker(int(self.ui.camera_box.currentText()), control=not self.paused,
                                  reach=reach_to_margin(self.ui.reach_slider.value()),
                                  capture_factory=self.capture_factory, mouse_factory=self.mouse_factory)
        self.worker.frame_ready.connect(self.displayImage)
        self.worker.message.connect(self.show_message)
        self.worker.request.connect(self.on_request)
        self.worker.stats.connect(self.ui.stats_label.setText)
        self.worker.start()

    def stop_camera(self):
        if self.worker is not None:
            self.worker.stop()
            self.worker = None

    def change_camera(self, _index=None):
        self.stop_camera()
        self.ui.img_label.setPixmap(QtGui.QPixmap())
        self.ui.status_label.setText("")
        self._pixmap = None
        self.start_camera()

    def toggle_control(self, paused):
        self.ui.control_btn.setText("Включить управление" if paused else "Остановить управление")
        if self.worker is not None:
            self.worker.set_control(not paused)
        if self.mini is not None:
            self.mini.set_paused(paused)

    def toggle_on_top(self, on_top):
        self.setWindowFlag(Qt.WindowStaysOnTopHint, on_top)
        self.show()

    def set_reach(self, value):
        self.ui.reach_label.setText("Чувствительность: %d" % value)
        if self.worker is not None:
            self.worker.post("reach", reach_to_margin(value))

    def post(self, command, value=None):
        if self.worker is not None:
            self.worker.post(command, value)

    # --- экранная клавиатура и рисование --------------------------------------
    def on_request(self, name):
        if name == "keyboard":
            self.show_keyboard()

    def show_keyboard(self):
        if self.osk is None:
            from osk import OnScreenKeyboard
            self.osk = OnScreenKeyboard(os_input=self.input, dwell_allowed=lambda: not self.paused)
            self.osk.closed.connect(lambda: self.post("keyboard_visible", False))
        self.start_camera()
        self.osk.show_keyboard()
        self.post("keyboard_visible", True)

    def open_painter(self):
        self.show_webcam_page()
        self.post("painter", True)

    # --- мини-окно ---------------------------------------------------------------
    def enter_mini(self):
        """Главное окно свёрнуто: остаётся маленькое окно поверх всех окон, жесты продолжают работать."""
        if not self.isMinimized():
            return
        if self.mini is None:
            from miniwindow import MiniWindow
            self.mini = MiniWindow(dwell_allowed=lambda: not self.paused)
            self.mini.restore_requested.connect(self.restore_from_mini)
            self.mini.pause_toggled.connect(self.ui.control_btn.setChecked)
            self.mini.keyboard_requested.connect(self.show_keyboard)
            self.mini.set_paused(self.paused)
        self.start_camera()
        self.mini.move_to_corner()
        self.mini.show()

    def exit_mini(self):
        if self.mini is not None:
            self.mini.hide()

    def restore_from_mini(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def changeEvent(self, event):
        QtWidgets.QMainWindow.changeEvent(self, event)
        if event.type() == QtCore.QEvent.WindowStateChange:
            if self.isMinimized():
                QtCore.QTimer.singleShot(0, self.enter_mini)
            elif self.mini is not None and self.mini.isVisible():
                self.exit_mini()

    # --- страницы ----------------------------------------------------------
    def show_webcam_page(self):
        self.ui.stackedWidget.setCurrentWidget(self.ui.webcam_page)
        self.start_camera()

    def show_instruction_page(self):
        self.ui.stackedWidget.setCurrentWidget(self.ui.instruction_page)

    def show_about_page(self):
        self.ui.stackedWidget.setCurrentWidget(self.ui.about_page)

    def show_message(self, text):
        if self._pixmap is None:       # пока видео нет, сообщение показываем на месте видео
            self.ui.img_label.setText(text)
            if self.mini is not None and self.mini.isVisible():
                self.mini.video.setText(text)
        else:                          # когда видео идёт, оно не закрывается, сообщение - в строке состояния
            self.ui.status_label.setText(text.splitlines()[0][:90])

    def displayImage(self, img):
        if self.mini is not None and self.mini.isVisible():
            self.mini.show_frame(img)
        if not self.isMinimized():
            self._pixmap = QtGui.QPixmap.fromImage(img)
            self._show_scaled()
        elif self._pixmap is None:
            self._pixmap = QtGui.QPixmap.fromImage(img)

    def _show_scaled(self):
        if self._pixmap is not None:
            label = self.ui.img_label
            label.setPixmap(self._pixmap.scaled(label.size(), Qt.KeepAspectRatio, Qt.FastTransformation))

    def resizeEvent(self, event):
        QtWidgets.QMainWindow.resizeEvent(self, event)
        self._show_scaled()

    # --- меню ---------------------------------------------------------------
    def slideLeftMenu(self):
        """Выдвинуть или задвинуть левое меню (плавно, 250 мс)."""
        frame = self.ui.left_menu_cont_frame
        wide, narrow = self.ui.MENU_WIDE, self.ui.MENU_NARROW
        width = frame.width()
        new_width = narrow if width > (wide + narrow) / 2 else wide
        group = QtCore.QParallelAnimationGroup(self)
        for prop in (b"minimumWidth", b"maximumWidth"):
            animation = QtCore.QPropertyAnimation(frame, prop)
            animation.setDuration(250)
            animation.setStartValue(width)
            animation.setEndValue(new_width)
            animation.setEasingCurve(QtCore.QEasingCurve.InOutQuad)
            group.addAnimation(animation)
        group.start()
        self.animation = group

    def closeEvent(self, event):
        self.stop_camera()
        for window in (self.osk, self.mini):
            if window is not None:
                window.hide()
        event.accept()
        QtWidgets.QApplication.quit()


def main():
    QtWidgets.QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()  # noqa: F841 - окно должно жить, пока работает приложение
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
