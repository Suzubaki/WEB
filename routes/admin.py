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

@admin_bp.route('/pricing', methods=['GET', 'POST'])
@admin_required
def pricing():
    """Просмотр и редактирование нормативов цен и методики расчета ущерба BYN"""
    from database import get_setting, set_setting
    
    if request.method == 'POST':
        if session.get('user_type') != 'admin':
            flash('Редактирование доступно только администраторам', 'danger')
            return redirect(url_for('admin.pricing'))
            
        fields = [
            'price_calves', 'price_youngstock', 'price_heifers', 'price_cows', 'price_dry_cows',
            'meat_price_per_kg', 'milk_price_per_kg', 'replacement_cost',
            'norm_youngstock_preservation', 'norm_fresh_cow_disposal', 'norm_first_lactation_culling',
            'norm_mortality_rate', 'norm_locomotor_disorders', 'norm_mastitis_disorders'
        ]
        for f in fields:
            val = request.form.get(f)
            if val is not None:
                try:
                    set_setting(f, str(float(val)))
                except ValueError:
                    pass
        flash('Экономические нормативы и зоотехнические пороги цен успешно обновлены!', 'success')
        return redirect(url_for('admin.pricing'))
        
    pricing_data = {
        'price_calves': float(get_setting('price_calves', 900.0)),
        'price_youngstock': float(get_setting('price_youngstock', 1650.0)),
        'price_heifers': float(get_setting('price_heifers', 2700.0)),
        'price_cows': float(get_setting('price_cows', 3200.0)),
        'price_dry_cows': float(get_setting('price_dry_cows', 3000.0)),
        'meat_price_per_kg': float(get_setting('meat_price_per_kg', 6.20)),
        'milk_price_per_kg': float(get_setting('milk_price_per_kg', 1.18)),
        'replacement_cost': float(get_setting('replacement_cost', 2950.0)),
        'norm_youngstock_preservation': float(get_setting('norm_youngstock_preservation', 92.0)),
        'norm_fresh_cow_disposal': float(get_setting('norm_fresh_cow_disposal', 10.0)),
        'norm_first_lactation_culling': float(get_setting('norm_first_lactation_culling', 20.0)),
        'norm_mortality_rate': float(get_setting('norm_mortality_rate', 25.0)),
        'norm_locomotor_disorders': float(get_setting('norm_locomotor_disorders', 15.0)),
        'norm_mastitis_disorders': float(get_setting('norm_mastitis_disorders', 15.0))
    }
    
    return render_template('pricing.html', pricing=pricing_data, user_type=session.get('user_type'))
