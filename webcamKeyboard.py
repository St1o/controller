import cv2
import pyautogui
from pynput.keyboard import Controller
import time
import cvzone
import numpy as np

keyboard = Controller()

class Button():
    def __init__(self, pos, text, size=[85, 85]):
        self.pos = pos
        self.size = size
        self.text = text

def drawAll(img, buttonList):
    imgNew = np.zeros_like(img, np.uint8)
    for button in buttonList:
        x, y = button.pos

        cvzone.cornerRect(imgNew, (button.pos[0], button.pos[1], button.size[0], button.size[1]), 20, rt=0)

        cv2.rectangle(imgNew, button.pos, (x + button.size[0], y + button.size[1]), (255, 51, 102), cv2.FILLED)
        cv2.putText(img, button.text, (x + 6, y + 62), cv2.FONT_HERSHEY_COMPLEX, 2, (255, 255, 255), 2)

    out = img.copy()
    alpha = 0.5
    mask = imgNew.astype(bool)
    out[mask] = cv2.addWeighted(img, alpha, imgNew, 1 - alpha, 0)[mask]

    return out

def addButtonList(buttonList, keys):
    for i in range(len(keys)):
        for j, key in enumerate(keys[i]):
            buttonList.append(Button([100 * j + 50, 100 * i + 50], key))

def main(img, lmList, detector, keys, ru_keys, en_keys, finalText, register):
    buttonList = []
    addButtonList(buttonList, keys)

    new_img = drawAll(img, buttonList)

    if lmList:
        for button in buttonList:
            x, y = button.pos
            w, h = button.size

            if x < lmList[8][1] < x + w and y < lmList[8][2] < y + h:
                cv2.rectangle(new_img, button.pos, (x + w, y + h), (255, 51, 102), cv2.FILLED)
                cv2.putText(new_img, button.text, (x + 20, y + 64), cv2.FONT_HERSHEY_COMPLEX, 2, (255, 255, 255), 2)

                l, _, _ = detector.findDistance(4, 8, img, draw=True)
                if l < 40:
                    if button.text == "SH" or button.text == "sh":
                        if button.text == "SH":
                            keys = [[x.lower() for x in y] for y in keys]
                            register = "lower"
                        else:
                            keys = [[x.upper() for x in y] for y in keys]
                            register = "upper"
                    elif button.text == "CL" or button.text == "cl":
                        finalText = ""
                    elif button.text == "EN" or button.text == "en":
                        pyautogui.press('enter')
                    elif button.text == "LN" or button.text == "ln":
                        if keys == ru_keys:
                            keys = en_keys
                        elif ru_keys == [[x.upper() for x in y] for y in keys]:
                            keys = [[x.lower() for x in y] for y in en_keys]
                        elif keys == en_keys:
                            keys = ru_keys
                        elif en_keys == [[x.upper() for x in y] for y in keys]:
                            keys = [[x.lower() for x in y] for y in ru_keys]
                    else:
                        keyboard.press(button.text)
                        cv2.rectangle(new_img, button.pos, (x + w, y + h), (0, 255, 0), cv2.FILLED)
                        cv2.putText(new_img, button.text, (x + 20, y + 64), cv2.FONT_HERSHEY_COMPLEX, 2,
                                    (255, 255, 255), 2)
                        finalText += button.text
                    time.sleep(0.3)

    cv2.rectangle(new_img, (50, 450), (1240, 550), (255, 51, 102), cv2.FILLED)
    cv2.putText(new_img, finalText, (60, 530), cv2.FONT_HERSHEY_COMPLEX, 2, (255, 255, 255), 2)

    return new_img, finalText, keys
