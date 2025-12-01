@echo off
D:
cd \dev\microphone

REM Активация виртуального окружения
call .venv\Scripts\activate.bat

REM Установка зависимостей
pip install -r requirements.txt

REM Запуск программы
python main.py
