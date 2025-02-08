import cv2
import pyautogui
from GestureFunction import CollectionGesture


def main(detector, cap):
    old_combo = ""
    basic_lenght_finger = 50

    while True:
        success, img = cap.read()
        img = detector.findHands(img)
        lmList, bbox = detector.findPosition(img, draw=False)

        if lmList:
            x1, y1 = lmList[12][1:]
            changeable_lenght_finger = detector.findDistance(11, 12, img, draw=False)[0]
            fingers = detector.halfFingersUp()

            if fingers == [1, 1, 1, 1, 1]:
                if old_combo == "took":
                    pyautogui.mouseUp(button="left")
                basic_lenght_finger = CollectionGesture().basic(img, detector)
                old_combo = "basic"

            elif fingers == [0, 1, 1, 0,
                             0] and changeable_lenght_finger + 10 > basic_lenght_finger and old_combo not in [
                "keyboard_mode", "ai_keyboard", "ai_painter"]:
                CollectionGesture().moveMouse(img, detector, x1, y1)
                old_combo = "move_mouse"

            elif fingers == [0, 1, 1, 0, 0] and old_combo == "move_mouse":
                CollectionGesture().double_click(img, detector, x1, y1)

            elif fingers == [0, 0, 1, 0, 0] and old_combo == "move_mouse":
                CollectionGesture().left_click()
                old_combo = "left_click"

            elif fingers == [0, 1, 0, 0, 0] and old_combo == "move_mouse":
                CollectionGesture().right_click()
                old_combo = "right_click"

            elif fingers == [1, 1, 0, 0, 0] and old_combo in ["basic", "volume_control"]:
                CollectionGesture().volume_control(img, lmList)
                old_combo = "volume_control"

        cv2.imshow("Image", img)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break