import unittest

import numpy as np

from tests.helpers import H, Rig, W

PEACE, INDEX, THREE, MIDDLE, FIST = [0, 1, 1, 0, 0], [0, 1, 0, 0, 0], [0, 1, 1, 1, 0], [0, 0, 1, 0, 0], [0, 0, 0, 0, 0]


class KeyboardRequestTest(unittest.TestCase):
    def test_three_fingers_ask_window_for_keyboard_once(self):
        rig = Rig()
        rig.open_palm()
        rig.feed(THREE, frames=40)
        self.assertEqual(rig.requests, ["keyboard"])         # один раз, хотя жест держится долго
        self.assertTrue(rig.mouse.keyboard_visible)
        self.assertEqual(rig.os.calls, [])                    # сама рука ничего не нажимает

    def test_keyboard_opens_from_any_state(self):
        for setup in ("basic", "move", "left", "right"):
            rig = Rig()
            rig.open_palm()
            if setup != "basic":
                rig.feed(PEACE, frames=10)
            if setup == "left":
                rig.feed(MIDDLE, frames=12)
            if setup == "right":
                rig.feed(INDEX, frames=12)
            rig.os.calls.clear()
            rig.feed(THREE, frames=30)
            self.assertEqual(rig.requests, ["keyboard"], setup)

    def test_short_three_fingers_do_not_open(self):
        rig = Rig()
        rig.open_palm()
        rig.feed(THREE, frames=10)
        self.assertEqual(rig.requests, [])

    def test_no_second_request_while_keyboard_is_visible_and_hand_keeps_working(self):
        rig = Rig()
        rig.open_palm()
        rig.feed(THREE, frames=30)
        rig.feed(PEACE, at=(W * 0.3, H * 0.3), frames=40)    # курсор продолжает двигаться при открытой клавиатуре
        self.assertTrue(rig.os.of("move"))
        rig.feed(THREE, frames=90)
        self.assertEqual(rig.requests, ["keyboard"])

    def test_can_ask_again_after_window_reports_it_was_closed(self):
        rig = Rig()
        rig.open_palm()
        rig.feed(THREE, frames=30)
        rig.mouse.post("keyboard_visible", False)            # окно сообщило: «Назад» нажата
        rig.feed(PEACE, frames=6)
        rig.feed(THREE, frames=90)
        self.assertEqual(rig.requests, ["keyboard", "keyboard"])

    def test_not_while_dragging(self):
        rig = Rig()
        rig.open_palm()
        rig.feed(PEACE, frames=10)
        rig.feed(FIST, frames=25)
        rig.feed(THREE, frames=40)
        self.assertEqual(rig.requests, [])


class SlowCameraTest(unittest.TestCase):
    """На слабом компьютере камера даёт 10 кадров/с: всё должно работать так же, только с задержкой кадров."""

    def test_move_click_and_keyboard_at_10_fps(self):
        rig = Rig(fps=10)
        rig.open_palm()
        rig.feed(PEACE, at=(W * 0.3, H * 0.3), frames=12)
        self.assertTrue(rig.os.of("move"))
        x, y = rig.os.pos
        self.assertLess(x, 800)                              # курсор добежал за ~1 секунду, а не завис на полпути
        rig.feed(MIDDLE, frames=12)
        self.assertEqual(rig.os.of("click"), [("click", "left", 1)])
        rig.feed(THREE, frames=20)
        self.assertEqual(rig.requests, ["keyboard"])

    def test_cursor_follows_hand_at_same_speed_in_seconds_at_10_and_30_fps(self):
        def seconds_to_reach(fps):
            rig = Rig(fps=fps)
            rig.open_palm()
            rig.feed(PEACE, at=(W * 0.5, H * 0.5), frames=3)
            start = rig.os.pos[0]
            frames = 0
            while abs(rig.os.pos[0] - 300) > 100 and frames < 400:
                rig.feed(PEACE, at=(W * 0.3, H * 0.5), frames=1)
                frames += 1
            return frames / fps
        slow, fast = seconds_to_reach(10), seconds_to_reach(30)
        self.assertLess(abs(slow - fast), 0.35)


class ReachTest(unittest.TestCase):
    def test_smaller_zone_reaches_screen_edges_with_less_hand_travel(self):
        def left_edge(margin):
            rig = Rig()
            rig.mouse.post("reach", margin)
            rig.open_palm()
            rig.feed(PEACE, at=(W * 0.5, H * 0.5), frames=3)
            rig.feed(PEACE, at=(W * 0.12, H * 0.5), frames=60)
            return rig.os.pos[0]
        self.assertLess(left_edge(0.30), 5)          # зона 40% кадра: до левого края хватает руки в 12% от края кадра
        self.assertGreater(left_edge(0.05), 40)      # зона почти во весь кадр: рука у края кадра ещё не у края экрана

    def test_hand_at_edge_of_frame_reaches_corners_with_default_zone(self):
        rig = Rig()
        rig.open_palm()
        rig.feed(PEACE, at=(W * 0.2, H * 0.22), frames=60)
        self.assertLess(rig.os.pos[0], 20)
        self.assertLess(rig.os.pos[1], 20)


if __name__ == "__main__":
    unittest.main()
