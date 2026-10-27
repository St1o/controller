"""Виртуальная клавиатура: раскладки и логика клавиш (диплом, раздел 3.5).

Рисует клавиатуру окно osk.py: это настоящее окно поверх рабочего стола, которое не забирает фокус,
поэтому текст печатается туда, где стоит текстовый курсор. Здесь только то, что не зависит от Qt:
раскладки RU/EN и модель клавиатуры (регистр, язык, что напечатано), её удобно проверять тестами.

Служебные клавиши: SH - регистр, LN - язык (RU/EN), EN - Enter, CL - очистить строку на экране, BS - стереть символ.
"""
from SystemInput import SystemInput

_DIGITS = list("1234567890-=")
CONTROL_ROW = [" ", "SH", "LN", "EN", "CL", "BS"]
# Раскладки как в дипломе: буквы заглавными, регистр переключается клавишей SH
en_keys = [_DIGITS, list("QWERTYUIOP[]"), list("ASDFGHJKL;'*"), list("ZXCVBNM,./?$"), CONTROL_ROW]
ru_keys = [_DIGITS, list("ЙЦУКЕНГШЩЗХЪ"), list("ФЫВАПРОЛДЖЭ;"), list("ЯЧСМИТЬБЮ,.?"), CONTROL_ROW]
CONTROL_NAMES = ("SH", "LN", "EN", "CL", "BS")


def apply_case(rows, upper):
    """Буквы и подписи служебных клавиш в нужном регистре."""
    return [[k.upper() if upper else k.lower() for k in row] for row in rows]


def is_control(text):
    return text.upper() in CONTROL_NAMES


class KeyboardModel:
    def __init__(self, os_input=None):
        self.os = os_input or SystemInput()
        self.lang = "ru"
        self.upper = True
        self.finalText = ""

    @property
    def register(self):
        return "upper" if self.upper else "lower"

    def keys(self):
        """Текущая раскладка с учётом языка и регистра."""
        return apply_case(ru_keys if self.lang == "ru" else en_keys, self.upper)

    def press(self, text):
        """Нажать клавишу с подписью text. Возвращает имя действия."""
        name = text.upper()
        if name == "SH":
            self.upper = not self.upper
            return "shift"
        if name == "LN":
            self.lang = "en" if self.lang == "ru" else "ru"
            return "language"
        if name == "EN":
            self.os.press("enter")
            return "enter"
        if name == "CL":
            self.finalText = ""
            return "clear"
        if name == "BS":
            self.os.press("backspace")
            self.finalText = self.finalText[:-1]
            return "backspace"
        self.os.type_text(text)
        self.finalText += text
        return "char"
