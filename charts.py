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
    
    # 2. Выборка строк за выбранный период
    cursor.execute(f'''
        SELECT id, cow_id, ear_tag, farm_name, category, reason, disposal_date, 
               lactation, lactation_days, lactation_phase, weight, age_group, milk_yield, book_value,
               is_pregnant, gestation_days, is_stillborn
        FROM cows
        {where_clause}
        ORDER BY disposal_date DESC, id DESC
    ''', params)
    period_cows = [dict(r) for r in cursor.fetchall()]
    
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

    for c in live_cows:
        cat = c['category']
        category_counts[cat] = category_counts.get(cat, 0) + 1
        val = estimate_cow_val(c)
        total_loss_byn += val
        if cat == 'падёж':
            death_loss_byn += val
        elif cat == 'выбраковка':
            culling_loss_byn += val
        
    total_disposals = len(live_cows)
    avg_head_loss = round(total_loss_byn / max(total_disposals, 1))
    
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
        age_group_data[g] = {'total': 0, 'падёж': 0, 'выбраковка': 0, 'санитарный': 0, 'loss': 0.0, 'dims': [], 'weights': [], 'reasons': {}}

    for c in live_cows:
        ag = normalize_age_group(c.get('age_group'), c.get('lactation'))
        if ag not in age_group_data:
            age_group_data[ag] = {'total': 0, 'падёж': 0, 'выбраковка': 0, 'санитарный': 0, 'loss': 0.0, 'dims': [], 'weights': [], 'reasons': {}}
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
        top_r = sorted(d_grp['reasons'].items(), key=lambda x: x[1], reverse=True)[:2]
        top_r_str = ', '.join([f"{k} ({v})" for k, v in top_r]) if top_r else 'Нет записей'
        category_analytics.append({
            'category_name': g,
            'total': tot,
            'death': d_grp['падёж'],
            'culling': d_grp['выбраковка'],
            'sanitary': d_grp['санитарный'],
            'death_rate_pct': round((d_grp['падёж'] / tot) * 100, 1),
            'avg_dim': round(sum(d_grp['dims']) / len(d_grp['dims'])) if d_grp['dims'] else 0,
            'avg_weight': round(sum(d_grp['weights']) / len(d_grp['weights'])) if d_grp['weights'] else 0,
            'loss_byn': round(d_grp['loss']),
            'top_reasons': top_r_str
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

        if lact > 0:
            total_lact += lact
            cows_with_lact += 1
            l_idx = min(lact - 1, 4)
            if is_death:
                lact_num_death[l_idx] += 1
            else:
                lact_num_culling[l_idx] += 1

    avg_dim = round(total_dim / cows_with_dim) if cows_with_dim > 0 else 0
    avg_lact = round(total_lact / cows_with_lact, 1) if cows_with_lact > 0 else 0

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

    sorted_farms = sorted([(f, d['total']) for f, d in farm_data.items()], key=lambda x: x[1], reverse=True)
    farm_matrix = []
    for f, d in sorted(farm_data.items(), key=lambda x: x[1]['total'], reverse=True):
        d_pct = round((d['death'] / max(d['total'], 1)) * 100, 1)
        stat = 'optimal'
        stat_lbl = 'Норма'
        if d_pct > 30 or d['fresh'] >= 5:
            stat = 'critical'
            stat_lbl = 'Критический риск'
        elif d_pct > 15 or d['fresh'] >= 2:
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
    # Динамические зоотехнические нормативы и пороги тревог из БД
    norm_calf_preservation = float(get_setting('norm_calf_preservation', 95.0))
    norm_young_preservation = float(get_setting('norm_youngstock_preservation', 98.0))
    norm_fresh = float(get_setting('norm_fresh_cow_disposal', 10.0))
    norm_first_lact = float(get_setting('norm_first_lactation_culling', 20.0))
    norm_mortality = float(get_setting('norm_mortality_rate', 25.0))
    norm_locomotor = float(get_setting('norm_locomotor_disorders', 15.0))
    norm_mastitis = float(get_setting('norm_mastitis_disorders', 15.0))

    # Расчет процента заполнения progress-bar скоркарда, отражающего реальное отклонение от норматива
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
            'warn_val': float(norm_fresh + 4.0),
            'crit_val': float(norm_fresh + 8.0),
            'current_num': float(fresh_rate),
            'title': 'Выбытие новотельных (0-30 DIM)',
            'target': f"≤ {norm_fresh:.1f}%",
            'current': f"{fresh_rate}%",
            'progress_pct': prog_fresh,
            'status': 'success' if fresh_rate <= norm_fresh else ('warning' if fresh_rate <= (norm_fresh + 8.0) else 'danger'),
            'statusText': 'Норма' if fresh_rate <= norm_fresh else ('Внимание' if fresh_rate <= (norm_fresh + 8.0) else 'Риск'),
            'note': f"Новотел: {fresh_disposals} гол. ({fresh_deaths} пало)",
            'icon': 'bi-exclamation-octagon-fill'
        },
        {
            'key': 'norm_first_lactation_culling',
            'operator': '<=',
            'val': float(norm_first_lact),
            'warn_val': float(norm_first_lact + 5.0),
            'crit_val': float(norm_first_lact + 10.0),
            'current_num': float(first_lact_rate),
            'title': 'Выбраковка первотёлок',
            'target': f"≤ {norm_first_lact:.1f}%",
            'current': f"{first_lact_rate}%",
            'progress_pct': prog_first_lact,
            'status': 'success' if first_lact_rate <= norm_first_lact else ('warning' if first_lact_rate <= (norm_first_lact + 8.0) else 'danger'),
            'statusText': 'Норма' if first_lact_rate <= norm_first_lact else 'Высокая',
            'note': 'Доля 1-й лактации в выбраковке',
            'icon': 'bi-gem'
        },
        {
            'key': 'norm_mortality_rate',
            'operator': '<=',
            'val': float(norm_mortality),
            'warn_val': float(norm_mortality + 10.0),
            'crit_val': float(norm_mortality + 20.0),
            'current_num': float(death_overall_rate),
            'title': 'Общая летальность (Падёж)',
            'target': f"≤ {norm_mortality:.1f}%",
            'current': f"{death_overall_rate}%",
            'progress_pct': prog_mortality,
            'status': 'success' if death_overall_rate <= norm_mortality else ('warning' if death_overall_rate <= (norm_mortality + 15.0) else 'danger'),
            'statusText': 'Норма' if death_overall_rate <= norm_mortality else ('Повышен' if death_overall_rate <= (norm_mortality + 15.0) else 'Критич.'),
            'note': f"Пало {category_counts.get('падёж', 0)} из {total_disposals} гол.",
            'icon': 'bi-heart-pulse-fill'
        },
        {
            'key': 'norm_locomotor_disorders',
            'operator': '<=',
            'val': float(norm_locomotor),
            'warn_val': float(norm_locomotor + 5.0),
            'crit_val': float(norm_locomotor + 10.0),
            'current_num': float(locomotor_rate),
            'title': 'Болезни конечностей',
            'target': f"≤ {norm_locomotor:.1f}%",
            'current': f"{locomotor_rate}%",
            'progress_pct': prog_locomotor,
            'status': 'success' if locomotor_rate <= norm_locomotor else 'warning',
            'statusText': 'В норме' if locomotor_rate <= norm_locomotor else 'Контроль',
            'note': 'Ортопедическая патология',
            'icon': 'bi-bandaid-fill'
        },
        {
            'key': 'norm_mastitis_disorders',
            'operator': '<=',
            'val': float(norm_mastitis),
            'warn_val': float(norm_mastitis + 5.0),
            'crit_val': float(norm_mastitis + 10.0),
            'current_num': float(mastitis_rate),
            'title': 'Маститы и патологии вымени',
            'target': f"≤ {norm_mastitis:.1f}%",
            'current': f"{mastitis_rate}%",
            'progress_pct': prog_mastitis,
            'status': 'success' if mastitis_rate <= norm_mastitis else 'warning',
            'statusText': 'В норме' if mastitis_rate <= norm_mastitis else 'Контроль',
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
            
        is_stillborn = False
        if c.get('is_stillborn') == 1:
            is_stillborn = True
        elif any(k in reason_lower for k in stillborn_keywords) or 'мертворожд' in age_grp_lower or 'аборт' in age_grp_lower:
            is_stillborn = True
            
        if is_stillborn:
            stillborn_cows.append(c)
            
    pregnant_count = len(pregnant_cows)
    adult_cows_total = sum(1 for c in period_cows if normalize_age_group(c.get('age_group'), c.get('lactation')) not in ['Телята (до 6 мес.)', 'Ремонтный молодняк (6–18 мес.)', 'Бычки на откорме'])
    pregnant_pct = round((pregnant_count / max(adult_cows_total, 1)) * 100, 1)
    pregnant_loss_byn = round(sum(estimate_cow_val(c) for c in pregnant_cows))
    
    gestation_vals = [c.get('gestation_days') for c in pregnant_cows if c.get('gestation_days') and c['gestation_days'] > 0]
    avg_gestation_months = round(sum(gestation_vals) / len(gestation_vals) / 30.0, 1) if gestation_vals else 6.5
    
    stillborn_count = len(stillborn_cows)
    stillborn_pct = round((stillborn_count / max(total_disposals, 1)) * 100, 1)
    
    stillborn_reasons = {}
    for c in stillborn_cows:
        r = c.get('reason') or 'Патология плода'
        stillborn_reasons[r] = stillborn_reasons.get(r, 0) + 1
    stillborn_reasons_list = [{'reason': k, 'count': v} for k, v in sorted(stillborn_reasons.items(), key=lambda x: x[1], reverse=True)]
    
    reproduction_by_farm = []
    for f in sorted_farms:
        farm_name = f[0]
        f_cows = [c for c in period_cows if (c.get('farm_name') or 'Не указана') == farm_name]
        f_preg_cows = [c for c in f_cows if c in pregnant_cows]
        f_preg_death = sum(1 for c in f_preg_cows if (c.get('category') or '').lower() == 'падёж')
        f_preg_cull = sum(1 for c in f_preg_cows if (c.get('category') or '').lower() != 'падёж')
        f_preg_loss = round(sum(estimate_cow_val(c) for c in f_preg_cows))
        f_stillborn = sum(1 for c in f_cows if c in stillborn_cows)
        reproduction_by_farm.append({
            'farm_name': farm_name,
            'total': len(f_cows),
            'pregnant_count': len(f_preg_cows),
            'pregnant_pct': round((len(f_preg_cows) / max(len(f_cows), 1)) * 100, 1),
            'pregnant_death': f_preg_death,
            'pregnant_culling': f_preg_cull,
            'pregnant_loss_byn': f_preg_loss,
            'stillborn_count': f_stillborn,
            'stillborn_pct': round((f_stillborn / max(len(f_cows), 1)) * 100, 1)
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
        'stillborn_reasons': stillborn_reasons_list,
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
            'total_loss_byn': round(total_loss_byn),
            'death_loss_byn': round(death_loss_byn),
            'culling_loss_byn': round(culling_loss_byn),
            'avg_head_loss': avg_head_loss,
            'all_time_total': all_time_total
        },
        'scorecard': scorecard,
        'farm_matrix': farm_matrix,
        'category_analytics': category_analytics,
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
            'lactation_numbers': {
                'labels': lact_nums_labels,
                'death_data': lact_num_death,
                'culling_data': lact_num_culling
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
