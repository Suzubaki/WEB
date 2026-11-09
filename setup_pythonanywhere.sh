#!/bin/bash
# setup_pythonanywhere.sh - Скрипт быстрой настройки на PythonAnywhere

echo "=== Установка всех зависимостей ==="
pip install --user -r requirements.txt

echo "=== Инициализация базы данных и пользователей ==="
python3 create_users.py

echo "=== Запуск проверки системы ==="
python3 check_system.py

echo "=== Готово к запуску! ==="
