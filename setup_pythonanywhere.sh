#!/bin/bash
# setup_pythonanywhere.sh - Скрипт быстрой настройки на PythonAnywhere

echo "=== Установка зависимостей ==="
pip install --user Flask==2.3.3 Werkzeug==2.3.7 openpyxl==3.1.2

echo "=== Инициализация базы данных и пользователей ==="
python3 create_users.py

echo "=== Готово! ==="
