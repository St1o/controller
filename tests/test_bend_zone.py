import unittest

import numpy as np

from WorkingHand import handDetector
from handSketch import make_hand, place
from tests.helpers import FakeBackend, H, Rig, W

PEACE, MIDDLE, INDEX, FIST, FOUR = [0, 1, 1, 0, 0], [0, 0, 1, 0, 0], [0, 1, 0, 0, 0], [0, 0, 0, 0, 0], [0, 1, 1, 1, 1]
BENT = {"bend_index": 70}       # заметный сгиб (на скрине около 58 градусов, и палец ещё наклонён к камере)


def detector_for(fingers, scale=1.6, **hand):
    backend = FakeBackend()
    det = handDetector(backend=backend)
    backend.points = place(make_hand(fingers, scale, **hand), 9, W // 2, H // 2)
    img = np.zeros((H, W, 3), np.uint8)
    det.findHands(img, draw=False)
    det.findPosition(img, draw=False)
    return det


class DetectorMeasuresTest(unittest.TestCase):
    def test_tilting_whole_hand_toward_camera_is_not_a_bend(self):
        """Наклон кисти к камере укорачивает оба пальца: указательный не становится «короче среднего»."""
        straight = detector_for(PEACE)
        ratio = straight.fingerReach(1) / straight.fingerReach(2)
        self.assertGreater(ratio, 0.85)
        bent = detector_for(PEACE, bend_index=70)
        self.assertLess(bent.fingerReach(1) / bent.fingerReach(2), 0.85)

    def test_straight_finger_has_small_bend_and_bent_finger_large(self):
        straight = detector_for(PEACE).fingerBend(1)
        bent = detector_for(PEACE, bend_index=58).fingerBend(1)
        self.assertLess(straight, 12)           # по скрину ~6
        self.assertGreater(bent, 50)            # по скрину ~58
        self.assertAlmostEqual(detector_for(PEACE, bend_index=58).fingerBend(2), 0, delta=5)   # средний не тронут

    def test_bent_finger_still_counts_as_raised(self):
        """Согнутый на фаланге палец остаётся «поднятым»: жест V не сбивается и курсор продолжает быть в режиме движения."""
        self.assertEqual(detector_for(PEACE, bend_index=58).halfFingersUp(), PEACE)

    def test_bend_is_independent_of_hand_size_and_position(self):
        values = [detector_for(PEACE, scale, bend_index=58).fingerBend(1) for scale in (0.8, 1.6, 2.4)]
        self.assertLess(max(values) - min(values), 4)       # разница только от округления до пикселя

    def test_spread_matches_screenshots(self):
        together = detector_for(FOUR, spread="together").fingerSpread()
        relaxed = detector_for(FOUR).fingerSpread()
        wide = detector_for(FOUR, spread="wide").fingerSpread()
        very = detector_for(FOUR, spread="very_wide").fingerSpread()
        self.assertAlmostEqual(together, 0.58, delta=0.08)
        self.assertAlmostEqual(wide, 1.09, delta=0.08)
        self.assertTrue(0.70 < relaxed < 0.95, relaxed)      # расслабленная рука попадает в «покой»
        self.assertGreater(very, wide)

    def test_four_fingers_gesture_is_recognized_at_any_spread(self):
        for spread in ("together", "normal", "wide", "very_wide"):
            self.assertEqual(detector_for(FOUR, spread=spread).halfFingersUp(), FOUR, spread)


class LeftClickByBendTest(unittest.TestCase):
    def setUp(self):
        self.rig = Rig()
        self.rig.open_palm()
        self.rig.feed(PEACE, frames=10)

    def lefts(self):
        return [c for c in self.rig.os.of("click") if c[1] == "left" and c[2] == 1]

    def test_holding_a_bend_is_one_left_click(self):
        self.rig.feed(PEACE, hand=BENT, frames=20)
        self.assertEqual(self.lefts(), [("click", "left", 1)])           # один раз, хотя сгиб держится долго
        self.assertEqual([c for c in self.rig.os.of("click") if c[1] == "right"], [])

    def test_can_click_again_after_straightening(self):
        self.rig.feed(PEACE, hand=BENT, frames=15)
        self.rig.feed(PEACE, frames=6)
        self.rig.feed(PEACE, hand=BENT, frames=15)
        self.assertEqual(len(self.lefts()), 2)

    def test_short_bend_is_not_a_click(self):
        self.rig.feed(PEACE, hand=BENT, frames=4)
        self.rig.feed(PEACE, frames=10)
        self.assertEqual(self.lefts(), [])

    def test_cursor_stays_while_bending(self):
        self.rig.feed(PEACE, at=(W * 0.35, H * 0.4), frames=40)
        before = self.rig.os.pos
        self.rig.feed(PEACE, at=(W * 0.35, H * 0.4), hand=BENT, frames=20)
        self.assertEqual(self.rig.os.pos, before)
        self.assertEqual(len(self.lefts()), 1)

    def test_no_double_click_when_bending_toward_middle_finger(self):
        def close(pts):
            pts = list(pts)
            pts[8] = (pts[12][0] - 10, pts[12][1] + 5)      # кончик указательного у среднего, как при сгибе в сторону
            return pts
        self.rig.feed(PEACE, hand=BENT, tweak=close, frames=20)
        self.assertEqual([c for c in self.rig.os.of("click") if c[2] == 2], [])

    def test_entering_v_with_finger_already_bent_does_not_click(self):
        rig = Rig()
        rig.open_palm()
        rig.feed(PEACE, hand=BENT, frames=20)               # сразу согнутым: сначала нужно выпрямить
        self.assertEqual([c for c in rig.os.of("click")], [])
        rig.feed(PEACE, frames=5)
        rig.feed(PEACE, hand=BENT, frames=15)
        self.assertEqual(len([c for c in rig.os.of("click") if c[1] == "left"]), 1)

    def test_folding_finger_fast_for_old_left_click_gives_exactly_one_click(self):
        rig = self.rig
        for bend in (30, 60, 90):                             # палец складывается за полсекунды
            rig.feed(PEACE, hand={"bend_index": bend}, frames=1)
        rig.feed(MIDDLE, frames=14)
        self.assertEqual(rig.os.of("click"), [("click", "left", 1)])           # не два (сгиб + старый жест)

    def test_old_gesture_index_only_still_right_click(self):
        rig = Rig()
        rig.open_palm()
        rig.feed(PEACE, frames=10)
        rig.feed(INDEX, frames=12)
        self.assertEqual(rig.os.of("click"), [("click", "right", 1)])

    def test_hud_shows_what_happened(self):
        frame = self.rig.feed(PEACE, hand=BENT, frames=20)
        self.assertGreater(int(np.count_nonzero(frame[:60, :500])), 0)
        self.assertEqual(self.rig.mouse._flash_label[0], "left_click")


class HandZoneTest(unittest.TestCase):
    def zone(self, rig, scale):
        palm = 100 * scale
        return rig.mouse.gesture.hand_zone(W, H, palm), palm

    def test_zone_margins_grow_with_hand_size(self):
        rig = Rig()
        small, _ = self.zone(rig, 0.8)
        big, _ = self.zone(rig, 1.6)
        self.assertGreater(big[1], small[1])                 # у крупной кисти верхняя граница ниже

    def test_hand_stays_fully_in_frame_at_the_top_and_side_limits(self):
        rig = Rig()
        for scale in (1.0, 1.6, 2.0):
            (left, top, right, bottom), palm = self.zone(rig, scale)
            pts = place(make_hand(PEACE, scale), 9, left, top)
            self.assertGreaterEqual(min(p[1] for p in pts), 0, scale)          # кончики пальцев не выше кадра
            self.assertGreaterEqual(min(p[0] for p in pts), 0, scale)
            pts = place(make_hand(PEACE, scale), 9, right, bottom)
            self.assertLessEqual(max(p[0] for p in pts), W, scale)
            self.assertLessEqual(max(p[1] for p in pts), H + 0.15 * palm, scale)   # запястье почти в кадре

    def test_every_screen_corner_is_reachable_while_hand_is_visible(self):
        rig = Rig()
        for scale in (1.0, 1.6, 2.0):
            (left, top, right, bottom), _ = self.zone(rig, scale)
            for (x, y, want) in ((left, top, (0, 0)), (right, bottom, (1919, 1079)), (left, bottom, (0, 1079)),
                                 (right, top, (1919, 0))):
                r = Rig()
                r.open_palm()
                r.feed(PEACE, at=(W // 2, H // 2), hand=None, frames=3, scale=scale)
                r.feed(PEACE, at=(x, y), frames=80, scale=scale)
                self.assertLess(abs(r.os.pos[0] - want[0]), 25, (scale, x, y, r.os.pos))
                self.assertLess(abs(r.os.pos[1] - want[1]), 25, (scale, x, y, r.os.pos))

    def test_zone_is_never_tiny(self):
        rig = Rig()
        left, top, right, bottom = rig.mouse.gesture.hand_zone(W, H, 100 * 6)      # кисть на весь кадр
        self.assertGreaterEqual(right - left, 0.18 * W - 1)
        self.assertGreaterEqual(bottom - top, 0.18 * H - 1)
        self.assertGreaterEqual(top, 0)
        self.assertLessEqual(bottom, H)

    def test_slider_margin_is_a_minimum_not_replaced(self):
        rig = Rig()
        rig.mouse.post("reach", 0.40)
        rig.open_palm()
        rig.feed(PEACE, frames=3)
        left, top, right, bottom = rig.mouse.gesture.hand_zone(W, H, 100)
        self.assertAlmostEqual(left, 0.40 * W, delta=1)

    def test_hint_when_hand_is_too_close(self):
        rig = Rig()
        rig.open_palm()
        frame = rig.feed(PEACE, frames=15, scale=2.4)           # ладонь 240 px из 720: больше 30% высоты кадра
        self.assertGreater(int(np.count_nonzero(frame[int(H * 0.9):, :, 2])), 100)

    def test_no_hint_for_normal_distance(self):
        rig = Rig()
        rig.open_palm()
        frame = rig.feed(PEACE, frames=15, scale=1.2)
        self.assertEqual(int(np.count_nonzero(frame[int(H * 0.9):, :, 2])), 0)


if __name__ == "__main__":
    unittest.main()
