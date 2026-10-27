import unittest

import numpy as np

from AiPainter import PALETTE, AiPainter
from tests.helpers import H, Rig, W

PEACE, INDEX, ROCK, FOUR = [0, 1, 1, 0, 0], [0, 1, 0, 0, 0], [0, 1, 0, 0, 1], [0, 1, 1, 1, 1]
MIDDLE, FIST = [0, 0, 1, 0, 0], [0, 0, 0, 0, 0]


def open_painter(rig):
    rig.feed(ROCK, frames=30)
    return rig.state


class PainterTest(unittest.TestCase):
    def setUp(self):
        self.rig = Rig()
        self.rig.open_palm()
        self.assertEqual(open_painter(self.rig), "ai_painter")

    def painter_buttons(self):
        return self.rig.mouse.painter.buttons(np.zeros((H, W, 3), np.uint8))

    def test_index_finger_draws_line_on_canvas(self):
        rig = self.rig
        for i in range(10):
            rig.feed(INDEX, at=(300 + i * 40, 420), anchor=8, frames=1)
        self.assertGreater(int(np.count_nonzero(rig.mouse.painter.imgCanvas)), 500)
        self.assertEqual(rig.os.calls, [])             # в рисовалке мышь не двигается

    def test_two_fingers_do_not_draw(self):
        rig = self.rig
        for i in range(10):
            rig.feed(PEACE, at=(300 + i * 40, 420), anchor=8, frames=1)
        self.assertEqual(int(np.count_nonzero(rig.mouse.painter.imgCanvas)), 0)

    def test_cannot_draw_on_palette_and_title_strip(self):
        rig = self.rig
        for i in range(10):
            rig.feed(INDEX, at=(300 + i * 40, 60), anchor=8, frames=1)
        self.assertEqual(int(np.count_nonzero(rig.mouse.painter.imgCanvas)), 0)

    def test_two_fingers_over_palette_pick_color(self):
        rig = self.rig
        step = W / len(PALETTE)
        rig.feed(PEACE, at=(step * 3.5, 40), anchor=8, frames=10)
        self.assertEqual(rig.mouse.painter.drawColor, PALETTE[3])
        rig.feed(PEACE, at=(step * 5.5, 40), anchor=8, frames=10)
        self.assertEqual(rig.mouse.painter.drawColor, PALETTE[5])

    def test_eraser_removes_drawing(self):
        painter = AiPainter()
        img = np.zeros((H, W, 3), np.uint8)
        lm = [[i, 0, 0] for i in range(21)]
        for x in range(300, 500, 20):
            lm[8][1:] = [x, 400]
            lm[12][1:] = [x, 380]
            painter.main(img.copy(), lm, [0, 1, 0, 0, 0], now=0.0)
        before = int(np.count_nonzero(painter.imgCanvas))
        self.assertGreater(before, 0)
        painter.drawColor = (0, 0, 0)
        painter.xp = painter.yp = 0
        for x in range(300, 500, 20):
            lm[8][1:] = [x, 400]
            painter.main(img.copy(), lm, [0, 1, 0, 0, 0], now=0.0)
        self.assertLess(int(np.count_nonzero(painter.imgCanvas)), before)

    def test_four_fingers_leave_painter(self):
        self.rig.feed(FOUR, frames=30)
        self.assertEqual(self.rig.state, "basic")

    def test_drawing_stays_after_leaving(self):
        rig = self.rig
        for i in range(10):
            rig.feed(INDEX, at=(300 + i * 40, 420), anchor=8, frames=1)
        rig.feed(FOUR, frames=30)
        self.assertGreater(int(np.count_nonzero(rig.mouse.painter.imgCanvas)), 0)

    # --- кнопка «Назад» и «Очистить»: нажимаются удержанием кончика указательного пальца
    def hold_on(self, name, seconds):
        x, y, w, h = self.painter_buttons()[name]
        self.rig.feed(INDEX, at=(x + w / 2, y + h / 2), anchor=8, frames=int(seconds * 30))

    def test_back_button_needs_hold_and_leaves_painter(self):
        rig = self.rig
        self.hold_on("back", 0.5)                       # короткое касание не выходит
        self.assertEqual(rig.state, "ai_painter")
        self.hold_on("back", 1.0)
        self.assertEqual(rig.state, "basic")

    def test_back_button_works_with_two_fingers_too(self):
        rig = self.rig
        x, y, w, h = self.painter_buttons()["back"]
        rig.feed(PEACE, at=(x + w / 2, y + h / 2), anchor=8, frames=50)
        self.assertNotEqual(rig.state, "ai_painter")       # вышли; V-жест после выхода снова двигает курсор

    def test_clear_button_erases_canvas(self):
        rig = self.rig
        for i in range(10):
            rig.feed(INDEX, at=(300 + i * 40, 420), anchor=8, frames=1)
        self.assertGreater(int(np.count_nonzero(rig.mouse.painter.imgCanvas)), 0)
        self.hold_on("clear", 1.6)
        self.assertEqual(int(np.count_nonzero(rig.mouse.painter.imgCanvas)), 0)
        self.assertEqual(rig.state, "ai_painter")       # из режима не вышли

    def test_hand_resting_on_button_does_not_repeat(self):
        rig = self.rig
        for i in range(10):
            rig.feed(INDEX, at=(300 + i * 40, 420), anchor=8, frames=1)
        self.hold_on("clear", 1.6)                       # нажалось один раз
        for i in range(10):                              # рисуем заново...
            rig.feed(INDEX, at=(300 + i * 40, 420), anchor=8, frames=1)
        canvas = int(np.count_nonzero(rig.mouse.painter.imgCanvas))
        self.assertGreater(canvas, 0)

    def test_title_is_drawn_on_frame(self):
        frame = self.rig.feed(INDEX, at=(600, 420), anchor=8, frames=2)
        head = int(H * 0.14)
        strip = frame[head:head + int(H * 0.09), W // 3:2 * W // 3]
        self.assertGreater(int(np.count_nonzero(strip > 200)), 200)      # белые буквы названия на тёмной панели

    def test_painter_button_in_window_opens_it_from_any_state(self):
        rig = Rig()
        rig.open_palm()
        rig.feed(PEACE, frames=10)
        rig.mouse.post("painter", True)
        rig.feed(PEACE, frames=2)
        self.assertEqual(rig.state, "ai_painter")
        rig.mouse.post("painter", False)
        rig.feed(PEACE, frames=2)
        self.assertNotEqual(rig.state, "ai_painter")


class OpenFromAnyStateTest(unittest.TestCase):
    def test_rock_opens_painter_after_right_click(self):
        """Было: рисовалка не открывалась, если до этого был клик. Теперь открывается из любого состояния."""
        rig = Rig()
        rig.open_palm()
        rig.feed(PEACE, frames=10)
        rig.feed(INDEX, frames=12)
        self.assertEqual(rig.state, "right_click")
        rig.feed(ROCK, frames=30)
        self.assertEqual(rig.state, "ai_painter")

    def test_rock_opens_painter_from_move_and_left_click(self):
        for first in (PEACE, MIDDLE):
            rig = Rig()
            rig.open_palm()
            rig.feed(PEACE, frames=10)
            if first is MIDDLE:
                rig.feed(MIDDLE, frames=12)
            rig.feed(ROCK, frames=30)
            self.assertEqual(rig.state, "ai_painter", first)

    def test_rock_does_not_open_while_dragging(self):
        rig = Rig()
        rig.open_palm()
        rig.feed(PEACE, frames=10)
        rig.feed(FIST, frames=25)
        self.assertEqual(rig.state, "took")
        rig.feed(ROCK, frames=40)
        self.assertEqual(rig.state, "took")

    def test_rock_works_with_thumb_out_or_in(self):
        for thumb in (0, 1):
            rig = Rig()
            rig.open_palm()
            rig.feed([thumb, 1, 0, 0, 1], frames=30)
            self.assertEqual(rig.state, "ai_painter", thumb)

    def test_short_rock_flash_does_not_open(self):
        rig = Rig()
        rig.open_palm()
        rig.feed(ROCK, frames=8)
        self.assertEqual(rig.state, "basic")


if __name__ == "__main__":
    unittest.main()
