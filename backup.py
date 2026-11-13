# backup.py - Модуль резервного копирования и восстановления базы данных
import os
import tempfile
import shutil
import sqlite3
from datetime import datetime
from config import Config
from database import log_audit_event, init_db, invalidate_settings_cache

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

    tmp_fd, tmp_path = tempfile.mkstemp(suffix='.sqlite')
    os.close(tmp_fd)
    try:
        src = sqlite3.connect(source_db_path)
        dst = sqlite3.connect(tmp_path)
        src.backup(dst)
        dst.close()
        src.close()
        with open(tmp_path, 'rb') as f:
            file_bytes = f.read()
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return file_bytes, filename

def restore_db_from_upload(upload_file, username=None, ip_address=None):
    """
    Восстановление базы данных из загруженного файла .db/.sqlite с валидацией
    """
    try:
        # Проверка размера загружаемого файла (лимит 50 МБ)
        upload_file.seek(0, os.SEEK_END)
        file_size = upload_file.tell()
        upload_file.seek(0)
        
        if file_size > 50 * 1024 * 1024:
            return False, 'Файл резервной копии слишком велик (максимум 50 МБ)'
        if file_size < 100:
            return False, 'Файл резервной копии поврежден или пуст'

        # Читаем первые 16 байт для проверки SQLite заголовка: "SQLite format 3\000"
        header = upload_file.read(16)
        if not header.startswith(b'SQLite format 3'):
            upload_file.seek(0)
            return False, 'Загруженный файл не является корректной базой данных SQLite'
            
        upload_file.seek(0)
        
        # Сохраняем во временный файл для проверки таблиц
        temp_path = Config.DATABASE + '.restore_temp'
        upload_file.save(temp_path)
        
        # Проверяем целостность и список таблиц
        test_conn = sqlite3.connect(temp_path)
        test_cursor = test_conn.cursor()
        
        # Проверка целостности SQLite
        test_cursor.execute("PRAGMA quick_check")
        check_result = test_cursor.fetchone()
        if not check_result or check_result[0] != 'ok':
            test_conn.close()
            os.remove(temp_path)
            return False, 'Файл резервной копии поврежден (PRAGMA quick_check failed)'

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
        invalidate_settings_cache()
        
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
