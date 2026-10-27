import unittest

import numpy as np

from overlay import DwellTracker, fill_rect, inside, put_text


class DwellTrackerTest(unittest.TestCase):
    def test_fires_after_dwell_time_once(self):
        t = DwellTracker(0.8)
        self.assertIsNone(t.update("A", 0.0))
        self.assertIsNone(t.update("A", 0.5))
        self.assertEqual(t.update("A", 0.85), "A")
        self.assertIsNone(t.update("A", 1.5))           # не повторяется, пока кнопку не покинули
        self.assertIsNone(t.update("A", 5.0))

    def test_must_leave_to_fire_again(self):
        t = DwellTracker(0.5)
        t.update("A", 0.0)
        self.assertEqual(t.update("A", 0.6), "A")
        t.update(None, 0.7)
        t.update("A", 0.8)
        self.assertIsNone(t.update("A", 1.0))
        self.assertEqual(t.update("A", 1.4), "A")

    def test_passing_over_keys_does_not_fire(self):
        t = DwellTracker(0.8)
        for i, key in enumerate("ABCDEF"):
            self.assertIsNone(t.update(key, i * 0.3))   # на каждой кнопке по 0,3 с

    def test_changing_key_restarts_timer(self):
        t = DwellTracker(0.8)
        t.update("A", 0.0)
        t.update("B", 0.7)
        self.assertIsNone(t.update("B", 1.0))
        self.assertEqual(t.update("B", 1.6), "B")

    def test_ignore_current_after_reset(self):
        t = DwellTracker(0.5)
        t.reset(ignore_current=True)
        t.update("A", 0.0)
        self.assertIsNone(t.update("A", 2.0))           # было под курсором в момент появления окна
        t.update(None, 2.1)
        t.update("A", 2.2)
        self.assertEqual(t.update("A", 2.8), "A")

    def test_ignore_current_does_not_block_first_real_target(self):
        t = DwellTracker(0.5)
        t.reset(ignore_current=True)
        t.update(None, 0.0)                              # курсор был вне кнопок
        t.update("A", 0.1)
        self.assertEqual(t.update("A", 0.7), "A")

    def test_progress(self):
        t = DwellTracker(1.0)
        self.assertEqual(t.progress(0.0), 0.0)
        t.update("A", 0.0)
        self.assertAlmostEqual(t.progress(0.25), 0.25)
        t.update("A", 1.1)
        self.assertEqual(t.progress(1.2), 0.0)           # сработала - индикатор сброшен


class TextOnFrameTest(unittest.TestCase):
    def test_russian_text_is_drawn(self):
        img = np.zeros((100, 400, 3), np.uint8)
        put_text(img, "Графический редактор", (0, 0, 400, 100), 30)
        self.assertGreater(int(np.count_nonzero(img)), 500)

    def test_text_outside_frame_does_not_crash(self):
        img = np.zeros((50, 50, 3), np.uint8)
        put_text(img, "Очень длинная подпись, которая не влезает", (-100, 0, 400, 50), 30)
        fill_rect(img, (-10, -10, 20, 20), (255, 0, 0), 0.5)

    def test_inside(self):
        self.assertTrue(inside((10, 10, 20, 20), (15, 15)))
        self.assertFalse(inside((10, 10, 20, 20), (5, 15)))
        self.assertFalse(inside((10, 10, 20, 20), None))


if __name__ == "__main__":
    unittest.main()
