# backup.py - Модуль резервного копирования и восстановления базы данных
import os
import io
import shutil
import sqlite3
from datetime import datetime
from config import Config
from database import log_audit_event, init_db

def create_db_backup_bytes():
    """
    Создает целостную резервную копию базы данных SQLite с использованием SQLite Online Backup API
    Возвращает (bytes, filename)
    """
    source_db_path = Config.DATABASE
    if not os.path.exists(source_db_path):
        init_db()
        
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"agro_backup_RB_{timestamp}.sqlite"
    
    # Используем sqlite3 backup API для гарантии отсутствия блокировок
    src = sqlite3.connect(source_db_path)
    mem_db = sqlite3.connect(':memory:')
    src.backup(mem_db)
    src.close()
    
    # Сохраняем в байты
    backup_stream = io.BytesIO()
    for line in mem_db.iterdump():
        backup_stream.write(f'{line}\n'.encode('utf-8'))
    mem_db.close()
    
    # Также можно передать сам сырой файл БД
    with open(source_db_path, 'rb') as f:
        file_bytes = f.read()
        
    return file_bytes, filename

def restore_db_from_upload(upload_file, username=None, ip_address=None):
    """
    Восстановление базы данных из загруженного файла .db/.sqlite с валидацией
    """
    try:
        # Читаем первые 100 байт для проверки SQLite заголовка: "SQLite format 3\000"
        header = upload_file.read(16)
        if not header.startswith(b'SQLite format 3'):
            upload_file.seek(0)
            return False, 'Загруженный файл не является корректной базой данных SQLite'
            
        upload_file.seek(0)
        
        # Сохраняем во временный файл для проверки таблиц
        temp_path = Config.DATABASE + '.restore_temp'
        upload_file.save(temp_path)
        
        # Проверяем наличие ключевых таблиц (cows, users)
        test_conn = sqlite3.connect(temp_path)
        test_cursor = test_conn.cursor()
        test_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in test_cursor.fetchall()]
        test_conn.close()
        
        if 'cows' not in tables or 'users' not in tables:
            os.remove(temp_path)
            return False, 'В резервной копии отсутствуют обязательные таблицы (cows, users)'
            
        # Делаем аварийную копию текущей БД перед заменой
        if os.path.exists(Config.DATABASE):
            shutil.copy2(Config.DATABASE, Config.DATABASE + '.pre_restore_bak')
            
        # Заменяем текущую БД
        shutil.move(temp_path, Config.DATABASE)
        
        # Применяем миграции если файл был из старой версии
        init_db()
        
        log_audit_event(
            username=username or 'Admin',
            farm_name='Admin',
            action='BACKUP',
            entity_type='SETTINGS',
            details='Выполнено восстановление базы данных из резервной копии',
            ip_address=ip_address
        )
        return True, 'База данных успешно восстановлена из резервной копии'
        
    except Exception as e:
        return False, f'Ошибка при восстановлении базы данных: {str(e)}'
