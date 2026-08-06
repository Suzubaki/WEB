import sqlite3
import os
from datetime import datetime

def init_db():
    """Инициализация базы данных SQLite"""
    conn = sqlite3.connect('livestock.db')
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            user_type TEXT NOT NULL,  -- 'admin' или 'farm'
            farm_name TEXT,  -- название фермы (для пользователей типа farm)
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица коров
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cow_id TEXT NOT NULL,  -- уникальный идентификатор коровы
            farm_name TEXT NOT NULL,  -- к какой ферме принадлежит
            category TEXT NOT NULL,  -- 'падёж', 'выбраковка', 'санитарный'
            reason TEXT NOT NULL,  -- конкретная причина
            disposal_date DATE NOT NULL,  -- дата выбытия
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER,
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
    ''')
    
    # Создаём индексы для быстрого поиска
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_cows_farm ON cows(farm_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_cows_date ON cows(disposal_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_cows_category ON cows(category)')
    
    conn.commit()
    conn.close()
    
    print("База данных инициализирована")

def get_db_connection():
    """Получение соединения с базой данных"""
    conn = sqlite3.connect('livestock.db')
    conn.row_factory = sqlite3.Row  # Возвращает словари вместо кортежей
    return conn

if __name__ == '__main__':
    init_db()


def generate_cow_id(farm_name):
    """Генерация автоматического ID коровы для фермы"""
    conn = get_db_connection()
    
    # Получаем максимальный номер для этой фермы
    cursor = conn.execute('''
        SELECT MAX(CAST(SUBSTR(cow_id, INSTR(cow_id, "-") + 1) AS INTEGER)) as max_num
        FROM cows 
        WHERE farm_name = ? AND cow_id LIKE ? || '-%'
    ''', (farm_name, farm_name))
    
    result = cursor.fetchone()
    max_num = result['max_num'] if result['max_num'] else 0
    
    # Генерируем новый ID
    new_num = max_num + 1
    new_id = f"{farm_name}-{new_num:03d}"  # Формат: ФЕРМА-001
    
    conn.close()
    return new_id