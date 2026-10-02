# create_users.py - Создание тестовых пользователей
import sqlite3
from database import init_db, get_db_connection
from auth import register_user

def create_default_users():
    init_db()
    
    # 1. Создаем администратора
    success, msg = register_user('admin', 'admin123', 'admin')
    print(f"Администратор admin: {msg}")
    
    # 2. Создаем пользователей ферм
    success, msg = register_user('farm1', 'farm123', 'farm', 'Ферма 1')
    print(f"Пользователь farm1: {msg}")
    
    success, msg = register_user('farm2', 'farm123', 'farm', 'Ферма 2')
    print(f"Пользователь farm2: {msg}")

if __name__ == '__main__':
    create_default_users()
