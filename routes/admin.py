# routes/admin.py - Системное администрирование, журнал аудита и резервные копии
import io
from flask import (
    Blueprint, render_template, request, redirect, 
    url_for, flash, session, send_file
)
from database import get_db_connection, log_audit_event
from backup import create_db_backup_bytes, restore_db_from_upload
from .auth import login_required, admin_required

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/reasons', methods=['GET', 'POST'])
@admin_required
def manage_reasons():
    """Управление справочником причин выбытия скота (для администратора)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        category = request.form.get('category')
        name = request.form.get('name', '').strip()
        
        if category and name:
            cursor.execute('INSERT OR IGNORE INTO disposal_reasons (category, name, is_active) VALUES (?, ?, 1)', (category, name))
            conn.commit()
            
            log_audit_event(
                username=session.get('username'),
                farm_name='Admin',
                action='CREATE_REASON',
                entity_type='REASON',
                details=f"Добавлена новая причина '{name}' в категорию '{category}'",
                user_id=session.get('user_id'),
                ip_address=request.remote_addr
            )
            flash(f"Причина '{name}' успешно добавлена в справочник", 'success')
            
    cursor.execute('SELECT * FROM disposal_reasons ORDER BY category, name')
    reasons = [dict(r) for r in cursor.fetchall()]
    conn.close()
    
    return render_template('manage_reasons.html', reasons=reasons)

@admin_bp.route('/reasons/toggle/<int:reason_id>', methods=['POST'])
@admin_required
def toggle_reason(reason_id):
    """Переключение активности причины выбытия"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM disposal_reasons WHERE id = ?', (reason_id,))
    reason = cursor.fetchone()
    if reason:
        new_status = 0 if reason['is_active'] == 1 else 1
        cursor.execute('UPDATE disposal_reasons SET is_active = ? WHERE id = ?', (new_status, reason_id))
        conn.commit()
        status_text = 'активирована' if new_status == 1 else 'скрыта'
        flash(f"Причина '{reason['name']}' {status_text}", 'info')
    conn.close()
    return redirect(url_for('admin.manage_reasons'))

@admin_bp.route('/reasons/delete/<int:reason_id>', methods=['POST'])
@admin_required
def delete_reason(reason_id):
    """Удаление причины выбытия из справочника"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM disposal_reasons WHERE id = ?', (reason_id,))
    reason = cursor.fetchone()
    if reason:
        cursor.execute('DELETE FROM disposal_reasons WHERE id = ?', (reason_id,))
        conn.commit()
        log_audit_event(
            username=session.get('username'),
            farm_name='Admin',
            action='DELETE_REASON',
            entity_type='REASON',
            details=f"Удалена причина '{reason['name']}' из категории '{reason['category']}'",
            user_id=session.get('user_id'),
            ip_address=request.remote_addr
        )
        flash(f"Причина '{reason['name']}' удалена из справочника", 'success')
    conn.close()
    return redirect(url_for('admin.manage_reasons'))

@admin_bp.route('/audit_log')
@admin_required
def audit_log():
    """Журнал аудита действий пользователей"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 200')
    logs = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return render_template('audit_log.html', logs=logs)

@admin_bp.route('/backup')
@admin_required
def backup():
    """Панель управления резервными копиями базы данных"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM audit_logs WHERE action = 'BACKUP' ORDER BY created_at DESC LIMIT 20")
    backup_logs = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return render_template('backup.html', backup_logs=backup_logs)

@admin_bp.route('/backup/download')
@admin_required
def download_backup():
    """Скачивание бинарного дампа SQLite базы данных"""
    file_bytes, filename = create_db_backup_bytes()
    log_audit_event(
        username=session.get('username'),
        farm_name='Admin',
        action='BACKUP',
        entity_type='SETTINGS',
        details=f"Скачана резервная копия базы данных: {filename}",
        user_id=session.get('user_id'),
        ip_address=request.remote_addr
    )
    return send_file(
        io.BytesIO(file_bytes),
        download_name=filename,
        as_attachment=True,
        mimetype='application/octet-stream'
    )

@admin_bp.route('/backup/restore', methods=['POST'])
@admin_required
def restore_backup():
    """Восстановление базы данных из загруженного файла бэкапа"""
    if 'backup_file' not in request.files:
        flash('Файл резервной копии не выбран', 'danger')
        return redirect(url_for('admin.backup'))
        
    file = request.files['backup_file']
    if file.filename == '':
        flash('Файл резервной копии не выбран', 'danger')
        return redirect(url_for('admin.backup'))
        
    success, msg = restore_db_from_upload(file, session.get('username'), request.remote_addr)
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')
    return redirect(url_for('admin.backup'))

@admin_bp.route('/seed_test_data')
@login_required
def seed_test_data():
    """Генерация реалистичного массива тестовых данных (1 000 коров)"""
    from add_test_cows import generate_test_cows
    generate_test_cows(1000)
    flash('Успешно добавлено 1 000 коров в базу данных!', 'success')
    return redirect(url_for('cows.view_cows'))
