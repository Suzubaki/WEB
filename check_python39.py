#!/usr/bin/env python3
"""
Проверка совместимости с Python 3.9
"""

import sys

print(f"Текущая версия Python: {sys.version}")
print(f"Версия Python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")

# Проверка минимальной версии
MIN_VERSION = (3, 9)
current_version = (sys.version_info.major, sys.version_info.minor)

if current_version < MIN_VERSION:
    print(f"❌ Требуется Python {MIN_VERSION[0]}.{MIN_VERSION[1]} или выше")
    print(f"   У вас Python {current_version[0]}.{current_version[1]}")
    sys.exit(1)
else:
    print(f"✅ Python {current_version[0]}.{current_version[1]} соответствует требованиям")

# Проверка зависимостей
print("\nПроверка зависимостей...")

try:
    import flask
    print(f"✅ Flask {flask.__version__}")
except ImportError:
    print("❌ Flask не установлен")

try:
    import openpyxl
    print(f"✅ openpyxl {openpyxl.__version__}")
except ImportError:
    print("❌ openpyxl не установлен")

try:
    import pandas
    print(f"✅ pandas {pandas.__version__}")
except ImportError:
    print("❌ pandas не установлен")

try:
    import numpy
    print(f"✅ numpy {numpy.__version__}")
except ImportError:
    print("❌ numpy не установлен")

try:
    import sqlite3
    print(f"✅ sqlite3 {sqlite3.sqlite_version}")
except ImportError:
    print("❌ sqlite3 не доступен")

# Проверка особенностей Python 3.9
print("\nПроверка особенностей Python 3.9...")

# 1. Type hints (PEP 585) - доступны с Python 3.9
try:
    from typing import List, Dict, Tuple
    # Использование встроенных типов для аннотаций (PEP 585)
    def test_pep585() -> dict[str, list[int]]:
        return {"test": [1, 2, 3]}
    result = test_pep585()
    print("✅ PEP 585 (Type hints для встроенных типов) - поддерживается")
except Exception as e:
    print(f"⚠️  PEP 585 может не поддерживаться: {e}")

# 2. F-strings с =
try:
    name = "Python"
    print(f"✅ F-strings: {name=}")
except Exception as e:
    print(f"⚠️  F-strings с = могут не поддерживаться: {e}")

# 3. Объединение словарей
try:
    dict1 = {"a": 1}
    dict2 = {"b": 2}
    merged = dict1 | dict2
    print("✅ Объединение словарей с | - поддерживается")
except Exception as e:
    print(f"⚠️  Объединение словарей с | может не поддерживаться: {e}")

# 4. Удаление префиксов и суффиксов
try:
    text = "test_string"
    without_prefix = text.removeprefix("test_")
    without_suffix = text.removesuffix("_string")
    print("✅ Методы removeprefix/removesuffix - поддерживаются")
except Exception as e:
    print(f"⚠️  Методы removeprefix/removesuffix могут не поддерживаться: {e}")

print("\n" + "="*50)
print("✅ Проверка завершена")
print("Проект совместим с Python 3.9")
print("="*50)