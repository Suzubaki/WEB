# Инструкция по развертыванию на PythonAnywhere

## ⚠️ ВАЖНО: Ошибки путей на PythonAnywhere
На PythonAnywhere важно правильно указывать пути:
1. **WSGI файл** должен импортировать модуль из `.py` файла
2. **Пути** должны быть абсолютными и правильными
3. **Имена файлов** должны быть корректными именами модулей Python

## 1. Вход в систему
- Перейдите на https://www.pythonanywhere.com
- Войдите под логином: `Suzubaki`

## 2. Создание нового веб-приложения
1. На панели управления перейдите во вкладку **Web**
2. Нажмите **Add a new web app**
3. Выберите **Manual configuration**
4. Выберите Python версии 3.9 (минимальная версия на PythonAnywhere)

## 3. Загрузка файлов проекта
1. На главной странице PythonAnywhere перейдите во вкладку **Files**
2. Создайте новую папку: `/home/Suzubaki/livestock_accounting/`
   - Нажмите **New directory** вверху
   - Введите `livestock_accounting`
3. Загрузите файлы проекта:
   - Зайдите в созданную папку
   - Нажмите **Upload a file**
   - Загрузите все необходимые файлы

**ВАЖНО:** Убедитесь, что структура файлов правильная:
```
/home/Suzubaki/livestock_accounting/
├── app.py                 # Главное приложение
├── auth.py                # Аутентификация
├── database.py            # Работа с базой данных
├── config.py              # Конфигурация
├── charts.py              # Графики статистики
├── models.py              # Модели данных
├── requirements.txt       # Зависимости
├── wsgi_simple.py         # WSGI файл (альтернатива)
├── templates/             # HTML шаблоны
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   └── ... (все остальные .html файлы)
└── static/                # Статические файлы (CSS, JS)
    └── charts.js
```

**Необходимые файлы для загрузки:**
- `app.py` - главный файл приложения
- `auth.py` - аутентификация
- `database.py` - работа с базой данных
- `config.py` - конфигурация
- `charts.py` - графики статистики
- `models.py` - модели данных
- все файлы в папке `templates/` - HTML шаблоны
- все файлы в папке `static/` - статические файлы (CSS, JS)
- `requirements.txt` - зависимости
- `wsgi_simple.py` - упрощенный WSGI файл (альтернатива)

**Совет:** Можно загрузить ZIP архив и распаковать его прямо на PythonAnywhere

## 4. Установка зависимостей
1. Перейдите во вкладку **Consoles**
2. Создайте новую консоль **Bash**
3. В консоли выполните:
```bash
cd /home/Suzubaki/livestock_accounting/
pip install -r requirements.txt
```

## 5. Настройка WSGI файла
1. Во вкладке **Web** найдите раздел **Code**
2. Нажмите на ссылку **WSGI configuration file** (обычно `/var/www/suzubaki_pythonanywhere_com_wsgi.py`)
3. УДАЛИТЕ всё содержимое файла и замените на:

```python
import sys
import os

# Добавляем путь к проекту
path = '/home/Suzubaki/livestock_accounting'
if path not in sys.path:
    sys.path.insert(0, path)

# Устанавливаем рабочую директорию
os.chdir(path)

# Импортируем приложение из app.py
from app import app as application

# Устанавливаем секретный ключ для production
application.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Инициализация базы данных при первом запуске
try:
    from database import init_db
    init_db()
    
    # Создаем тестовых пользователей если их нет
    import sqlite3
    conn = sqlite3.connect('livestock.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        from auth import register_user
        register_user('admin', 'admin123', 'admin')
        register_user('farm1', 'farm123', 'farm', 'Ферма 1')
        register_user('farm2', 'farm123', 'farm', 'Ферма 2')
        print("Созданы тестовые пользователи")
    conn.close()
except Exception as e:
    print(f"Ошибка при инициализации базы данных: {e}")
```

**ВАЖНО:** Файл WSGI на PythonAnywhere должен иметь расширение `.py` и импортировать `app` из вашего файла `app.py`

## 6. Настройка статических файлов
1. Во вкладке **Web** найдите раздел **Static files**
2. Добавьте:
   - URL: `/static/`
   - Path: `/home/Suzubaki/livestock_accounting/static/`

## 7. Настройка базы данных
1. В консоли выполните:
```bash
cd /home/Suzubaki/livestock_accounting/
python -c "from database import init_db; init_db()"
```

Это создаст файл базы данных `livestock.db`

## 8. Перезапуск приложения
1. Вернитесь во вкладку **Web**
2. Нажмите кнопку **Reload Suzubaki.pythonanywhere.com**

## 9. Проверка
- Перейдите на ваш домен: `Suzubaki.pythonanywhere.com`
- Используйте тестовые аккаунты:
  - Администратор: `admin` / `admin123`
  - Ферма 1: `farm1` / `farm123`
  - Ферма 2: `farm2` / `farm123`

## 10. Важные замечания

### Безопасность
1. Измените пароли тестовых аккаунтов после первого входа
2. Измените SECRET_KEY в config.py на более сложный
3. В production используйте более надежную базу данных (PostgreSQL)

### Ограничения PythonAnywhere
1. Бесплатный аккаунт имеет ограничения на дисковое пространство и время работы
2. База данных SQLite будет работать, но для большого объема данных лучше использовать MySQL
3. Для файлов отчетов убедитесь, что папка `reports` существует и доступна для записи

### Мониторинг
- Проверяйте логи во вкладке **Web** -> **Error log**
- Для отладки используйте консоль PythonAnywhere

## 11. Обновление приложения
Для обновления приложения:
1. Загрузите новые файлы
2. Перезапустите приложение (Reload)
3. При изменении структуры базы данных может потребоваться миграция