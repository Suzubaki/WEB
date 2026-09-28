"""
Модуль для генерации данных графиков статистики
"""
import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict


def get_statistics_data(user_type, farm_name=None):
    """Получение данных для графиков статистики"""
    conn = sqlite3.connect('livestock.db')
    cursor = conn.cursor()
    
    # Основные данные статистики
    stats_data = {
        'categories': defaultdict(int),
        'farms': defaultdict(int),
        'monthly_data': defaultdict(lambda: defaultdict(int)),
        'weekly_data': defaultdict(lambda: defaultdict(int)),
        'overview': {
            'total_cows': 0,
            'total_farms': 0,
            'avg_per_farm': 0
        }
    }
    
    # SQL запросы в зависимости от прав пользователя
    if user_type == 'admin':
        # Общая статистика по категориям
        cursor.execute('''
            SELECT category, COUNT(*) as count 
            FROM cows 
            GROUP BY category
        ''')
        categories = cursor.fetchall()
        for category, count in categories:
            stats_data['categories'][category] = count
        
        # Статистика по фермам
        cursor.execute('''
            SELECT farm_name, COUNT(*) as count 
            FROM cows 
            GROUP BY farm_name 
            ORDER BY count DESC
            LIMIT 10
        ''')
        farms = cursor.fetchall()
        for farm_name, count in farms:
            stats_data['farms'][farm_name] = count
        
        # Ежемесячные данные (последние 12 месяцев)
        cursor.execute('''
            SELECT strftime('%Y-%m', disposal_date) as month, 
                   category, 
                   COUNT(*) as count
            FROM cows 
            WHERE disposal_date >= date('now', '-12 months')
            GROUP BY month, category
            ORDER BY month
        ''')
        monthly_data = cursor.fetchall()
        for month, category, count in monthly_data:
            stats_data['monthly_data'][month][category] = count
        
        # Общее количество коров и ферм
        cursor.execute('SELECT COUNT(*) FROM cows')
        stats_data['overview']['total_cows'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(DISTINCT farm_name) FROM cows')
        stats_data['overview']['total_farms'] = cursor.fetchone()[0]
        
        # Среднее количество коров на ферму
        if stats_data['overview']['total_farms'] > 0:
            stats_data['overview']['avg_per_farm'] = round(
                stats_data['overview']['total_cows'] / stats_data['overview']['total_farms'], 1
            )
    else:
        # Статистика для пользователя фермы
        cursor.execute('''
            SELECT category, COUNT(*) as count 
            FROM cows 
            WHERE farm_name = ?
            GROUP BY category
        ''', (farm_name,))
        categories = cursor.fetchall()
        for category, count in categories:
            stats_data['categories'][category] = count
        
        # Ежемесячные данные (последние 12 месяцев)
        cursor.execute('''
            SELECT strftime('%Y-%m', disposal_date) as month, 
                   category, 
                   COUNT(*) as count
            FROM cows 
            WHERE farm_name = ? 
            AND disposal_date >= date('now', '-12 months')
            GROUP BY month, category
            ORDER BY month
        ''', (farm_name,))
        monthly_data = cursor.fetchall()
        for month, category, count in monthly_data:
            stats_data['monthly_data'][month][category] = count
        
        # Общее количество коров
        cursor.execute('SELECT COUNT(*) FROM cows WHERE farm_name = ?', (farm_name,))
        stats_data['overview']['total_cows'] = cursor.fetchone()[0]
        stats_data['overview']['total_farms'] = 1
        stats_data['overview']['avg_per_farm'] = stats_data['overview']['total_cows']
    
    conn.close()
    return stats_data


def get_dashboard_stats(user_type, farm_name=None):
    """Получение данных для дашборда"""
    conn = sqlite3.connect('livestock.db')
    cursor = conn.cursor()
    
    # Получаем данные за последние 30 дней
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    if user_type == 'admin':
        # Статистика за последние 30 дней по категориям
        cursor.execute('''
            SELECT category, COUNT(*) as count 
            FROM cows 
            WHERE disposal_date >= ?
            GROUP BY category
        ''', (thirty_days_ago,))
        
        recent_stats = cursor.fetchall()
        
        # Общая статистика
        cursor.execute('SELECT COUNT(*) FROM cows')
        total_cows = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(DISTINCT farm_name) FROM cows')
        total_farms = cursor.fetchone()[0]
        
        your_farm_total = None  # Для админов не используется
        
    else:
        # Статистика для фермы за последние 30 дней
        cursor.execute('''
            SELECT category, COUNT(*) as count 
            FROM cows 
            WHERE farm_name = ? AND disposal_date >= ?
            GROUP BY category
        ''', (farm_name, thirty_days_ago))
        
        recent_stats = cursor.fetchall()
        
        # Общая статистика для фермы
        cursor.execute('SELECT COUNT(*) FROM cows WHERE farm_name = ?', (farm_name,))
        total_cows = cursor.fetchone()[0]
        total_farms = 1
        your_farm_total = total_cows  # Сохраняем отдельно для отображения
    
    conn.close()
    
    return {
        'recent_stats': recent_stats,
        'total_cows': total_cows,
        'total_farms': total_farms,
        'your_farm_total': total_cows if user_type != 'admin' else None
    }


def prepare_chart_data(stats_data):
    """Подготовка данных для Chart.js"""
    # Данные для круговой диаграммы по категориям
    categories_chart = {
        'labels': [],
        'data': [],
        'backgroundColors': [
            '#FF6384',  # Красный
            '#36A2EB',  # Синий
            '#FFCE56',  # Желтый
            '#4BC0C0',  # Бирюзовый
            '#9966FF',  # Фиолетовый
            '#FF9F40',  # Оранжевый
        ]
    }
    
    for category, count in stats_data['categories'].items():
        categories_chart['labels'].append(category)
        categories_chart['data'].append(count)
    
    # Данные для столбчатой диаграммы по фермам (только для админов)
    farms_chart = {
        'labels': [],
        'data': [],
        'backgroundColors': '#36A2EB'
    }
    
    if stats_data['farms']:
        for farm, count in stats_data['farms'].items():
            farms_chart['labels'].append(farm)
            farms_chart['data'].append(count)
    
    # Данные для линейного графика по месяцам
    months = sorted(stats_data['monthly_data'].keys())
    line_chart = {
        'labels': months,
        'datasets': []
    }
    
    # Группируем данные по категориям
    category_colors = {
        'падёж': '#FF6384',
        'выбраковка': '#36A2EB',
        'санитарный': '#FFCE56'
    }
    
    for category in ['падёж', 'выбраковка', 'санитарный']:
        if any(category in stats_data['monthly_data'][month] for month in months):
            data = []
            for month in months:
                data.append(stats_data['monthly_data'][month].get(category, 0))
            
            line_chart['datasets'].append({
                'label': category,
                'data': data,
                'borderColor': category_colors.get(category, '#36A2EB'),
                'backgroundColor': category_colors.get(category, '#36A2EB') + '20',
                'fill': True,
                'tension': 0.1
            })
    
    return {
        'categories_chart': categories_chart,
        'farms_chart': farms_chart,
        'line_chart': line_chart,
        'overview': stats_data['overview']
    }


def get_user_statistics():
    """Получение статистики по пользователям"""
    conn = sqlite3.connect('livestock.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT user_type, COUNT(*) as count 
        FROM users 
        GROUP BY user_type
    ''')
    user_stats = cursor.fetchall()
    
    # Статистика активности пользователей
    cursor.execute('''
        SELECT u.username, u.user_type, u.farm_name, 
               COUNT(c.id) as cows_count,
               MAX(c.disposal_date) as last_activity
        FROM users u
        LEFT JOIN cows c ON c.created_by = u.id
        GROUP BY u.id
        ORDER BY cows_count DESC
    ''')
    user_activity = cursor.fetchall()
    
    conn.close()
    
    return {
        'user_types': dict(user_stats),
        'user_activity': [
            {
                'username': row[0],
                'user_type': row[1],
                'farm_name': row[2] or '-',
                'cows_count': row[3],
                'last_activity': row[4] or 'Нет данных'
            }
            for row in user_activity
        ]
    }