from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
import sqlite3
from datetime import datetime, timedelta
import os
import json
from config import Config
from auth import login_required, admin_required, farm_user_required, login_user, register_user, update_user
from database import init_db, get_db_connection
from models import Cow, Report
from charts import get_statistics_data, prepare_chart_data, get_dashboard_stats, get_user_statistics
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
import io

app = Flask(__name__)
app.config.from_object(Config)

# Создаем папку для отчётов
if not os.path.exists(Config.REPORT_FOLDER):
    os.makedirs(Config.REPORT_FOLDER)

@app.route('/')
def index():
    """Главная страница - всегда перенаправляет на вход"""
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = login_user(username, password)
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['user_type'] = user['user_type']
            session['farm_name'] = user['farm_name']
            flash('Вход выполнен успешно', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Неверное имя пользователя или пароль', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
@login_required
@admin_required
def register():
    """Страница регистрации (только для администраторов)"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user_type = request.form.get('user_type')
        farm_name = request.form.get('farm_name') if user_type == 'farm' else None
        
        if register_user(username, password, user_type, farm_name):
            flash('Регистрация успешна. Новый пользователь создан.', 'success')
            return redirect(url_for('register'))  # Остаемся на странице регистрации
        else:
            flash('Имя пользователя уже занято', 'danger')
    
    return render_template('register.html')

@app.route('/user_management')
@login_required
@admin_required
def user_management():
    """Управление пользователями (только для администраторов)"""
    from auth import get_all_users
    users = get_all_users()
    return render_template('user_management.html', users=users)

@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    """Редактирование пользователя (только для администраторов)"""
    from auth import get_user_by_id, update_user
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user_type = request.form.get('user_type')
        farm_name = request.form.get('farm_name') if user_type == 'farm' else None
        
        # Если пароль не указан, не обновляем его
        update_password = password if password else None
        
        if update_user(user_id, username, update_password, user_type, farm_name):
            flash('Данные пользователя успешно обновлены', 'success')
            return redirect(url_for('user_management'))
        else:
            flash('Ошибка при обновлении данных пользователя', 'danger')
    
    user = get_user_by_id(user_id)
    if not user:
        flash('Пользователь не найден', 'danger')
        return redirect(url_for('user_management'))
    
    return render_template('edit_user.html', user=user)

@app.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    """Удаление пользователя (только для администраторов)"""
    # Нельзя удалить самого себя
    if user_id == session.get('user_id'):
        flash('Вы не можете удалить свою собственную учетную запись', 'danger')
        return redirect(url_for('user_management'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Получаем информацию о пользователе перед удалением
    cursor.execute('SELECT username FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    
    if user:
        # Удаляем пользователя
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        flash(f'Пользователь {user[0]} успешно удален', 'success')
    else:
        flash('Пользователь не найден', 'danger')
    
    conn.close()
    return redirect(url_for('user_management'))

@app.route('/logout')
def logout():
    """Выход из системы"""
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Панель управления"""
    user_type = session.get('user_type')
    farm_name = session.get('farm_name')
    
    # Получаем данные для графиков
    stats_data = get_statistics_data(user_type, farm_name)
    chart_data = prepare_chart_data(stats_data)
    dashboard_stats = get_dashboard_stats(user_type, farm_name)
    
    # Для админов добавляем статистику пользователей
    user_stats_data = None
    if user_type == 'admin':
        user_stats_data = get_user_statistics()
    
    return render_template('dashboard.html', 
                         user_type=user_type,
                         farm_name=farm_name,
                         chart_data=chart_data,
                         dashboard_stats=dashboard_stats,
                         user_stats_data=user_stats_data)

@app.route('/add_cow', methods=['GET', 'POST'])
@login_required
def add_cow():
    """Добавление одной коровы (только для пользователей ферм)"""
    user_type = session.get('user_type')
    
    # Администраторы не могут добавлять коров
    if user_type == 'admin':
        flash('Администраторы не могут добавлять коров. Используйте просмотр и отчёты.', 'warning')
        return redirect(url_for('dashboard'))
    
    farm_name = session.get('farm_name')
    
    if request.method == 'POST':
        # ID генерируется автоматически
        from database import generate_cow_id
        cow_id = generate_cow_id(farm_name)
        
        category = request.form.get('category')
        reason = request.form.get('reason')
        disposal_date = request.form.get('disposal_date')
        
        if not all([category, reason, disposal_date]):
            flash('Заполните все поля', 'danger')
            return redirect(url_for('add_cow'))
        
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO cows (cow_id, farm_name, category, reason, disposal_date, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (cow_id, farm_name, category, reason, disposal_date, session.get('user_id')))
        conn.commit()
        conn.close()
        
        flash(f'Корова успешно добавлена с ID: {cow_id}', 'success')
        return redirect(url_for('view_cows'))
    
    return render_template('add_cow.html', 
                         categories=Config.DISPOSAL_CATEGORIES,
                         user_type=user_type,
                         farm_name=farm_name)

@app.route('/add_cows_dynamic')
@login_required
def add_cows_dynamic():
    """Динамическое добавление коров (только для пользователей ферм)"""
    user_type = session.get('user_type')
    
    # Администраторы не могут добавлять коров
    if user_type == 'admin':
        flash('Администраторы не могут добавлять коров. Используйте просмотр и отчёты.', 'warning')
        return redirect(url_for('dashboard'))
    
    farm_name = session.get('farm_name')
    
    return render_template('add_cows_dynamic.html',
                         categories=Config.DISPOSAL_CATEGORIES,
                         user_type=user_type,
                         farm_name=farm_name)

@app.route('/add_multiple_cows', methods=['GET', 'POST'])
@login_required
def add_multiple_cows():
    """Добавление нескольких коров одновременно (только для пользователей ферм)"""
    user_type = session.get('user_type')
    
    # Администраторы не могут добавлять коров
    if user_type == 'admin':
        flash('Администраторы не могут добавлять коров. Используйте просмотр и отчёты.', 'warning')
        return redirect(url_for('dashboard'))
    
    farm_name = session.get('farm_name')
    
    if request.method == 'POST':
        # Получаем данные из JSON запроса
        if request.is_json:
            data = request.get_json()
            cows = data.get('cows_data', [])
        else:
            cows_data = request.form.get('cows_data')
            if not cows_data:
                flash('Введите данные коров', 'danger')
                return redirect(url_for('add_multiple_cows'))
            
            # Парсим JSON данные
            try:
                cows = json.loads(cows_data)
            except json.JSONDecodeError:
                flash('Неверный формат данных. Используйте JSON', 'danger')
                return redirect(url_for('add_multiple_cows'))
        
        from database import generate_cow_id
        conn = get_db_connection()
        added_count = 0
        
        for cow in cows:
            if all(k in cow for k in ['category', 'reason', 'disposal_date']):
                # Генерируем автоматический ID для каждой коровы
                cow_id = generate_cow_id(farm_name)
                
                conn.execute('''
                    INSERT INTO cows (cow_id, farm_name, category, reason, disposal_date, created_by)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (cow_id, farm_name, cow['category'], cow['reason'], cow['disposal_date'], session.get('user_id')))
                added_count += 1
        
        conn.commit()
        conn.close()
        
        # Если это AJAX запрос, возвращаем JSON
        if request.is_json:
            return jsonify({'success': True, 'added_count': added_count})
        
        flash(f'Добавлено {added_count} коров с автоматически сгенерированными ID', 'success')
        return redirect(url_for('view_cows'))
    
    return render_template('add_multiple_cows.html',
                         categories=Config.DISPOSAL_CATEGORIES,
                         user_type=user_type,
                         farm_name=farm_name)

@app.route('/cows')
@login_required
def view_cows():
    """Просмотр списка коров"""
    user_type = session.get('user_type')
    farm_name = session.get('farm_name')
    
    conn = get_db_connection()
    
    if user_type == 'admin':
        cursor = conn.execute('''
            SELECT * FROM cows ORDER BY disposal_date DESC
        ''')
    else:
        cursor = conn.execute('''
            SELECT * FROM cows WHERE farm_name = ? ORDER BY disposal_date DESC
        ''', (farm_name,))
    
    cows = cursor.fetchall()
    conn.close()
    
    return render_template('view_cows.html', cows=cows, user_type=user_type)

@app.route('/delete_cow/<int:cow_id>', methods=['POST'])
@login_required
def delete_cow(cow_id):
    """Удаление записи о корове (только для пользователей ферм, только свои записи)"""
    user_type = session.get('user_type')
    farm_name = session.get('farm_name')
    
    # Администраторы не могут удалять записи
    if user_type == 'admin':
        flash('Администраторы не могут удалять записи о коровах.', 'warning')
        return redirect(url_for('view_cows'))
    
    conn = get_db_connection()
    
    # Проверяем, принадлежит ли корова ферме пользователя
    cursor = conn.execute('SELECT * FROM cows WHERE id = ? AND farm_name = ?', (cow_id, farm_name))
    cow = cursor.fetchone()
    
    if not cow:
        flash('Запись не найдена или вы не имеете прав на её удаление.', 'danger')
        conn.close()
        return redirect(url_for('view_cows'))
    
    # Удаляем запись
    conn.execute('DELETE FROM cows WHERE id = ?', (cow_id,))
    conn.commit()
    conn.close()
    
    flash(f'Запись о корове с ID {cow["cow_id"]} успешно удалена.', 'success')
    return redirect(url_for('view_cows'))

@app.route('/reports')
@login_required
def reports():
    """Страница отчётов"""
    return render_template('reports.html', user_type=session.get('user_type'))

@app.route('/generate_report', methods=['POST'])
@login_required
def generate_report():
    """Генерация отчёта"""
    report_type = request.form.get('report_type')
    format_type = request.form.get('format')
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    farm_filter = request.form.get('farm_filter')
    
    user_type = session.get('user_type')
    farm_name = session.get('farm_name')
    
    # Формируем запрос в зависимости от прав пользователя
    conn = get_db_connection()
    query = '''
        SELECT * FROM cows 
        WHERE disposal_date BETWEEN ? AND ?
    '''
    params = [start_date, end_date]
    
    if user_type == 'farm':
        query += ' AND farm_name = ?'
        params.append(farm_name)
    elif farm_filter and farm_filter != 'all':
        query += ' AND farm_name = ?'
        params.append(farm_filter)
    
    query += ' ORDER BY farm_name, disposal_date'
    
    cursor = conn.execute(query, params)
    data = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    if not data:
        flash('Нет данных для выбранного периода', 'warning')
        return redirect(url_for('reports'))
    
    # Генерация отчёта в нужном формате
    if format_type == 'excel':
        # Выбор между структурированным и простым отчётом
        if report_type == 'structured':
            # Используем новую структурированную генерацию
            try:
                from structured_report import generate_structured_report
                filename = generate_structured_report(start_date, end_date, farm_filter)
                
                if filename:
                    import os
                    from flask import send_file
                    
                    return send_file(
                        filename,
                        as_attachment=True,
                        download_name=f'структурированный_отчет_{start_date}_по_{end_date}.xlsx',
                        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    )
                else:
                    flash('Ошибка при создании отчёта', 'danger')
                    return redirect(url_for('reports'))
                    
            except Exception as e:
                print(f"Ошибка при создании структурированного отчёта: {e}")
                # Если новая генерация не работает, используем простой
                flash('Не удалось создать структурированный отчёт, используется простой', 'warning')
                return generate_excel_report(data, start_date, end_date)
        elif report_type == 'matrix':
            # Матричный отчёт
            report_category = request.form.get('report_category')
            
            if not report_category:
                flash('Для матричного отчёта необходимо выбрать категорию', 'danger')
                return redirect(url_for('reports'))
            
            try:
                from matrix_report import generate_matrix_report
                filename = generate_matrix_report(start_date, end_date, report_category, farm_filter)
                
                if filename:
                    import os
                    from flask import send_file
                    
                    return send_file(
                        filename,
                        as_attachment=True,
                        download_name=f'матричный_отчет_{report_category}_{start_date}_по_{end_date}.xlsx',
                        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    )
                else:
                    flash('Ошибка при создании матричного отчёта', 'danger')
                    return redirect(url_for('reports'))
                    
            except Exception as e:
                print(f"Ошибка при создании матричного отчёта: {e}")
                flash(f'Не удалось создать матричный отчёт: {e}', 'danger')
                return redirect(url_for('reports'))
        else:
            # Простой отчёт
            return generate_excel_report(data, start_date, end_date)
            
    elif format_type == 'csv':
        return generate_csv_report(data, start_date, end_date)
    else:
        # HTML отчет для предпросмотра
        report = Report(data, farm_filter, start_date, end_date)
        summary = report.generate_summary()
        return render_template('report_preview.html', 
                             data=data, 
                             summary=summary,
                             start_date=start_date,
                             end_date=end_date,
                             farm_filter=farm_filter)

def generate_excel_report(data, start_date, end_date):
    """Генерация простого отчёта в Excel"""
    wb = Workbook()
    ws = wb.active
    ws.title = "Данные"
    
    # Минимальные заголовки
    headers = ['ID', 'Ферма', 'Категория', 'Причина', 'Дата']
    ws.append(headers)
    
    # Только данные
    for row in data:
        ws.append([
            row['cow_id'],
            row['farm_name'],
            row['category'],
            row['reason'],
            row['disposal_date']
        ])
    
    # Без форматирования
    # Сохранение в байты
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    filename = f'простые_данные_{start_date}_по_{end_date}.xlsx'
    return send_file(output, 
                     download_name=filename,
                     as_attachment=True,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

def generate_csv_report(data, start_date, end_date):
    """Генерация простого отчёта в CSV"""
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(['ID', 'Ферма', 'Категория', 'Причина', 'Дата'])
    
    for row in data:
        writer.writerow([
            row['cow_id'],
            row['farm_name'],
            row['category'],
            row['reason'],
            row['disposal_date']
        ])
    
    output.seek(0)
    filename = f'простые_данные_{start_date}_по_{end_date}.csv'
    return send_file(io.BytesIO(output.getvalue().encode('utf-8')),
                     download_name=filename,
                     as_attachment=True,
                     mimetype='text/csv')


@app.route('/generate_original_excel', methods=['POST'])
@login_required
@admin_required
def generate_original_excel():
    """Генерация отчёта на основе оригинального Excel файла (только для администраторов)"""
    try:
        # Используем упрощенную функцию для веб-приложения
        from generate_original_web import generate_original_excel_report
        
        # Создаем отчет
        report_path = generate_original_excel_report()
        
        if report_path and os.path.exists(report_path):
            # Отправляем файл пользователю
            filename = os.path.basename(report_path)
            return send_file(
                report_path,
                as_attachment=True,
                download_name=filename,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        else:
            flash('Ошибка при создании отчёта по оригинальному шаблону', 'danger')
            return redirect(url_for('reports'))
            
    except Exception as e:
        print(f"Ошибка при создании оригинального отчёта: {e}")
        import traceback
        traceback.print_exc()
        flash(f'Ошибка при создании отчёта: {e}', 'danger')
        return redirect(url_for('reports'))


@app.route('/get_farms')
@login_required
@admin_required
def get_farms():
    """Получение списка ферм (только для админов)"""
    conn = get_db_connection()
    cursor = conn.execute('SELECT DISTINCT farm_name FROM cows ORDER BY farm_name')
    farms = [row['farm_name'] for row in cursor.fetchall()]
    conn.close()
    
    return jsonify(farms)

@app.route('/get_reasons/<category>')
@login_required
def get_reasons(category):
    """Получение списка причин для выбранной категории"""
    reasons = Config.DISPOSAL_CATEGORIES.get(category, [])
    return jsonify(reasons)

@app.route('/get_stats_data')
@login_required
def get_stats_data():
    """Получение данных для графиков статистики"""
    user_type = session.get('user_type')
    farm_name = session.get('farm_name')
    
    conn = get_db_connection()
    
    # Статистика по категориям
    if user_type == 'admin':
        cursor = conn.execute('''
            SELECT category, COUNT(*) as count 
            FROM cows 
            WHERE disposal_date >= date('now', '-30 days')
            GROUP BY category
            ORDER BY count DESC
        ''')
    else:
        cursor = conn.execute('''
            SELECT category, COUNT(*) as count 
            FROM cows 
            WHERE farm_name = ? AND disposal_date >= date('now', '-30 days')
            GROUP BY category
            ORDER BY count DESC
        ''', (farm_name,))
    
    category_stats = [{'category': row['category'], 'count': row['count']} for row in cursor.fetchall()]
    
    # Статистика по датам (последние 30 дней)
    if user_type == 'admin':
        cursor = conn.execute('''
            SELECT date(disposal_date) as date, COUNT(*) as count 
            FROM cows 
            WHERE disposal_date >= date('now', '-30 days')
            GROUP BY date(disposal_date)
            ORDER BY date
        ''')
    else:
        cursor = conn.execute('''
            SELECT date(disposal_date) as date, COUNT(*) as count 
            FROM cows 
            WHERE farm_name = ? AND disposal_date >= date('now', '-30 days')
            GROUP BY date(disposal_date)
            ORDER BY date
        ''', (farm_name,))
    
    date_stats = [{'date': row['date'], 'count': row['count']} for row in cursor.fetchall()]
    
    # Статистика по фермам (только для админов)
    farm_stats = []
    if user_type == 'admin':
        cursor = conn.execute('''
            SELECT farm_name, COUNT(*) as count 
            FROM cows 
            WHERE disposal_date >= date('now', '-30 days')
            GROUP BY farm_name
            ORDER BY count DESC
        ''')
        farm_stats = [{'farm_name': row['farm_name'], 'count': row['count']} for row in cursor.fetchall()]
    
    # Статистика по причинам в категории
    reason_stats = []
    if category_stats:
        top_category = category_stats[0]['category'] if category_stats else 'падёж'
        
        if user_type == 'admin':
            cursor = conn.execute('''
                SELECT reason, COUNT(*) as count 
                FROM cows 
                WHERE category = ? AND disposal_date >= date('now', '-30 days')
                GROUP BY reason
                ORDER BY count DESC
                LIMIT 5
            ''', (top_category,))
        else:
            cursor = conn.execute('''
                SELECT reason, COUNT(*) as count 
                FROM cows 
                WHERE category = ? AND farm_name = ? AND disposal_date >= date('now', '-30 days')
                GROUP BY reason
                ORDER BY count DESC
                LIMIT 5
            ''', (top_category, farm_name))
        
        reason_stats = [{'reason': row['reason'], 'count': row['count']} for row in cursor.fetchall()]
    
    conn.close()
    
    return jsonify({
        'category_stats': category_stats,
        'date_stats': date_stats,
        'farm_stats': farm_stats,
        'reason_stats': reason_stats,
        'user_type': user_type
    })

if __name__ == '__main__':
    # Проверяем, запущено ли на PythonAnywhere
    is_pythonanywhere = 'PYTHONANYWHERE_DOMAIN' in os.environ
    
    if not is_pythonanywhere:
        # Локальный запуск
        init_db()
        
        # Создаем тестовых пользователей если их нет
        conn = sqlite3.connect('livestock.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            from auth import register_user
            register_user('admin', 'admin123', 'admin')
            register_user('farm1', 'farm123', 'farm', 'Ферма 1')
            register_user('farm2', 'farm123', 'farm', 'Ферма 2')
            print("Созданы тестовые пользователи")
        conn.close()
        
        app.run(debug=True, host='0.0.0.0', port=5000)
    else:
        # На PythonAnywhere база данных и пользователи будут созданы через WSGI
        print("Запущено на PythonAnywhere")