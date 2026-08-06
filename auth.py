import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask import session, redirect, url_for, flash

def register_user(username, password, user_type, farm_name=None):
    """Регистрация нового пользователя"""
    conn = sqlite3.connect('livestock.db')
    cursor = conn.cursor()
    
    try:
        password_hash = generate_password_hash(password)
        cursor.execute('''
            INSERT INTO users (username, password_hash, user_type, farm_name)
            VALUES (?, ?, ?, ?)
        ''', (username, password_hash, user_type, farm_name))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # Пользователь уже существует
    finally:
        conn.close()

def login_user(username, password):
    """Аутентификация пользователя"""
    conn = sqlite3.connect('livestock.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, username, password_hash, user_type, farm_name 
        FROM users WHERE username = ?
    ''', (username,))
    
    user = cursor.fetchone()
    conn.close()
    
    if user and check_password_hash(user[2], password):
        return {
            'id': user[0],
            'username': user[1],
            'user_type': user[3],
            'farm_name': user[4]
        }
    return None

def login_required(f):
    """Декоратор для проверки аутентификации"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Пожалуйста, войдите в систему', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Декоратор для проверки прав администратора"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_type' not in session or session['user_type'] != 'admin':
            flash('Доступ запрещен. Требуются права администратора', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def farm_user_required(f):
    """Декоратор для проверки прав пользователя фермы"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_type' not in session or session['user_type'] != 'farm':
            flash('Доступ запрещен. Требуются права пользователя фермы', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def update_user(user_id, username=None, password=None, user_type=None, farm_name=None):
    """Обновление данных пользователя"""
    conn = sqlite3.connect('livestock.db')
    cursor = conn.cursor()
    
    try:
        # Собираем поля для обновления
        updates = []
        params = []
        
        if username is not None:
            updates.append("username = ?")
            params.append(username)
        
        if password is not None:
            password_hash = generate_password_hash(password)
            updates.append("password_hash = ?")
            params.append(password_hash)
        
        if user_type is not None:
            updates.append("user_type = ?")
            params.append(user_type)
            
            # Если меняется тип на farm, нужно указать farm_name
            if user_type == 'farm' and farm_name is None:
                # Получаем текущий farm_name
                cursor.execute("SELECT farm_name FROM users WHERE id = ?", (user_id,))
                current = cursor.fetchone()
                if current and current[0] is None:
                    # Если farm_name не указан и был None, устанавливаем пустое значение
                    updates.append("farm_name = ?")
                    params.append('')
        
        if farm_name is not None:
            updates.append("farm_name = ?")
            params.append(farm_name)
        
        if not updates:
            return False  # Нечего обновлять
        
        params.append(user_id)
        
        query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, params)
        conn.commit()
        
        return cursor.rowcount > 0
        
    except sqlite3.IntegrityError:
        return False  # Пользователь с таким именем уже существует
    except Exception as e:
        print(f"Ошибка при обновлении пользователя: {e}")
        return False
    finally:
        conn.close()

def get_all_users():
    """Получение списка всех пользователей (без паролей)"""
    conn = sqlite3.connect('livestock.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, username, user_type, farm_name 
        FROM users ORDER BY user_type, username
    ''')
    
    users = cursor.fetchall()
    conn.close()
    
    return [
        {
            'id': user[0],
            'username': user[1],
            'user_type': user[2],
            'farm_name': user[3]
        }
        for user in users
    ]

def get_user_by_id(user_id):
    """Получение пользователя по ID (без пароля)"""
    conn = sqlite3.connect('livestock.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, username, user_type, farm_name 
        FROM users WHERE id = ?
    ''', (user_id,))
    
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return {
            'id': user[0],
            'username': user[1],
            'user_type': user[2],
            'farm_name': user[3]
        }
    return None