#!/usr/bin/env python3
"""
Упрощенный WSGI файл для PythonAnywhere
Используйте этот файл, если есть проблемы с основным
"""

import sys
import os

# Указываем путь к проекту
path = '/home/Suzubaki/livestock_accounting'

# Добавляем путь в sys.path
if path not in sys.path:
    sys.path.insert(0, path)

# Устанавливаем рабочую директорию
os.chdir(path)

# Импортируем приложение
try:
    from app import app as application
    print("✅ Приложение успешно импортировано")
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    print("Проверьте: app.py, пути, зависимости")
    raise

# Устанавливаем секретный ключ
application.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

print(f"WSGI загружен: {path}")