# charts.py - Генерация данных для графиков Chart.js, аналитики, ПВГ и алертов (РБ)
import sqlite3
from datetime import datetime, timedelta
from database import get_db_connection, get_setting
from config import Config

# Классификация диагнозов по системам органов и патологиям (ветеринарный стандарт РБ)
def classify_pathology_system(reason):
    r = (reason or '').lower()
    if any(k in r for k in ['роды', 'моцерац', 'эндометр', 'кист', 'яловост', 'маточн', 'сальпинг', 'матк', 'гинекол']):
        return 'Акушерство и гинекология'
    elif any(k in r for k in ['мастит', 'агалакти', 'вымен', 'соск']):
        return 'Болезни вымени (маститы)'
    elif any(k in r for k in ['тимпани', 'гастро', 'язв', 'сычуг', 'рубец', 'перитонит', 'ретикул', 'атони', 'печен', 'цирроз', 'селезенк']):
        return 'Органы пищеварения'
    elif any(k in r for k in ['бронхопневмон', 'пневмон', 'легк', 'отек легких', 'дыхан']):
        return 'Органы дыхания'
    elif any(k in r for k in ['диспепси', 'гипотрофи', 'колибакт', 'пупочн']):
        return 'Болезни молодняка (диспепсия)'
    elif any(k in r for k in ['конечност', 'перелом', 'позвоноч', 'хромот', 'копыт', 'сустав', 'травм']):
        return 'Конечности и травматизм'
    elif any(k in r for k in ['кетоз', 'ацидоз', 'обмен']):
        return 'Нарушения обмена веществ'
    elif any(k in r for k in ['кровотеч', 'артери', 'сердц', 'инфаркт', 'миокард']):
        return 'Сердечно-сосудистая система'
    else:
        return 'Прочие заболевания'

def get_dashboard_full_data(user_type='admin', farm_name=None, period=None, custom_start=None, custom_end=None):
    """
    Комплексный расчет всех статистических срезов для аналитического дашборда
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now()
    
    # 0. Автоопределение периода, если не передан явно (чтобы дашборд не открывался пустым на 1-е число месяца)
    if not period or period == 'auto':
        cur_m_start = now.replace(day=1).strftime('%Y-%m-%d')
        cur_m_end = now.strftime('%Y-%m-%d')
        p_check_where = ["disposal_date BETWEEN ? AND ?"]
        p_check_params = [cur_m_start, cur_m_end]
        if user_type == 'farm' and farm_name:
            p_check_where.append("farm_name = ?")
            p_check_params.append(farm_name)
        elif user_type == 'admin' and farm_name and farm_name != 'all':
            p_check_where.append("farm_name = ?")
            p_check_params.append(farm_name)
            
        cursor.execute(f"SELECT COUNT(*) as cnt FROM cows WHERE {' AND '.join(p_check_where)}", p_check_params)
        cur_m_cnt = cursor.fetchone()['cnt']
        
        if cur_m_cnt > 0:
            period = 'this_month'
        else:
            # Проверяем прошлый месяц
            last_m_end = (now.replace(day=1) - timedelta(days=1)).strftime('%Y-%m-%d')
            last_m_start = (now.replace(day=1) - timedelta(days=1)).replace(day=1).strftime('%Y-%m-%d')
            p_last_where = ["disposal_date BETWEEN ? AND ?"]
            p_last_params = [last_m_start, last_m_end]
            if user_type == 'farm' and farm_name:
                p_last_where.append("farm_name = ?")
                p_last_params.append(farm_name)
            elif user_type == 'admin' and farm_name and farm_name != 'all':
                p_last_where.append("farm_name = ?")
                p_last_params.append(farm_name)
            cursor.execute(f"SELECT COUNT(*) as cnt FROM cows WHERE {' AND '.join(p_last_where)}", p_last_params)
            last_m_cnt = cursor.fetchone()['cnt']
            if last_m_cnt > 0:
                period = 'last_month'
            else:
                period = 'all'

    # 1. Расчет дат периода
    if period == 'this_month':
        start_date = now.replace(day=1).strftime('%Y-%m-%d')
        end_date = now.strftime('%Y-%m-%d')
        period_title = f"Текущий месяц ({now.strftime('%B %Y')})"
    elif period == 'last_month':
        last_month_end = now.replace(day=1) - timedelta(days=1)
        start_date = last_month_end.replace(day=1).strftime('%Y-%m-%d')
        end_date = last_month_end.strftime('%Y-%m-%d')
        period_title = f"Прошлый месяц ({last_month_end.strftime('%B %Y')})"
    elif period == 'quarter':
        quarter_month = ((now.month - 1) // 3) * 3 + 1
        start_date = now.replace(month=quarter_month, day=1).strftime('%Y-%m-%d')
        end_date = now.strftime('%Y-%m-%d')
        period_title = f"Текущий квартал ({((now.month - 1) // 3) + 1} кв. {now.year})"
    elif period == 'ytd':
        start_date = now.replace(month=1, day=1).strftime('%Y-%m-%d')
        end_date = now.strftime('%Y-%m-%d')
        period_title = f"С начала {now.year} года (YTD)"
    elif period == 'all':
        start_date = '2000-01-01'
        end_date = '2099-12-31'
        period_title = "За всё время учёта"
    elif period == 'custom' and custom_start and custom_end:
        start_date = custom_start
        end_date = custom_end
        period_title = f"С {start_date} по {end_date}"
    else:
        start_date = now.replace(day=1).strftime('%Y-%m-%d')
        end_date = now.strftime('%Y-%m-%d')
        period_title = "Текущий месяц"

    # Формируем WHERE-фильтр
    where_parts = ["disposal_date BETWEEN ? AND ?"]
    params = [start_date, end_date]
    
    if user_type == 'farm' and farm_name:
        where_parts.append("farm_name = ?")
        params.append(farm_name)
    elif user_type == 'admin' and farm_name and farm_name != 'all':
        where_parts.append("farm_name = ?")
        params.append(farm_name)
        
    where_clause = "WHERE " + " AND ".join(where_parts)
    
    # 2. Выборка строк за выбранный период
    cursor.execute(f'''
        SELECT id, cow_id, ear_tag, farm_name, category, reason, disposal_date, 
               lactation, weight, age_group, milk_yield, book_value
        FROM cows
        {where_clause}
        ORDER BY disposal_date DESC, id DESC
    ''', params)
    period_cows = [dict(r) for r in cursor.fetchall()]
    
    # 3. Агрегация по категориям за период
    category_counts = {'падёж': 0, 'выбраковка': 0, 'санитарный': 0}
    for c in period_cows:
        cat = c['category']
        category_counts[cat] = category_counts.get(cat, 0) + 1
        
    total_disposals = len(period_cows)
    
    # 4. Распределение по Половозрастным группам (ПВГ)
    age_group_counts = {}
    for c in period_cows:
        ag = c['age_group'] or 'Коровы дойного стада'
        age_group_counts[ag] = age_group_counts.get(ag, 0) + 1
        
    # Сортировка групп
    sorted_age_groups = sorted(age_group_counts.items(), key=lambda x: x[1], reverse=True)
    
    # 6. Патологический профиль (по системам органов)
    pathology_systems = {}
    for c in period_cows:
        system = classify_pathology_system(c['reason'])
        pathology_systems[system] = pathology_systems.get(system, 0) + 1
    sorted_pathology = sorted(pathology_systems.items(), key=lambda x: x[1], reverse=True)
    
    # 7. Топ причин выбытия за период
    reason_counts = {}
    for c in period_cows:
        key = (c['reason'], c['category'])
        reason_counts[key] = reason_counts.get(key, 0) + 1
    top_reasons_list = [
        {'reason': k[0], 'category': k[1], 'count': v}
        for k, v in sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)[:8]
    ]
    
    # 8. Распределение по фермам / МТФ
    farm_counts = {}
    for c in period_cows:
        f = c['farm_name']
        farm_counts[f] = farm_counts.get(f, 0) + 1
    sorted_farms = sorted(farm_counts.items(), key=lambda x: x[1], reverse=True)
    
    # 9. Динамика по месяцам за последние 12 месяцев
    twelve_months_ago = (now - timedelta(days=365)).strftime('%Y-%m-%d')
    m_where_parts = [f"disposal_date >= '{twelve_months_ago}'"]
    m_params = []
    if user_type == 'farm' and farm_name:
        m_where_parts.append("farm_name = ?")
        m_params.append(farm_name)
    elif user_type == 'admin' and farm_name and farm_name != 'all':
        m_where_parts.append("farm_name = ?")
        m_params.append(farm_name)
        
    cursor.execute(f'''
        SELECT strftime('%Y-%m', disposal_date) as month, category, COUNT(*) as count
        FROM cows
        WHERE {' AND '.join(m_where_parts)}
        GROUP BY month, category
        ORDER BY month ASC
    ''', m_params)
    
    monthly_data = {}
    for row in cursor.fetchall():
        m = row['month']
        c = row['category']
        cnt = row['count']
        if m not in monthly_data:
            monthly_data[m] = {}
        monthly_data[m][c] = cnt
        
    months_keys = sorted(list(monthly_data.keys()))
    trend_datasets = []
    category_colors = {
        'падёж': '#DC2626',      # Красный
        'выбраковка': '#2563EB',  # Синий
        'санитарный': '#D97706'   # Янтарный
    }
    for cat_name in ['падёж', 'выбраковка', 'санитарный']:
        data_pts = [monthly_data.get(m, {}).get(cat_name, 0) for m in months_keys]
        col = category_colors.get(cat_name, '#64748B')
        trend_datasets.append({
            'label': cat_name.capitalize(),
            'data': data_pts,
            'borderColor': col,
            'backgroundColor': col + '20',
            'fill': True,
            'tension': 0.25
        })
        
    # 10. Сохранность молодняка (Телята 0-6 мес.)
    calf_disposals = [c for c in period_cows if 'телята' in (c['age_group'] or '').lower()]
    calf_death_count = sum(1 for c in calf_disposals if c['category'] == 'падёж')
    
    # 11. Общая статистика базы (за всё время)
    all_time_where = ""
    all_time_params = []
    if user_type == 'farm' and farm_name:
        all_time_where = "WHERE farm_name = ?"
        all_time_params = [farm_name]
    elif user_type == 'admin' and farm_name and farm_name != 'all':
        all_time_where = "WHERE farm_name = ?"
        all_time_params = [farm_name]
        
    cursor.execute(f'SELECT COUNT(*) as total FROM cows {all_time_where}', all_time_params)
    all_time_total = cursor.fetchone()['total']
    
    # 12. Динамика относительно предыдущего аналогичного периода
    try:
        d_start = datetime.strptime(start_date, '%Y-%m-%d')
        d_end = datetime.strptime(end_date, '%Y-%m-%d')
        delta_days = (d_end - d_start).days + 1
        prev_end_date = (d_start - timedelta(days=1)).strftime('%Y-%m-%d')
        prev_start_date = (d_start - timedelta(days=delta_days)).strftime('%Y-%m-%d')
        
        p_where_parts = ["disposal_date BETWEEN ? AND ?"]
        p_params = [prev_start_date, prev_end_date]
        if user_type == 'farm' and farm_name:
            p_where_parts.append("farm_name = ?")
            p_params.append(farm_name)
        elif user_type == 'admin' and farm_name and farm_name != 'all':
            p_where_parts.append("farm_name = ?")
            p_params.append(farm_name)
            
        cursor.execute(f"SELECT COUNT(*) as count FROM cows WHERE {' AND '.join(p_where_parts)}", p_params)
        prev_period_count = cursor.fetchone()['count']
        if prev_period_count > 0:
            growth_pct = round(((total_disposals - prev_period_count) / prev_period_count) * 100, 1)
        else:
            growth_pct = 100.0 if total_disposals > 0 else 0.0
    except Exception:
        growth_pct = 0.0
        prev_period_count = 0
        
    # Список доступных ферм (из пользователей и из таблицы cows)
    cursor.execute('''
        SELECT DISTINCT farm_name FROM (
            SELECT farm_name FROM users WHERE farm_name IS NOT NULL AND farm_name != ''
            UNION
            SELECT farm_name FROM cows WHERE farm_name IS NOT NULL AND farm_name != ''
        ) ORDER BY farm_name
    ''')
    all_farms_list = [r['farm_name'] for r in cursor.fetchall()]
    
    # Последние коровы: если за выбранный период пусто, показываем последние выбытия из базы
    if len(period_cows) > 0:
        recent_cows = period_cows[:10]
    else:
        cursor.execute(f'''
            SELECT id, cow_id, ear_tag, farm_name, category, reason, disposal_date, 
                   lactation, weight, age_group, milk_yield, book_value
            FROM cows
            {all_time_where}
            ORDER BY disposal_date DESC, id DESC
            LIMIT 10
        ''', all_time_params)
        recent_cows = [dict(r) for r in cursor.fetchall()]
    
    conn.close()
    
    return {
        'period_info': {
            'period': period,
            'start_date': start_date,
            'end_date': end_date,
            'title': period_title
        },
        'kpi': {
            'total_disposals': total_disposals,
            'prev_period_count': prev_period_count,
            'growth_pct': growth_pct,
            'death_count': category_counts.get('падёж', 0),
            'culling_count': category_counts.get('выбраковка', 0),
            'sanitary_count': category_counts.get('санитарный', 0),
            'death_rate_pct': round((category_counts.get('падёж', 0) / max(total_disposals, 1)) * 100, 1),
            'calf_disposals': len(calf_disposals),
            'calf_death_count': calf_death_count,
            'all_time_total': all_time_total
        },
        'charts': {
            'categories': {
                'labels': ['Падёж', 'Выбраковка', 'Санитарный брак'],
                'data': [category_counts.get('падёж', 0), category_counts.get('выбраковка', 0), category_counts.get('санитарный', 0)],
                'colors': ['#EF4444', '#3B82F6', '#F59E0B']
            },
            'age_groups': {
                'labels': [x[0] for x in sorted_age_groups],
                'data': [x[1] for x in sorted_age_groups],
                'colors': '#10B981'
            },
            'pathology': {
                'labels': [x[0] for x in sorted_pathology],
                'data': [x[1] for x in sorted_pathology],
                'colors': '#6366F1'
            },
            'farms': {
                'labels': [x[0] for x in sorted_farms],
                'data': [x[1] for x in sorted_farms],
                'colors': '#0284C7'
            },
            'trend': {
                'labels': months_keys,
                'datasets': trend_datasets
            }
        },
        'top_reasons': top_reasons_list,
        'recent_cows': recent_cows,
        'all_farms': all_farms_list
    }

def get_anomaly_alerts(user_type='admin', farm_name=None):
    """
    Поиск аномалий и предупреждений ветеринарной службы
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    alerts = []
    now = datetime.now()
    d7_ago = (now - timedelta(days=7)).strftime('%Y-%m-%d')
    d14_ago = (now - timedelta(days=14)).strftime('%Y-%m-%d')
    d30_ago = (now - timedelta(days=30)).strftime('%Y-%m-%d')
    
    where_farm = ""
    params = []
    if user_type == 'farm' and farm_name:
        where_farm = "AND farm_name = ?"
        params.append(farm_name)
    elif user_type == 'admin' and farm_name and farm_name != 'all':
        where_farm = "AND farm_name = ?"
        params.append(farm_name)
    
    # 1. Сравнение падежа за последние 7 дней
    cursor.execute(f'''
        SELECT COUNT(*) as cnt FROM cows 
        WHERE category = 'падёж' AND disposal_date >= '{d7_ago}' {where_farm}
    ''', params)
    last_7_days = cursor.fetchone()['cnt']
    
    cursor.execute(f'''
        SELECT COUNT(*) as cnt FROM cows 
        WHERE category = 'падёж' AND disposal_date >= '{d14_ago}' AND disposal_date < '{d7_ago}' {where_farm}
    ''', params)
    prev_7_days = cursor.fetchone()['cnt']
    
    if last_7_days > 2 and last_7_days > prev_7_days * 1.4:
        growth = round(((last_7_days - prev_7_days) / max(prev_7_days, 1)) * 100)
        alerts.append({
            'type': 'danger',
            'icon': 'bi-exclamation-octagon-fill',
            'title': 'Резкий рост падежа скота за 7 дней',
            'message': f'Зафиксировано {last_7_days} случаев падежа (+{growth}% по сравнению с предшествующей неделей ({prev_7_days} случаев)). Требуется срочный контроль ветврача.'
        })
    
    # 2. Серийные вспышки конкретных причин за 30 дней
    cursor.execute(f'''
        SELECT reason, category, farm_name, COUNT(*) as cnt 
        FROM cows 
        WHERE disposal_date >= '{d30_ago}' {where_farm}
        GROUP BY reason, category, farm_name
        HAVING cnt >= 3
        ORDER BY cnt DESC
        LIMIT 3
    ''', params)
    for row in cursor.fetchall():
        alerts.append({
            'type': 'warning',
            'icon': 'bi-exclamation-triangle-fill',
            'title': f'Повторяющаяся патология: {row["reason"]}',
            'message': f'Подразделение «{row["farm_name"]}»: за 30 дней выявлено {row["cnt"]} случаев ({row["category"]}). Рекомендуется проверить баланс рациона и микроклимат.'
        })
        
    # 3. Предупреждение по падежу телят (0-6 мес.)
    cursor.execute(f'''
        SELECT COUNT(*) as cnt FROM cows
        WHERE category = 'падёж' AND disposal_date >= '{d30_ago}' 
          AND (LOWER(age_group) LIKE '%телят%' OR LOWER(age_group) LIKE '%молодняк%')
          {where_farm}
    ''', params)
    calf_deaths = cursor.fetchone()['cnt']
    if calf_deaths >= 3:
        alerts.append({
            'type': 'info',
            'icon': 'bi-info-circle-fill',
            'title': f'Падёж телят и молодняка: {calf_deaths} гол. за 30 дней',
            'message': 'Обратите внимание на выпойку молозива, параметры влажности и схему вакцинации телят в профилактории.'
        })
        
    conn.close()
    return alerts

# Совместимость для старых вызовов
def get_statistics_data(user_type='admin', farm_name=None):
    res = get_dashboard_full_data(user_type, farm_name, period='all')
    return {
        'categories': dict(zip(res['charts']['categories']['labels'], res['charts']['categories']['data'])),
        'farms': dict(zip(res['charts']['farms']['labels'], res['charts']['farms']['data'])),
        'top_reasons': res['top_reasons'],
        'monthly_data': {},
        'overview': {
            'total_cows': res['kpi']['total_disposals'],
            'total_farms': len(res['all_farms']),
            'avg_per_farm': round(res['kpi']['total_disposals'] / max(len(res['all_farms']), 1), 1)
        }
    }

def prepare_chart_data(stats_data):
    return {
        'categories_chart': {},
        'farms_chart': {},
        'line_chart': {},
        'top_reasons': stats_data.get('top_reasons', []),
        'overview': stats_data.get('overview', {})
    }

def get_dashboard_stats(user_type='admin', farm_name=None):
    res = get_dashboard_full_data(user_type, farm_name, period='this_month')
    return {
        'recent_stats': {'падёж': res['kpi']['death_count'], 'выбраковка': res['kpi']['culling_count'], 'санитарный': res['kpi']['sanitary_count']},
        'total_cows': res['kpi']['all_time_total'],
        'total_farms': len(res['all_farms']),
        'this_month_count': res['kpi']['total_disposals'],
        'prev_month_count': res['kpi']['prev_period_count'],
        'mom_change': res['kpi']['growth_pct'],
        'your_farm_total': res['kpi']['total_disposals']
    }

def get_user_statistics():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_type, COUNT(*) as count FROM users GROUP BY user_type')
    user_types = {row['user_type']: row['count'] for row in cursor.fetchall()}
    cursor.execute('''
        SELECT u.id, u.username, u.user_type, u.farm_name, COUNT(c.id) as cows_count, MAX(c.created_at) as last_activity
        FROM users u LEFT JOIN cows c ON u.id = c.created_by
        GROUP BY u.id ORDER BY cows_count DESC
    ''')
    user_activity = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {'user_types': user_types, 'user_activity': user_activity}
