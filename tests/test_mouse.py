import unittest

import numpy as np

from AiVirtualMouse import GESTURES, GestureStabilizer, match
from tests.helpers import H, Rig, W

PALM, PEACE, MIDDLE, INDEX = [1, 1, 1, 1, 1], [0, 1, 1, 0, 0], [0, 0, 1, 0, 0], [0, 1, 0, 0, 0]
FIST, FOUR, GUN, THREE, ROCK = [0, 0, 0, 0, 0], [0, 1, 1, 1, 1], [1, 1, 0, 0, 0], [0, 1, 1, 1, 0], [0, 1, 0, 0, 1]


class StabilizerTest(unittest.TestCase):
    def test_waits_for_three_equal_frames(self):
        s = GestureStabilizer()
        self.assertIsNone(s.update(PEACE))
        self.assertIsNone(s.update(PEACE))
        self.assertEqual(s.update(PEACE), PEACE)

    def test_single_flicker_is_ignored(self):
        s = GestureStabilizer()
        for _ in range(4):
            s.update(PEACE)
        self.assertEqual(s.update(INDEX), PEACE)          # один кадр «мигания»
        self.assertEqual(s.update(PEACE), PEACE)

    def test_thumb_flicker_does_not_break_gesture(self):
        s = GestureStabilizer()
        seen = [s.update([i % 2, 0, 1, 0, 0]) for i in range(10)]
        self.assertIsNotNone(seen[-1])
        self.assertEqual(seen[-1][1:], [0, 1, 0, 0])

    def test_reset(self):
        s = GestureStabilizer()
        for _ in range(4):
            s.update(PEACE)
        s.reset()
        self.assertIsNone(s.update(PEACE))

    def test_match_ignores_thumb_where_table_says_none(self):
        self.assertTrue(match([1, 1, 1, 0, 0], "peace"))
        self.assertTrue(match([0, 1, 1, 0, 0], "peace"))
        self.assertFalse(match([0, 1, 1, 1, 0], "peace"))
        self.assertFalse(match([0, 1, 1, 1, 1], "palm"))
        self.assertFalse(match(None, "palm"))
        self.assertTrue(set(GESTURES) >= {"palm", "peace", "middle", "index", "fist", "four", "three"})


class MouseTest(unittest.TestCase):
    def setUp(self):
        self.rig = Rig()

    def test_starts_in_basic_state(self):
        self.assertEqual(self.rig.state, "basic")
        self.rig.open_palm()
        self.assertEqual(self.rig.state, "basic")
        self.assertEqual(self.rig.os.calls, [])

    def test_two_fingers_move_cursor_across_screen(self):
        rig = self.rig
        rig.open_palm()
        rig.feed(PEACE, at=(W * 0.2, H * 0.2), frames=40)
        self.assertEqual(rig.state, "move_mouse")
        left_top = rig.os.pos
        rig.feed(PEACE, at=(W * 0.8, H * 0.8), frames=60)
        right_bottom = rig.os.pos
        self.assertLess(left_top[0], 400)
        self.assertLess(left_top[1], 250)
        self.assertGreater(right_bottom[0], 1500)      # зеркало: рука вправо - курсор вправо
        self.assertGreater(right_bottom[1], 800)
        self.assertEqual(rig.os.of("click"), [])

    def test_cursor_stays_inside_screen(self):
        rig = self.rig
        rig.open_palm()
        rig.feed(PEACE, at=(5, 5), frames=60)
        x, y = rig.os.pos
        self.assertTrue(0 <= x <= 1920 and 0 <= y <= 1080)

    def test_middle_finger_is_left_click_once(self):
        rig = self.rig
        rig.open_palm()
        rig.feed(PEACE, frames=10)
        rig.feed(MIDDLE, frames=30)
        self.assertEqual(rig.os.of("click"), [("click", "left", 1)])    # один клик, хотя жест держится долго
        self.assertEqual(rig.state, "left_click")

    def test_index_finger_is_right_click_once(self):
        rig = self.rig
        rig.open_palm()
        rig.feed(PEACE, frames=10)
        rig.feed(INDEX, frames=30)
        self.assertEqual(rig.os.of("click"), [("click", "right", 1)])
        self.assertEqual(rig.state, "right_click")

    def test_click_gesture_without_move_state_does_nothing(self):
        rig = self.rig
        rig.open_palm()
        rig.feed(MIDDLE, frames=30)
        rig.feed(INDEX, frames=30)
        self.assertEqual(rig.os.of("click"), [])

    def test_can_click_again_after_returning_to_move(self):
        rig = self.rig
        rig.open_palm()
        rig.feed(PEACE, frames=10)
        rig.feed(MIDDLE, frames=10)
        rig.feed(PEACE, frames=10)
        rig.feed(MIDDLE, frames=10)
        self.assertEqual(len(rig.os.of("click")), 2)

    def test_short_flicker_does_not_click(self):
        rig = self.rig
        rig.open_palm()
        rig.feed(PEACE, frames=10)
        rig.feed(INDEX, frames=2)       # палец «мигнул» на два кадра
        rig.feed(PEACE, frames=10)
        self.assertEqual(rig.os.of("click"), [])

    def test_click_does_not_move_cursor(self):
        rig = self.rig
        rig.open_palm()
        rig.feed(PEACE, at=(W * 0.4, H * 0.4), frames=40)
        before = rig.os.pos
        rig.feed(MIDDLE, at=(W * 0.4, H * 0.4), frames=10)
        self.assertEqual(rig.os.pos, before)

    def test_double_click_when_fingers_close_together(self):
        rig = self.rig
        rig.open_palm()

        def close_fingers(pts):     # кончик среднего пальца к кончику указательного
            pts = list(pts)
            pts[12] = (pts[8][0] + 8, pts[8][1])
            pts[11] = (pts[10][0] + 4, pts[10][1])
            return pts

        rig.feed(PEACE, frames=10)                    # пальцы разведены: идёт движение
        self.assertEqual(rig.os.of("click"), [])
        rig.feed(PEACE, frames=10, tweak=close_fingers)
        self.assertEqual(rig.os.of("click"), [("click", "left", 2)])
        rig.feed(PEACE, frames=10, tweak=close_fingers)   # держим сведёнными: повтора нет
        self.assertEqual(len(rig.os.of("click")), 1)

    def test_no_double_click_when_entering_move_with_fingers_together(self):
        rig = self.rig
        rig.open_palm()

        def close_fingers(pts):
            pts = list(pts)
            pts[12] = (pts[8][0] + 8, pts[8][1])
            return pts

        rig.feed(PEACE, frames=12, tweak=close_fingers)
        self.assertEqual(rig.os.of("click"), [])

    def test_fist_drags_and_palm_drops(self):
        rig = self.rig
        rig.open_palm()
        rig.feed(PEACE, at=(W * 0.3, H * 0.5), frames=30)
        rig.feed(FIST, at=(W * 0.3, H * 0.5), frames=15)
        self.assertEqual(rig.state, "took")
        self.assertEqual(rig.os.of("down"), [("down", "left")])
        start = rig.os.pos
        rig.feed(FIST, at=(W * 0.7, H * 0.5), frames=40)
        self.assertGreater(rig.os.pos[0], start[0] + 400)          # рука тащит курсор
        self.assertEqual(rig.os.of("up"), [])
        rig.feed(PALM, frames=4)
        self.assertEqual(rig.os.of("up"), [("up", "left")])
        self.assertEqual(rig.state, "basic")

    def test_drag_released_when_hand_disappears(self):
        rig = self.rig
        rig.open_palm()
        rig.feed(PEACE, frames=12)
        rig.feed(FIST, frames=15)
        self.assertEqual(rig.state, "took")
        rig.no_hand(frames=20)
        self.assertEqual(rig.os.of("up"), [("up", "left")])
        self.assertEqual(rig.state, "basic")

    def test_peace_while_dragging_releases_button(self):
        rig = self.rig
        rig.open_palm()
        rig.feed(PEACE, frames=12)
        rig.feed(FIST, frames=15)
        rig.feed(PEACE, frames=6)
        self.assertEqual(rig.os.of("up"), [("up", "left")])
        self.assertEqual(rig.state, "move_mouse")

    def test_shutdown_releases_button(self):
        rig = self.rig
        rig.open_palm()
        rig.feed(PEACE, frames=12)
        rig.feed(FIST, frames=15)
        rig.mouse.shutdown()
        self.assertEqual(rig.os.of("up"), [("up", "left")])

    def test_scroll_up_down_and_dead_zone(self):
        rig = self.rig
        rig.open_palm()
        rig.feed(FOUR, at=(W // 2, H // 2), frames=20)         # середина кадра: прокрутки нет
        self.assertEqual(rig.state, "scroll")
        self.assertEqual(rig.os.of("scroll"), [])
        rig.feed(FOUR, at=(W // 2, int(H * 0.2)), frames=10)   # рука выше середины: вверх
        up = [c[1] for c in rig.os.of("scroll")]
        self.assertTrue(up and all(a > 0 for a in up))
        rig.os.calls.clear()
        rig.feed(FOUR, at=(W // 2, int(H * 0.8)), frames=10)   # ниже: вниз
        down = [c[1] for c in rig.os.of("scroll")]
        self.assertTrue(down and all(a < 0 for a in down))

    def test_scroll_faster_when_hand_is_farther_from_middle(self):
        rig = self.rig
        rig.open_palm()
        rig.feed(FOUR, at=(W // 2, int(H * 0.34)), frames=14)
        near = [c[1] for c in rig.os.of("scroll")]
        rig.os.calls.clear()
        rig.feed(FOUR, at=(W // 2, int(H * 0.10)), frames=10)
        far = [c[1] for c in rig.os.of("scroll")]
        self.assertGreater(sum(far) / len(far), sum(near) / len(near))

    def test_scroll_stops_when_leaving_scroll_gesture(self):
        rig = self.rig
        rig.open_palm()
        rig.feed(FOUR, at=(W // 2, int(H * 0.2)), frames=15)
        rig.feed(PEACE, at=(W // 2, int(H * 0.2)), frames=6)
        rig.os.calls.clear()
        rig.feed(PEACE, at=(W // 2, int(H * 0.2)), frames=6)
        self.assertEqual(rig.os.of("scroll"), [])

    def test_volume_gesture_enters_state_only_from_basic(self):
        rig = self.rig
        rig.open_palm()
        rig.feed(GUN, frames=12)
        self.assertEqual(rig.state, "volume_control")
        rig2 = Rig()
        rig2.open_palm()
        rig2.feed(PEACE, frames=10)
        rig2.feed(GUN, frames=12)
        self.assertNotEqual(rig2.state, "volume_control")

    def test_volume_gesture_without_audio_backend_does_not_crash(self):
        rig = self.rig
        rig.open_palm()
        rig.feed(GUN, frames=12)
        rig.feed(GUN, frames=6, scale=2.0)       # расстояние между пальцами меняется - громкость пытаются выставить
        self.assertEqual(rig.state, "volume_control")

    def test_pause_blocks_os_but_keeps_tracking(self):
        rig = self.rig
        rig.open_palm()
        rig.mouse.set_enabled(False)
        rig.feed(PEACE, at=(W * 0.3, H * 0.3), frames=10)
        rig.feed(MIDDLE, at=(W * 0.3, H * 0.3), frames=10)
        self.assertEqual(rig.os.calls, [])
        self.assertEqual(rig.state, "left_click")             # жесты по-прежнему распознаются
        rig.mouse.set_enabled(True)
        rig.feed(PEACE, at=(W * 0.3, H * 0.3), frames=10)
        self.assertTrue(rig.os.of("move"))

    def test_far_hand_is_not_accepted_as_move(self):
        rig = self.rig
        rig.feed(PALM, frames=6, scale=2.4)        # близко: длинный палец запомнен
        rig.feed(PEACE, frames=12, scale=1.0)      # рука отодвинулась: движение не принимается
        self.assertEqual(rig.os.of("move"), [])
        rig.feed(PALM, frames=6, scale=1.0)        # показали ладонь заново на новом расстоянии
        rig.feed(PEACE, at=(W * 0.3, H * 0.3), frames=12, scale=1.0)
        self.assertTrue(rig.os.of("move"))

    def test_hud_text_is_drawn(self):
        frame = self.rig.open_palm()
        self.assertEqual(frame.shape, (H, W, 3))
        self.assertGreater(int(np.count_nonzero(frame[:60, :400])), 0)


if __name__ == "__main__":
    unittest.main()
