# routes/stillborn.py - Специализированный журнал учёта мертворождений и абортов (РБ)
import os
import io
from datetime import datetime
from flask import (
    Blueprint, render_template, request, redirect, 
    url_for, flash, session, jsonify, send_file
)
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

from config import Config
from database import get_db_connection, generate_stillborn_code, log_audit_event, get_setting
from .auth import login_required

stillborn_bp = Blueprint('stillborn', __name__)

@stillborn_bp.route('/stillborn')
@login_required
def stillborn_list():
    """Просмотр профильного журнала учёта мертворождений и абортов"""
    user_type = session.get('user_type')
    session_farm = session.get('farm_name')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    farm_filter = request.args.get('farm', '').strip()
    event_type_filter = request.args.get('event_type', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    search = request.args.get('search', '').strip().lower()
    
    conditions = []
    params = []
    
    if user_type != 'admin':
        conditions.append("farm_name = ?")
        params.append(session_farm)
    elif farm_filter and farm_filter != 'all':
        conditions.append("farm_name = ?")
        params.append(farm_filter)
        
    if event_type_filter and event_type_filter != 'all':
        conditions.append("event_type = ?")
        params.append(event_type_filter)
        
    if start_date and end_date:
        conditions.append("event_date BETWEEN ? AND ?")
        params.extend([start_date, end_date])
        
    if search:
        conditions.append("(record_code LIKE ? OR mother_tag LIKE ? OR cause LIKE ? OR farm_name LIKE ? OR attendant LIKE ?)")
        wild = f"%{search}%"
        params.extend([wild, wild, wild, wild, wild])
        
    where_sql = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    
    # Список ферм для фильтра администратора
    if user_type == 'admin':
        cursor.execute('SELECT DISTINCT farm_name FROM stillbirth_records WHERE farm_name IS NOT NULL AND farm_name != "" ORDER BY farm_name')
        farms = [r['farm_name'] for r in cursor.fetchall()]
        if not farms:
            cursor.execute('SELECT DISTINCT farm_name FROM users WHERE farm_name IS NOT NULL AND farm_name != "" ORDER BY farm_name')
            farms = [r['farm_name'] for r in cursor.fetchall()]
    else:
        farms = [session_farm]
        
    # Сводные показатели
    cursor.execute(f"SELECT COUNT(*) as total_cnt FROM stillbirth_records{where_sql}", params)
    total_count = cursor.fetchone()['total_cnt']
    
    term_conds = list(conditions) + ["event_type LIKE '%Мертворожд%'"]
    term_where = " WHERE " + " AND ".join(term_conds)
    cursor.execute(f"SELECT COUNT(*) as cnt FROM stillbirth_records{term_where}", params)
    term_stillborn_cnt = cursor.fetchone()['cnt']
    
    abort_conds = list(conditions) + ["event_type LIKE '%Аборт%'"]
    abort_where = " WHERE " + " AND ".join(abort_conds)
    cursor.execute(f"SELECT COUNT(*) as cnt FROM stillbirth_records{abort_where}", params)
    abortion_cnt = cursor.fetchone()['cnt']
    
    cursor.execute(f'''
        SELECT * FROM stillbirth_records 
        {where_sql} 
        ORDER BY event_date DESC, id DESC 
        LIMIT 100
    ''', params)
    records = [dict(r) for r in cursor.fetchall()]
    conn.close()
    
    return render_template('stillborn_list.html',
                           records=records,
                           total_count=total_count,
                           term_stillborn_cnt=term_stillborn_cnt,
                           abortion_cnt=abortion_cnt,
                           farms=farms,
                           event_types=Config.STILLBIRTH_EVENT_TYPES,
                           causes=Config.STILLBIRTH_CAUSES,
                           initial_farm=farm_filter,
                           initial_event_type=event_type_filter,
                           initial_start_date=start_date,
                           initial_end_date=end_date,
                           initial_search=search,
                           user_type=user_type)

@stillborn_bp.route('/add_stillborn', methods=['GET', 'POST'])
@login_required
def add_stillborn():
    """Регистрация мертворождения или аборта"""
    if session.get('user_type') == 'admin':
        flash('Администраторы не регистрируют первичные акты. Используйте учётную запись ветврача фермы.', 'warning')
        return redirect(url_for('stillborn.stillborn_list'))
        
    farm_name = session.get('farm_name')
    
    if request.method == 'POST':
        event_date = request.form.get('event_date')
        mother_tag = request.form.get('mother_tag', '').strip() or None
        mother_group = request.form.get('mother_group') or 'Полновозрастные коровы (2+ лакт.)'
        event_type = request.form.get('event_type') or 'Мертворождённый телёнок (в срок)'
        fetus_sex = request.form.get('fetus_sex') or 'Не определён'
        cause = request.form.get('cause', '').strip()
        custom_cause = request.form.get('custom_cause', '').strip()
        if custom_cause and (cause == 'Другое' or not cause):
            cause = custom_cause
            
        mother_condition = request.form.get('mother_condition') or 'Здорова, оставлена в стаде'
        attendant = request.form.get('attendant', '').strip() or 'Дежурный ветврач'
        notes = request.form.get('notes', '').strip() or None
        
        try:
            fetus_weight = float(request.form.get('fetus_weight')) if request.form.get('fetus_weight') else 25.0
        except (ValueError, TypeError):
            fetus_weight = 25.0
            
        try:
            gestation_days = int(request.form.get('gestation_days')) if request.form.get('gestation_days') else 280
        except (ValueError, TypeError):
            gestation_days = 280
            
        if not event_date or not cause or not event_type:
            flash('Пожалуйста, заполните дату, тип события и причину гибели плода.', 'danger')
            return render_template('stillborn_form.html',
                                   action='add',
                                   farm_name=farm_name,
                                   event_types=Config.STILLBIRTH_EVENT_TYPES,
                                   causes=Config.STILLBIRTH_CAUSES,
                                   fetus_sexes=Config.FETUS_SEXES,
                                   mother_conditions=Config.MOTHER_CONDITIONS,
                                   mother_groups=Config.MOTHER_GROUPS)
                                   
        record_code = generate_stillborn_code(farm_name)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO stillbirth_records 
            (record_code, farm_name, event_date, mother_tag, mother_group, event_type, 
             fetus_sex, fetus_weight, gestation_days, cause, mother_condition, attendant, notes, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (record_code, farm_name, event_date, mother_tag, mother_group, event_type,
              fetus_sex, fetus_weight, gestation_days, cause, mother_condition, attendant, notes, session.get('user_id')))
        new_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        log_audit_event(
            username=session.get('username'),
            farm_name=farm_name,
            action='CREATE',
            entity_type='STILLBIRTH',
            entity_id=new_id,
            details=f"Зарегистрировано {event_type} № {record_code} (Мать: {mother_tag or 'нет'}), причина: {cause}",
            user_id=session.get('user_id'),
            ip_address=request.remote_addr
        )
        
        flash(f'Акт мертворождения успешно зарегистрирован под номером {record_code}', 'success')
        return redirect(url_for('stillborn.stillborn_list'))
        
    return render_template('stillborn_form.html',
                           action='add',
                           farm_name=farm_name,
                           today=datetime.now().strftime('%Y-%m-%d'),
                           event_types=Config.STILLBIRTH_EVENT_TYPES,
                           causes=Config.STILLBIRTH_CAUSES,
                           fetus_sexes=Config.FETUS_SEXES,
                           mother_conditions=Config.MOTHER_CONDITIONS,
                           mother_groups=Config.MOTHER_GROUPS)

@stillborn_bp.route('/edit_stillborn/<int:record_id>', methods=['GET', 'POST'])
@login_required
def edit_stillborn(record_id):
    """Редактирование записи о мертворождении/аборте"""
    user_type = session.get('user_type')
    farm_name = session.get('farm_name')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if user_type == 'admin':
        cursor.execute('SELECT * FROM stillbirth_records WHERE id = ?', (record_id,))
    else:
        cursor.execute('SELECT * FROM stillbirth_records WHERE id = ? AND farm_name = ?', (record_id, farm_name))
        
    record_row = cursor.fetchone()
    if not record_row:
        conn.close()
        flash('Запись не найдена или у вас нет прав на её изменение', 'danger')
        return redirect(url_for('stillborn.stillborn_list'))
        
    record = dict(record_row)
    
    if request.method == 'POST':
        event_date = request.form.get('event_date')
        mother_tag = request.form.get('mother_tag', '').strip() or None
        mother_group = request.form.get('mother_group') or 'Полновозрастные коровы (2+ лакт.)'
        event_type = request.form.get('event_type') or 'Мертворождённый телёнок (в срок)'
        fetus_sex = request.form.get('fetus_sex') or 'Не определён'
        cause = request.form.get('cause', '').strip()
        custom_cause = request.form.get('custom_cause', '').strip()
        if custom_cause and (cause == 'Другое' or not cause):
            cause = custom_cause
            
        mother_condition = request.form.get('mother_condition') or 'Здорова, оставлена в стаде'
        attendant = request.form.get('attendant', '').strip() or 'Дежурный ветврач'
        notes = request.form.get('notes', '').strip() or None
        
        try:
            fetus_weight = float(request.form.get('fetus_weight')) if request.form.get('fetus_weight') else 25.0
        except (ValueError, TypeError):
            fetus_weight = 25.0
            
        try:
            gestation_days = int(request.form.get('gestation_days')) if request.form.get('gestation_days') else 280
        except (ValueError, TypeError):
            gestation_days = 280
            
        cursor.execute('''
            UPDATE stillbirth_records SET 
                event_date = ?,
                mother_tag = ?,
                mother_group = ?,
                event_type = ?,
                fetus_sex = ?,
                fetus_weight = ?,
                gestation_days = ?,
                cause = ?,
                mother_condition = ?,
                attendant = ?,
                notes = ?,
                updated_at = CURRENT_TIMESTAMP,
                updated_by = ?
            WHERE id = ?
        ''', (event_date, mother_tag, mother_group, event_type, fetus_sex, fetus_weight, 
              gestation_days, cause, mother_condition, attendant, notes, session.get('user_id'), record_id))
        conn.commit()
        conn.close()
        
        log_audit_event(
            username=session.get('username'),
            farm_name=record['farm_name'],
            action='UPDATE',
            entity_type='STILLBIRTH',
            entity_id=record_id,
            details=f"Отредактирован акт мертворождения {record['record_code']}. Новая причина: {cause}",
            user_id=session.get('user_id'),
            ip_address=request.remote_addr
        )
        
        flash(f'Акт {record["record_code"]} успешно сохранён', 'success')
        return redirect(url_for('stillborn.stillborn_list'))
        
    conn.close()
    return render_template('stillborn_form.html',
                           action='edit',
                           record=record,
                           farm_name=record['farm_name'],
                           event_types=Config.STILLBIRTH_EVENT_TYPES,
                           causes=Config.STILLBIRTH_CAUSES,
                           fetus_sexes=Config.FETUS_SEXES,
                           mother_conditions=Config.MOTHER_CONDITIONS,
                           mother_groups=Config.MOTHER_GROUPS)

@stillborn_bp.route('/delete_stillborn/<int:record_id>', methods=['POST'])
@login_required
def delete_stillborn(record_id):
    """Удаление акта мертворождения"""
    user_type = session.get('user_type')
    farm_name = session.get('farm_name')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if user_type == 'admin':
        cursor.execute('SELECT * FROM stillbirth_records WHERE id = ?', (record_id,))
    else:
        cursor.execute('SELECT * FROM stillbirth_records WHERE id = ? AND farm_name = ?', (record_id, farm_name))
        
    record = cursor.fetchone()
    if not record:
        conn.close()
        flash('Запись не найдена или нет прав на удаление', 'danger')
        return redirect(url_for('stillborn.stillborn_list'))
        
    cursor.execute('DELETE FROM stillbirth_records WHERE id = ?', (record_id,))
    conn.commit()
    conn.close()
    
    log_audit_event(
        username=session.get('username'),
        farm_name=record['farm_name'],
        action='DELETE',
        entity_type='STILLBIRTH',
        entity_id=record_id,
        details=f"Удалён акт мертворождения {record['record_code']} (Мать: {record['mother_tag'] or 'нет'})",
        user_id=session.get('user_id'),
        ip_address=request.remote_addr
    )
    
    flash(f'Акт {record["record_code"]} удалён', 'info')
    return redirect(url_for('stillborn.stillborn_list'))

@stillborn_bp.route('/export_stillborn_excel')
@login_required
def export_stillborn_excel():
    """Выгрузка журнала мертворождений и абортов в Excel"""
    user_type = session.get('user_type')
    session_farm = session.get('farm_name')
    
    farm_filter = request.args.get('farm', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    conditions = []
    params = []
    
    if user_type != 'admin':
        conditions.append("farm_name = ?")
        params.append(session_farm)
    elif farm_filter and farm_filter != 'all':
        conditions.append("farm_name = ?")
        params.append(farm_filter)
        
    if start_date and end_date:
        conditions.append("event_date BETWEEN ? AND ?")
        params.extend([start_date, end_date])
        
    where_sql = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    cursor.execute(f"SELECT * FROM stillbirth_records {where_sql} ORDER BY event_date ASC", params)
    rows = cursor.fetchall()
    conn.close()
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Мертворождения и аборты"
    
    # Стили
    title_font = Font(name='Arial', size=12, bold=True)
    header_font = Font(name='Arial', size=9, bold=True, color='FFFFFF')
    body_font = Font(name='Arial', size=9)
    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    thin_border = Border(
        left=Side(style='thin', color='CCCCCC'),
        right=Side(style='thin', color='CCCCCC'),
        top=Side(style='thin', color='CCCCCC'),
        bottom=Side(style='thin', color='CCCCCC')
    )
    
    org_name = get_setting('farm_org_name', 'ОАО «Новая Припять»')
    ws.merge_cells('A1:J1')
    ws['A1'] = f"{org_name} — Журнал учёта мертворождений и абортов"
    ws['A1'].font = title_font
    ws['A1'].alignment = Alignment(horizontal='left', vertical='center')
    
    ws.merge_cells('A2:J2')
    period_str = f"Период: {start_date} — {end_date}" if start_date and end_date else "За весь период"
    ws['A2'] = f"{period_str} | Подразделение: {farm_filter or session_farm or 'Все фермы'}"
    ws['A2'].font = Font(name='Arial', size=10, italic=True)
    
    headers = [
        "№ п/п", "Код акта", "Дата события", "МТФ / Ферма", 
        "Идент. № матери (AITS)", "Группа матери", "Тип события", 
        "Пол плода", "Масса плода (кг)", "Срок (дней)", "Причина гибели плода", 
        "Состояние матери", "Принял отёл", "Примечание"
    ]
    
    col_widths = [6, 18, 12, 16, 22, 22, 25, 14, 15, 12, 35, 25, 20, 25]
    for col_idx, width in enumerate(col_widths, start=1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = width
        
    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=4, column=col_idx, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = thin_border
        
    ws.row_dimensions[4].height = 28
    
    for row_idx, r in enumerate(rows, start=5):
        data = [
            row_idx - 4,
            r['record_code'],
            r['event_date'],
            r['farm_name'],
            r['mother_tag'] or '—',
            r['mother_group'] or '—',
            r['event_type'],
            r['fetus_sex'] or 'Не определён',
            r['fetus_weight'] or 0.0,
            r['gestation_days'] or 0,
            r['cause'],
            r['mother_condition'] or 'Здорова',
            r['attendant'] or '—',
            r['notes'] or ''
        ]
        for col_idx, val in enumerate(data, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.font = body_font
            cell.border = thin_border
            if col_idx in [1, 2, 3, 8, 10]:
                cell.alignment = Alignment(horizontal='center', vertical='center')
            elif col_idx == 9:
                cell.alignment = Alignment(horizontal='right', vertical='center')
            else:
                cell.alignment = Alignment(horizontal='left', vertical='center')
                
    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    filename = f"reestr_mertvorozhdenij_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
    return send_file(out, download_name=filename, as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
