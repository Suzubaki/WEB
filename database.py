# database.py - Работа с базой данных SQLite
import sqlite3
import os
import shutil
from datetime import datetime
from config import Config

def get_db_connection():
    """Создает оптимизированное соединение с базой данных SQLite с поддержкой WAL-режима"""
    conn = sqlite3.connect(Config.DATABASE, timeout=10.0)
    conn.row_factory = sqlite3.Row  # Позволяет обращаться к колонкам по имени

    # Включение WAL-режима и тонкая настройка производительности SQLite
    cursor = conn.cursor()
    cursor.execute('PRAGMA journal_mode=WAL;')       # Параллельное чтение без блокировки при записи
    cursor.execute('PRAGMA synchronous=NORMAL;')     # Снижение нагрузки на диск при сохранении надежности в WAL
    cursor.execute('PRAGMA cache_size=-10000;')      # Выделение ~10 МБ RAM под кэш страниц
    cursor.execute('PRAGMA busy_timeout=5000;')      # Ожидание освобождения блокировки до 5 секунд
    cursor.close()

    return conn

def optimize_database_indexes():
    """
    Создание B-Tree индексов для ускорения поиска, фильтрации и группировки в таблице cows.
    Устраняет Full Table Scan в аналитических отчетах, матрицах и дашборде.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Составной индекс (farm_name, disposal_date) - основной индекс для фильтрации по ферме за период
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_cows_farm_date 
            ON cows (farm_name, disposal_date);
        ''')

        # 2. Индекс по категории (падёж, выбраковка, санитарный) - для группировок в статистике и диаграммах
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_cows_category 
            ON cows (category);
        ''')

        # 3. Индекс по системному идентификатору (cow_id) - для быстрого поиска карточки животного
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_cows_cow_id 
            ON cows (cow_id);
        ''')

        # 4. Индекс по государственному идентификационному номеру AITS (ear_tag)
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_cows_ear_tag 
            ON cows (ear_tag);
        ''')

        # 5. Индекс по дате выбытия - для общих временных срезов и годовых отчетов
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_cows_disposal_date 
            ON cows (disposal_date);
        ''')

        # 6. Составной индекс для отчётов и актов (disposal_date, category, farm_name)
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_cows_date_cat_farm 
            ON cows (disposal_date, category, farm_name);
        ''')

        # 7. Составной индекс для матричных отчетов (category, reason, farm_name)
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_cows_cat_reason_farm 
            ON cows (category, reason, farm_name);
        ''')

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Ошибка при создании индексов базы данных: {e}")

def sync_farm_data():
    """
    Синхронизация названий ферм в таблице cows с актуальными названиями ферм пользователей (по created_by)
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE cows
            SET farm_name = (
                SELECT u.farm_name 
                FROM users u 
                WHERE u.id = cows.created_by 
                  AND u.farm_name IS NOT NULL 
                  AND u.farm_name != ''
            )
            WHERE created_by IN (
                SELECT id FROM users 
                WHERE farm_name IS NOT NULL 
                  AND farm_name != ''
            )
        ''')
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Ошибка синхронизации названий ферм: {e}")

def init_db():
    """Инициализация базы данных и создание/миграция таблиц"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            user_type TEXT NOT NULL,  -- 'admin' или 'farm'
            farm_name TEXT,           -- Название фермы для пользователей типа 'farm'
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 2. Таблица коров (учет выбытия)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cow_id TEXT NOT NULL,        -- Системный номер выбытия ('Farm1-001')
            ear_tag TEXT,               -- Инвентарный / ушной номер AITS (РБ)
            farm_name TEXT NOT NULL,     -- Название фермы / МТФ
            category TEXT NOT NULL,      -- 'падёж', 'выбраковка', 'санитарный'
            reason TEXT NOT NULL,        -- Причина выбытия (диагноз)
            disposal_date DATE NOT NULL, -- Дата выбытия
            lactation INTEGER,          -- Номер лактации / возраст
            weight REAL,                -- Живая масса (кг)
            notes TEXT,                 -- Примечание / заключение ветеринара
            age_group TEXT,             -- Половозрастная группа скота (ПВГ)
            breed TEXT,                 -- Порода
            milk_yield REAL,            -- Надой за последнюю лактацию (кг)
            book_value REAL,            -- Балансовая / первоначальная стоимость (BYN)
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER,          -- ID пользователя, добавившего запись
            updated_at TIMESTAMP,
            updated_by INTEGER,
            FOREIGN KEY (created_by) REFERENCES users (id),
            FOREIGN KEY (updated_by) REFERENCES users (id)
        )
    ''')
    
    # 3. Динамический справочник причин выбытия
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS disposal_reasons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,     -- 'падёж', 'выбраковка', 'санитарный'
            name TEXT NOT NULL,         -- Название причины
            is_active INTEGER DEFAULT 1, -- 1: активна, 0: скрыта
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(category, name)
        )
    ''')
    
    # 4. Журнал аудита действий (Audit Log)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT NOT NULL,
            farm_name TEXT,
            action TEXT NOT NULL,       -- 'CREATE', 'UPDATE', 'DELETE', 'IMPORT', 'BACKUP'
            entity_type TEXT NOT NULL,  -- 'COW', 'USER', 'REASON', 'SETTINGS'
            entity_id TEXT,
            details TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 5. Системные настройки (включая экономические расценки)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            description TEXT
        )
    ''')
    
    # Миграция: проверка и добавление недостающих колонок в cows
    cursor.execute("PRAGMA table_info(cows)")
    existing_cols = [row['name'] for row in cursor.fetchall()]
    columns_to_add = {
        'ear_tag': 'TEXT',
        'lactation': 'INTEGER',
        'weight': 'REAL',
        'notes': 'TEXT',
        'age_group': 'TEXT',
        'breed': 'TEXT',
        'milk_yield': 'REAL',
        'book_value': 'REAL',
        'updated_at': 'TIMESTAMP',
        'updated_by': 'INTEGER'
    }
    for col_name, col_type in columns_to_add.items():
        if col_name not in existing_cols:
            cursor.execute(f"ALTER TABLE cows ADD COLUMN {col_name} {col_type}")
    
    # Заполнение справочника причин по умолчанию, если он пуст
    cursor.execute("SELECT COUNT(*) as cnt FROM disposal_reasons")
    if cursor.fetchone()['cnt'] == 0:
        for cat, reasons in Config.DISPOSAL_CATEGORIES.items():
            for reason in reasons:
                cursor.execute('''
                    INSERT OR IGNORE INTO disposal_reasons (category, name, is_active)
                    VALUES (?, ?, 1)
                ''', (cat, reason))
                
    # Заполнение настроек по умолчанию, если пусты
    default_settings = [
        ('meat_price_per_kg', str(Config.DEFAULT_PRICES['meat_price_per_kg']), 'Закупочная цена 1 кг живой массы КРС (BYN)'),
        ('milk_price_per_kg', str(Config.DEFAULT_PRICES['milk_price_per_kg']), 'Закупочная цена 1 кг базисного молока (BYN)'),
        ('replacement_cost', str(Config.DEFAULT_PRICES['replacement_cost']), 'Стоимость восстановления головы / нетели (BYN)'),
        ('farm_unp', '190000000', 'УНП сельскохозяйственной организации (для ГИС AITS)'),
        ('farm_org_name', 'ОАО «Агро-Плем»', 'Полное наименование сельхозпредприятия (РБ)')
    ]
    for k, v, d in default_settings:
        cursor.execute('''
            INSERT OR IGNORE INTO system_settings (key, value, description)
            VALUES (?, ?, ?)
        ''', (k, v, d))
        
    conn.commit()
    conn.close()
    
    # Вызов синхронизации названий ферм
    sync_farm_data()

    # Создание и оптимизация индексов
    optimize_database_indexes()

def get_setting(key, default=None):
    """Получение значения настройки из БД"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM system_settings WHERE key = ?', (key,))
    row = cursor.fetchone()
    conn.close()
    return row['value'] if row else default

def set_setting(key, value, description=None):
    """Сохранение или обновление настройки в БД"""
    conn = get_db_connection()
    cursor = conn.cursor()
    if description:
        cursor.execute('''
            INSERT INTO system_settings (key, value, description) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, description = excluded.description
        ''', (key, str(value), description))
    else:
        cursor.execute('''
            INSERT INTO system_settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        ''', (key, str(value)))
    conn.commit()
    conn.close()

def get_all_settings():
    """Получение всех настроек в виде словаря"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM system_settings')
    rows = cursor.fetchall()
    conn.close()
    return {r['key']: r['value'] for r in rows}

def log_audit_event(username, farm_name, action, entity_type, entity_id=None, details=None, user_id=None, ip_address=None):
    """Запись события в журнал аудита"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO audit_logs (user_id, username, farm_name, action, entity_type, entity_id, details, ip_address)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, username, farm_name, action, entity_type, str(entity_id) if entity_id else None, details, ip_address))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Ошибка логирования аудита: {e}")

def generate_cow_id(farm_name):
    """Генерирует следующий номер выбытия для фермы в формате 'FarmName-XXX'"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT cow_id FROM cows 
        WHERE farm_name = ? 
        ORDER BY id DESC LIMIT 1
    ''', (farm_name,))
    last_cow = cursor.fetchone()
    conn.close()
    
    if last_cow:
        last_id = last_cow['cow_id']
        try:
            parts = last_id.split('-')
            number = int(parts[-1])
            new_number = number + 1
        except (IndexError, ValueError):
            new_number = 1
    else:
        new_number = 1
    
    return f"{farm_name}-{new_number:03d}"

def get_reasons_for_category(category, include_inactive=False):
    """Получение причин выбытия из базы данных"""
    conn = get_db_connection()
    cursor = conn.cursor()
    if include_inactive:
        cursor.execute('SELECT * FROM disposal_reasons WHERE category = ? ORDER BY name ASC', (category,))
    else:
        cursor.execute('SELECT name FROM disposal_reasons WHERE category = ? AND is_active = 1 ORDER BY name ASC', (category,))
    results = cursor.fetchall()
    conn.close()
    
    if include_inactive:
        return [dict(r) for r in results]
    else:
        return [r['name'] for r in results]
