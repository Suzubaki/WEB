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
    if period == 'last_7':
        start_date = (now - timedelta(days=6)).strftime('%Y-%m-%d')
        end_date = now.strftime('%Y-%m-%d')
        period_title = "Последние 7 дней"
    elif period == 'last_30':
        start_date = (now - timedelta(days=29)).strftime('%Y-%m-%d')
        end_date = now.strftime('%Y-%m-%d')
        period_title = "Последние 30 дней"
    elif period == 'this_month':
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
    
    # 2. Выборка строк за выбранный период (с авто-миграцией при устаревшей схеме БД)
    try:
        cursor.execute(f'''
            SELECT id, cow_id, ear_tag, farm_name, category, reason, disposal_date, 
                   lactation, lactation_days, lactation_phase, weight, age_group, milk_yield, book_value,
                   is_pregnant, gestation_days, is_stillborn
            FROM cows
            {where_clause}
            ORDER BY disposal_date DESC, id DESC
        ''', params)
        period_cows = [dict(r) for r in cursor.fetchall()]
    except sqlite3.OperationalError as op_err:
        if 'no such column' in str(op_err):
            from database import init_db
            init_db()
            cursor.execute(f'''
                SELECT id, cow_id, ear_tag, farm_name, category, reason, disposal_date, 
                       lactation, lactation_days, lactation_phase, weight, age_group, milk_yield, book_value,
                       is_pregnant, gestation_days, is_stillborn
                FROM cows
                {where_clause}
                ORDER BY disposal_date DESC, id DESC
            ''', params)
            period_cows = [dict(r) for r in cursor.fetchall()]
        else:
            raise
    
    # 3. Агрегация по категориям за период и экономический баланс
    category_counts = {'падёж': 0, 'выбраковка': 0, 'санитарный': 0}
    total_loss_byn = 0.0
    death_loss_byn = 0.0
    culling_loss_byn = 0.0
    
    # Динамическая стоимостная оценка скота по группам (BYN за голову из БД/настроек)
    try:
        from database import get_setting
        dynamic_prices = {
            'телята': float(get_setting('price_calves', 900.0)),
            'молодняк': float(get_setting('price_youngstock', 1650.0)),
            'нетели': float(get_setting('price_heifers', 2700.0)),
            'дойное': float(get_setting('price_cows', 3200.0)),
            'сухостой': float(get_setting('price_dry_cows', 3000.0))
        }
    except Exception:
        dynamic_prices = {
            'телята': 900.0,
            'молодняк': 1650.0,
            'нетели': 2700.0,
            'дойное': 3200.0,
            'сухостой': 3000.0
        }

    def normalize_age_group(raw_group, lactation=None):
        g = (raw_group or '').lower().strip()
        if any(k in g for k in ['мертворож', 'аборт', 'плод']):
            return 'Мертворождённые / Аборты'
        if any(k in g for k in ['новотел', '0-30', '0–30']):
            return 'Новотельные коровы (0–30 дн DIM)'
        if any(k in g for k in ['телят', 'до 6', '0-6', '0–6', 'новорожд', 'молочн']):
            return 'Телята (до 6 мес.)'
        if any(k in g for k in ['молодняк', '6-18', '6–18', 'от 6 до 18', '6-12', '6–12']):
            return 'Ремонтный молодняк (6–18 мес.)'
        if any(k in g for k in ['нетел', 'старше 18', '> 18', '>18']):
            return 'Нетели (>18 мес.)'
        if any(k in g for k in ['быч', 'бык', 'откорм']):
            return 'Бычки на откорме'
        if 'сухосто' in g:
            return 'Сухостойные коровы'
        if lactation == 1 or any(k in g for k in ['первотел', '1-я лакт', '1 лакт']):
            return 'Коровы 1-й лактации (первотёлки)'
        if (lactation and lactation > 1) or any(k in g for k in ['полновозраст', '2+ лакт']):
            return 'Полновозрастные коровы (2+ лакт.)'
        return 'Коровы дойного стада'

    def estimate_cow_val(c):
        bv = c.get('book_value')
        if bv is not None and bv > 0:
            return float(bv)
        norm_grp = normalize_age_group(c.get('age_group'), c.get('lactation'))
        if norm_grp == 'Телята (до 6 мес.)':
            return dynamic_prices.get('телята', 900.0)
        elif norm_grp == 'Ремонтный молодняк (6–18 мес.)':
            return dynamic_prices.get('молодняк', 1650.0)
        elif norm_grp == 'Нетели (>18 мес.)':
            return dynamic_prices.get('нетели', 2700.0)
        elif norm_grp == 'Сухостойные коровы':
            return dynamic_prices.get('сухостой', 3000.0)
        elif norm_grp == 'Бычки на откорме':
            return dynamic_prices.get('молодняк', 1650.0)
        return dynamic_prices.get('дойное', 3200.0)

    live_cows = [c for c in period_cows if not c.get('is_stillborn') and c.get('category') != 'мертворождение' and normalize_age_group(c.get('age_group'), c.get('lactation')) != 'Мертворождённые / Аборты']

    meat_price_per_kg = float(get_setting('meat_price_per_kg', 6.20))
    milk_price_per_kg = float(get_setting('milk_price_per_kg', 1.18))
    replacement_cost = float(get_setting('replacement_cost', 2950.0))

    culled_live_weight_total = 0.0
    estimated_meat_revenue_byn = 0.0
    unrealized_milk_loss_byn = 0.0
    unrealized_milk_kg_total = 0.0
    unrecovered_heifer_loss_byn = 0.0

    for c in live_cows:
        cat = c['category']
        category_counts[cat] = category_counts.get(cat, 0) + 1
        val = estimate_cow_val(c)
        total_loss_byn += val
        
        w = float(c.get('weight') or 0.0)
        if w <= 0:
            norm_grp = normalize_age_group(c.get('age_group'), c.get('lactation'))
            w = 520.0 if ('Коровы' in norm_grp or 'Нетели' in norm_grp or 'Сухостой' in norm_grp) else (320.0 if 'молодняк' in norm_grp.lower() else 45.0)

        dim = int(c.get('lactation_days') or 0)
        lact = int(c.get('lactation') or 0)

        # 1. Расчет упущенной выгоды от недополученного молока (305 дней лактации)
        if lact > 0 and dim < 305:
            rem_days = 305 - dim
            daily_milk = (float(c.get('milk_yield') or 0.0) / 305.0) if c.get('milk_yield') else 22.0
            if daily_milk <= 0: daily_milk = 22.0
            lost_milk_kg = rem_days * daily_milk
            unrealized_milk_kg_total += lost_milk_kg
            unrealized_milk_loss_byn += lost_milk_kg * milk_price_per_kg

        # 2. Расчет неамортизированного ущерба при выбытии первотёлок (до окупаемости ремонта)
        if lact == 1 and dim < 305:
            unrecovered_heifer_loss_byn += max(0.0, replacement_cost * (1.0 - (dim / 305.0)))

        if cat == 'падёж':
            death_loss_byn += val
        elif cat == 'выбраковка':
            culling_loss_byn += val
            culled_live_weight_total += w
            estimated_meat_revenue_byn += w * meat_price_per_kg
        elif cat == 'санитарный':
            culling_loss_byn += val
            culled_live_weight_total += w
            # Санбрак: дисконт 30% на реализационную стоимость мяса (2-я категория)
            estimated_meat_revenue_byn += w * (meat_price_per_kg * 0.70)

    total_disposals = len(live_cows)
    avg_head_loss = round(total_loss_byn / max(total_disposals, 1))
    estimated_meat_revenue_byn = round(estimated_meat_revenue_byn)
    unrealized_milk_loss_byn = round(unrealized_milk_loss_byn)
    unrecovered_heifer_loss_byn = round(unrecovered_heifer_loss_byn)

    # Совокупный чистый экономический ущерб с учетом мясной выручки, упущенного молока и ремонта
    net_economic_loss_byn = round(death_loss_byn + max(0.0, culling_loss_byn - estimated_meat_revenue_byn) + unrealized_milk_loss_byn + unrecovered_heifer_loss_byn)
    
    # 4. Распределение по Половозрастным группам (ПВГ) со стеком
    age_group_data = {}
    standard_groups = [
        'Телята (до 6 мес.)',
        'Ремонтный молодняк (6–18 мес.)',
        'Нетели (>18 мес.)',
        'Бычки на откорме',
        'Новотельные коровы (0–30 дн DIM)',
        'Коровы 1-й лактации (первотёлки)',
        'Полновозрастные коровы (2+ лакт.)',
        'Сухостойные коровы',
        'Мертворождённые / Аборты'
    ]
    for g in standard_groups:
        age_group_data[g] = {
            'total': 0, 'падёж': 0, 'выбраковка': 0, 'санитарный': 0, 'loss': 0.0,
            'dims': [], 'weights': [],
            'reasons': {},
            'culling_reasons': {},
            'death_reasons': {},
            'sanitary_reasons': {}
        }

    for c in live_cows:
        ag = normalize_age_group(c.get('age_group'), c.get('lactation'))
        if ag not in age_group_data:
            age_group_data[ag] = {
                'total': 0, 'падёж': 0, 'выбраковка': 0, 'санитарный': 0, 'loss': 0.0,
                'dims': [], 'weights': [],
                'reasons': {},
                'culling_reasons': {},
                'death_reasons': {},
                'sanitary_reasons': {}
            }
        cat = c['category']
        val = estimate_cow_val(c)
        age_group_data[ag]['total'] += 1
        age_group_data[ag][cat] = age_group_data[ag].get(cat, 0) + 1
        age_group_data[ag]['loss'] += val
        if c.get('lactation_days') and c['lactation_days'] > 0:
            age_group_data[ag]['dims'].append(c['lactation_days'])
        if c.get('weight') and c['weight'] > 0:
            age_group_data[ag]['weights'].append(c['weight'])
        r = c.get('reason') or 'Не указана'
        age_group_data[ag]['reasons'][r] = age_group_data[ag]['reasons'].get(r, 0) + 1
        if cat == 'выбраковка':
            age_group_data[ag]['culling_reasons'][r] = age_group_data[ag]['culling_reasons'].get(r, 0) + 1
        elif cat == 'падёж':
            age_group_data[ag]['death_reasons'][r] = age_group_data[ag]['death_reasons'].get(r, 0) + 1
        elif cat == 'санитарный':
            age_group_data[ag]['sanitary_reasons'][r] = age_group_data[ag]['sanitary_reasons'].get(r, 0) + 1

    sorted_groups = sorted(age_group_data.keys(), key=lambda x: age_group_data[x]['total'], reverse=True)
    age_labels = sorted_groups
    age_death = [age_group_data[g]['падёж'] for g in sorted_groups]
    age_culling = [age_group_data[g]['выбраковка'] for g in sorted_groups]
    age_sanitary = [age_group_data[g]['санитарный'] for g in sorted_groups]

    category_analytics = []
    for g in sorted_groups:
        d_grp = age_group_data[g]
        tot = d_grp['total']
        if tot == 0:
            continue
        sorted_reasons = sorted(d_grp['reasons'].items(), key=lambda x: x[1], reverse=True)
        top_r = sorted_reasons[:3]
        top_r_str = ', '.join([f"{k} ({v})" for k, v in top_r]) if top_r else 'Нет записей'
        reasons_list = [
            {'reason': k, 'count': v, 'pct': round((v / tot) * 100, 1)}
            for k, v in sorted_reasons[:6]
        ]

        culling_cnt = d_grp['выбраковка']
        culling_reasons_list = [
            {'reason': k, 'count': v, 'pct': round((v / max(culling_cnt, 1)) * 100, 1)}
            for k, v in sorted(d_grp['culling_reasons'].items(), key=lambda x: x[1], reverse=True)[:5]
        ]

        death_cnt = d_grp['падёж']
        death_reasons_list = [
            {'reason': k, 'count': v, 'pct': round((v / max(death_cnt, 1)) * 100, 1)}
            for k, v in sorted(d_grp['death_reasons'].items(), key=lambda x: x[1], reverse=True)[:5]
        ]

        sanitary_cnt = d_grp['санитарный']
        sanitary_reasons_list = [
            {'reason': k, 'count': v, 'pct': round((v / max(sanitary_cnt, 1)) * 100, 1)}
            for k, v in sorted(d_grp['sanitary_reasons'].items(), key=lambda x: x[1], reverse=True)[:5]
        ]

        culling_pct = round((culling_cnt / tot) * 100, 1)
        death_pct = round((death_cnt / tot) * 100, 1)
        sanitary_pct = round((sanitary_cnt / tot) * 100, 1)

        category_analytics.append({
            'category_name': g,
            'total': tot,
            'death': death_cnt,
            'culling': culling_cnt,
            'sanitary': sanitary_cnt,
            'death_rate_pct': death_pct,
            'culling_pct': culling_pct,
            'sanitary_pct': sanitary_pct,
            'avg_dim': round(sum(d_grp['dims']) / len(d_grp['dims'])) if d_grp['dims'] else 0,
            'avg_weight': round(sum(d_grp['weights']) / len(d_grp['weights'])) if d_grp['weights'] else 0,
            'loss_byn': round(d_grp['loss']),
            'top_reasons': top_r_str,
            'reasons_list': reasons_list,
            'culling_reasons': culling_reasons_list,
            'death_reasons': death_reasons_list,
            'sanitary_reasons': sanitary_reasons_list
        })

    # 5. Аналитика лактации: DIM Bins (8 интервалов) & Parity
    dim_bins_labels = ['0-15 дн', '16-30 дн', '31-60 дн', '61-100 дн', '101-150 дн', '151-200 дн', '201-305 дн', '>305 дн']
    dim_curve_death = [0] * 8
    dim_curve_culling = [0] * 8

    lact_nums_labels = ['1-я (первотёлки)', '2-я лактация', '3-я лактация', '4-я лактация', '5+ лактация']
    lact_num_death = [0] * 5
    lact_num_culling = [0] * 5

    lact_phase_labels = ['Ранний новотел (0-15)', 'Поздний новотел (16-30)', 'Раздой и пик (31-100)', 'Середина (101-200)', 'Спад (201-305)', 'Сухостой']
    lact_phase_death = [0] * 6
    lact_phase_culling = [0] * 6

    total_dim = 0
    cows_with_dim = 0
    total_lact = 0
    cows_with_lact = 0
    fresh_disposals = 0
    fresh_deaths = 0

    # Аналитика продуктивности (когорты надоя, кг)
    milk_cohort_labels = ['До 4 500 кг', '4 500–6 500 кг', '6 500–8 500 кг', 'Свыше 8 500 кг']
    milk_cohort_death = [0, 0, 0, 0]
    milk_cohort_culling = [0, 0, 0, 0]
    cows_with_milk = 0
    total_milk_sum = 0.0
    high_yield_lost_count = 0  # Потеря высокопродуктивных (>6500 кг)
    high_yield_death_count = 0

    # Матрица «Патология × Фаза лактации (DIM)»
    pathology_dim_matrix = {}

    # Сезонность выбытия
    seasons_labels = ['Зима (Дек–Фев)', 'Весна (Мар–Май)', 'Лето (Июн–Авг)', 'Осень (Сен–Ноя)']
    seasons_death = [0, 0, 0, 0]
    seasons_culling = [0, 0, 0, 0]

    for c in live_cows:
        dim = c.get('lactation_days') or 0
        lact = c.get('lactation') or 1
        cat = c.get('category')
        is_death = (cat == 'падёж')

        if dim > 0:
            total_dim += dim
            cows_with_dim += 1
            if dim <= 30:
                fresh_disposals += 1
                if is_death:
                    fresh_deaths += 1

            # 8 DIM интервалов
            b_idx = 7
            if dim <= 15: b_idx = 0
            elif dim <= 30: b_idx = 1
            elif dim <= 60: b_idx = 2
            elif dim <= 100: b_idx = 3
            elif dim <= 150: b_idx = 4
            elif dim <= 200: b_idx = 5
            elif dim <= 305: b_idx = 6

            if is_death:
                dim_curve_death[b_idx] += 1
            else:
                dim_curve_culling[b_idx] += 1

            # 6 Фаз лактации
            p_idx = 5
            if dim <= 15: p_idx = 0
            elif dim <= 30: p_idx = 1
            elif dim <= 100: p_idx = 2
            elif dim <= 200: p_idx = 3
            elif dim <= 305: p_idx = 4

            if is_death:
                lact_phase_death[p_idx] += 1
            else:
                lact_phase_culling[p_idx] += 1

            # Заполнение матрицы Патология x DIM
            p_phase_name = 'Новотел (0-30 дн)' if dim <= 30 else ('Раздой (31-100 дн)' if dim <= 100 else ('Середина (101-200 дн)' if dim <= 200 else 'Спад и сухостой (>200)'))
            sys_name = classify_pathology_system(c.get('reason'))
            if sys_name not in pathology_dim_matrix:
                pathology_dim_matrix[sys_name] = {'total': 0, 'Новотел (0-30 дн)': 0, 'Раздой (31-100 дн)': 0, 'Середина (101-200 дн)': 0, 'Спад и сухостой (>200)': 0}
            pathology_dim_matrix[sys_name]['total'] += 1
            pathology_dim_matrix[sys_name][p_phase_name] += 1

        if lact > 0:
            total_lact += lact
            cows_with_lact += 1
            l_idx = min(lact - 1, 4)
            if is_death:
                lact_num_death[l_idx] += 1
            else:
                lact_num_culling[l_idx] += 1

        # Анализ продуктивности коров
        m = float(c.get('milk_yield') or 0.0)
        norm_ag = normalize_age_group(c.get('age_group'), lact)
        if ('Коровы' in norm_ag or lact > 0) and 'Телята' not in norm_ag and 'молодняк' not in norm_ag.lower():
            if m <= 0:
                m = 6200.0 if lact > 1 else 5300.0
            cows_with_milk += 1
            total_milk_sum += m
            if m < 4500: m_idx = 0
            elif m <= 6500: m_idx = 1
            elif m <= 8500: m_idx = 2
            else: m_idx = 3

            if is_death:
                milk_cohort_death[m_idx] += 1
                if m >= 6500: high_yield_death_count += 1
            else:
                milk_cohort_culling[m_idx] += 1

            if m >= 6500:
                high_yield_lost_count += 1

        # Анализ сезонности
        d_str = c.get('disposal_date')
        if d_str:
            try:
                m_num = int(d_str.split('-')[1])
                s_idx = 0 if m_num in (12, 1, 2) else (1 if m_num in (3, 4, 5) else (2 if m_num in (6, 7, 8) else 3))
                if is_death:
                    seasons_death[s_idx] += 1
                else:
                    seasons_culling[s_idx] += 1
            except Exception:
                pass

    avg_dim = round(total_dim / cows_with_dim) if cows_with_dim > 0 else 0
    avg_lact = round(total_lact / cows_with_lact, 1) if cows_with_lact > 0 else 0
    avg_milk_yield = round(total_milk_sum / max(cows_with_milk, 1)) if cows_with_milk > 0 else 0

    total_adult_disposals = sum(lact_num_death) + sum(lact_num_culling)
    unrecovered_cows_count = lact_num_death[0] + lact_num_culling[0]  # Выбыли на 1-й лактации
    unrecovered_pct = round((unrecovered_cows_count / max(total_adult_disposals, 1)) * 100, 1)

    # Преобразование матрицы патологий в сортированный список для шаблона
    pathology_dim_list = []
    for s_name, counts in sorted(pathology_dim_matrix.items(), key=lambda x: x[1]['total'], reverse=True)[:7]:
        pathology_dim_list.append({
            'system': s_name,
            'total': counts['total'],
            'fresh_0_30': counts['Новотел (0-30 дн)'],
            'peak_31_100': counts['Раздой (31-100 дн)'],
            'mid_101_200': counts['Середина (101-200 дн)'],
            'late_200_plus': counts['Спад и сухостой (>200)']
        })

    # 5. Строго разделенные физиологические группы и сохранность
    calf_cows = [c for c in live_cows if normalize_age_group(c.get('age_group'), c.get('lactation')) == 'Телята (до 6 мес.)']
    calf_deaths = sum(1 for c in calf_cows if c['category'] == 'падёж')
    calf_mortality_pct = round((calf_deaths / max(len(calf_cows), 1)) * 100, 1) if calf_cows else 0.0
    calf_preservation = round(100.0 - calf_mortality_pct, 1)

    youngstock_cows = [c for c in live_cows if normalize_age_group(c.get('age_group'), c.get('lactation')) == 'Ремонтный молодняк (6–18 мес.)']
    youngstock_deaths = sum(1 for c in youngstock_cows if c['category'] == 'падёж')
    youngstock_pct = round((youngstock_deaths / max(len(youngstock_cows), 1)) * 100, 1) if youngstock_cows else 0.0
    youngstock_preservation = round(100.0 - youngstock_pct, 1)

    heifer_cows = [c for c in live_cows if normalize_age_group(c.get('age_group'), c.get('lactation')) == 'Нетели (>18 мес.)']
    heifer_deaths = sum(1 for c in heifer_cows if c['category'] == 'падёж')

    bull_cows = [c for c in live_cows if normalize_age_group(c.get('age_group'), c.get('lactation')) == 'Бычки на откорме']
    bull_deaths = sum(1 for c in bull_cows if c['category'] == 'падёж')

    first_lact_cows = [c for c in live_cows if normalize_age_group(c.get('age_group'), c.get('lactation')) == 'Коровы 1-й лактации (первотёлки)']
    first_lact_deaths = sum(1 for c in first_lact_cows if c['category'] == 'падёж')

    multiparous_cows = [c for c in live_cows if normalize_age_group(c.get('age_group'), c.get('lactation')) == 'Полновозрастные коровы (2+ лакт.)']
    multiparous_deaths = sum(1 for c in multiparous_cows if c['category'] == 'падёж')

    dry_cows = [c for c in live_cows if normalize_age_group(c.get('age_group'), c.get('lactation')) == 'Сухостойные коровы']
    dry_deaths = sum(1 for c in dry_cows if c['category'] == 'падёж')

    # 6. Патологический профиль (по системам органов)
    pathology_systems = {}
    for c in live_cows:
        system = classify_pathology_system(c['reason'])
        pathology_systems[system] = pathology_systems.get(system, 0) + 1
    sorted_pathology = sorted(pathology_systems.items(), key=lambda x: x[1], reverse=True)
    
    # 7. Топ причин выбытия за период
    reason_counts = {}
    for c in live_cows:
        key = (c['reason'], c['category'])
        reason_counts[key] = reason_counts.get(key, 0) + 1
    top_reasons_list = [
        {'reason': k[0], 'category': k[1], 'count': v}
        for k, v in sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)[:8]
    ]
    
    # 8. Распределение и Сравнительная матрица по фермам / МТФ
    farm_data = {}
    for c in live_cows:
        f = c['farm_name'] or 'Не указана'
        if f not in farm_data:
            farm_data[f] = {'total': 0, 'death': 0, 'culling': 0, 'sanitary': 0, 'calves': 0, 'young': 0, 'heifers': 0, 'fresh': 0, 'dims': [], 'loss': 0.0}
        cat = c['category']
        val = estimate_cow_val(c)
        farm_data[f]['total'] += 1
        farm_data[f]['loss'] += val
        if cat == 'падёж': farm_data[f]['death'] += 1
        elif cat == 'выбраковка': farm_data[f]['culling'] += 1
        else: farm_data[f]['sanitary'] += 1
        
        grp = normalize_age_group(c.get('age_group'), c.get('lactation'))
        if grp == 'Телята (до 6 мес.)':
            farm_data[f]['calves'] += 1
        elif grp == 'Ремонтный молодняк (6–18 мес.)':
            farm_data[f]['young'] += 1
        elif grp == 'Нетели (>18 мес.)':
            farm_data[f]['heifers'] += 1

        d_val = c.get('lactation_days') or 0
        if d_val > 0:
            farm_data[f]['dims'].append(d_val)
            if d_val <= 30:
                farm_data[f]['fresh'] += 1

    # Динамические зоотехнические нормативы и пороги тревог строго из базы данных
    norm_calf_preservation = float(get_setting('norm_calf_preservation', 95.0))
    warn_calf_preservation = float(get_setting('warn_calf_preservation', 92.0))
    crit_calf_preservation = float(get_setting('crit_calf_preservation', 88.0))

    norm_young_preservation = float(get_setting('norm_youngstock_preservation', 92.0))
    warn_young_preservation = float(get_setting('warn_youngstock_preservation', 88.0))
    crit_young_preservation = float(get_setting('crit_youngstock_preservation', 82.0))

    norm_fresh = float(get_setting('norm_fresh_cow_disposal', 10.0))
    warn_fresh = float(get_setting('warn_fresh_cow_disposal', 14.0))
    crit_fresh = float(get_setting('crit_fresh_cow_disposal', 18.0))

    norm_first_lact = float(get_setting('norm_first_lactation_culling', 20.0))
    warn_first_lact = float(get_setting('warn_first_lactation_culling', 25.0))
    crit_first_lact = float(get_setting('crit_first_lactation_culling', 30.0))

    norm_mortality = float(get_setting('norm_mortality_rate', 25.0))
    warn_mortality = float(get_setting('warn_mortality_rate', 35.0))
    crit_mortality = float(get_setting('crit_mortality_rate', 45.0))

    norm_locomotor = float(get_setting('norm_locomotor_disorders', 15.0))
    warn_locomotor = float(get_setting('warn_locomotor_disorders', 20.0))
    crit_locomotor = float(get_setting('crit_locomotor_disorders', 25.0))

    norm_mastitis = float(get_setting('norm_mastitis_disorders', 15.0))
    warn_mastitis = float(get_setting('warn_mastitis_disorders', 20.0))
    crit_mastitis = float(get_setting('crit_mastitis_disorders', 25.0))

    sorted_farms = sorted([(f, d['total']) for f, d in farm_data.items()], key=lambda x: x[1], reverse=True)
    farm_matrix = []
    for f, d in sorted(farm_data.items(), key=lambda x: x[1]['total'], reverse=True):
        d_pct = round((d['death'] / max(d['total'], 1)) * 100, 1)
        stat = 'optimal'
        stat_lbl = 'Норма'
        if d_pct >= crit_mortality or (d['total'] > 10 and (d['fresh'] / max(d['total'], 1) * 100) >= crit_fresh):
            stat = 'critical'
            stat_lbl = 'Критический риск'
        elif d_pct >= warn_mortality or (d['total'] > 10 and (d['fresh'] / max(d['total'], 1) * 100) >= warn_fresh):
            stat = 'warning'
            stat_lbl = 'Внимание'
        farm_matrix.append({
            'farm': f,
            'total': d['total'],
            'death': d['death'],
            'culling': d['culling'],
            'sanitary': d['sanitary'],
            'death_pct': d_pct,
            'calves': d['calves'],
            'youngstock': d['young'],
            'heifers': d['heifers'],
            'fresh_0_30': d['fresh'],
            'avg_dim': round(sum(d['dims']) / len(d['dims'])) if d['dims'] else 0,
            'total_loss_byn': round(d['loss']),
            'status': stat,
            'status_label': stat_lbl
        })

    # Ветеринарный скоркард (7 индикаторов)
    death_overall_rate = round((category_counts.get('падёж', 0) / max(total_disposals, 1)) * 100, 1)
    fresh_rate = round((fresh_disposals / max(total_disposals, 1)) * 100, 1)
    first_lact_rate = round((lact_num_culling[0] / max(sum(lact_num_culling), 1)) * 100, 1) if sum(lact_num_culling) > 0 else 0.0
    locomotor_rate = round((pathology_systems.get('Конечности и травматизм', 0) / max(total_disposals, 1)) * 100, 1)
    mastitis_rate = round((pathology_systems.get('Болезни вымени (маститы)', 0) / max(total_disposals, 1)) * 100, 1)

    prog_calf = max(5, min(100, round(float(calf_preservation))))
    prog_young = max(5, min(100, round(float(youngstock_preservation))))
    prog_fresh = max(5, min(100, round((fresh_rate / max(norm_fresh, 0.1)) * 100)))
    prog_first_lact = max(5, min(100, round((first_lact_rate / max(norm_first_lact, 0.1)) * 100)))
    prog_mortality = max(5, min(100, round((death_overall_rate / max(norm_mortality, 0.1)) * 100)))
    prog_locomotor = max(5, min(100, round((locomotor_rate / max(norm_locomotor, 0.1)) * 100)))
    prog_mastitis = max(5, min(100, round((mastitis_rate / max(norm_mastitis, 0.1)) * 100)))

    scorecard = [
        {
            'key': 'norm_fresh_cow_disposal',
            'operator': '<=',
            'val': float(norm_fresh),
            'warn_val': float(warn_fresh),
            'crit_val': float(crit_fresh),
            'current_num': float(fresh_rate),
            'title': 'Выбытие новотельных (0-30 DIM)',
            'target': f"≤ {norm_fresh:.1f}%",
            'current': f"{fresh_rate}%",
            'progress_pct': prog_fresh,
            'status': 'success' if fresh_rate <= norm_fresh else ('warning' if fresh_rate <= crit_fresh else 'danger'),
            'statusText': 'Норма' if fresh_rate <= norm_fresh else ('Внимание' if fresh_rate <= crit_fresh else 'Риск'),
            'note': f"Новотел: {fresh_disposals} гол. ({fresh_deaths} пало)",
            'icon': 'bi-exclamation-octagon-fill'
        },
        {
            'key': 'norm_first_lactation_culling',
            'operator': '<=',
            'val': float(norm_first_lact),
            'warn_val': float(warn_first_lact),
            'crit_val': float(crit_first_lact),
            'current_num': float(first_lact_rate),
            'title': 'Выбраковка первотёлок',
            'target': f"≤ {norm_first_lact:.1f}%",
            'current': f"{first_lact_rate}%",
            'progress_pct': prog_first_lact,
            'status': 'success' if first_lact_rate <= norm_first_lact else ('warning' if first_lact_rate <= crit_first_lact else 'danger'),
            'statusText': 'Норма' if first_lact_rate <= norm_first_lact else 'Высокая',
            'note': 'Доля 1-й лактации в выбраковке',
            'icon': 'bi-gem'
        },
        {
            'key': 'norm_mortality_rate',
            'operator': '<=',
            'val': float(norm_mortality),
            'warn_val': float(warn_mortality),
            'crit_val': float(crit_mortality),
            'current_num': float(death_overall_rate),
            'title': 'Общая летальность (Падёж)',
            'target': f"≤ {norm_mortality:.1f}%",
            'current': f"{death_overall_rate}%",
            'progress_pct': prog_mortality,
            'status': 'success' if death_overall_rate <= norm_mortality else ('warning' if death_overall_rate <= crit_mortality else 'danger'),
            'statusText': 'Норма' if death_overall_rate <= norm_mortality else ('Повышен' if death_overall_rate <= crit_mortality else 'Критич.'),
            'note': f"Пало {category_counts.get('падёж', 0)} из {total_disposals} гол.",
            'icon': 'bi-heart-pulse-fill'
        },
        {
            'key': 'norm_locomotor_disorders',
            'operator': '<=',
            'val': float(norm_locomotor),
            'warn_val': float(warn_locomotor),
            'crit_val': float(crit_locomotor),
            'current_num': float(locomotor_rate),
            'title': 'Болезни конечностей',
            'target': f"≤ {norm_locomotor:.1f}%",
            'current': f"{locomotor_rate}%",
            'progress_pct': prog_locomotor,
            'status': 'success' if locomotor_rate <= norm_locomotor else ('warning' if locomotor_rate <= crit_locomotor else 'danger'),
            'statusText': 'В норме' if locomotor_rate <= norm_locomotor else ('Контроль' if locomotor_rate <= crit_locomotor else 'Риск'),
            'note': 'Ортопедическая патология',
            'icon': 'bi-bandaid-fill'
        },
        {
            'key': 'norm_mastitis_disorders',
            'operator': '<=',
            'val': float(norm_mastitis),
            'warn_val': float(warn_mastitis),
            'crit_val': float(crit_mastitis),
            'current_num': float(mastitis_rate),
            'title': 'Маститы и патологии вымени',
            'target': f"≤ {norm_mastitis:.1f}%",
            'current': f"{mastitis_rate}%",
            'progress_pct': prog_mastitis,
            'status': 'success' if mastitis_rate <= norm_mastitis else ('warning' if mastitis_rate <= crit_mastitis else 'danger'),
            'statusText': 'В норме' if mastitis_rate <= norm_mastitis else ('Контроль' if mastitis_rate <= crit_mastitis else 'Риск'),
            'note': 'Инфекции молочной железы',
            'icon': 'bi-droplet-fill'
        }
    ]

    
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
        
    # 10. Сохранность молодняка (Телята 0-6 мес. уже рассчитаны выше через normalize_age_group)
    calf_disposals_count = len(calf_cows)
    calf_death_count = calf_deaths
    
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
                   lactation, weight, age_group, milk_yield, book_value,
                   is_pregnant, gestation_days, is_stillborn
            FROM cows
            {all_time_where}
            ORDER BY disposal_date DESC, id DESC
            LIMIT 10
        ''', all_time_params)
        recent_cows = [dict(r) for r in cursor.fetchall()]
    
    # 9. Аналитика стельности и мертворождений / абортов
    pregnant_cows = []
    stillborn_cows = []
    stillborn_keywords = ['мертворож', 'аборт', 'плод', 'мумификац', 'мацерац', 'патология родов', 'патологические роды', 'гибель плода', 'мертвый теленок']
    
    for c in period_cows:
        reason_lower = (c.get('reason') or '').lower()
        age_grp_lower = (c.get('age_group') or '').lower()
        phase_lower = (c.get('lactation_phase') or '').lower()
        
        is_preg = False
        if c.get('is_pregnant') == 1 or (c.get('gestation_days') and c['gestation_days'] > 0):
            is_preg = True
        elif 'сухостой' in phase_lower or 'сухостой' in age_grp_lower or 'нетел' in age_grp_lower or 'стельн' in reason_lower or 'стельн' in age_grp_lower:
            is_preg = True
            
        if is_preg:
            pregnant_cows.append(c)
    # Извлечение мертворождений из отдельной таблицы stillbirth_records
    sb_where = ["event_date BETWEEN ? AND ?"]
    sb_params = [start_date, end_date]
    if user_type == 'farm' and farm_name:
        sb_where.append("farm_name = ?")
        sb_params.append(farm_name)
    elif user_type == 'admin' and farm_name and farm_name != 'all':
        sb_where.append("farm_name = ?")
        sb_params.append(farm_name)

    cursor.execute(f"SELECT * FROM stillbirth_records WHERE {' AND '.join(sb_where)}", sb_params)
    period_stillborn_rows = [dict(r) for r in cursor.fetchall()]
    # Детальная аналитика мертворождений из stillbirth_records
    sb_sex_counts = {'Бычки': 0, 'Тёлочки': 0, 'Двойня': 0, 'Не определён': 0}
    sb_mother_groups = {}
    sb_causes = {}
    total_fetus_weight = 0.0
    total_gest_days = 0
    sb_weight_cnt = 0
    sb_days_cnt = 0

    for r in period_stillborn_rows:
        sx = r.get('fetus_sex') or 'Не определён'
        if 'быч' in sx.lower(): sb_sex_counts['Бычки'] += 1
        elif 'тёл' in sx.lower() or 'тел' in sx.lower(): sb_sex_counts['Тёлочки'] += 1
        elif 'двойн' in sx.lower(): sb_sex_counts['Двойня'] += 1
        else: sb_sex_counts['Не определён'] += 1

        mg = r.get('mother_group') or 'Полновозрастные'
        sb_mother_groups[mg] = sb_mother_groups.get(mg, 0) + 1

        cs = r.get('cause') or 'Патология плода'
        sb_causes[cs] = sb_causes.get(cs, 0) + 1

        fw = float(r.get('fetus_weight') or 0.0)
        if fw > 0:
            total_fetus_weight += fw
            sb_weight_cnt += 1

        gd = int(r.get('gestation_days') or 0)
        if gd > 0:
            total_gest_days += gd
            sb_days_cnt += 1

    avg_fetus_weight = round(total_fetus_weight / max(sb_weight_cnt, 1), 1) if sb_weight_cnt > 0 else 25.0
    avg_gest_days = round(total_gest_days / max(sb_days_cnt, 1)) if sb_days_cnt > 0 else 275

    sb_causes_sorted = sorted(sb_causes.items(), key=lambda x: x[1], reverse=True)
    sb_causes_labels = [x[0] for x in sb_causes_sorted[:6]]
    sb_causes_data = [x[1] for x in sb_causes_sorted[:6]]

    sb_mg_sorted = sorted(sb_mother_groups.items(), key=lambda x: x[1], reverse=True)
    sb_mg_labels = [x[0] for x in sb_mg_sorted]
    sb_mg_data = [x[1] for x in sb_mg_sorted]

    stillborn_count = len(period_stillborn_rows)
    term_stillborn_cnt = sum(1 for r in period_stillborn_rows if 'Мертворожд' in (r.get('event_type') or ''))
    abortion_cnt = sum(1 for r in period_stillborn_rows if 'Аборт' in (r.get('event_type') or ''))

    stillborn_reasons = {}
    for r in period_stillborn_rows:
        cause = r.get('cause') or 'Патология плода'
        stillborn_reasons[cause] = stillborn_reasons.get(cause, 0) + 1
    stillborn_reasons_list = [{'reason': k, 'count': v} for k, v in sorted(stillborn_reasons.items(), key=lambda x: x[1], reverse=True)]

    pregnant_count = len(pregnant_cows)
    adult_cows_total = sum(1 for c in period_cows if normalize_age_group(c.get('age_group'), c.get('lactation')) not in ['Телята (до 6 мес.)', 'Ремонтный молодняк (6–18 мес.)', 'Бычки на откорме'])
    pregnant_pct = round((pregnant_count / max(adult_cows_total, 1)) * 100, 1)
    pregnant_loss_byn = round(sum(estimate_cow_val(c) for c in pregnant_cows))
    
    gestation_vals = [c.get('gestation_days') for c in pregnant_cows if c.get('gestation_days') and c['gestation_days'] > 0]
    avg_gestation_months = round(sum(gestation_vals) / len(gestation_vals) / 30.0, 1) if gestation_vals else 6.5
    
    stillborn_pct = round((stillborn_count / max(total_disposals + stillborn_count, 1)) * 100, 1)
    
    reproduction_by_farm = []
    for f in sorted_farms:
        f_name = f[0]
        f_cows = [c for c in period_cows if (c.get('farm_name') or 'Не указана') == f_name]
        f_preg_cows = [c for c in f_cows if c in pregnant_cows]
        f_preg_death = sum(1 for c in f_preg_cows if (c.get('category') or '').lower() == 'падёж')
        f_preg_cull = sum(1 for c in f_preg_cows if (c.get('category') or '').lower() != 'падёж')
        f_preg_loss = round(sum(estimate_cow_val(c) for c in f_preg_cows))
        f_stillborn = sum(1 for r in period_stillborn_rows if (r.get('farm_name') or 'Не указана') == f_name)
        reproduction_by_farm.append({
            'farm_name': f_name,
            'total': len(f_cows),
            'pregnant_count': len(f_preg_cows),
            'pregnant_pct': round((len(f_preg_cows) / max(len(f_cows), 1)) * 100, 1),
            'pregnant_death': f_preg_death,
            'pregnant_culling': f_preg_cull,
            'pregnant_loss_byn': f_preg_loss,
            'stillborn_count': f_stillborn,
            'stillborn_pct': round((f_stillborn / max(len(f_cows) + f_stillborn, 1)) * 100, 1)
        })
        
    # Сроки стельности выбывших коров (без примешивания мертворождений)
    t1_count = 0  # 1–90 дн
    t2_count = 0  # 91–180 дн
    t3_count = 0  # 181–240 дн
    t4_count = 0  # 241+ дн (глубокий сухостой перед отелом)
    for c in pregnant_cows:
        days = c.get('gestation_days') or 0
        ag_l = (c.get('age_group') or '').lower()
        if days > 240 or ('сухосто' in ag_l and days > 210):
            t4_count += 1
        elif days > 180 or 'сухосто' in ag_l:
            t3_count += 1
        elif days > 90:
            t2_count += 1
        else:
            t1_count += 1

    structure_labels = [
        '1–90 дн (1-й триместр)',
        '91–180 дн (2-й триместр)',
        '181–240 дн (3-й триместр)',
        '241+ дн (сухостой перед отёлом)'
    ]
    structure_data = [t1_count, t2_count, t3_count, t4_count]
    structure_colors = ['#3B82F6', '#F59E0B', '#F97316', '#EF4444']

    preg_death = sum(1 for c in pregnant_cows if (c.get('category') or '').lower() == 'падёж')
    preg_culling = sum(1 for c in pregnant_cows if (c.get('category') or '').lower() == 'выбраковка')
    preg_sanitary = sum(1 for c in pregnant_cows if 'сан' in (c.get('category') or '').lower())

    preg_reasons = {}
    for c in pregnant_cows:
        r = c.get('reason') or 'Не указана'
        preg_reasons[r] = preg_reasons.get(r, 0) + 1
    preg_reasons_list = [{'reason': k, 'count': v} for k, v in sorted(preg_reasons.items(), key=lambda x: x[1], reverse=True)]

    farm_labels = [f['farm_name'] for f in reproduction_by_farm]
    farm_pregnant_total = [f['pregnant_count'] for f in reproduction_by_farm]
    farm_pregnant_death = [f['pregnant_death'] for f in reproduction_by_farm]
    farm_pregnant_culling = [f['pregnant_culling'] for f in reproduction_by_farm]

    reproduction_summary = {
        'pregnant_count': pregnant_count,
        'pregnant_pct': pregnant_pct,
        'pregnant_loss_byn': pregnant_loss_byn,
        'pregnant_death_count': preg_death,
        'pregnant_culling_count': preg_culling,
        'pregnant_sanitary_count': preg_sanitary,
        'pregnant_top_reasons': preg_reasons_list[:5],
        'late_gestation_count': t3_count + t4_count,
        'avg_gestation_months': avg_gestation_months,
        'stillborn_count': stillborn_count,
        'stillborn_pct': stillborn_pct,
        'term_stillborn_cnt': term_stillborn_cnt,
        'abortion_cnt': abortion_cnt,
        'avg_fetus_weight': avg_fetus_weight,
        'avg_gest_days': avg_gest_days,
        'stillborn_reasons': stillborn_reasons_list,
        'stillbirth_profile': {
            'causes_labels': sb_causes_labels,
            'causes_data': sb_causes_data,
            'mother_groups_labels': sb_mg_labels,
            'mother_groups_data': sb_mg_data,
            'sex_labels': list(sb_sex_counts.keys()),
            'sex_data': list(sb_sex_counts.values())
        },
        'by_farm': reproduction_by_farm,
        'stages': {
            'trimester_1': t1_count,
            'trimester_2': t2_count,
            'trimester_3': t3_count,
            'trimester_4': t4_count
        },
        'charts': {
            'structure': {
                'labels': structure_labels,
                'data': structure_data,
                'colors': structure_colors
            },
            'farms': {
                'labels': farm_labels,
                'pregnant_total': farm_pregnant_total,
                'pregnant_death': farm_pregnant_death,
                'pregnant_culling': farm_pregnant_culling
            },
            'reasons': {
                'labels': [r['reason'] for r in preg_reasons_list[:6]],
                'data': [r['count'] for r in preg_reasons_list[:6]]
            }
        }
    }

    return {
        'reproduction': reproduction_summary,
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
            'calf_disposals': len(calf_cows),
            'calf_death_count': calf_deaths,
            'calf_death_pct': calf_mortality_pct,
            'calf_preservation': calf_preservation,
            'youngstock_disposals': len(youngstock_cows),
            'youngstock_death_count': youngstock_deaths,
            'youngstock_death_pct': youngstock_pct,
            'youngstock_preservation': youngstock_preservation,
            'heifer_disposals': len(heifer_cows),
            'heifer_death_count': heifer_deaths,
            'bull_disposals': len(bull_cows),
            'bull_death_count': bull_deaths,
            'first_lact_disposals': len(first_lact_cows),
            'first_lact_death_count': first_lact_deaths,
            'multiparous_disposals': len(multiparous_cows),
            'multiparous_death_count': multiparous_deaths,
            'dry_disposals': len(dry_cows),
            'dry_death_count': dry_deaths,
            'fresh_disposals': fresh_disposals,
            'fresh_deaths': fresh_deaths,
            'fresh_share_pct': round((fresh_disposals / max(total_disposals, 1)) * 100, 1),
            'avg_dim': avg_dim,
            'avg_lactation': avg_lact,
            'avg_milk_yield': avg_milk_yield,
            'high_yield_lost_count': high_yield_lost_count,
            'high_yield_death_count': high_yield_death_count,
            'unrecovered_cows_count': unrecovered_cows_count,
            'unrecovered_cows_pct': unrecovered_pct,
            'culled_live_weight_total': round(culled_live_weight_total),
            'estimated_meat_revenue_byn': estimated_meat_revenue_byn,
            'net_economic_loss_byn': net_economic_loss_byn,
            'meat_price_per_kg': meat_price_per_kg,
            'milk_price_per_kg': milk_price_per_kg,
            'replacement_cost': replacement_cost,
            'unrealized_milk_loss_byn': unrealized_milk_loss_byn,
            'unrealized_milk_kg_total': round(unrealized_milk_kg_total),
            'unrecovered_heifer_loss_byn': unrecovered_heifer_loss_byn,
            'total_loss_byn': round(total_loss_byn),
            'death_loss_byn': round(death_loss_byn),
            'culling_loss_byn': round(culling_loss_byn),
            'avg_head_loss': avg_head_loss,
            'all_time_total': all_time_total
        },
        'scorecard': scorecard,
        'farm_matrix': farm_matrix,
        'category_analytics': category_analytics,
        'pathology_by_dim': pathology_dim_list,
        'charts': {
            'categories': {
                'labels': ['Падёж', 'Выбраковка', 'Санитарный брак'],
                'data': [category_counts.get('падёж', 0), category_counts.get('выбраковка', 0), category_counts.get('санитарный', 0)],
                'colors': ['#EF4444', '#3B82F6', '#F59E0B']
            },
            'age_groups': {
                'labels': age_labels,
                'data': [age_group_data[g]['total'] for g in age_labels],
                'death_data': age_death,
                'culling_data': age_culling,
                'sanitary_data': age_sanitary
            },
            'dim_curve': {
                'labels': dim_bins_labels,
                'death_data': dim_curve_death,
                'culling_data': dim_curve_culling,
                'total_data': [d + c for d, c in zip(dim_curve_death, dim_curve_culling)]
            },
            'dim_comprehensive': {
                'labels': lact_phase_labels,
                'death_data': lact_phase_death,
                'culling_data': lact_phase_culling,
                'total_data': [d + c for d, c in zip(lact_phase_death, lact_phase_culling)]
            },
            'milk_productivity': {
                'labels': milk_cohort_labels,
                'death_data': milk_cohort_death,
                'culling_data': milk_cohort_culling
            },
            'lactation_numbers': {
                'labels': lact_nums_labels,
                'death_data': lact_num_death,
                'culling_data': lact_num_culling
            },
            'longevity': {
                'labels': lact_nums_labels,
                'death_data': lact_num_death,
                'culling_data': lact_num_culling
            },
            'seasonality': {
                'labels': seasons_labels,
                'death_data': seasons_death,
                'culling_data': seasons_culling,
                'total_data': [d + c for d, c in zip(seasons_death, seasons_culling)]
            },
            'lactation_phases': {
                'labels': lact_phase_labels,
                'death_data': lact_phase_death,
                'culling_data': lact_phase_culling
            },
            'economics_by_group': {
                'labels': age_labels,
                'data': [round(age_group_data[g]['loss']) for g in age_labels],
                'death_data': [round(age_group_data[g]['падёж'] * estimate_cow_val({'age_group': g})) for g in age_labels],
                'culling_data': [round((age_group_data[g]['выбраковка'] + age_group_data[g]['санитарный']) * estimate_cow_val({'age_group': g})) for g in age_labels]
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
    
    # 2. Серийные вспышки конкретных причин за 30 дней (группировка по фермам без дублирования)
    cursor.execute(f'''
        SELECT reason, category, farm_name, COUNT(*) as cnt 
        FROM cows 
        WHERE disposal_date >= '{d30_ago}' {where_farm}
        GROUP BY reason, category, farm_name
        HAVING cnt >= 3
        ORDER BY cnt DESC
        LIMIT 5
    ''', params)
    pathology_rows = cursor.fetchall()
    if pathology_rows:
        farm_pathologies = {}
        for r in pathology_rows:
            f_name = r['farm_name'] or 'Подразделение'
            if f_name not in farm_pathologies:
                farm_pathologies[f_name] = []
            farm_pathologies[f_name].append(f"{r['reason']} ({r['cnt']} гол.)")
        
        for f_name, p_list in farm_pathologies.items():
            if len(p_list) == 1:
                alerts.append({
                    'type': 'warning',
                    'icon': 'bi-exclamation-triangle-fill',
                    'title': f'Повторяющаяся патология ({f_name})',
                    'message': f'За 30 дней зафиксированы случаи: {p_list[0]}. Рекомендуется проверить рацион, условия содержания и микроклимат.'
                })
            else:
                p_str = "; ".join(p_list)
                alerts.append({
                    'type': 'warning',
                    'icon': 'bi-exclamation-triangle-fill',
                    'title': f'Часто повторяющиеся патологии ({f_name})',
                    'message': f'За последние 30 дней зарегистрировано несколько повторяющихся диагнозов: {p_str}. Рекомендуется комплексный ветконтроль и проверка микроклимата.'
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
