#!/bin/bash
# Скрипт для настройки на PythonAnywhere
# Запустите в консоли PythonAnywhere

echo "Настройка проекта на PythonAnywhere..."
echo "======================================"

# 1. Проверка Python версии
echo "1. Проверка версии Python..."
python --version

# 2. Создание папки если не существует
echo "2. Проверка папки проекта..."
if [ ! -d "/home/Suzubaki/livestock_accounting" ]; then
    echo "  Создаю папку /home/Suzubaki/livestock_accounting..."
    mkdir -p /home/Suzubaki/livestock_accounting
else
    echo "  Папка уже существует"
fi

# 3. Проверка файлов
echo "3. Проверка необходимых файлов..."
cd /home/Suzubaki/livestock_accounting 2>/dev/null || { echo "Ошибка: не могу перейти в папку"; exit 1; }

required_files=("app.py" "requirements.txt" "pythonanywhere_wsgi.py")
missing_files=0

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✅ $file"
    else
        echo "  ❌ $file - ОТСУТСТВУЕТ"
        missing_files=1
    fi
done

if [ $missing_files -eq 1 ]; then
    echo "  ❌ Некоторые файлы отсутствуют. Загрузите их сначала."
    exit 1
fi

# 4. Установка зависимостей
echo "4. Установка зависимостей..."
if [ -f "requirements.txt" ]; then
    echo "  Устанавливаю зависимости из requirements.txt..."
    pip install -r requirements.txt
    if [ $? -eq 0 ]; then
        echo "  ✅ Зависимости установлены"
    else
        echo "  ❌ Ошибка при установке зависимостей"
        exit 1
    fi
else
    echo "  ❌ Файл requirements.txt не найден"
    exit 1
fi

# 5. Проверка импорта приложения
echo "5. Проверка импорта приложения..."
python -c "
import sys
sys.path.insert(0, '/home/Suzubaki/livestock_accounting')
try:
    from app import app
    print('  ✅ Приложение успешно импортировано')
except ImportError as e:
    print(f'  ❌ Ошибка импорта: {e}')
    exit(1)
except Exception as e:
    print(f'  ❌ Другая ошибка: {e}')
    exit(1)
"

# 6. Создание базы данных
echo "6. Инициализация базы данных..."
python -c "
import sys
sys.path.insert(0, '/home/Suzubaki/livestock_accounting')
try:
    from database import init_db
    init_db()
    print('  ✅ База данных инициализирована')
    
    # Проверка создания тестовых пользователей
    import sqlite3
    conn = sqlite3.connect('livestock.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    count = cursor.fetchone()[0]
    conn.close()
    
    if count == 0:
        print('  ⚠️  В базе нет пользователей')
        print('  После запуска приложения создадутся тестовые пользователи:')
        print('    - admin / admin123')
        print('    - farm1 / farm123')
        print('    - farm2 / farm123')
    else:
        print(f'  ✅ В базе {count} пользователей')
        
except Exception as e:
    print(f'  ❌ Ошибка при инициализации базы данных: {e}')
"

echo ""
echo "======================================"
echo "✅ Настройка завершена!"
echo ""
echo "Следующие шаги на PythonAnywhere:"
echo "1. Во вкладке Web настройте WSGI файл"
echo "2. Укажите путь: /home/Suzubaki/livestock_accounting/pythonanywhere_wsgi.py"
echo "3. Настройте Static files:"
echo "   - URL: /static/"
echo "   - Path: /home/Suzubaki/livestock_accounting/static/"
echo "4. Нажмите Reload"
echo "5. Перейдите по вашей ссылке: suzubaki.pythonanywhere.com"
echo ""
echo "Тестовые аккаунты:"
echo "- Админ: admin / admin123"
echo "- Ферма 1: farm1 / farm123"
echo "- Ферма 2: farm2 / farm123"
echo ""
echo "Удачи! 🚀"