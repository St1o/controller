import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

try:
    from PyQt5 import QtCore, QtTest, QtWidgets
    HAVE_QT = True
except ImportError:      # без PyQt5 окно не проверить
    HAVE_QT = False

import instruction
from AiVirtualMouse import GESTURES, VirtualMouse, match
from tests.helpers import FakeBackend, FakeInput
from WorkingHand import handDetector


class FakeCapture:
    def __init__(self):
        self.released = False

    def read(self):
        return True, np.zeros((720, 1280, 3), np.uint8)

    def release(self):
        self.released = True


@unittest.skipUnless(HAVE_QT, "нет PyQt5")
class WindowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def make(self, capture=None, mouse=None):
        from main import MainWindow
        self.capture = capture
        self.mouse_input = FakeInput()
        factory = mouse or (lambda: VirtualMouse(detector=handDetector(backend=FakeBackend()), os_input=self.mouse_input))
        window = MainWindow(capture_factory=lambda index: self.capture, mouse_factory=factory)
        self.addCleanup(window.close)
        return window

    def click(self, widget):
        QtTest.QTest.mouseClick(widget, QtCore.Qt.LeftButton)

    def test_three_pages_and_navigation(self):
        w = self.make()
        ui = w.ui
        self.assertEqual(ui.stackedWidget.count(), 3)
        self.assertIs(ui.stackedWidget.currentWidget(), ui.about_page)        # как в дипломе: стартуем с «Информации»
        self.click(ui.instruction_btn)
        self.assertIs(ui.stackedWidget.currentWidget(), ui.instruction_page)
        self.click(ui.about_btn)
        self.assertIs(ui.stackedWidget.currentWidget(), ui.about_page)
        self.assertEqual(ui.bottom_label.text(), "Version 1.0 | Cooperating Egipko")
        self.assertEqual(w.windowTitle(), "VMouse")

    def test_menu_slides_between_wide_and_narrow(self):
        w = self.make()
        w.show()
        frame = w.ui.left_menu_cont_frame
        self.assertEqual(frame.width(), w.ui.MENU_WIDE)
        self.click(w.ui.pushButton)
        QtTest.QTest.qWait(450)
        self.assertEqual(frame.width(), 60)
        self.click(w.ui.pushButton)
        QtTest.QTest.qWait(450)
        self.assertEqual(frame.width(), w.ui.MENU_WIDE)

    def test_instruction_page_has_picture_for_every_gesture(self):
        w = self.make()
        pictures = w.ui.instruction_pictures
        self.assertEqual(len(pictures), len(instruction.ENTRIES))
        for label in pictures:
            self.assertFalse(label.pixmap().isNull())

    def test_instruction_gestures_exist_in_state_machine(self):
        for fingers, tag, title, gesture, description, vee in instruction.ENTRIES:
            self.assertTrue(any(match(fingers, name) for name in GESTURES), title)
            self.assertTrue(gesture.startswith(str(fingers)), title)        # запись жеста в тексте совпадает с картинкой

    def test_video_reaches_window_and_camera_is_released(self):
        cap = FakeCapture()
        w = self.make(capture=cap)
        self.click(w.ui.webcam_btn)
        self.assertIs(w.ui.stackedWidget.currentWidget(), w.ui.webcam_page)
        for _ in range(60):
            QtTest.QTest.qWait(50)
            if w._pixmap is not None:
                break
        self.assertIsNotNone(w._pixmap)
        self.assertEqual((w._pixmap.width(), w._pixmap.height()), (1280, 720))
        self.assertFalse(w.ui.img_label.pixmap().isNull())
        w.close()
        self.assertTrue(cap.released)

    def test_missing_camera_shows_message(self):
        w = self.make(capture=None)
        self.click(w.ui.webcam_btn)
        for _ in range(60):
            QtTest.QTest.qWait(50)
            if "не найдена" in w.ui.img_label.text():
                break
        self.assertIn("не найдена", w.ui.img_label.text())

    def test_pause_button_switches_control_off_and_on(self):
        w = self.make(capture=FakeCapture())
        self.click(w.ui.webcam_btn)
        QtTest.QTest.qWait(300)
        self.assertTrue(w.worker.control)
        self.click(w.ui.control_btn)
        self.assertFalse(w.worker.control)
        self.assertEqual(w.ui.control_btn.text(), "Включить управление")
        self.click(w.ui.control_btn)
        self.assertTrue(w.worker.control)

    def test_error_while_video_runs_goes_to_status_line(self):
        w = self.make(capture=FakeCapture())
        self.click(w.ui.webcam_btn)
        for _ in range(60):
            QtTest.QTest.qWait(50)
            if w._pixmap is not None:
                break
        w.show_message("Ошибка: что-то пошло не так\nподробности")
        self.assertEqual(w.ui.status_label.text(), "Ошибка: что-то пошло не так")
        self.assertFalse(w.ui.img_label.pixmap().isNull())      # видео не закрыто сообщением

    def test_broken_model_shows_error_instead_of_crash(self):
        def broken():
            raise RuntimeError("нет модели")
        w = self.make(capture=FakeCapture(), mouse=broken)
        self.click(w.ui.webcam_btn)
        for _ in range(60):
            QtTest.QTest.qWait(50)
            if "нет модели" in w.ui.img_label.text():
                break
        self.assertIn("нет модели", w.ui.img_label.text())


if __name__ == "__main__":
    unittest.main()
