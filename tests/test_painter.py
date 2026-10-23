import unittest

import numpy as np

from AiPainter import PALETTE, AiPainter
from tests.helpers import H, Rig, W

PEACE, INDEX, ROCK, FOUR = [0, 1, 1, 0, 0], [0, 1, 0, 0, 0], [0, 1, 0, 0, 1], [0, 1, 1, 1, 1]


class PainterTest(unittest.TestCase):
    def setUp(self):
        self.rig = Rig()
        self.rig.open_palm()
        self.rig.feed(ROCK, frames=14)
        self.assertEqual(self.rig.state, "ai_painter")

    def test_index_finger_draws_line_on_canvas(self):
        rig = self.rig
        for i in range(10):
            rig.feed(INDEX, at=(300 + i * 40, 400), anchor=8, frames=1)
        canvas = rig.mouse.painter.imgCanvas
        self.assertGreater(int(np.count_nonzero(canvas)), 500)
        self.assertEqual(rig.os.calls, [])             # в рисовалке мышь не двигается

    def test_two_fingers_do_not_draw(self):
        rig = self.rig
        for i in range(10):
            rig.feed(PEACE, at=(300 + i * 40, 400), anchor=8, frames=1)
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
            painter.main(img.copy(), lm, [0, 1, 0, 0, 0])
        before = int(np.count_nonzero(painter.imgCanvas))
        self.assertGreater(before, 0)
        painter.drawColor = (0, 0, 0)
        painter.reset()
        for x in range(300, 500, 20):
            lm[8][1:] = [x, 400]
            painter.main(img.copy(), lm, [0, 1, 0, 0, 0])
        self.assertLess(int(np.count_nonzero(painter.imgCanvas)), before)

    def test_four_fingers_leave_painter(self):
        self.rig.feed(FOUR, frames=14)
        self.assertEqual(self.rig.state, "basic")

    def test_drawing_stays_after_leaving(self):
        rig = self.rig
        for i in range(10):
            rig.feed(INDEX, at=(300 + i * 40, 400), anchor=8, frames=1)
        rig.feed(FOUR, frames=14)
        self.assertGreater(int(np.count_nonzero(rig.mouse.painter.imgCanvas)), 0)


if __name__ == "__main__":
    unittest.main()
