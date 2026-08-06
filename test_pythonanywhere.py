#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы на PythonAnywhere
Запустите этот скрипт в консоли PythonAnywhere для проверки
"""

import sys
import os

print("Тестирование окружения PythonAnywhere")
print("=" * 50)

# Проверка Python версии
print(f"Python версия: {sys.version}")
print(f"Python info: {sys.version_info}")

# Проверка путей
print(f"\nТекущая директория: {os.getcwd()}")
print(f"sys.path: {sys.path}")

# Проверка проекта
project_home = '/home/Suzubaki/livestock_accounting'
print(f"\nПроект должен быть в: {project_home}")
print(f"Существует ли папка: {os.path.exists(project_home)}")

if os.path.exists(project_home):
    print("Содержимое папки проекта:")
    try:
        files = os.listdir(project_home)
        for file in files[:10]:  # Покажем первые 10 файлов
            print(f"  - {file}")
        if len(files) > 10:
            print(f"  ... и еще {len(files) - 10} файлов")
    except Exception as e:
        print(f"  Ошибка при чтении папки: {e}")

# Проверка импорта приложения
print("\nПопытка импорта приложения...")
try:
    # Добавляем путь если нужно
    if project_home not in sys.path:
        sys.path.insert(0, project_home)
    
    from app import app
    print("✅ Приложение успешно импортировано")
    print(f"   Имя приложения: {app.name}")
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    print("\nВозможные причины:")
    print("1. Файл app.py не в правильной папке")
    print("2. Ошибки в коде app.py")
    print("3. Не хватает зависимостей")
except Exception as e:
    print(f"❌ Другая ошибка: {e}")

# Проверка зависимостей
print("\nПроверка основных зависимостей...")
dependencies = ['flask', 'sqlite3', 'openpyxl', 'pandas']

for dep in dependencies:
    try:
        module = __import__(dep)
        print(f"✅ {dep}: {getattr(module, '__version__', 'версия неизвестна')}")
    except ImportError:
        print(f"❌ {dep}: не установлен")

print("\n" + "=" * 50)
print("Инструкция по устранению проблем:")

if not os.path.exists(project_home):
    print("1. Создайте папку: /home/Suzubaki/livestock_accounting/")
    print("2. Загрузите файлы проекта в эту папку")

print("""
Если есть ошибки импорта:
1. Убедитесь, что app.py находится в правильной папке
2. Проверьте, нет ли синтаксических ошибок в app.py
3. Установите зависимости: pip install -r requirements.txt

Если приложение импортируется, но не работает:
1. Проверьте WSGI конфигурацию
2. Проверьте логи ошибок на PythonAnywhere
3. Убедитесь, что статические файлы настроены правильно
""")

print("=" * 50)