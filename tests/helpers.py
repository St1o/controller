"""Общие заготовки для тестов: поддельные ОС и камера, рука из нарисованных точек."""
import numpy as np

from AiVirtualMouse import VirtualMouse
from WorkingHand import handDetector
from handSketch import make_hand, place

W, H = 1280, 720


class FakeInput:
    """Вместо pyautogui и pynput: запоминает, что программа попросила сделать."""

    def __init__(self, screen=(1920, 1080)):
        self.enabled = True
        self.screen = screen
        self.pos = (960, 540)
        self.calls = []

    def screen_size(self):
        return self.screen

    def position(self):
        return self.pos

    def move(self, x, y):
        if self.enabled:
            self.pos = (x, y)
            self.calls.append(("move", round(x), round(y)))

    def click(self, button="left", clicks=1):
        if self.enabled:
            self.calls.append(("click", button, clicks))

    def mouse_down(self, button="left"):
        if self.enabled:
            self.calls.append(("down", button))

    def mouse_up(self, button="left"):
        self.calls.append(("up", button))

    def scroll(self, amount):
        if self.enabled:
            self.calls.append(("scroll", amount))

    def type_text(self, text):
        if self.enabled:
            self.calls.append(("type", text))

    def press(self, key):
        if self.enabled:
            self.calls.append(("press", key))

    def of(self, kind):
        return [c for c in self.calls if c[0] == kind]


class FakeBackend:
    """Вместо mediapipe: отдаёт заранее заданные точки руки (в пикселях кадра)."""
    name = "fake"

    def __init__(self):
        self.points = None

    def detect(self, rgb):
        if self.points is None:
            return []
        h, w = rgb.shape[:2]
        return [[(x / w, y / h, 0.0) for x, y in self.points]]

    def close(self):
        pass


class Rig:
    """Программа целиком с поддельными камерой и ОС. feed() показывает жест несколько кадров подряд."""

    def __init__(self, fps=30.0):
        self.os = FakeInput()
        self.backend = FakeBackend()
        self.time = 0.0
        self.dt = 1.0 / fps
        self.requests = []      # что жесты попросили показать окно: 'keyboard'
        self.mouse = VirtualMouse(detector=handDetector(backend=self.backend), os_input=self.os,
                                  clock=lambda: self.time, on_request=self.requests.append)
        self.frame = None

    @property
    def state(self):
        return self.mouse.old_combo

    def feed(self, fingers, at=(W // 2, H // 2), frames=12, scale=1.6, anchor=9, tweak=None, hand=None):
        """Показать жест fingers; точка anchor руки стоит в at. tweak(points) может подправить точки."""
        for _ in range(frames):
            pts = place(make_hand(fingers, scale, **(hand or {})), anchor, *at)
            if tweak:
                pts = tweak(pts)
            self.backend.points = pts
            self.time += self.dt
            self.frame = self.mouse.process(np.zeros((H, W, 3), np.uint8))
        return self.frame

    def no_hand(self, frames=3):
        self.backend.points = None
        for _ in range(frames):
            self.time += self.dt
            self.frame = self.mouse.process(np.zeros((H, W, 3), np.uint8))
        return self.frame

    def open_palm(self):
        return self.feed([1, 1, 1, 1, 1], frames=4)
