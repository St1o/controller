import unittest

import numpy as np

from WorkingHand import handDetector
from handSketch import make_hand, place
from tests.helpers import FakeBackend, H, W

GESTURES = {
    "palm": [1, 1, 1, 1, 1], "four": [0, 1, 1, 1, 1], "peace": [0, 1, 1, 0, 0], "middle": [0, 0, 1, 0, 0],
    "index": [0, 1, 0, 0, 0], "fist": [0, 0, 0, 0, 0], "gun": [1, 1, 0, 0, 0], "three": [0, 1, 1, 1, 0],
    "rock": [0, 1, 0, 0, 1],
}


class FingersTest(unittest.TestCase):
    def detect(self, fingers, scale):
        backend = FakeBackend()
        det = handDetector(backend=backend)
        backend.points = place(make_hand(fingers, scale), 9, W // 2, H // 2)
        img = np.zeros((H, W, 3), np.uint8)
        det.findHands(img, draw=False)
        det.findPosition(img, draw=False)
        return det

    def test_every_gesture_at_several_distances(self):
        for name, fingers in GESTURES.items():
            for scale in (0.8, 1.6, 2.4):
                det = self.detect(fingers, scale)
                self.assertEqual(det.fingersUp(), fingers, "%s x%s строгий" % (name, scale))
                self.assertEqual(det.halfFingersUp(), fingers, "%s x%s мягкий" % (name, scale))

    def test_no_hand_gives_empty_list(self):
        det = handDetector(backend=FakeBackend())
        lm, bbox = det.findPosition(det.findHands(np.zeros((H, W, 3), np.uint8)), draw=False)
        self.assertEqual(lm, [])
        self.assertEqual(bbox, [])

    def test_hand_size_does_not_depend_on_fingers(self):
        sizes = {round(self.detect(f, 1.6).handSize()) for f in GESTURES.values()}
        self.assertEqual(len(sizes), 1)

    def test_find_distance_returns_length_and_center(self):
        det = self.detect([0, 1, 1, 0, 0], 1.6)
        img = np.zeros((H, W, 3), np.uint8)
        length, _, info = det.findDistance(8, 12, img, draw=False)
        self.assertGreater(length, 0)
        self.assertEqual(len(info), 6)

    def test_left_hand_mirrored_still_works(self):
        """Зеркальная (левая) рука: большой палец считается по стороне ладони, а не по правой/левой."""
        for name, fingers in GESTURES.items():
            backend = FakeBackend()
            det = handDetector(backend=backend)
            pts = place(make_hand(fingers, 1.6), 9, 0, 0)
            backend.points = [(W // 2 - x, H // 2 + y) for x, y in pts]
            img = np.zeros((H, W, 3), np.uint8)
            det.findHands(img, draw=False)
            det.findPosition(img, draw=False)
            self.assertEqual(det.fingersUp(), fingers, name)


if __name__ == "__main__":
    unittest.main()
