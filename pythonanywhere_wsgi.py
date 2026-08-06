#!/usr/bin/env python3
"""
WSGI файл для PythonAnywhere - основной вариант
Этот файл должен быть указан как WSGI конфигурация на PythonAnywhere
"""

import sys
import os

# Путь к проекту - ВАЖНО: именно так!
project_home = '/home/Suzubaki/livestock_accounting'

# Добавляем путь в sys.path
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Устанавливаем рабочую директорию
os.chdir(project_home)

# Теперь импортируем наше приложение
from app import app as application

# Устанавливаем секретный ключ
application.secret_key = 'your-production-secret-key-change-this-12345'

print(f"✅ WSGI файл загружен успешно")
print(f"   Путь к проекту: {project_home}")
print(f"   sys.path: {sys.path[:2]}...")