import unittest

import numpy as np

from tests.helpers import H, Rig, W
from webcamKeyboard import VirtualKeyboard, addButtonList, apply_case, en_keys, ru_keys

PEACE, INDEX, THREE, FOUR = [0, 1, 1, 0, 0], [0, 1, 0, 0, 0], [0, 1, 1, 1, 0], [0, 1, 1, 1, 1]


def center(rig, text):
    for b in addButtonList([], rig.mouse.keyboard.keys(), W / 1280.0):
        if b.text == text:
            return b.pos[0] + b.size[0] / 2, b.pos[1] + b.size[1] / 2
    raise KeyError(text)


def pose(x, y, pinched):
    """Указательный палец в точке (x, y); большой палец рядом (щипок) или в стороне."""
    def tweak(pts):
        pts = list(pts)
        pts[4] = (pts[8][0] + (8 if pinched else 90), pts[8][1])
        return pts
    return dict(at=(x, y), anchor=8, tweak=tweak)


class KeyboardLayoutTest(unittest.TestCase):
    def test_layouts_have_same_shape_and_russian_letters(self):
        self.assertEqual([len(r) for r in ru_keys], [len(r) for r in en_keys])
        self.assertIn("Ж", ru_keys[2])
        self.assertIn("Q", en_keys[1])

    def test_case_switch_changes_control_labels_too(self):
        low = apply_case(ru_keys, False)
        self.assertEqual(low[1][0], "й")
        self.assertEqual(low[-1][1], "sh")

    def test_buttons_fit_in_frame_at_720p_and_480p(self):
        for w, h in ((1280, 720), (640, 480)):
            for b in addButtonList([], ru_keys, w / 1280.0):
                self.assertLessEqual(b.pos[0] + b.size[0], w)
                self.assertLessEqual(b.pos[1] + b.size[1], h * 0.8)


class KeyboardModeTest(unittest.TestCase):
    def setUp(self):
        self.rig = Rig()
        self.rig.open_palm()
        self.rig.feed(THREE, frames=14)
        self.assertEqual(self.rig.state, "ai_keyboard")
        self.rig.os.calls.clear()

    def press(self, text, wait=12):
        rig = self.rig
        x, y = center(rig, text)
        rig.feed(INDEX, frames=6, **pose(x, y, False))
        rig.feed(INDEX, frames=3, **pose(x, y, True))
        rig.feed(INDEX, frames=wait, **pose(x, y, False))     # разжали пальцы, ждём паузу между нажатиями

    def test_pinch_over_key_types_that_letter(self):
        self.press("П")
        self.assertEqual(self.rig.os.of("type"), [("type", "П")])
        self.assertEqual(self.rig.mouse.keyboard.finalText, "П")

    def test_holding_pinch_types_only_once(self):
        rig = self.rig
        x, y = center(rig, "А")
        rig.feed(INDEX, frames=6, **pose(x, y, False))
        rig.feed(INDEX, frames=30, **pose(x, y, True))
        self.assertEqual(len(rig.os.of("type")), 1)

    def test_no_typing_without_pinch(self):
        rig = self.rig
        x, y = center(rig, "Р")
        rig.feed(INDEX, frames=30, **pose(x, y, False))
        self.assertEqual(rig.os.of("type"), [])

    def test_pinch_outside_keys_does_nothing(self):
        rig = self.rig
        rig.feed(INDEX, frames=6, **pose(W - 30, H - 30, False))
        rig.feed(INDEX, frames=6, **pose(W - 30, H - 30, True))
        self.assertEqual(rig.os.calls, [])

    def test_finger_slipping_during_pinch_still_hits_original_key(self):
        """При щипке указательный палец смещается: считается клавиша, на которой он стоял до щипка."""
        rig = self.rig
        x, y = center(rig, "О")
        rig.feed(INDEX, frames=8, **pose(x, y, False))
        rig.feed(INDEX, frames=3, **pose(x + 160, y + 110, True))     # палец уехал далеко от клавиши
        self.assertEqual(rig.os.of("type"), [("type", "О")])

    def test_shift_switches_case_and_language_switches_layout(self):
        rig = self.rig
        kb = rig.mouse.keyboard
        self.assertEqual((kb.lang, kb.register), ("ru", "upper"))
        self.press("SH")
        self.assertEqual(kb.register, "lower")
        self.press("п")
        self.assertEqual(rig.os.of("type"), [("type", "п")])
        self.press("ln")
        self.assertEqual(kb.lang, "en")
        self.press("q")
        self.assertEqual(rig.os.of("type")[-1], ("type", "q"))
        self.assertEqual(kb.finalText, "пq")

    def test_enter_backspace_and_clear(self):
        rig = self.rig
        kb = rig.mouse.keyboard
        self.press("А")
        self.press("Б")
        self.press("BS")
        self.assertEqual(kb.finalText, "А")
        self.assertEqual(rig.os.of("press"), [("press", "backspace")])
        self.press("EN")
        self.assertEqual(rig.os.of("press")[-1], ("press", "enter"))
        self.press("CL")
        self.assertEqual(kb.finalText, "")

    def test_space_and_digits(self):
        rig = self.rig
        self.press("1")
        self.press(" ")
        self.assertEqual([c[1] for c in rig.os.of("type")], ["1", " "])

    def test_cursor_is_not_moved_in_keyboard_mode(self):
        rig = self.rig
        x, y = center(rig, "К")
        rig.feed(PEACE, frames=20, at=(W * 0.2, H * 0.2))
        self.assertEqual(rig.os.of("move"), [])
        self.assertEqual(rig.state, "ai_keyboard")

    def test_four_fingers_leave_keyboard(self):
        rig = self.rig
        rig.feed(FOUR, frames=4)
        self.assertEqual(rig.state, "ai_keyboard")          # короткое раскрытие не выходит
        rig.feed(FOUR, frames=14)
        self.assertEqual(rig.state, "basic")

    def test_keyboard_is_drawn_on_frame(self):
        rig = self.rig
        frame = rig.feed(INDEX, frames=3, **pose(W - 30, H - 30, False))
        self.assertGreater(int(np.count_nonzero(frame[40:140, 40:1250])), 5000)
        self.assertGreater(int(np.count_nonzero(frame[570:650, 60:1230])), 5000)    # строка с текстом

    def test_works_on_small_frame(self):
        kb = VirtualKeyboard(os_input=self.rig.os)
        out = kb.main(np.zeros((480, 640, 3), np.uint8), [], self.rig.mouse.detector)
        self.assertEqual(out.shape, (480, 640, 3))
        self.assertGreater(int(np.count_nonzero(out)), 1000)


class KeyboardEntryTest(unittest.TestCase):
    def test_keyboard_opens_only_from_basic_like_states(self):
        rig = Rig()
        rig.open_palm()
        rig.feed(PEACE, frames=10)
        rig.feed(THREE, frames=14)
        self.assertNotEqual(rig.state, "ai_keyboard")


if __name__ == "__main__":
    unittest.main()
