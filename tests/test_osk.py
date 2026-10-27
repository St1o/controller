import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5 import QtCore, QtTest, QtWidgets
    from PyQt5.QtCore import Qt
    HAVE_QT = True
except ImportError:
    HAVE_QT = False

from tests.helpers import FakeInput


@unittest.skipUnless(HAVE_QT, "нет PyQt5")
class KeyboardWindowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        from osk import OnScreenKeyboard
        self.os = FakeInput()
        self.now = [100.0]
        self.cursor = [QtCore.QPoint(-5000, -5000)]
        self.allowed = [True]
        self.osk = OnScreenKeyboard(os_input=self.os, dwell=0.8, clock=lambda: self.now[0],
                                    cursor_pos=lambda: self.cursor[0], dwell_allowed=lambda: self.allowed[0])
        self.addCleanup(self.osk.close)
        self.osk.show_keyboard()
        self.osk.poll()          # курсор вне окна: «сброс при появлении» отработал, дальше всё как обычно

    # --- помощники -------------------------------------------------------
    def key(self, text):
        for widgets in self.osk.rows:
            for k in widgets:
                if k.text == text:
                    return k
        raise KeyError(text)

    def point_at(self, key):
        self.cursor[0] = key.mapToGlobal(key.rect().center())

    def dwell(self, key, seconds, step=0.05):
        self.point_at(key)
        for _ in range(int(seconds / step) + 1):
            self.now[0] += step
            self.osk.poll()

    def leave(self):
        self.cursor[0] = QtCore.QPoint(-5000, -5000)
        self.now[0] += 0.05
        self.osk.poll()

    def typed(self):
        return [c[1] for c in self.os.of("type")]

    # --- окно ---------------------------------------------------------------
    def test_window_is_a_titled_topmost_window_that_does_not_take_focus(self):
        flags = self.osk.windowFlags()
        self.assertTrue(flags & Qt.WindowStaysOnTopHint)
        self.assertTrue(flags & Qt.WindowDoesNotAcceptFocus)
        self.assertTrue(flags & Qt.Tool)
        self.assertTrue(self.osk.testAttribute(Qt.WA_ShowWithoutActivating))
        texts = [l.text() for l in self.osk.findChildren(QtWidgets.QLabel)]
        self.assertIn("Виртуальная клавиатура", texts)
        self.assertEqual(self.osk.back_key.text, "← Назад")

    def test_window_fits_on_screen_and_is_at_bottom(self):
        g = self.osk.screen_rect
        self.assertLessEqual(self.osk.width(), g.width())
        self.assertGreater(self.osk.y(), g.height() // 3)

    # --- нажатие задержкой -------------------------------------------------------
    def test_key_is_typed_after_dwell(self):
        self.dwell(self.key("П"), 1.0)
        self.assertEqual(self.typed(), ["П"])
        self.assertEqual(self.osk.model.finalText, "П")
        self.assertEqual(self.osk.text_label.text(), "П")

    def test_short_touch_does_not_type(self):
        self.dwell(self.key("П"), 0.4)
        self.assertEqual(self.typed(), [])

    def test_sweeping_across_row_does_not_type(self):
        for label in "ФЫВАПРО":
            self.dwell(self.key(label), 0.3)
        self.assertEqual(self.typed(), [])

    def test_holding_does_not_repeat_but_leaving_and_returning_does(self):
        key = self.key("А")
        self.dwell(key, 3.0)
        self.assertEqual(self.typed(), ["А"])
        self.leave()
        self.dwell(key, 1.0)
        self.assertEqual(self.typed(), ["А", "А"])

    def test_cursor_under_window_when_it_appears_does_not_press(self):
        self.osk.hide()
        self.now[0] += 1
        self.point_at(self.key("Ш"))
        self.osk.show_keyboard()
        for _ in range(40):
            self.now[0] += 0.05
            self.osk.poll()
        self.assertEqual(self.typed(), [])

    def test_progress_indicator_grows_while_holding(self):
        key = self.key("К")
        self.dwell(key, 0.4)
        self.assertGreater(key.progress, 0.3)
        self.assertLess(key.progress, 1.0)
        self.leave()
        self.assertEqual(key.progress, 0.0)

    def test_pause_disables_dwell_but_not_mouse_clicks(self):
        self.allowed[0] = False
        self.dwell(self.key("Т"), 2.0)
        self.assertEqual(self.typed(), [])
        QtTest.QTest.mouseClick(self.key("Т"), Qt.LeftButton)
        self.assertEqual(self.typed(), ["Т"])

    def test_dwell_time_button_cycles_through_choices(self):
        seconds = [self.osk.tracker.seconds]
        for _ in range(4):
            self.osk.on_key(self.osk.dwell_key)
            seconds.append(self.osk.tracker.seconds)
        self.assertEqual(seconds, [0.8, 1.2, 1.8, 0.5, 0.8])
        self.assertIn("0,8", self.osk.dwell_key.text)

    # --- служебные клавиши ----------------------------------------------------------
    def test_shift_and_language_change_labels(self):
        self.dwell(self.key("SH"), 1.0)
        self.assertEqual(self.osk.model.register, "lower")
        self.assertEqual(self.key("п").text, "п")
        self.leave()
        self.dwell(self.key("ln"), 1.0)
        self.assertEqual(self.osk.model.lang, "en")
        self.assertEqual(self.key("q").text, "q")
        self.leave()
        self.dwell(self.key("q"), 1.0)
        self.assertEqual(self.typed(), ["q"])

    def test_enter_backspace_clear_and_space(self):
        self.dwell(self.key("А"), 1.0)
        self.leave()
        self.dwell(self.key("␣"), 1.0)
        self.leave()
        self.dwell(self.key("BS"), 1.0)
        self.assertEqual(self.os.of("press"), [("press", "backspace")])
        self.assertEqual(self.osk.model.finalText, "А")
        self.leave()
        self.dwell(self.key("EN"), 1.0)
        self.assertEqual(self.os.of("press")[-1], ("press", "enter"))
        self.leave()
        self.dwell(self.key("CL"), 1.0)
        self.assertEqual(self.osk.text_label.text(), "")

    def test_back_button_hides_window_and_reports(self):
        closed = []
        self.osk.closed.connect(lambda: closed.append(1))
        self.dwell(self.osk.back_key, 1.0)
        self.assertFalse(self.osk.isVisible())
        self.assertEqual(closed, [1])
        self.assertEqual(self.typed(), [])

    def test_back_button_by_mouse_click(self):
        QtTest.QTest.mouseClick(self.osk.back_key, Qt.LeftButton)
        self.assertFalse(self.osk.isVisible())

    def test_window_can_be_shown_again_in_same_place(self):
        self.osk.move(123, 321)
        self.osk.hide_keyboard()
        self.osk.show_keyboard()
        self.assertEqual((self.osk.x(), self.osk.y()), (123, 321))


@unittest.skipUnless(HAVE_QT, "нет PyQt5")
class MiniWindowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        from miniwindow import MiniWindow
        self.now = [10.0]
        self.cursor = [QtCore.QPoint(-5000, -5000)]
        self.mini = MiniWindow(clock=lambda: self.now[0], cursor_pos=lambda: self.cursor[0])
        self.addCleanup(self.mini.close)
        self.mini.show()
        self.mini.poll()
        self.events = []
        self.mini.restore_requested.connect(lambda: self.events.append("restore"))
        self.mini.keyboard_requested.connect(lambda: self.events.append("keyboard"))
        self.mini.pause_toggled.connect(lambda p: self.events.append("pause" if p else "resume"))

    def hold(self, key, seconds=1.3):
        self.cursor[0] = key.mapToGlobal(key.rect().center())
        for _ in range(int(seconds / 0.05) + 1):
            self.now[0] += 0.05
            self.mini.poll()

    def test_buttons_by_dwell(self):
        self.hold(self.mini.keyboard_key)
        self.cursor[0] = QtCore.QPoint(-5000, -5000)
        self.mini.poll()
        self.hold(self.mini.pause_key)
        self.assertEqual(self.events, ["keyboard", "pause"])
        self.assertIn("паузе", self.mini.title.text())
        self.cursor[0] = QtCore.QPoint(-5000, -5000)
        self.mini.poll()
        self.hold(self.mini.restore_key)
        self.assertEqual(self.events[-1], "restore")

    def test_buttons_by_click(self):
        QtTest.QTest.mouseClick(self.mini.restore_key, Qt.LeftButton)
        self.assertEqual(self.events, ["restore"])

    def test_does_not_take_focus_and_stays_on_top(self):
        flags = self.mini.windowFlags()
        self.assertTrue(flags & Qt.WindowDoesNotAcceptFocus)
        self.assertTrue(flags & Qt.WindowStaysOnTopHint)

    def test_shows_frames(self):
        from PyQt5 import QtGui
        image = QtGui.QImage(640, 480, QtGui.QImage.Format_RGB888)
        image.fill(QtGui.QColor("red"))
        self.mini.show_frame(image)
        self.assertFalse(self.mini.video.pixmap().isNull())
        self.assertLessEqual(self.mini.video.pixmap().width(), 288)

    def test_corner_position_is_on_screen(self):
        self.mini.move_to_corner()
        g = QtWidgets.QApplication.primaryScreen().availableGeometry()
        self.assertTrue(g.contains(self.mini.geometry().bottomRight()))


if __name__ == "__main__":
    unittest.main()
