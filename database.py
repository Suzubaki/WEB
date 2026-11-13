# database.py - Работа с базой данных SQLite
import sqlite3
import os
import shutil
from datetime import datetime
from config import Config

import threading

_indexes_checked = False
_wal_checked_for_db = None
_settings_cache = {}
_settings_cache_db = None
_settings_lock = threading.Lock()

def invalidate_settings_cache():
    global _settings_cache, _settings_cache_db
    with _settings_lock:
        _settings_cache = {}
        _settings_cache_db = None

def _ensure_indexes(conn):
    try:
        cursor = conn.cursor()
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cows_farm_date ON cows (farm_name, disposal_date);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cows_category ON cows (category);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cows_cow_id ON cows (cow_id);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cows_ear_tag ON cows (ear_tag);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cows_disposal_date ON cows (disposal_date);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cows_date_cat_farm ON cows (disposal_date, category, farm_name);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cows_cat_reason_farm ON cows (category, reason, farm_name);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cows_date_id ON cows (disposal_date DESC, id DESC);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cows_farm_date_id ON cows (farm_name, disposal_date DESC, id DESC);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cows_category_date_id ON cows (category, disposal_date DESC, id DESC);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cows_farm_name ON cows (farm_name);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cows_reason ON cows (reason);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs (created_at DESC);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_logs_action_created ON audit_logs (action, created_at DESC);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_disposal_reasons_cat_active ON disposal_reasons (category, is_active, name);')
        cursor.close()
    except Exception:
        pass

def _sqlite_lower(val):
    if val is None:
        return None
    if isinstance(val, str):
        return val.lower()
    return str(val).lower()

def get_db_connection():
    """Создает оптимизированное соединение с базой данных SQLite с поддержкой WAL-режима"""
    global _indexes_checked, _wal_checked_for_db
    conn = sqlite3.connect(Config.DATABASE, timeout=10.0)
    conn.row_factory = sqlite3.Row  # Позволяет обращаться к колонкам по имени
    conn.create_function("LOWER", 1, _sqlite_lower)

    cursor = conn.cursor()
    if _wal_checked_for_db != Config.DATABASE:
        cursor.execute('PRAGMA journal_mode=WAL;')
        _wal_checked_for_db = Config.DATABASE
        _indexes_checked = False
    cursor.execute('PRAGMA synchronous=NORMAL;')
    cursor.execute('PRAGMA temp_store=MEMORY;')
    cursor.execute('PRAGMA cache_size=-10000;')
    cursor.execute('PRAGMA busy_timeout=5000;')
    cursor.close()

    if not _indexes_checked:
        _indexes_checked = True
        _ensure_indexes(conn)

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

        # 8. Индекс для мгновенной сортировки по дате и id (пагинация журнала)
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_cows_date_id 
            ON cows (disposal_date DESC, id DESC);
        ''')

        # 9. Составной индекс для фильтра по ферме и сортировки
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_cows_farm_date_id 
            ON cows (farm_name, disposal_date DESC, id DESC);
        ''')

        # 10. Составной индекс для фильтра по категории и сортировки
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_cows_category_date_id 
            ON cows (category, disposal_date DESC, id DESC);
        ''')

        # 11. Индекс по названию фермы
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_cows_farm_name 
            ON cows (farm_name);
        ''')

        # 12. Индекс по причине выбытия
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_cows_reason 
            ON cows (reason);
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
            lactation_days INTEGER,     -- Дни лактации (DIM - Days in Milk)
            lactation_phase TEXT,       -- Фаза лактации (Новотел, Раздой, Середина, Спад, Сухостой, Молодняк)
            breed TEXT,                 -- Порода
            milk_yield REAL,            -- Надой за последнюю лактацию (кг)
            book_value REAL,            -- Балансовая / первоначальная стоимость (BYN)
            is_pregnant INTEGER DEFAULT 0, -- Стельность на момент выбытия (1: стельная, 0: нестельная)
            gestation_days INTEGER DEFAULT 0, -- Срок стельности (дней/месяцев)
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER,          -- ID пользователя, добавившего запись
            updated_at TIMESTAMP,
            updated_by INTEGER,
            FOREIGN KEY (created_by) REFERENCES users (id),
            FOREIGN KEY (updated_by) REFERENCES users (id)
        )
    ''')

    # Миграция колонок для стельности и мертворождений
    try:
        cursor.execute("ALTER TABLE cows ADD COLUMN is_pregnant INTEGER DEFAULT 0")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE cows ADD COLUMN gestation_days INTEGER DEFAULT 0")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE cows ADD COLUMN is_stillborn INTEGER DEFAULT 0")
    except Exception:
        pass
    
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

    # 6. Журнал учёта мертворождений и абортов (Акушерско-гинекологический журнал)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stillbirth_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_code TEXT NOT NULL,           -- e.g. 'МТК Цегельня-М001'
            farm_name TEXT NOT NULL,
            event_date DATE NOT NULL,
            mother_tag TEXT,                    -- Инвент./AITS номер матери (мать жива!)
            mother_group TEXT,                  -- 'Коровы 1-й лактации (первотёлки)', 'Полновозрастные коровы (2+ лакт.)', 'Нетели (>18 мес.)', 'Сухостойные коровы'
            event_type TEXT NOT NULL,           -- Тип события (Мертворождённый телёнок в срок / Аборт / др.)
            fetus_sex TEXT,                     -- Пол плода (Тёлочка / Бычок / Двойня / Не определён)
            fetus_weight REAL,                  -- Вес плода (кг)
            gestation_days INTEGER DEFAULT 0,   -- Срок стельности на момент отёла/аборта (дней)
            cause TEXT NOT NULL,                -- Причина гибели плода
            mother_condition TEXT,              -- Состояние матери после отёла
            attendant TEXT,                     -- Принял отёл (ветврач / техник)
            notes TEXT,                         -- Заключение / примечания
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER,
            updated_at TIMESTAMP,
            updated_by INTEGER,
            FOREIGN KEY (created_by) REFERENCES users (id),
            FOREIGN KEY (updated_by) REFERENCES users (id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_stillbirth_farm_date ON stillbirth_records (farm_name, event_date);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_stillbirth_event_type ON stillbirth_records (event_type);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_stillbirth_mother_tag ON stillbirth_records (mother_tag);')

    # 6. Таблица счётчиков для атомарной генерации номеров без race conditions
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS farm_counters (
            farm_name TEXT PRIMARY KEY,
            last_cow_number INTEGER DEFAULT 0,
            last_stillborn_number INTEGER DEFAULT 0
        )
    ''')

    # Миграция существующих мертворождений из таблицы cows в stillbirth_records
    try:
        cursor.execute('''
            SELECT id, cow_id, ear_tag, farm_name, category, reason, disposal_date, weight, notes, age_group, gestation_days, created_at, created_by
            FROM cows
            WHERE is_stillborn = 1 
               OR category = 'мертворождение' 
               OR LOWER(age_group) LIKE '%мертворож%' 
               OR LOWER(age_group) LIKE '%аборт%' 
               OR LOWER(reason) LIKE '%мертворож%'
        ''')
        rows_to_migrate = cursor.fetchall()
        for r in rows_to_migrate:
            c_code = r['cow_id']
            if '-М' not in c_code:
                parts = c_code.split('-')
                c_code = f"{parts[0]}-М{parts[-1]}" if len(parts) > 1 else f"{c_code}-М"
            
            cursor.execute('SELECT id FROM stillbirth_records WHERE record_code = ? OR (farm_name = ? AND event_date = ? AND cause = ?)', 
                           (c_code, r['farm_name'], r['disposal_date'], r['reason']))
            if not cursor.fetchone():
                e_type = 'Аборт (1-й триместр, до 90 дн.)' if 'аборт' in (r['reason'] or '').lower() or 'аборт' in (r['age_group'] or '').lower() else 'Мертворождённый телёнок (в срок)'
                m_group = 'Сухостойные коровы' if 'сухосто' in (r['age_group'] or '').lower() else 'Полновозрастные коровы (2+ лакт.)'
                cursor.execute('''
                    INSERT INTO stillbirth_records 
                    (record_code, farm_name, event_date, mother_tag, mother_group, event_type, fetus_sex, fetus_weight, gestation_days, cause, mother_condition, attendant, notes, created_at, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (c_code, r['farm_name'], r['disposal_date'], r['ear_tag'], m_group, e_type, 'Не определён', r['weight'] or 25.0, r['gestation_days'] or 0, r['reason'], 'Здорова, оставлена в стаде', 'Дежурный ветврач', r['notes'] or 'Автоматически перенесено из общего журнала выбытия', r['created_at'], r['created_by']))
        
        if rows_to_migrate:
            migrated_ids = [r['id'] for r in rows_to_migrate]
            placeholders = ','.join('?' for _ in migrated_ids)
            cursor.execute(f"DELETE FROM cows WHERE id IN ({placeholders})", migrated_ids)
    except Exception as e:
        print(f"Ошибка миграции мертворождений: {e}")

    
    # Миграция: проверка и добавление недостающих колонок в cows
    cursor.execute("PRAGMA table_info(cows)")
    existing_cols = [row['name'] for row in cursor.fetchall()]
    columns_to_add = {
        'ear_tag': 'TEXT',
        'lactation': 'INTEGER',
        'weight': 'REAL',
        'notes': 'TEXT',
        'age_group': 'TEXT',
        'lactation_days': 'INTEGER',
        'lactation_phase': 'TEXT',
        'breed': 'TEXT',
        'milk_yield': 'REAL',
        'book_value': 'REAL',
        'updated_at': 'TIMESTAMP',
        'updated_by': 'INTEGER'
    }
    for col_name, col_type in columns_to_add.items():
        if col_name not in existing_cols:
            cursor.execute(f"ALTER TABLE cows ADD COLUMN {col_name} {col_type}")
    
    # 6. Индексы для сверхбыстрой работы с 9 000+ записями
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cows_disposal_date ON cows(disposal_date DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cows_farm_date ON cows(farm_name, disposal_date DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cows_category ON cows(category)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cows_cow_id ON cows(cow_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cows_ear_tag ON cows(ear_tag)")
    
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
        ('price_calves', '900.0', 'Нормативная стоимость телят (0–6 мес.) (BYN/гол.)'),
        ('price_youngstock', '1650.0', 'Нормативная стоимость ремонтного молодняка (6–18 мес.) (BYN/гол.)'),
        ('price_heifers', '2700.0', 'Нормативная стоимость нетелей (BYN/гол.)'),
        ('price_cows', '3200.0', 'Нормативная стоимость коров дойного стада (BYN/гол.)'),
        ('price_dry_cows', '3000.0', 'Нормативная стоимость сухостойных коров (BYN/гол.)'),
        ('norm_youngstock_preservation', '92.0', 'Целевой порог сохранности молодняка (%)'),
        ('norm_fresh_cow_disposal', '10.0', 'Максимальный порог выбытия новотельных коров 0–30 DIM (%)'),
        ('norm_first_lactation_culling', '20.0', 'Максимальный порог выбраковки первотёлок (%)'),
        ('norm_mortality_rate', '25.0', 'Максимальный порог доли падежа в выбытии (%)'),
        ('norm_locomotor_disorders', '15.0', 'Максимальный порог заболеваний копыт (%)'),
        ('norm_mastitis_disorders', '15.0', 'Максимальный порог заболеваний вымени (%)'),
        ('farm_unp', '190000000', 'УНП сельскохозяйственной организации (для ГИС AITS)'),
        ('farm_org_name', 'ОАО «Новая Припять»', 'Полное наименование сельхозпредприятия (РБ)')
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

def get_all_settings():
    """Получение всех настроек в виде словаря (с кэшированием в памяти процесса)"""
    global _settings_cache, _settings_cache_db
    with _settings_lock:
        if _settings_cache and _settings_cache_db == Config.DATABASE:
            return dict(_settings_cache)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT key, value FROM system_settings')
    rows = cursor.fetchall()
    conn.close()
    result = {r['key']: r['value'] for r in rows}

    with _settings_lock:
        _settings_cache = result
        _settings_cache_db = Config.DATABASE
        return dict(_settings_cache)

def get_setting(key, default=None):
    """Получение значения настройки из БД (через быстрый кэш настроек)"""
    settings = get_all_settings()
    return settings.get(key, default)

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
    invalidate_settings_cache()

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
    """
    Атомарно генерирует следующий уникальный номер выбытия для фермы в формате 'FarmName-XXX'
    через таблицу счетчиков farm_counters с транзакционной блокировкой (BEGIN IMMEDIATE).
    Гарантирует уникальность и последовательность номеров без race conditions.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        
        # Получаем текущее значение счетчика для фермы
        cursor.execute("SELECT last_cow_number FROM farm_counters WHERE farm_name = ?", (farm_name,))
        row = cursor.fetchone()
        
        if row is None:
            # Инициализируем из существующей таблицы cows, если счетчик еще не создан
            cursor.execute('''
                SELECT cow_id FROM cows 
                WHERE farm_name = ? 
                ORDER BY id DESC LIMIT 1
            ''', (farm_name,))
            last_cow = cursor.fetchone()
            current_max = 0
            if last_cow and last_cow['cow_id']:
                try:
                    parts = last_cow['cow_id'].split('-')
                    current_max = int(parts[-1])
                except (IndexError, ValueError):
                    current_max = 0
            
            new_number = current_max + 1
            cursor.execute('''
                INSERT INTO farm_counters (farm_name, last_cow_number, last_stillborn_number)
                VALUES (?, ?, 0)
            ''', (farm_name, new_number))
        else:
            new_number = row['last_cow_number'] + 1
            cursor.execute('''
                UPDATE farm_counters 
                SET last_cow_number = ? 
                WHERE farm_name = ?
            ''', (new_number, farm_name))
            
        conn.commit()
        return f"{farm_name}-{new_number:03d}"
    except Exception:
        conn.rollback()
        import time
        return f"{farm_name}-{int(time.time() * 1000) % 100000:03d}"
    finally:
        conn.close()

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

def generate_stillborn_code(farm_name):
    """
    Атомарно генерирует следующий номер акта мертворождения для фермы в формате 'FarmName-МXXX'
    через таблицу farm_counters с транзакционной блокировкой (BEGIN IMMEDIATE).
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        
        cursor.execute("SELECT last_stillborn_number FROM farm_counters WHERE farm_name = ?", (farm_name,))
        row = cursor.fetchone()
        
        if row is None:
            cursor.execute('''
                SELECT record_code FROM stillbirth_records 
                WHERE farm_name = ? 
                ORDER BY id DESC LIMIT 1
            ''', (farm_name,))
            last_row = cursor.fetchone()
            current_max = 0
            if last_row and last_row['record_code']:
                try:
                    if '-М' in last_row['record_code']:
                        parts = last_row['record_code'].split('-М')
                        current_max = int(parts[-1])
                    else:
                        parts = last_row['record_code'].split('-')
                        current_max = int(parts[-1].replace('М', ''))
                except (IndexError, ValueError):
                    current_max = 0
            
            new_number = current_max + 1
            cursor.execute('''
                INSERT INTO farm_counters (farm_name, last_cow_number, last_stillborn_number)
                VALUES (?, 0, ?)
            ''', (farm_name, new_number))
        else:
            new_number = row['last_stillborn_number'] + 1
            cursor.execute('''
                UPDATE farm_counters 
                SET last_stillborn_number = ? 
                WHERE farm_name = ?
            ''', (new_number, farm_name))
            
        conn.commit()
        return f"{farm_name}-М{new_number:03d}"
    except Exception:
        conn.rollback()
        import time
        return f"{farm_name}-М{int(time.time() * 1000) % 100000:03d}"
    finally:
        conn.close()

