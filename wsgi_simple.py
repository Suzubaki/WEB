#!/usr/bin/env python3
"""
Упрощенный WSGI файл для PythonAnywhere
"""

import sys
import os

# Путь к проекту
project_home = '/home/Suzubaki/livestock_accounting'

# Добавляем путь в sys.path
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Меняем рабочую директорию
os.chdir(project_home)

# Импортируем приложение
from app import app as application

# Секретный ключ
application.secret_key = 'your-production-secret-key-change-this'