# auth.py - Аутентификация и управление пользователями
import sqlite3
from database import get_db_connection
from models import User

def authenticate_user(username, password):
    """
    Проверка учетных данных пользователя
    Возвращает объект User или None
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user_data = cursor.fetchone()
    conn.close()
    
    if user_data:
        user = User(
            id=user_data['id'],
            username=user_data['username'],
            password_hash=user_data['password_hash'],
            user_type=user_data['user_type'],
            farm_name=user_data['farm_name'],
            created_at=user_data['created_at']
        )
        if user.check_password(password):
            return user
    return None

def get_user_by_id(user_id):
    """Получение пользователя по ID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    
    if user_data:
        return User(
            id=user_data['id'],
            username=user_data['username'],
            password_hash=user_data['password_hash'],
            user_type=user_data['user_type'],
            farm_name=user_data['farm_name'],
            created_at=user_data['created_at']
        )
    return None

def register_user(username, password, user_type, farm_name=None):
    """
    Регистрация нового пользователя
    Возвращает (success, message)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Проверяем, существует ли пользователь с таким именем
        cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        if cursor.fetchone():
            return False, 'Пользователь с таким именем уже существует'
        
        # Хешируем пароль
        password_hash = User.create_password_hash(password)
        
        # Вставляем пользователя
        cursor.execute('''
            INSERT INTO users (username, password_hash, user_type, farm_name)
            VALUES (?, ?, ?, ?)
        ''', (username, password_hash, user_type, farm_name))
        
        conn.commit()
        return True, 'Пользователь успешно зарегистрирован'
        
    except sqlite3.Error as e:
        return False, f'Ошибка базы данных: {str(e)}'
    finally:
        conn.close()

def get_all_users():
    """Получение списка всех пользователей"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users ORDER BY created_at DESC')
    users_data = cursor.fetchall()
    conn.close()
    
    users = []
    for user_data in users_data:
        users.append(User(
            id=user_data['id'],
            username=user_data['username'],
            password_hash=user_data['password_hash'],
            user_type=user_data['user_type'],
            farm_name=user_data['farm_name'],
            created_at=user_data['created_at']
        ))
    return users

def update_user(user_id, username, password=None, user_type=None, farm_name=None):
    """
    Обновление данных пользователя с каскадным обновлением связанных записей коров
    Возвращает (success, message)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Проверяем существование пользователя
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        if not user:
            return False, 'Пользователь не найден'
        
        old_farm_name = user['farm_name']
        
        # Проверяем уникальность имени, если оно изменилось
        if username != user['username']:
            cursor.execute('SELECT id FROM users WHERE username = ? AND id != ?', (username, user_id))
            if cursor.fetchone():
                return False, 'Пользователь с таким именем уже существует'
        
        # Формируем запрос обновления
        update_fields = ['username = ?']
        params = [username]
        
        if password:
            password_hash = User.create_password_hash(password)
            update_fields.append('password_hash = ?')
            params.append(password_hash)
            
        if user_type:
            update_fields.append('user_type = ?')
            params.append(user_type)
            
        if farm_name is not None:
            update_fields.append('farm_name = ?')
            params.append(farm_name)
            
        params.append(user_id)
        
        query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?"
        cursor.execute(query, params)
        
        # Каскадное обновление названия фермы в таблице cows и audit_logs
        if farm_name and old_farm_name and farm_name != old_farm_name:
            cursor.execute('UPDATE cows SET farm_name = ? WHERE farm_name = ?', (farm_name, old_farm_name))
            cursor.execute('UPDATE cows SET farm_name = ? WHERE created_by = ?', (farm_name, user_id))
            cursor.execute('UPDATE audit_logs SET farm_name = ? WHERE farm_name = ?', (farm_name, old_farm_name))
        elif farm_name and not old_farm_name:
            cursor.execute('UPDATE cows SET farm_name = ? WHERE created_by = ?', (farm_name, user_id))
            
        conn.commit()
        return True, 'Данные пользователя и связанные записи коров успешно обновлены'
        
    except sqlite3.Error as e:
        return False, f'Ошибка базы данных: {str(e)}'
    finally:
        conn.close()

def delete_user(user_id):
    """
    Удаление пользователя
    Возвращает (success, message)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        return True, 'Пользователь успешно удален'
    except sqlite3.Error as e:
        return False, f'Ошибка базы данных: {str(e)}'
    finally:
        conn.close()
