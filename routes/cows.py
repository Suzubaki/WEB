# routes/cows.py - Управление записями выбытия скота (Журнал коров)
import os
import io
import csv
import json
from datetime import datetime
from flask import (
    Blueprint, render_template, request, redirect, 
    url_for, flash, session, jsonify, send_file
)
import openpyxl

from config import Config
from database import get_db_connection, generate_cow_id, log_audit_event
from .auth import login_required

cows_bp = Blueprint('cows', __name__)

def compute_lactation_phase(age_group, lactation_days, lactation=None):
    grp = (age_group or '').lower()
    if 'телят' in grp:
        return 'Молодняк (до 6 мес.)'
    if 'бычки' in grp:
        return 'Бычки на откорме'
    if 'молодняк' in grp:
        return 'Молодняк (6–18 мес.)'
    if 'нетел' in grp:
        return 'Нетели'
    if 'сухосто' in grp:
        return 'Сухостой'
    
    dim = None
    if lactation_days is not None and str(lactation_days).strip() != '':
        try:
            dim = int(lactation_days)
        except (ValueError, TypeError):
            pass
            
    if dim is not None:
        if dim <= 30:
            return 'Новотел (0–30 дн)'
        elif dim <= 100:
            return 'Раздой (31–100 дн)'
        elif dim <= 200:
            return 'Середина (101–200 дн)'
        else:
            return 'Спад (201–305+ дн)'
            
    return 'Новотел (0–30 дн)' if (lactation or 1) <= 1 else 'Раздой (31–100 дн)'

def build_age_group_sql(filter_val):
    if not filter_val or filter_val == 'all':
        return None, []
    f_lower = filter_val.lower().strip()
    if f_lower == 'молодняк_все':
        return "(LOWER(age_group) LIKE '%телят%' OR LOWER(age_group) LIKE '%молодняк%' OR LOWER(age_group) LIKE '%быч%')", []
    if any(k in f_lower for k in ['телят', 'до 6', '0-6', '0–6', 'новорожд']):
        return "(LOWER(age_group) LIKE '%телят%' OR LOWER(age_group) LIKE '%до 6%' OR LOWER(age_group) LIKE '%0-6%' OR LOWER(age_group) LIKE '%0–6%' OR LOWER(age_group) LIKE '%новорожд%')", []
    if any(k in f_lower for k in ['молодняк', '6-18', '6–18', '6-12', '6–12', 'ремонтн']):
        return "((LOWER(age_group) LIKE '%молодняк%' OR LOWER(age_group) LIKE '%6-18%' OR LOWER(age_group) LIKE '%6–18%' OR LOWER(age_group) LIKE '%6-12%' OR LOWER(age_group) LIKE '%ремонтн%') AND LOWER(age_group) NOT LIKE '%телят%')", []
    if any(k in f_lower for k in ['нетел', '18']):
        return "(LOWER(age_group) LIKE '%нетел%' OR LOWER(age_group) LIKE '%18%')", []
    if any(k in f_lower for k in ['быч', 'бык', 'откорм']):
        return "(LOWER(age_group) LIKE '%быч%' OR LOWER(age_group) LIKE '%бык%' OR LOWER(age_group) LIKE '%откорм%')", []
    if any(k in f_lower for k in ['первотел', 'первотёл', '1-я лакт', '1-й лакт', '1 лакт']):
        return "(LOWER(age_group) LIKE '%первотел%' OR LOWER(age_group) LIKE '%первотёл%' OR LOWER(age_group) LIKE '%1-я лакт%' OR LOWER(age_group) LIKE '%1-й лакт%' OR LOWER(age_group) LIKE '%1 лакт%' OR lactation = 1)", []
    if any(k in f_lower for k in ['полновозраст', '2+ лакт', '2+', '2 лакт', 'старше 2']):
        return "(LOWER(age_group) LIKE '%полновозраст%' OR LOWER(age_group) LIKE '%2+%' OR LOWER(age_group) LIKE '%2 лакт%' OR lactation > 1 OR (age_group LIKE '%дойное%' AND (lactation IS NULL OR lactation > 1)))", []
    if 'сухосто' in f_lower:
        return "LOWER(age_group) LIKE '%сухосто%'", []
    if any(k in f_lower for k in ['новотел', '0-30', '0–30']):
        return "(LOWER(age_group) LIKE '%новотел%' OR (lactation_days IS NOT NULL AND lactation_days <= 30 AND (lactation > 0 OR age_group LIKE '%коров%')))", []
    return "(age_group = ? OR LOWER(age_group) LIKE ?)", [filter_val, f"%{f_lower}%"]


@cows_bp.route('/cows')
@login_required
def view_cows():
    """Просмотр журнала выбытия коров (пагинированный, только первые 50 строк в HTML)"""
    user_type = session.get('user_type')
    farm_name = session.get('farm_name')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    farm_filter = request.args.get('farm', '').strip()
    category_filter = request.args.get('category', '').strip().lower()
    reason_filter = request.args.get('reason', '').strip()
    age_group_filter = request.args.get('age_group', '').strip()
    lactation_phase_filter = request.args.get('lactation_phase', '').strip()
    repro_filter = request.args.get('repro_filter', '').strip().lower()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    period = request.args.get('period', '').strip()
    
    where_parts = []
    base_params = []
    if user_type != 'admin':
        where_parts.append("farm_name = ?")
        base_params.append(farm_name)
    elif farm_filter and farm_filter != 'all':
        where_parts.append("farm_name = ?")
        base_params.append(farm_filter)

    if category_filter and category_filter != 'all':
        if 'сан' in category_filter:
            where_parts.append("category LIKE '%сан%'")
        else:
            where_parts.append("category = ?")
            base_params.append(category_filter)

    if reason_filter and reason_filter != 'all':
        where_parts.append("reason = ?")
        base_params.append(reason_filter)

    if age_group_filter and age_group_filter != 'all':
        ag_cond, ag_params = build_age_group_sql(age_group_filter)
        if ag_cond:
            where_parts.append(ag_cond)
            base_params.extend(ag_params)

    if lactation_phase_filter and lactation_phase_filter != 'all':
        where_parts.append("lactation_phase LIKE ?")
        base_params.append(f"%{lactation_phase_filter}%")

    if repro_filter == 'pregnant':
        where_parts.append("(is_pregnant = 1 OR gestation_days > 0 OR age_group LIKE '%сухостой%' OR age_group LIKE '%нетел%' OR reason LIKE '%стельн%')")
    elif repro_filter == 'pregnant_late':
        where_parts.append("(gestation_days >= 180 OR (is_pregnant = 1 AND age_group LIKE '%сухостой%'))")

    if start_date and end_date:
        where_parts.append("disposal_date BETWEEN ? AND ?")
        base_params.extend([start_date, end_date])
        
    initial_where = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""

    if user_type == 'admin':
        cursor.execute('SELECT DISTINCT farm_name FROM cows WHERE farm_name IS NOT NULL AND farm_name != "" ORDER BY farm_name')
        farms = [r['farm_name'] for r in cursor.fetchall()]
    else:
        farms = [farm_name]

    cursor.execute(f'SELECT COUNT(*) as cnt FROM cows{initial_where}', base_params)
    total_count = cursor.fetchone()['cnt']
    cursor.execute(f'SELECT id, cow_id, ear_tag, farm_name, age_group, category, reason, weight, lactation, lactation_days, lactation_phase, disposal_date, is_pregnant, gestation_days, is_stillborn FROM cows{initial_where} ORDER BY disposal_date DESC, id DESC LIMIT 50', base_params)
        
    cows_data = cursor.fetchall()
    conn.close()
    
    cows = [dict(c) for c in cows_data]
    return render_template('view_cows.html', cows=cows, user_type=user_type, total_count=total_count, farms=farms, categories=Config.DISPOSAL_CATEGORIES, repro_filter=repro_filter, initial_farm=farm_filter, initial_category=category_filter, initial_reason=reason_filter, initial_age_group=age_group_filter, initial_start_date=start_date, initial_end_date=end_date, initial_period=period)

@cows_bp.route('/api/cows')
@login_required
def api_cows():
    """Быстрый пагинированный API для журнала коров (0 мс задержки)"""
    from flask import jsonify
    user_type = session.get('user_type')
    session_farm = session.get('farm_name')
    
    page = max(1, request.args.get('page', 1, type=int))
    limit = min(500, max(10, request.args.get('limit', 50, type=int)))
    farm_filter = request.args.get('farm', '').strip()
    category_filter = request.args.get('category', '').strip().lower()
    reason_filter = request.args.get('reason', '').strip()
    age_group_filter = request.args.get('age_group', '').strip()
    lactation_phase_filter = request.args.get('lactation_phase', '').strip()
    repro_filter = request.args.get('repro_filter', '').strip().lower()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    period = request.args.get('period', '').strip()
    search_query = request.args.get('search', '').strip()[:100].lower()
    sort = request.args.get('sort', 'newest').strip()
    
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
        
    if category_filter and category_filter != 'all':
        if 'сан' in category_filter:
            conditions.append("category LIKE '%сан%'")
        else:
            conditions.append("category = ?")
            params.append(category_filter)
            
    if reason_filter and reason_filter != 'all':
        conditions.append("reason = ?")
        params.append(reason_filter)
        
    if age_group_filter and age_group_filter != 'all':
        ag_cond, ag_params = build_age_group_sql(age_group_filter)
        if ag_cond:
            conditions.append(ag_cond)
            params.extend(ag_params)

    if lactation_phase_filter and lactation_phase_filter != 'all':
        conditions.append("lactation_phase LIKE ?")
        params.append(f"%{lactation_phase_filter}%")

    if repro_filter == 'pregnant':
        conditions.append("(is_pregnant = 1 OR gestation_days > 0 OR age_group LIKE '%сухостой%' OR age_group LIKE '%нетел%' OR reason LIKE '%стельн%')")
    elif repro_filter == 'pregnant_late':
        conditions.append("(gestation_days >= 180 OR (is_pregnant = 1 AND age_group LIKE '%сухостой%'))")

    if start_date and end_date:
        conditions.append("disposal_date BETWEEN ? AND ?")
        params.extend([start_date, end_date])
        
    if search_query:
        conditions.append("(cow_id LIKE ? OR ear_tag LIKE ? OR reason LIKE ? OR farm_name LIKE ? OR age_group LIKE ? OR lactation_phase LIKE ?)")
        wild = f"%{search_query}%"
        params.extend([wild, wild, wild, wild, wild, wild])
        
    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    
    cursor.execute(f"SELECT COUNT(*) as cnt FROM cows{where_clause}", params)
    total_filtered = cursor.fetchone()['cnt']
    
    if sort == 'oldest':
        order_clause = "ORDER BY disposal_date ASC, id ASC"
    elif sort == 'weight_desc':
        order_clause = "ORDER BY weight DESC"
    elif sort == 'id_asc':
        order_clause = "ORDER BY id ASC"
    elif sort == 'id_desc':
        order_clause = "ORDER BY id DESC"
    else:
        order_clause = "ORDER BY disposal_date DESC, id DESC"
        
    offset = (page - 1) * limit
    cursor.execute(f"SELECT id, cow_id, ear_tag, farm_name, age_group, category, reason, weight, lactation, lactation_days, lactation_phase, disposal_date, is_pregnant, gestation_days, is_stillborn FROM cows{where_clause} {order_clause} LIMIT ? OFFSET ?", params + [limit, offset])
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    
    total_pages = max(1, (total_filtered + limit - 1) // limit)
    
    return jsonify({
        'success': True,
        'total_filtered': total_filtered,
        'page': page,
        'limit': limit,
        'total_pages': total_pages,
        'start_index': offset + 1 if total_filtered > 0 else 0,
        'end_index': min(offset + limit, total_filtered),
        'cows': rows
    })

@cows_bp.route('/add_cow', methods=['GET', 'POST'])
@login_required
def add_cow():
    """Добавление единичной записи выбытия КРС"""
    if session.get('user_type') == 'admin':
        flash('Администраторы не могут добавлять коров', 'warning')
        return redirect(url_for('main.dashboard'))
        
    farm_name = session.get('farm_name')
    
    if request.method == 'POST':
        # Если отправлена форма мертворождения со второй вкладки
        if request.form.get('form_mode') == 'stillborn':
            from database import generate_stillborn_code
            sb_date = request.form.get('disposal_date') or datetime.now().strftime('%Y-%m-%d')
            sb_reason = request.form.get('reason') or 'Мертворождённый телёнок (в срок)'
            sb_mother_tag = request.form.get('ear_tag', '').strip() or None
            sb_notes = request.form.get('notes', '').strip() or None
            try:
                sb_weight = float(request.form.get('weight')) if request.form.get('weight') else 25.0
            except (ValueError, TypeError):
                sb_weight = 25.0
            try:
                sb_gest = int(request.form.get('gestation_days')) if request.form.get('gestation_days') else 280
            except (ValueError, TypeError):
                sb_gest = 280
                
            sb_code = generate_stillborn_code(farm_name)
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO stillbirth_records (
                    record_code, farm_name, event_date, mother_tag, mother_group,
                    event_type, fetus_sex, fetus_weight, gestation_days, cause,
                    mother_condition, attendant, notes, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                sb_code, farm_name, sb_date, sb_mother_tag, 'Коровы дойного стада',
                sb_reason, 'Не определён', sb_weight, sb_gest, sb_reason,
                'Здорова, оставлена в стаде', 'Дежурный ветврач', sb_notes, session.get('user_id')
            ))
            new_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            log_audit_event(
                username=session.get('username'),
                farm_name=farm_name,
                action='CREATE',
                entity_type='STILLBORN',
                entity_id=new_id,
                details=f"Зарегистрирован акт мертворождения {sb_code} (мать: {sb_mother_tag or '-'})",
                user_id=session.get('user_id'),
                ip_address=request.remote_addr
            )
            flash(f'Акт мертворождения успешно зарегистрирован под номером: {sb_code}', 'success')
            return redirect(url_for('stillborn.stillborn_list'))

        category = request.form.get('category')
        reason = request.form.get('reason')
        disposal_date = request.form.get('disposal_date')
        ear_tag = request.form.get('ear_tag', '').strip() or None
        lactation = request.form.get('lactation') or None
        lactation_days = request.form.get('lactation_days') or None
        weight = request.form.get('weight') or None
        notes = request.form.get('notes', '').strip() or None
        age_group = request.form.get('age_group') or 'Коровы дойного стада'
        breed = request.form.get('breed') or 'Черно-пёстрая'
        milk_yield = request.form.get('milk_yield') or None
        book_value = request.form.get('book_value') or None
        
        # Вычисляем физиологическую фазу лактации
        lactation_phase = compute_lactation_phase(age_group, lactation_days, lactation)

        # Воспроизводство и стельность
        is_pregnant_val = 1 if request.form.get('is_pregnant') in ['1', 'on', 'true'] else 0
        try:
            gestation_days_val = int(request.form.get('gestation_days')) if request.form.get('gestation_days') else 0
        except (ValueError, TypeError):
            gestation_days_val = 0
        is_stillborn_val = 0
        if not is_pregnant_val:
            if 'сухосто' in (lactation_phase or '').lower() or 'сухосто' in (age_group or '').lower() or 'нетел' in (age_group or '').lower() or 'стельн' in (reason or '').lower():
                is_pregnant_val = 1
                if gestation_days_val == 0:
                    gestation_days_val = 210 if 'сухосто' in (age_group or '').lower() else 180

        
        if not category or not reason or not disposal_date:
            flash('Заполните обязательные поля: категория, причина и дата', 'danger')
            return render_template('add_cow.html', categories=Config.DISPOSAL_CATEGORIES, farm_name=farm_name, breeds=Config.BREEDS, age_groups=Config.AGE_GROUPS)
            
        today = datetime.now().strftime('%Y-%m-%d')
        if disposal_date > today:
            flash('Дата выбытия не может быть позже сегодняшнего дня', 'danger')
            return render_template('add_cow.html', categories=Config.DISPOSAL_CATEGORIES, farm_name=farm_name, breeds=Config.BREEDS, age_groups=Config.AGE_GROUPS)
            
        cow_id = generate_cow_id(farm_name)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO cows (cow_id, ear_tag, farm_name, category, reason, disposal_date, 
                              lactation, lactation_days, lactation_phase, weight, notes, age_group, breed, milk_yield, book_value, is_pregnant, gestation_days, is_stillborn, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (cow_id, ear_tag, farm_name, category, reason, disposal_date, 
              lactation, lactation_days, lactation_phase, weight, notes, age_group, breed, milk_yield, book_value, is_pregnant_val, gestation_days_val, is_stillborn_val, session.get('user_id')))
        new_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        log_audit_event(
            username=session.get('username'),
            farm_name=farm_name,
            action='CREATE',
            entity_type='COW',
            entity_id=new_id,
            details=f"Добавлена корова {cow_id} (Ушной № {ear_tag or '-'}), {category}: {reason}, фаза: {lactation_phase}",
            user_id=session.get('user_id'),
            ip_address=request.remote_addr
        )
        
        flash(f'Корова успешно добавлена с системным номером: {cow_id}', 'success')
        return redirect(url_for('cows.view_cows'))
        
    return render_template('add_cow.html', categories=Config.DISPOSAL_CATEGORIES, farm_name=farm_name, breeds=Config.BREEDS, age_groups=Config.AGE_GROUPS)

@cows_bp.route('/edit_cow/<int:cow_id>', methods=['GET', 'POST'])
@login_required
def edit_cow(cow_id):
    """Редактирование записи о корове"""
    user_type = session.get('user_type')
    farm_name = session.get('farm_name')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if user_type == 'admin':
        cursor.execute('SELECT * FROM cows WHERE id = ?', (cow_id,))
    else:
        cursor.execute('SELECT * FROM cows WHERE id = ? AND farm_name = ?', (cow_id, farm_name))
        
    cow_row = cursor.fetchone()
    
    if not cow_row:
        conn.close()
        flash('Запись не найдена или у вас нет прав на её редактирование', 'danger')
        return redirect(url_for('cows.view_cows'))
        
    cow = dict(cow_row)
    
    if request.method == 'POST':
        category = request.form.get('category')
        reason = request.form.get('reason')
        disposal_date = request.form.get('disposal_date')
        ear_tag = request.form.get('ear_tag', '').strip() or None
        lactation = request.form.get('lactation') or None
        lactation_days = request.form.get('lactation_days') or None
        weight = request.form.get('weight') or None
        notes = request.form.get('notes', '').strip() or None
        age_group = request.form.get('age_group') or 'Коровы дойного стада'
        breed = request.form.get('breed') or 'Черно-пёстрая'
        milk_yield = request.form.get('milk_yield') or None
        book_value = request.form.get('book_value') or None
        
        # Воспроизводство и стельность
        is_pregnant_val = 1 if request.form.get('is_pregnant') in ['1', 'on', 'true'] else 0
        try:
            gestation_days_val = int(request.form.get('gestation_days')) if request.form.get('gestation_days') else 0
        except (ValueError, TypeError):
            gestation_days_val = 0
        is_stillborn_val = 0

        lactation_phase = compute_lactation_phase(age_group, lactation_days, lactation)
        
        today = datetime.now().strftime('%Y-%m-%d')
        if disposal_date > today:
            flash('Дата выбытия не может быть в будущем', 'danger')
            conn.close()
            return render_template('edit_cow.html', cow=cow, categories=Config.DISPOSAL_CATEGORIES)
            
        cursor.execute('''
            UPDATE cows SET 
                category = ?, 
                reason = ?, 
                disposal_date = ?, 
                ear_tag = ?, 
                lactation = ?, 
                lactation_days = ?,
                lactation_phase = ?,
                weight = ?, 
                notes = ?, 
                age_group = ?,
                breed = ?,
                milk_yield = ?,
                book_value = ?,
                is_pregnant = ?,
                gestation_days = ?,
                is_stillborn = ?,
                updated_at = CURRENT_TIMESTAMP, 
                updated_by = ?
            WHERE id = ?
        ''', (category, reason, disposal_date, ear_tag, lactation, lactation_days, lactation_phase, weight, notes, 
              age_group, breed, milk_yield, book_value, is_pregnant_val, gestation_days_val, is_stillborn_val, session.get('user_id'), cow_id))
        conn.commit()
        conn.close()
        
        log_audit_event(
            username=session.get('username'),
            farm_name=cow['farm_name'],
            action='UPDATE',
            entity_type='COW',
            entity_id=cow_id,
            details=f"Отредактирована запись {cow['cow_id']}. Новые данные: {category} - {reason}, дата {disposal_date}",
            user_id=session.get('user_id'),
            ip_address=request.remote_addr
        )
        
        flash(f'Запись {cow["cow_id"]} успешно обновлена', 'success')
        return redirect(url_for('cows.view_cows'))
        
    conn.close()
    return render_template('edit_cow.html', cow=cow, categories=Config.DISPOSAL_CATEGORIES)

@cows_bp.route('/delete_cow/<int:cow_id>', methods=['POST'])
@login_required
def delete_cow(cow_id):
    """Удаление записи выбытия"""
    user_type = session.get('user_type')
    farm_name = session.get('farm_name')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if user_type == 'admin':
        cursor.execute('SELECT * FROM cows WHERE id = ?', (cow_id,))
    else:
        cursor.execute('SELECT * FROM cows WHERE id = ? AND farm_name = ?', (cow_id, farm_name))
        
    cow = cursor.fetchone()
    if not cow:
        conn.close()
        if request.is_json:
            return jsonify({'error': 'Запись не найдена'}), 404
        flash('Запись не найдена', 'danger')
        return redirect(url_for('cows.view_cows'))
        
    cow_dict = dict(cow)
    cursor.execute('DELETE FROM cows WHERE id = ?', (cow_id,))
    conn.commit()
    conn.close()
    
    log_audit_event(
        username=session.get('username'),
        farm_name=cow_dict['farm_name'],
        action='DELETE',
        entity_type='COW',
        entity_id=cow_id,
        details=f"Удалена запись {cow_dict['cow_id']} ({cow_dict['category']}: {cow_dict['reason']})",
        user_id=session.get('user_id'),
        ip_address=request.remote_addr
    )
    
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'message': 'Запись удалена'})
        
    flash(f'Запись {cow_dict["cow_id"]} успешно удалена', 'success')
    return redirect(url_for('cows.view_cows'))

@cows_bp.route('/bulk_delete_cows', methods=['POST'])
@cows_bp.route('/delete_multiple_cows', methods=['POST'], endpoint='delete_multiple_cows')
@login_required
def bulk_delete_cows():
    """Массовое удаление записей"""
    data = request.get_json() or {}
    cow_ids = data.get('ids', []) or data.get('cow_ids', [])
    if not cow_ids:
        return jsonify({'error': 'Не выбрано ни одной записи'}), 400
        
    user_type = session.get('user_type')
    farm_name = session.get('farm_name')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    placeholders = ','.join('?' * len(cow_ids))
    if user_type == 'admin':
        query = f"SELECT id, cow_id, farm_name FROM cows WHERE id IN ({placeholders})"
        cursor.execute(query, cow_ids)
    else:
        query = f"SELECT id, cow_id, farm_name FROM cows WHERE id IN ({placeholders}) AND farm_name = ?"
        cursor.execute(query, cow_ids + [farm_name])
        
    found_cows = cursor.fetchall()
    valid_ids = [c['id'] for c in found_cows]
    
    if valid_ids:
        del_placeholders = ','.join('?' * len(valid_ids))
        cursor.execute(f"DELETE FROM cows WHERE id IN ({del_placeholders})", valid_ids)
        conn.commit()
        
        log_audit_event(
            username=session.get('username'),
            farm_name=farm_name or 'Admin',
            action='BULK_DELETE',
            entity_type='COW',
            details=f"Массовое удаление {len(valid_ids)} записей",
            user_id=session.get('user_id'),
            ip_address=request.remote_addr
        )
        
    conn.close()
    return jsonify({'success': True, 'deleted_count': len(valid_ids)})

@cows_bp.route('/add_cows_dynamic')
@login_required
def add_cows_dynamic():
    """Динамическая форма множественного ввода записей"""
    if session.get('user_type') == 'admin':
        flash('Администраторы не могут добавлять коров', 'warning')
        return redirect(url_for('main.dashboard'))
        
    return render_template('add_cows_dynamic.html', 
                           categories=Config.DISPOSAL_CATEGORIES, 
                           farm_name=session.get('farm_name'),
                           breeds=Config.BREEDS,
                           age_groups=Config.AGE_GROUPS,
                           today=datetime.now().strftime('%Y-%m-%d'))

@cows_bp.route('/add_multiple_cows', methods=['GET', 'POST'])
@login_required
def add_multiple_cows():
    """Множественное добавление коров табличным списком"""
    if session.get('user_type') == 'admin':
        if request.is_json:
            return jsonify({'error': 'Администраторы не могут добавлять коров'}), 403
        flash('Администраторы не могут добавлять коров', 'warning')
        return redirect(url_for('main.dashboard'))
        
    farm_name = session.get('farm_name')
    
    if request.method == 'POST':
        cows_data = []
        if request.is_json:
            data = request.get_json()
            if isinstance(data, list):
                cows_data = data
            elif isinstance(data, dict):
                cows_data = data.get('cows_data', [])
        else:
            raw = request.form.get('cows_data')
            if raw:
                try:
                    parsed = json.loads(raw)
                    cows_data = parsed if isinstance(parsed, list) else parsed.get('cows_data', [])
                except:
                    pass
                    
        conn = get_db_connection()
        cursor = conn.cursor()
        today = datetime.now().strftime('%Y-%m-%d')
        added_count = 0
        
        for item in cows_data:
            cat = item.get('category')
            rea = item.get('reason')
            d_date = item.get('disposal_date')
            ear_tag = item.get('ear_tag') or None
            lactation = item.get('lactation') or None
            weight = item.get('weight') or None
            notes = item.get('notes') or None
            age_group = item.get('age_group') or 'Коровы дойного стада'
            breed = item.get('breed') or 'Черно-пёстрая'
            milk_yield = item.get('milk_yield') or None
            book_value = item.get('book_value') or None
            
            # Воспроизводство и стельность
            is_pregnant = 1 if item.get('is_pregnant') in [1, '1', True, 'true', 'on'] else 0
            gestation_days = int(item.get('gestation_days')) if item.get('gestation_days') else 0
            is_stillborn = 1 if item.get('is_stillborn') in [1, '1', True, 'true', 'on'] else 0
            
            # Автоопределение по признакам
            if not is_pregnant:
                if 'сухосто' in (age_group or '').lower() or 'нетел' in (age_group or '').lower() or 'стельн' in (rea or '').lower():
                    is_pregnant = 1
                    if gestation_days == 0:
                        gestation_days = 210 if 'сухосто' in (age_group or '').lower() else 180
            if not is_stillborn:
                stillborn_keys = ['мертворож', 'аборт', 'плод', 'мумификац', 'мацерац', 'патология родов', 'патологические роды', 'гибель плода', 'мертвый теленок']
                if any(k in (rea or '').lower() for k in stillborn_keys):
                    is_stillborn = 1
            
            if cat and rea and d_date and d_date <= today:
                cow_id = generate_cow_id(farm_name)
                cursor.execute('''
                    INSERT INTO cows (cow_id, ear_tag, farm_name, category, reason, disposal_date, 
                                      lactation, weight, notes, age_group, breed, milk_yield, book_value, is_pregnant, gestation_days, is_stillborn, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (cow_id, ear_tag, farm_name, cat, rea, d_date, 
                      lactation, weight, notes, age_group, breed, milk_yield, book_value, is_pregnant, gestation_days, is_stillborn, session.get('user_id')))
                added_count += 1
                
        conn.commit()
        conn.close()
        
        if added_count > 0:
            log_audit_event(
                username=session.get('username'),
                farm_name=farm_name,
                action='CREATE_BATCH',
                entity_type='COW',
                details=f"Пакетно добавлено {added_count} коров",
                user_id=session.get('user_id'),
                ip_address=request.remote_addr
            )
        
        if request.is_json:
            return jsonify({'success': True, 'added_count': added_count})
            
        flash(f'Успешно добавлено {added_count} коров', 'success')
        return redirect(url_for('cows.view_cows'))
        
    return render_template('add_multiple_cows.html', categories=Config.DISPOSAL_CATEGORIES, farm_name=farm_name)

@cows_bp.route('/import_cows', methods=['GET', 'POST'])
@login_required
def import_cows():
    """Импорт данных выбытия из Excel / CSV файлов"""
    if session.get('user_type') == 'admin':
        flash('Только пользователи ферм могут импортировать данные своего хозяйства', 'warning')
        return redirect(url_for('main.dashboard'))
        
    farm_name = session.get('farm_name')
    today = datetime.now().strftime('%Y-%m-%d')
    
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Файл не выбран', 'danger')
            return redirect(request.url)
            
        file = request.files['file']
        if file.filename == '':
            flash('Файл не выбран', 'danger')
            return redirect(request.url)
            
        filename = file.filename.lower()
        rows_to_insert = []
        errors = []
        
        try:
            if filename.endswith('.csv'):
                stream = io.StringIO(file.stream.read().decode("utf-8-sig"), newline=None)
                csv_reader = csv.reader(stream, delimiter=';' if ';' in stream.getvalue() else ',')
                header = next(csv_reader, None)
                for line_num, row in enumerate(csv_reader, start=2):
                    if not row or len(row) < 3:
                        continue
                    cat = row[0].strip().lower()
                    rea = row[1].strip()
                    d_date = row[2].strip()
                    ear_tag = row[3].strip() if len(row) > 3 and row[3].strip() else None
                    lact = int(row[4]) if len(row) > 4 and row[4].strip().isdigit() else None
                    w = float(row[5].replace(',', '.')) if len(row) > 5 and row[5].strip() else None
                    notes = row[6].strip() if len(row) > 6 and row[6].strip() else None
                    
                    if cat not in ['падёж', 'выбраковка', 'санитарный']:
                        errors.append(f"Строка {line_num}: недопустимая категория '{cat}'")
                        continue
                    if d_date > today:
                        errors.append(f"Строка {line_num}: дата {d_date} позже сегодняшней")
                        continue
                    rows_to_insert.append((cat, rea, d_date, ear_tag, lact, w, notes))
                    
            elif filename.endswith(('.xlsx', '.xls')):
                wb = openpyxl.load_workbook(file, data_only=True)
                ws = wb.active
                for line_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                    if not row or not row[0]:
                        continue
                    cat = str(row[0]).strip().lower()
                    rea = str(row[1]).strip() if row[1] else ''
                    
                    raw_date = row[2]
                    if isinstance(raw_date, datetime):
                        d_date = raw_date.strftime('%Y-%m-%d')
                    else:
                        d_date = str(raw_date).strip()
                        
                    ear_tag = str(row[3]).strip() if len(row) > 3 and row[3] else None
                    lact = int(row[4]) if len(row) > 4 and str(row[4]).strip().isdigit() else None
                    try:
                        w = float(str(row[5]).replace(',', '.')) if len(row) > 5 and row[5] else None
                    except ValueError:
                        w = None
                    notes = str(row[6]).strip() if len(row) > 6 and row[6] else None
                    
                    if cat not in ['падёж', 'выбраковка', 'санитарный']:
                        errors.append(f"Строка {line_num}: недопустимая категория '{cat}'")
                        continue
                    if d_date > today:
                        errors.append(f"Строка {line_num}: дата {d_date} позже сегодняшней")
                        continue
                    rows_to_insert.append((cat, rea, d_date, ear_tag, lact, w, notes))
            else:
                flash('Поддерживаются только форматы .xlsx, .xls и .csv', 'danger')
                return redirect(request.url)
                
        except Exception as e:
            flash(f'Ошибка обработки файла: {str(e)}', 'danger')
            return redirect(request.url)
            
        if rows_to_insert:
            conn = get_db_connection()
            cursor = conn.cursor()
            inserted_count = 0
            for r in rows_to_insert:
                cat, rea, d_date, ear_tag, lact, w, notes = r[:7]
                cow_id = generate_cow_id(farm_name)
                
                # Автоопределение группы скота
                age_group = 'Коровы дойного стада'
                rea_low = (rea or '').lower()
                notes_low = (notes or '').lower()

                if 'тел' in rea_low or 'диспепс' in rea_low or 'тел' in notes_low:
                    age_group = 'Телята (0–6 мес.)'
                elif 'нетел' in rea_low or 'нетел' in notes_low:
                    age_group = 'Нетели'
                elif 'сухосто' in rea_low or 'сухосто' in notes_low:
                    age_group = 'Коровы сухостойные'
                elif 'быч' in rea_low or 'быч' in notes_low:
                    age_group = 'Бычки на откорме'

                lact_phase = compute_lactation_phase(age_group, None, lact)

                is_pregnant = 0
                gestation_days = 0
                if 'сухосто' in age_group.lower() or 'нетел' in age_group.lower() or 'стельн' in rea_low or 'стельн' in notes_low:
                    is_pregnant = 1
                    gestation_days = 210 if 'сухосто' in age_group.lower() else 180

                is_stillborn = 0
                stillborn_keys = ['мертворож', 'аборт', 'плод', 'мумификац', 'мацерац', 'патология родов', 'патологические роды', 'гибель плода', 'мертвый теленок']
                if any(k in rea_low or k in notes_low for k in stillborn_keys):
                    is_stillborn = 1

                cursor.execute('''
                    INSERT INTO cows (cow_id, ear_tag, farm_name, category, reason, disposal_date, lactation, lactation_phase, weight, notes, age_group, is_pregnant, gestation_days, is_stillborn, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (cow_id, ear_tag, farm_name, cat, rea, d_date, lact, lact_phase, w, notes, age_group, is_pregnant, gestation_days, is_stillborn, session.get('user_id')))
                inserted_count += 1
            conn.commit()
            conn.close()
            
            log_audit_event(
                username=session.get('username'),
                farm_name=farm_name,
                action='IMPORT',
                entity_type='COW',
                details=f"Импортировано {inserted_count} записей из файла {file.filename}",
                user_id=session.get('user_id'),
                ip_address=request.remote_addr
            )
            
            flash(f'Успешно импортировано {inserted_count} коров!', 'success')
            if errors:
                flash(f'Внимание: пропущено строк с ошибками: {len(errors)}', 'warning')
            return redirect(url_for('cows.view_cows'))
        else:
            flash('В файле не найдено корректных строк для импорта.', 'danger')
            return redirect(request.url)
            
    return render_template('import_cows.html', farm_name=farm_name)

@cows_bp.route('/download_import_template')
@login_required
def download_import_template():
    """Скачать образец Excel-шаблона для импорта"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Шаблон_Импорта"
    
    headers = ['Категория (падёж/выбраковка/санитарный)*', 'Причина выбытия*', 'Дата (ГГГГ-ММ-ДД)*', 'Инв./Ушной №', 'Лактация', 'Масса (кг)', 'Примечание']
    ws.append(headers)
    
    # Примерные строки
    ws.append(['падёж', 'Острая тимпания', datetime.now().strftime('%Y-%m-%d'), '7701', 3, 520.5, 'Заключение ветврача'])
    ws.append(['выбраковка', 'Агалактия', datetime.now().strftime('%Y-%m-%d'), '7702', 4, 480.0, 'Низкая продуктивность'])
    ws.append(['санитарный', 'Травма конечностей', datetime.now().strftime('%Y-%m-%d'), '7703', 2, 510.0, 'Травма в секции'])
    
    # Стилизация шапки
    for cell in ws[1]:
        cell.font = openpyxl.styles.Font(bold=True, color="FFFFFF")
        cell.fill = openpyxl.styles.PatternFill(start_color="3B82F6", end_color="3B82F6", fill_type="solid")
        cell.alignment = openpyxl.styles.Alignment(horizontal="center")
        
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 14)
        
    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return send_file(out, download_name="shablon_importa_korov.xlsx", as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
