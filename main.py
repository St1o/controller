import cv2
from PyQt5.QtWidgets import QMainWindow
from ui_main import Ui_MainWindow
import AIVirtualMouseVer2
import autopy

wCam, hCam = 640, 480  # Разрешение камеры
frameR = 100  # Пограничная зона для жестов
wScr, hScr = autopy.screen.size()  # Размеры экрана

class MainWindow(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.ui.webcam_btn.clicked.connect(self.show_webcam_page)
        self.ui.instruction_btn.clicked.connect(self.show_instruction_page)
        self.ui.about_btn.clicked.connect(self.show_about_page)
        self.ui.pushButton.clicked.connect(self.slideLeftMenu)

        self.ui.stackedWidget.setCurrentWidget(self.ui.about_page)

        self.cap = cv2.VideoCapture(0)
        self.show()

    def closeEvent(self, event):
        self.cap.release()
        cv2.destroyAllWindows()

    def show_webcam_page(self):
        self.ui.stackedWidget.setCurrentWidget(self.ui.webcam_page)

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, wCam)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, hCam)

        AIVirtualMouseVer2.main(self.ui, self.cap)

        self.cap.release()
        cv2.destroyAllWindows()

    def show_instruction_page(self):
        self.ui.stackedWidget.setCurrentWidget(self.ui.instruction_page)

    def show_about_page(self):
        self.ui.stackedWidget.setCurrentWidget(self.ui.about_page)

    def slideLeftMenu(self):
        # Метод для анимации меню
        pass
