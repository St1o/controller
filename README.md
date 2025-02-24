# Распознавание жестов для управления компьютера с помощью жестов - ComputeController

## Описание проекта

Репозиторий содержит исходный код для системы управления компьютером с помощью жестов. Проект использует распознавание жестов для выполнения различных действий, таких как перемещение мыши, клики, управление громкостью и введение текста через виртуальную клавиатуру. Реализовано с использованием Python, OpenCV, PyQt5 и других библиотек.

## Возможности 

- Управление курсором мыши с помощью жестов руки;
  
- Клики мышью: левая, правая и двойной клик;
  
- Управление громкостью системы с помощью расстояния между пальцами;
  
- Виртуальная клавиатура для ввода текста с помощью жестов;
  
- Простая отрисовка графики через жесты;
  
- Графический интерфейс с PyQt5 для управления функциями.

## Требования

- Python 3.8+

- Установленные библиотеки из requirements.txt

- NVIDIA GPU с поддержкой CUDA (рекомендуется для работы OpenCV)

- Веб-камера для захвата изображений в реальном времени

## Установка

Клонируйте репозиторий:

```python
git clone <ссылка на репозиторий>
cd <имя папки>
```

Установите зависимости:

```python
pip install -r requirements.txt
```

## Инструкция по запуску

1. Выберите камеру с которой будет транслироваться видео 
2. Запустите стартовый файл:

```python
python main.py
```

