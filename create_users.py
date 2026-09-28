#!/usr/bin/env python3
"""
Скрипт для создания тестовых пользователей на PythonAnywhere
Запустите в консоли PythonAnywhere после создания базы данных
"""

import sqlite3
import os
from werkzeug.security import generate_password_hash

def create_test_users():
    """Создание тестовых пользователей"""
    
    # Проверяем существует ли база данных
    db_path = 'livestock.db'
    if not os.path.exists(db_path):
        print(f"❌ Файл базы данных не найден: {db_path}")
        print("Сначала создайте базу данных:")
        print("python -c \"from database import init_db; init_db()\"")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("=" * 50)
    print("СОЗДАНИЕ ТЕСТОВЫХ ПОЛЬЗОВАТЕЛЕЙ")
    print("=" * 50)
    
    # Список тестовых пользователей
    test_users = [
        {
            'username': 'admin',
            'password': 'admin123',
            'user_type': 'admin',
            'farm_name': None
        },
        {
            'username': 'farm1',
            'password': 'farm123',
            'user_type': 'farm',
            'farm_name': 'Ферма 1'
        },
        {
            'username': 'farm2',
            'password': 'farm123',
            'user_type': 'farm',
            'farm_name': 'Ферма 2'
        }
    ]
    
    created_count = 0
    
    for user in test_users:
        username = user['username']
        
        # Проверяем существует ли пользователь
        cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            print(f"⚠️ Пользователь '{username}' уже существует")
        else:
            # Создаем нового пользователя
            password_hash = generate_password_hash(user['password'])
            
            cursor.execute('''
                INSERT INTO users (username, password_hash, user_type, farm_name)
                VALUES (?, ?, ?, ?)
            ''', (username, password_hash, user['user_type'], user['farm_name']))
            
            print(f"✅ Создан пользователь: {username}")
            print(f"   Тип: {user['user_type']}")
            if user['farm_name']:
                print(f"   Ферма: {user['farm_name']}")
            print(f"   Пароль: {user['password']}")
            created_count += 1
    
    conn.commit()
    
    # Показываем всех пользователей
    print("\n" + "=" * 50)
    print("ВСЕ ПОЛЬЗОВАТЕЛИ В БАЗЕ ДАННЫХ:")
    print("=" * 50)
    
    cursor.execute('SELECT id, username, user_type, farm_name FROM users ORDER BY user_type, username')
    all_users = cursor.fetchall()
    
    if not all_users:
        print("Нет пользователей в базе данных")
    else:
        for user in all_users:
            print(f"ID: {user[0]}, Имя: {user[1]}, Тип: {user[2]}, Ферма: {user[3] or '-'}")
    
    conn.close()
    
    print("\n" + "=" * 50)
    if created_count > 0:
        print(f"✅ СОЗДАНО {created_count} ПОЛЬЗОВАТЕЛЕЙ")
    else:
        print("ℹ️ Все пользователи уже существуют")
    
    print("\nТЕСТОВЫЕ АККАУНТЫ:")
    print("-------------------")
    for user in test_users:
        print(f"{user['username']} / {user['password']} ({user['user_type']})")
    
    print("\n" + "=" * 50)
    return True

if __name__ == '__main__':
    try:
        create_test_users()
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        print("\nВозможные причины:")
        print("1. База данных не создана")
        print("2. Таблица users не существует")
        print("3. Ошибка в структуре базы данных")
        print("\nСначала создайте базу данных:")
        print("python -c \"from database import init_db; init_db()\"")