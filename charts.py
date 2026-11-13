# charts.py - Генерация данных для графиков Chart.js, аналитики, ПВГ и алертов (РБ)
import sqlite3
from functools import lru_cache
from datetime import datetime, timedelta
from database import get_db_connection, get_all_settings
from config import Config

# Классификация диагнозов по системам органов и патологиям (ветеринарный стандарт РБ)
PATHOLOGY_RULES = [
    ('Акушерство и гинекология', ['роды', 'моцерац', 'мацерац', 'эндометр', 'кист', 'яловост', 'маточн', 'сальпинг', 'матк', 'гинекол', 'фримартин']),
    ('Болезни вымени (маститы)', ['мастит', 'агалакти', 'вымен', 'соск']),
    ('Органы пищеварения', ['тимпани', 'гастро', 'язв', 'сычуг', 'рубец', 'перитонит', 'ретикул', 'атони', 'печен', 'цирроз', 'селезенк', 'преджелудк']),
    ('Органы дыхания', ['бронхопневмон', 'пневмон', 'легк', 'отек легких', 'дыхан']),
    ('Болезни молодняка (диспепсия)', ['диспепси', 'гипотрофи', 'колибакт', 'пупочн', 'эшерихиоз']),
    ('Конечности и травматизм', ['конечност', 'перелом', 'позвоноч', 'хромот', 'копыт', 'сустав', 'травм', 'мягких тканей', 'флегмон', 'рунхольц']),
    ('Нарушения обмена веществ', ['кетоз', 'ацидоз', 'обмен', 'парез']),
    ('Сердечно-сосудистая система', ['кровотеч', 'артери', 'сердц', 'инфаркт', 'миокард'])
]

PATHOLOGY_SYSTEM_NAMES = [r[0] for r in PATHOLOGY_RULES] + ['Прочие заболевания']

NON_COW_AGE_GROUPS = frozenset({
    'Телята (до 6 мес.)',
    'Ремонтный молодняк (6–18 мес.)',
    'Нетели (>18 мес.)',
    'Бычки на откорме',
    'Мертворождённые / Аборты'
})

@lru_cache(maxsize=512)
def classify_pathology_system(reason):
    r = (reason or '').lower()
    for sys_name, keywords in PATHOLOGY_RULES:
        for k in keywords:
            if k in r:
                return sys_name
    return 'Прочие заболевания'

@lru_cache(maxsize=512)
def normalize_age_group(raw_group, lactation=None):
    g = (raw_group or '').lower().strip()
    if any(k in g for k in ('мертворож', 'аборт', 'плод')):
        return 'Мертворождённые / Аборты'
    if any(k in g for k in ('телят', 'до 6', '0-6', '0–6', 'новорожд', 'молочн')):
        return 'Телята (до 6 мес.)'
    if any(k in g for k in ('молодняк', '6-18', '6–18', 'от 6 до 18', '6-12', '6–12', 'тёлки', 'телки', 'ремонтн')):
        return 'Ремонтный молодняк (6–18 мес.)'
    if any(k in g for k in ('нетел', 'старше 18', '> 18', '>18')):
        return 'Нетели (>18 мес.)'
    if any(k in g for k in ('быч', 'бык', 'откорм')):
        return 'Бычки на откорме'
    if 'сухосто' in g:
        return 'Сухостойные коровы'
    if any(k in g for k in ('новотел', '0-30', '0–30')):
        return 'Новотельные коровы (0–30 дн DIM)'
    if lactation == 1 or any(k in g for k in ('первотел', 'первотёл', '1-я лакт', '1-й лакт', '1 лакт')):
        return 'Коровы 1-й лактации (первотёлки)'
    if (lactation and lactation > 1) or any(k in g for k in ('полновозраст', '2+ лакт')):
        return 'Полновозрастные коровы (2+ лакт.)'
    return 'Коровы дойного стада'

def get_dashboard_full_data(user_type='admin', farm_name=None, period=None, custom_start=None, custom_end=None):
    """
    Комплексный расчет всех статистических срезов для аналитического дашборда
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now()

    # 0. Автоопределение периода (EXISTS останавливается на первой найденной строке)
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

        cursor.execute(f"SELECT EXISTS(SELECT 1 FROM cows WHERE {' AND '.join(p_check_where)} LIMIT 1)", p_check_params)
        if cursor.fetchone()[0]:
            period = 'this_month'
        else:
            last_m_end_dt = now.replace(day=1) - timedelta(days=1)
            last_m_end = last_m_end_dt.strftime('%Y-%m-%d')
            last_m_start = last_m_end_dt.replace(day=1).strftime('%Y-%m-%d')
            p_last_where = ["disposal_date BETWEEN ? AND ?"]
            p_last_params = [last_m_start, last_m_end]
            if user_type == 'farm' and farm_name:
                p_last_where.append("farm_name = ?")
                p_last_params.append(farm_name)
            elif user_type == 'admin' and farm_name and farm_name != 'all':
                p_last_where.append("farm_name = ?")
                p_last_params.append(farm_name)
            cursor.execute(f"SELECT EXISTS(SELECT 1 FROM cows WHERE {' AND '.join(p_last_where)} LIMIT 1)", p_last_params)
            period = 'last_month' if cursor.fetchone()[0] else 'all'

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
        period_cows = cursor.fetchall()
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
            period_cows = cursor.fetchall()
        else:
            conn.close()
            raise

    # Загружаем все настройки за 1 вызов (из быстрого кэша)
    all_settings = get_all_settings()
    def _setting_float(k, default):
        try:
            return float(all_settings.get(k, default))
        except (ValueError, TypeError):
            return float(default)

    dynamic_prices = {
        'телята': _setting_float('price_calves', 900.0),
        'молодняк': _setting_float('price_youngstock', 1650.0),
        'нетели': _setting_float('price_heifers', 2700.0),
        'дойное': _setting_float('price_cows', 3200.0),
        'сухостой': _setting_float('price_dry_cows', 3000.0)
    }
    meat_price_per_kg = _setting_float('meat_price_per_kg', 6.20)
    milk_price_per_kg = _setting_float('milk_price_per_kg', 1.18)
    replacement_cost = _setting_float('replacement_cost', 2950.0)

    def estimate_val(book_val, norm_grp):
        if book_val is not None and book_val > 0:
            return float(book_val)
        if norm_grp == 'Телята (до 6 мес.)':
            return dynamic_prices['телята']
        if norm_grp == 'Ремонтный молодняк (6–18 мес.)' or norm_grp == 'Бычки на откорме':
            return dynamic_prices['молодняк']
        if norm_grp == 'Нетели (>18 мес.)':
            return dynamic_prices['нетели']
        if norm_grp == 'Сухостойные коровы':
            return dynamic_prices['сухостой']
        return dynamic_prices['дойное']

    # Инициализация аккумуляторов для единого прохода O(N)
    category_counts = {'падёж': 0, 'выбраковка': 0, 'санитарный': 0}
    total_loss_byn = 0.0
    death_loss_byn = 0.0
    culling_loss_byn = 0.0
    culled_live_weight_total = 0.0
    estimated_meat_revenue_byn = 0.0
    unrealized_milk_loss_byn = 0.0
    unrealized_milk_kg_total = 0.0
    unrecovered_heifer_loss_byn = 0.0
    total_disposals = 0

    standard_groups = (
        'Телята (до 6 мес.)',
        'Ремонтный молодняк (6–18 мес.)',
        'Нетели (>18 мес.)',
        'Бычки на откорме',
        'Новотельные коровы (0–30 дн DIM)',
        'Коровы 1-й лактации (первотёлки)',
        'Полновозрастные коровы (2+ лакт.)',
        'Сухостойные коровы',
        'Мертворождённые / Аборты'
    )
    age_group_data = {
        g: {
            'total': 0, 'падёж': 0, 'выбраковка': 0, 'санитарный': 0,
            'loss': 0.0, 'death_loss': 0.0, 'culling_loss': 0.0,
            'dim_sum': 0, 'dim_cnt': 0, 'weight_sum': 0.0, 'weight_cnt': 0,
            'reasons': {}, 'culling_reasons': {}, 'death_reasons': {}, 'sanitary_reasons': {}
        }
        for g in standard_groups
    }

    dim_bins_labels = ['0-15 дн', '16-30 дн', '31-60 дн', '61-100 дн', '101-150 дн', '151-200 дн', '201-305 дн', '>305 дн']
    dim_curve_death = [0] * 8
    dim_curve_culling = [0] * 8

    lact_nums_labels = ['1-я (первотёлки)', '2-я лактация', '3-я лактация', '4-я лактация', '5+ лактация']
    lact_num_death = [0] * 5
    lact_num_culling = [0] * 5

    lact_phase_labels = ['Ранний новотел (0-15)', 'Поздний новотел (16-30)', 'Раздой и пик (31-100)', 'Середина (101-200)', 'Спад (201-305+)', 'Сухостой']
    lact_phase_death = [0] * 6
    lact_phase_culling = [0] * 6

    milk_cohort_labels = ['До 4 500 кг', '4 500–6 500 кг', '6 500–8 500 кг', 'Свыше 8 500 кг', 'Удой не указан']
    milk_cohort_death = [0, 0, 0, 0, 0]
    milk_cohort_culling = [0, 0, 0, 0, 0]

    seasons_labels = ['Зима (Дек–Фев)', 'Весна (Мар–Май)', 'Лето (Июн–Авг)', 'Осень (Сен–Ноя)']
    seasons_death = [0, 0, 0, 0]
    seasons_culling = [0, 0, 0, 0]

    total_dim = 0
    cows_with_dim = 0
    total_lact = 0
    cows_with_lact = 0
    fresh_disposals = 0
    fresh_deaths = 0
    cows_with_milk = 0
    total_milk_sum = 0.0
    high_yield_lost_count = 0
    high_yield_death_count = 0

    calf_cnt = calf_deaths = 0
    young_cnt = young_deaths = 0
    heifer_cnt = heifer_deaths = 0
    bull_cnt = bull_deaths = 0
    first_lact_cnt = first_lact_deaths = 0
    multi_cnt = multi_deaths = 0
    dry_cnt = dry_deaths = 0

    pathology_dim_matrix = {}
    pathology_systems = {}
    reason_counts = {}
    farm_data = {}
    farm_period_totals = {}
    farm_preg_stats = {}

    pregnant_cows = []
    adult_cows_total = 0
    pregnant_loss_byn_sum = 0.0
    gest_sum = 0
    gest_cnt = 0
    preg_death = 0
    preg_culling = 0
    preg_sanitary = 0
    preg_reasons = {}
    t1_count = t2_count = t3_count = t4_count = 0

    _non_adult_for_preg = frozenset({'Телята (до 6 мес.)', 'Ремонтный молодняк (6–18 мес.)', 'Бычки на откорме', 'Мертворождённые / Аборты'})

    # Единый проход по всем строкам периода
    for c in period_cows:
        f_name = c['farm_name'] or 'Не указана'
        farm_period_totals[f_name] = farm_period_totals.get(f_name, 0) + 1

        raw_lact = c['lactation']
        if raw_lact is not None and raw_lact != '':
            try:
                lact = int(raw_lact)
            except (ValueError, TypeError):
                lact = 0
        else:
            lact = 0

        raw_ag = c['age_group']
        norm_grp = normalize_age_group(raw_ag, lact if lact > 0 else None)
        cat = c['category']
        reason = c['reason'] or 'Не указана'
        reason_lower = reason.lower()
        val = estimate_val(c['book_value'], norm_grp)

        # Стельность
        if norm_grp not in _non_adult_for_preg:
            adult_cows_total += 1
        g_days = c['gestation_days'] or 0
        if c['is_pregnant'] == 1 or g_days > 0 or 'стельн' in reason_lower:
            pregnant_cows.append(c)
            pregnant_loss_byn_sum += val
            if g_days > 0:
                gest_sum += g_days
                gest_cnt += 1
            cat_l = (cat or '').lower()
            if cat_l == 'падёж':
                preg_death += 1
            elif cat_l == 'выбраковка':
                preg_culling += 1
            elif 'сан' in cat_l:
                preg_sanitary += 1
            preg_reasons[reason] = preg_reasons.get(reason, 0) + 1

            fp = farm_preg_stats.get(f_name)
            if fp is None:
                fp = {'count': 0, 'death': 0, 'cull': 0, 'loss': 0.0}
                farm_preg_stats[f_name] = fp
            fp['count'] += 1
            fp['loss'] += val
            if cat_l == 'падёж':
                fp['death'] += 1
            else:
                fp['cull'] += 1

            ag_l = (raw_ag or '').lower()
            if g_days > 240 or ('сухосто' in ag_l and g_days > 210):
                t4_count += 1
            elif g_days > 180 or 'сухосто' in ag_l:
                t3_count += 1
            elif g_days > 90:
                t2_count += 1
            else:
                t1_count += 1

        # Исключаем мертворождения из основного выбытия стада
        if c['is_stillborn'] or cat == 'мертворождение' or norm_grp == 'Мертворождённые / Аборты':
            continue

        total_disposals += 1
        is_death = (cat == 'падёж')
        category_counts[cat] = category_counts.get(cat, 0) + 1
        total_loss_byn += val

        raw_dim = c['lactation_days']
        dim_known = raw_dim is not None and raw_dim != ''
        if dim_known:
            try:
                dim = int(raw_dim)
            except (ValueError, TypeError):
                dim_known = False
                dim = 0
        else:
            dim = 0

        is_cow_group = norm_grp not in NON_COW_AGE_GROUPS
        is_dry_cow = (norm_grp == 'Сухостойные коровы' or 'сухосто' in (c['lactation_phase'] or '').lower())
        is_adult_lactating = (is_cow_group and not is_dry_cow)

        raw_w = c['weight']
        w = float(raw_w) if raw_w else 0.0
        w_eff = w if w > 0 else (520.0 if ('Коровы' in norm_grp or 'Нетели' in norm_grp or 'Сухостой' in norm_grp) else (320.0 if ('молодняк' in norm_grp.lower() or 'быч' in norm_grp.lower()) else 45.0))

        raw_milk = c['milk_yield']
        if is_adult_lactating and lact > 0 and dim_known and 0 <= dim < 305:
            rem_days = 305 - dim
            daily_milk = (float(raw_milk) / 305.0) if raw_milk else 22.0
            if daily_milk <= 0:
                daily_milk = 22.0
            lost_milk_kg = rem_days * daily_milk
            unrealized_milk_kg_total += lost_milk_kg
            unrealized_milk_loss_byn += lost_milk_kg * milk_price_per_kg

        if is_adult_lactating and lact == 1 and dim_known and 0 <= dim < 305:
            unrecovered_heifer_loss_byn += max(0.0, replacement_cost * (1.0 - (dim / 305.0)))

        if is_death:
            death_loss_byn += val
        elif cat == 'выбраковка':
            culling_loss_byn += val
            culled_live_weight_total += w_eff
            estimated_meat_revenue_byn += w_eff * meat_price_per_kg
        elif cat == 'санитарный':
            culling_loss_byn += val
            culled_live_weight_total += w_eff
            estimated_meat_revenue_byn += w_eff * (meat_price_per_kg * 0.70)

        # ПВГ статистика
        ag_bucket = age_group_data.get(norm_grp)
        if ag_bucket is None:
            ag_bucket = {
                'total': 0, 'падёж': 0, 'выбраковка': 0, 'санитарный': 0,
                'loss': 0.0, 'death_loss': 0.0, 'culling_loss': 0.0,
                'dim_sum': 0, 'dim_cnt': 0, 'weight_sum': 0.0, 'weight_cnt': 0,
                'reasons': {}, 'culling_reasons': {}, 'death_reasons': {}, 'sanitary_reasons': {}
            }
            age_group_data[norm_grp] = ag_bucket
        ag_bucket['total'] += 1
        ag_bucket[cat] = ag_bucket.get(cat, 0) + 1
        ag_bucket['loss'] += val
        if is_death:
            ag_bucket['death_loss'] += val
            ag_bucket['death_reasons'][reason] = ag_bucket['death_reasons'].get(reason, 0) + 1
        else:
            ag_bucket['culling_loss'] += val
            if cat == 'выбраковка':
                ag_bucket['culling_reasons'][reason] = ag_bucket['culling_reasons'].get(reason, 0) + 1
            elif cat == 'санитарный':
                ag_bucket['sanitary_reasons'][reason] = ag_bucket['sanitary_reasons'].get(reason, 0) + 1
        if dim_known and dim > 0:
            ag_bucket['dim_sum'] += dim
            ag_bucket['dim_cnt'] += 1
        if w > 0:
            ag_bucket['weight_sum'] += w
            ag_bucket['weight_cnt'] += 1
        ag_bucket['reasons'][reason] = ag_bucket['reasons'].get(reason, 0) + 1

        # Физиологические счётчики
        if norm_grp == 'Телята (до 6 мес.)':
            calf_cnt += 1
            if is_death: calf_deaths += 1
        elif norm_grp == 'Ремонтный молодняк (6–18 мес.)':
            young_cnt += 1
            if is_death: young_deaths += 1
        elif norm_grp == 'Нетели (>18 мес.)':
            heifer_cnt += 1
            if is_death: heifer_deaths += 1
        elif norm_grp == 'Бычки на откорме':
            bull_cnt += 1
            if is_death: bull_deaths += 1
        elif norm_grp == 'Коровы 1-й лактации (первотёлки)':
            first_lact_cnt += 1
            if is_death: first_lact_deaths += 1
        elif norm_grp == 'Полновозрастные коровы (2+ лакт.)':
            multi_cnt += 1
            if is_death: multi_deaths += 1
        elif norm_grp == 'Сухостойные коровы':
            dry_cnt += 1
            if is_death: dry_deaths += 1

        # Патологии и топ причин
        sys_name = classify_pathology_system(reason)
        pathology_systems[sys_name] = pathology_systems.get(sys_name, 0) + 1
        rc_key = (reason, cat)
        reason_counts[rc_key] = reason_counts.get(rc_key, 0) + 1

        # Лактация (DIM), удой и матрица Патология x DIM
        if is_cow_group:
            if is_dry_cow:
                if is_death: lact_phase_death[5] += 1
                else: lact_phase_culling[5] += 1
                pm = pathology_dim_matrix.get(sys_name)
                if pm is None:
                    pm = {'total': 0, 'Новотел (0-30 дн)': 0, 'Раздой (31-100 дн)': 0, 'Середина (101-200 дн)': 0, 'Спад и сухостой (>200)': 0}
                    pathology_dim_matrix[sys_name] = pm
                pm['total'] += 1
                pm['Спад и сухостой (>200)'] += 1
            elif dim_known and dim >= 0:
                total_dim += dim
                cows_with_dim += 1
                if dim <= 30:
                    fresh_disposals += 1
                    if is_death:
                        fresh_deaths += 1

                if dim <= 15: b_idx = 0
                elif dim <= 30: b_idx = 1
                elif dim <= 60: b_idx = 2
                elif dim <= 100: b_idx = 3
                elif dim <= 150: b_idx = 4
                elif dim <= 200: b_idx = 5
                elif dim <= 305: b_idx = 6
                else: b_idx = 7

                if is_death: dim_curve_death[b_idx] += 1
                else: dim_curve_culling[b_idx] += 1

                if dim <= 15: p_idx = 0
                elif dim <= 30: p_idx = 1
                elif dim <= 100: p_idx = 2
                elif dim <= 200: p_idx = 3
                else: p_idx = 4

                if is_death: lact_phase_death[p_idx] += 1
                else: lact_phase_culling[p_idx] += 1

                p_phase_name = 'Новотел (0-30 дн)' if dim <= 30 else ('Раздой (31-100 дн)' if dim <= 100 else ('Середина (101-200 дн)' if dim <= 200 else 'Спад и сухостой (>200)'))
                pm = pathology_dim_matrix.get(sys_name)
                if pm is None:
                    pm = {'total': 0, 'Новотел (0-30 дн)': 0, 'Раздой (31-100 дн)': 0, 'Середина (101-200 дн)': 0, 'Спад и сухостой (>200)': 0}
                    pathology_dim_matrix[sys_name] = pm
                pm['total'] += 1
                pm[p_phase_name] += 1

            if lact > 0:
                total_lact += lact
                cows_with_lact += 1
                l_idx = min(lact - 1, 4)
                if is_death: lact_num_death[l_idx] += 1
                else: lact_num_culling[l_idx] += 1

            m = float(raw_milk) if raw_milk else 0.0
            if m > 0:
                cows_with_milk += 1
                total_milk_sum += m
                if m < 4500: m_idx = 0
                elif m <= 6500: m_idx = 1
                elif m <= 8500: m_idx = 2
                else: m_idx = 3
                if m >= 6500:
                    high_yield_lost_count += 1
                    if is_death:
                        high_yield_death_count += 1
            else:
                m_idx = 4
            if is_death: milk_cohort_death[m_idx] += 1
            else: milk_cohort_culling[m_idx] += 1

        # Сезонность
        d_str = c['disposal_date']
        if d_str and len(d_str) >= 7:
            try:
                m_num = int(d_str[5:7])
                s_idx = 0 if m_num in (12, 1, 2) else (1 if m_num in (3, 4, 5) else (2 if m_num in (6, 7, 8) else 3))
                if is_death: seasons_death[s_idx] += 1
                else: seasons_culling[s_idx] += 1
            except Exception:
                pass

        # Агрегация по фермам
        fd = farm_data.get(f_name)
        if fd is None:
            fd = {
                'total': 0, 'death': 0, 'culling': 0, 'sanitary': 0,
                'calves': 0, 'young': 0, 'heifers': 0, 'fresh': 0,
                'dim_sum': 0, 'dim_cnt': 0, 'loss': 0.0,
                'systems': {}, 'reasons': {}
            }
            farm_data[f_name] = fd
        fd['total'] += 1
        fd['loss'] += val
        if is_death: fd['death'] += 1
        elif cat == 'выбраковка': fd['culling'] += 1
        else: fd['sanitary'] += 1

        if norm_grp == 'Телята (до 6 мес.)': fd['calves'] += 1
        elif norm_grp == 'Ремонтный молодняк (6–18 мес.)': fd['young'] += 1
        elif norm_grp == 'Нетели (>18 мес.)': fd['heifers'] += 1

        if dim_known and dim >= 0 and is_adult_lactating:
            fd['dim_sum'] += dim
            fd['dim_cnt'] += 1
            if dim <= 30:
                fd['fresh'] += 1

        fd['systems'][sys_name] = fd['systems'].get(sys_name, 0) + 1
        fd['reasons'][reason] = fd['reasons'].get(reason, 0) + 1

    # Итоговые финансовые показатели
    avg_head_loss = round(total_loss_byn / max(total_disposals, 1))
    estimated_meat_revenue_byn = round(estimated_meat_revenue_byn)
    unrealized_milk_loss_byn = round(unrealized_milk_loss_byn)
    unrecovered_heifer_loss_byn = round(unrecovered_heifer_loss_byn)
    net_economic_loss_byn = round(death_loss_byn + max(0.0, culling_loss_byn - estimated_meat_revenue_byn) + unrealized_milk_loss_byn + unrecovered_heifer_loss_byn)

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
        reasons_list = [{'reason': k, 'count': v, 'pct': round((v / tot) * 100, 1)} for k, v in sorted_reasons[:6]]

        culling_cnt = d_grp['выбраковка']
        culling_reasons_list = [{'reason': k, 'count': v, 'pct': round((v / max(culling_cnt, 1)) * 100, 1)} for k, v in sorted(d_grp['culling_reasons'].items(), key=lambda x: x[1], reverse=True)[:5]]

        death_cnt = d_grp['падёж']
        death_reasons_list = [{'reason': k, 'count': v, 'pct': round((v / max(death_cnt, 1)) * 100, 1)} for k, v in sorted(d_grp['death_reasons'].items(), key=lambda x: x[1], reverse=True)[:5]]

        sanitary_cnt = d_grp['санитарный']
        sanitary_reasons_list = [{'reason': k, 'count': v, 'pct': round((v / max(sanitary_cnt, 1)) * 100, 1)} for k, v in sorted(d_grp['sanitary_reasons'].items(), key=lambda x: x[1], reverse=True)[:5]]

        category_analytics.append({
            'category_name': g,
            'total': tot,
            'death': death_cnt,
            'culling': culling_cnt,
            'sanitary': sanitary_cnt,
            'death_rate_pct': round((death_cnt / tot) * 100, 1),
            'culling_pct': round((culling_cnt / tot) * 100, 1),
            'sanitary_pct': round((sanitary_cnt / tot) * 100, 1),
            'avg_dim': round(d_grp['dim_sum'] / d_grp['dim_cnt']) if d_grp['dim_cnt'] > 0 else 0,
            'avg_weight': round(d_grp['weight_sum'] / d_grp['weight_cnt']) if d_grp['weight_cnt'] > 0 else 0,
            'loss_byn': round(d_grp['loss']),
            'top_reasons': top_r_str,
            'reasons_list': reasons_list,
            'culling_reasons': culling_reasons_list,
            'death_reasons': death_reasons_list,
            'sanitary_reasons': sanitary_reasons_list
        })

    avg_dim = round(total_dim / cows_with_dim) if cows_with_dim > 0 else 0
    avg_lact = round(total_lact / cows_with_lact, 1) if cows_with_lact > 0 else 0
    avg_milk_yield = round(total_milk_sum / cows_with_milk) if cows_with_milk > 0 else 0

    total_adult_disposals = sum(lact_num_death) + sum(lact_num_culling)
    unrecovered_cows_count = lact_num_death[0] + lact_num_culling[0]
    unrecovered_pct = round((unrecovered_cows_count / total_adult_disposals) * 100, 1) if total_adult_disposals > 0 else 0.0

    pathology_dim_list = [
        {
            'system': s_name,
            'total': counts['total'],
            'fresh_0_30': counts['Новотел (0-30 дн)'],
            'peak_31_100': counts['Раздой (31-100 дн)'],
            'mid_101_200': counts['Середина (101-200 дн)'],
            'late_200_plus': counts['Спад и сухостой (>200)']
        }
        for s_name, counts in sorted(pathology_dim_matrix.items(), key=lambda x: x[1]['total'], reverse=True)[:7]
    ]

    calf_mortality_pct = round((calf_deaths / max(calf_cnt, 1)) * 100, 1) if calf_cnt else 0.0
    youngstock_pct = round((young_deaths / max(young_cnt, 1)) * 100, 1) if young_cnt else 0.0

    sorted_pathology = sorted(pathology_systems.items(), key=lambda x: x[1], reverse=True)
    top_reasons_list = [
        {'reason': k[0], 'category': k[1], 'count': v}
        for k, v in sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)[:8]
    ]

    # Динамические зоотехнические нормативы и пороги тревог (из кэша настроек)
    norm_fresh = _setting_float('norm_fresh_cow_disposal', 10.0)
    warn_fresh = _setting_float('warn_fresh_cow_disposal', 14.0)
    crit_fresh = _setting_float('crit_fresh_cow_disposal', 18.0)

    norm_first_lact = _setting_float('norm_first_lactation_culling', 20.0)
    warn_first_lact = _setting_float('warn_first_lactation_culling', 25.0)
    crit_first_lact = _setting_float('crit_first_lactation_culling', 30.0)

    norm_mortality = _setting_float('norm_mortality_rate', 25.0)
    warn_mortality = _setting_float('warn_mortality_rate', 35.0)
    crit_mortality = _setting_float('crit_mortality_rate', 45.0)

    norm_locomotor = _setting_float('norm_locomotor_disorders', 15.0)
    warn_locomotor = _setting_float('warn_locomotor_disorders', 20.0)
    crit_locomotor = _setting_float('crit_locomotor_disorders', 25.0)

    norm_mastitis = _setting_float('norm_mastitis_disorders', 15.0)
    warn_mastitis = _setting_float('warn_mastitis_disorders', 20.0)
    crit_mastitis = _setting_float('crit_mastitis_disorders', 25.0)

    sorted_farms_rows = sorted(farm_data.items(), key=lambda x: x[1]['total'], reverse=True)
    sorted_farms = [(f, d['total']) for f, d in sorted_farms_rows]
    farm_matrix = []
    farm_pathology_matrix = []
    key_problem_systems = [
        'Органы пищеварения',
        'Акушерство и гинекология',
        'Болезни вымени (маститы)',
        'Конечности и травматизм',
        'Органы дыхания',
        'Болезни молодняка (диспепсия)',
        'Нарушения обмена веществ'
    ]
    for f, d in sorted_farms_rows:
        tot_f = max(d['total'], 1)
        d_pct = round((d['death'] / tot_f) * 100, 1)
        fresh_pct_f = round((d['fresh'] / tot_f) * 100, 1)
        stat = 'optimal'
        stat_lbl = 'Норма'
        if d_pct >= crit_mortality or (d['total'] > 10 and fresh_pct_f >= crit_fresh):
            stat = 'critical'
            stat_lbl = 'Критический риск'
        elif d_pct >= warn_mortality or (d['total'] > 10 and fresh_pct_f >= warn_fresh):
            stat = 'warning'
            stat_lbl = 'Внимание'

        top_sys_item = max(d['systems'].items(), key=lambda x: x[1]) if d['systems'] else ('Нет данных', 0)
        top_rea_item = max(d['reasons'].items(), key=lambda x: x[1]) if d['reasons'] else ('Нет данных', 0)

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
            'avg_dim': round(d['dim_sum'] / d['dim_cnt']) if d['dim_cnt'] > 0 else 0,
            'total_loss_byn': round(d['loss']),
            'top_system': top_sys_item[0],
            'top_system_pct': round((top_sys_item[1] / tot_f) * 100, 1),
            'top_reason': top_rea_item[0],
            'top_reason_count': top_rea_item[1],
            'status': stat,
            'status_label': stat_lbl
        })

        sys_cells = [
            {'system': s_key, 'count': d['systems'].get(s_key, 0), 'pct': round((d['systems'].get(s_key, 0) / tot_f) * 100, 1)}
            for s_key in key_problem_systems
        ]
        other_cnt = d['systems'].get('Сердечно-сосудистая система', 0) + d['systems'].get('Прочие заболевания', 0)
        farm_pathology_matrix.append({
            'farm': f,
            'total': d['total'],
            'death_pct': d_pct,
            'top_system': top_sys_item[0],
            'top_system_pct': round((top_sys_item[1] / tot_f) * 100, 1),
            'top_reason': top_rea_item[0],
            'top_reason_count': top_rea_item[1],
            'cells': sys_cells,
            'other_count': other_cnt,
            'other_pct': round((other_cnt / tot_f) * 100, 1)
        })

    death_overall_rate = round((category_counts.get('падёж', 0) / max(total_disposals, 1)) * 100, 1)
    fresh_rate = round((fresh_disposals / max(total_disposals, 1)) * 100, 1)
    first_lact_rate = round((lact_num_culling[0] / max(sum(lact_num_culling), 1)) * 100, 1) if sum(lact_num_culling) > 0 else 0.0
    locomotor_rate = round((pathology_systems.get('Конечности и травматизм', 0) / max(total_disposals, 1)) * 100, 1)
    mastitis_rate = round((pathology_systems.get('Болезни вымени (маститы)', 0) / max(total_disposals, 1)) * 100, 1)

    prog_fresh = max(5, min(100, round((fresh_rate / max(norm_fresh, 0.1)) * 100)))
    prog_first_lact = max(5, min(100, round((first_lact_rate / max(norm_first_lact, 0.1)) * 100)))
    prog_mortality = max(5, min(100, round((death_overall_rate / max(norm_mortality, 0.1)) * 100)))
    prog_locomotor = max(5, min(100, round((locomotor_rate / max(norm_locomotor, 0.1)) * 100)))
    prog_mastitis = max(5, min(100, round((mastitis_rate / max(norm_mastitis, 0.1)) * 100)))

    scorecard = [
        {
            'key': 'norm_fresh_cow_disposal', 'operator': '<=',
            'val': float(norm_fresh), 'warn_val': float(warn_fresh), 'crit_val': float(crit_fresh),
            'current_num': float(fresh_rate),
            'title': 'Выбытие новотельных (0-30 DIM)', 'target': f"≤ {norm_fresh:.1f}%", 'current': f"{fresh_rate}%",
            'progress_pct': prog_fresh,
            'status': 'success' if fresh_rate <= norm_fresh else ('warning' if fresh_rate <= crit_fresh else 'danger'),
            'statusText': 'Норма' if fresh_rate <= norm_fresh else ('Внимание' if fresh_rate <= crit_fresh else 'Риск'),
            'note': f"Новотел: {fresh_disposals} гол. ({fresh_deaths} пало)",
            'icon': 'bi-exclamation-octagon-fill'
        },
        {
            'key': 'norm_first_lactation_culling', 'operator': '<=',
            'val': float(norm_first_lact), 'warn_val': float(warn_first_lact), 'crit_val': float(crit_first_lact),
            'current_num': float(first_lact_rate),
            'title': 'Выбраковка первотёлок', 'target': f"≤ {norm_first_lact:.1f}%", 'current': f"{first_lact_rate}%",
            'progress_pct': prog_first_lact,
            'status': 'success' if first_lact_rate <= norm_first_lact else ('warning' if first_lact_rate <= crit_first_lact else 'danger'),
            'statusText': 'Норма' if first_lact_rate <= norm_first_lact else 'Высокая',
            'note': 'Доля 1-й лактации в выбраковке',
            'icon': 'bi-gem'
        },
        {
            'key': 'norm_mortality_rate', 'operator': '<=',
            'val': float(norm_mortality), 'warn_val': float(warn_mortality), 'crit_val': float(crit_mortality),
            'current_num': float(death_overall_rate),
            'title': 'Общая летальность (Падёж)', 'target': f"≤ {norm_mortality:.1f}%", 'current': f"{death_overall_rate}%",
            'progress_pct': prog_mortality,
            'status': 'success' if death_overall_rate <= norm_mortality else ('warning' if death_overall_rate <= crit_mortality else 'danger'),
            'statusText': 'Норма' if death_overall_rate <= norm_mortality else ('Повышен' if death_overall_rate <= crit_mortality else 'Критич.'),
            'note': f"Пало {category_counts.get('падёж', 0)} из {total_disposals} гол.",
            'icon': 'bi-heart-pulse-fill'
        },
        {
            'key': 'norm_locomotor_disorders', 'operator': '<=',
            'val': float(norm_locomotor), 'warn_val': float(warn_locomotor), 'crit_val': float(crit_locomotor),
            'current_num': float(locomotor_rate),
            'title': 'Болезни конечностей', 'target': f"≤ {norm_locomotor:.1f}%", 'current': f"{locomotor_rate}%",
            'progress_pct': prog_locomotor,
            'status': 'success' if locomotor_rate <= norm_locomotor else ('warning' if locomotor_rate <= crit_locomotor else 'danger'),
            'statusText': 'В норме' if locomotor_rate <= norm_locomotor else ('Контроль' if locomotor_rate <= crit_locomotor else 'Риск'),
            'note': 'Ортопедическая патология',
            'icon': 'bi-bandaid-fill'
        },
        {
            'key': 'norm_mastitis_disorders', 'operator': '<=',
            'val': float(norm_mastitis), 'warn_val': float(warn_mastitis), 'crit_val': float(crit_mastitis),
            'current_num': float(mastitis_rate),
            'title': 'Маститы и патологии вымени', 'target': f"≤ {norm_mastitis:.1f}%", 'current': f"{mastitis_rate}%",
            'progress_pct': prog_mastitis,
            'status': 'success' if mastitis_rate <= norm_mastitis else ('warning' if mastitis_rate <= crit_mastitis else 'danger'),
            'statusText': 'В норме' if mastitis_rate <= norm_mastitis else ('Контроль' if mastitis_rate <= crit_mastitis else 'Риск'),
            'note': 'Инфекции молочной железы',
            'icon': 'bi-droplet-fill'
        }
    ]

    # 9. Динамика по месяцам за последние 12 месяцев
    twelve_months_ago = (now - timedelta(days=365)).strftime('%Y-%m-%d')
    m_where_parts = ["disposal_date >= ?"]
    m_params = [twelve_months_ago]
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

    months_keys = sorted(monthly_data.keys())
    trend_datasets = []
    category_colors = {'падёж': '#DC2626', 'выбраковка': '#2563EB', 'санитарный': '#D97706'}
    for cat_name in ('падёж', 'выбраковка', 'санитарный'):
        data_pts = [monthly_data.get(m, {}).get(cat_name, 0) for m in months_keys]
        col = category_colors[cat_name]
        trend_datasets.append({
            'label': cat_name.capitalize(),
            'data': data_pts,
            'borderColor': col,
            'backgroundColor': col + '20',
            'fill': True,
            'tension': 0.25
        })

    calf_disposals_count = calf_cnt
    calf_death_count = calf_deaths

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

    cursor.execute('''
        SELECT DISTINCT farm_name FROM (
            SELECT farm_name FROM users WHERE farm_name IS NOT NULL AND farm_name != ''
            UNION
            SELECT farm_name FROM cows WHERE farm_name IS NOT NULL AND farm_name != ''
        ) ORDER BY farm_name
    ''')
    all_farms_list = [r['farm_name'] for r in cursor.fetchall()]

    if len(period_cows) > 0:
        recent_cows = [dict(r) for r in period_cows[:10]]
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

    # Извлечение мертворождений из stillbirth_records
    sb_where = ["event_date BETWEEN ? AND ?"]
    sb_params = [start_date, end_date]
    if user_type == 'farm' and farm_name:
        sb_where.append("farm_name = ?")
        sb_params.append(farm_name)
    elif user_type == 'admin' and farm_name and farm_name != 'all':
        sb_where.append("farm_name = ?")
        sb_params.append(farm_name)

    cursor.execute(f"""
        SELECT farm_name, event_type, fetus_sex, mother_group, cause, fetus_weight, gestation_days
        FROM stillbirth_records WHERE {' AND '.join(sb_where)}
    """, sb_params)
    period_stillborn_rows = cursor.fetchall()
    conn.close()

    sb_sex_counts = {'Бычки': 0, 'Тёлочки': 0, 'Двойня': 0, 'Не определён': 0}
    sb_mother_groups = {}
    sb_causes = {}
    sb_by_farm = {}
    total_fetus_weight = 0.0
    total_gest_days = 0
    sb_weight_cnt = 0
    sb_days_cnt = 0
    term_stillborn_cnt = 0
    abortion_cnt = 0

    for r in period_stillborn_rows:
        f_sb = r['farm_name'] or 'Не указана'
        sb_by_farm[f_sb] = sb_by_farm.get(f_sb, 0) + 1

        ev_t = r['event_type'] or ''
        if 'Мертворожд' in ev_t:
            term_stillborn_cnt += 1
        if 'Аборт' in ev_t:
            abortion_cnt += 1

        sx = (r['fetus_sex'] or 'Не определён').lower()
        if 'быч' in sx: sb_sex_counts['Бычки'] += 1
        elif 'тёл' in sx or 'тел' in sx: sb_sex_counts['Тёлочки'] += 1
        elif 'двойн' in sx: sb_sex_counts['Двойня'] += 1
        else: sb_sex_counts['Не определён'] += 1

        mg = r['mother_group'] or 'Полновозрастные'
        sb_mother_groups[mg] = sb_mother_groups.get(mg, 0) + 1

        cs = r['cause'] or 'Патология плода'
        sb_causes[cs] = sb_causes.get(cs, 0) + 1

        fw = float(r['fetus_weight'] or 0.0)
        if fw > 0:
            total_fetus_weight += fw
            sb_weight_cnt += 1

        gd = int(r['gestation_days'] or 0)
        if gd > 0:
            total_gest_days += gd
            sb_days_cnt += 1

    avg_fetus_weight = round(total_fetus_weight / sb_weight_cnt, 1) if sb_weight_cnt > 0 else 0.0
    avg_gest_days = round(total_gest_days / sb_days_cnt) if sb_days_cnt > 0 else 0

    sb_causes_sorted = sorted(sb_causes.items(), key=lambda x: x[1], reverse=True)
    sb_causes_labels = [x[0] for x in sb_causes_sorted[:6]]
    sb_causes_data = [x[1] for x in sb_causes_sorted[:6]]

    sb_mg_sorted = sorted(sb_mother_groups.items(), key=lambda x: x[1], reverse=True)
    sb_mg_labels = [x[0] for x in sb_mg_sorted]
    sb_mg_data = [x[1] for x in sb_mg_sorted]

    stillborn_count = len(period_stillborn_rows)
    stillborn_reasons_list = [{'reason': k, 'count': v} for k, v in sb_causes_sorted]

    pregnant_count = len(pregnant_cows)
    pregnant_pct = round((pregnant_count / adult_cows_total) * 100, 1) if adult_cows_total > 0 else 0.0
    pregnant_loss_byn = round(pregnant_loss_byn_sum)
    avg_gestation_months = round(gest_sum / gest_cnt / 30.0, 1) if gest_cnt > 0 else 0.0
    stillborn_pct = round((stillborn_count / max(total_disposals + stillborn_count, 1)) * 100, 1)

    reproduction_by_farm = []
    for f_name, _ in sorted_farms:
        f_tot = farm_period_totals.get(f_name, 0)
        fp = farm_preg_stats.get(f_name, {'count': 0, 'death': 0, 'cull': 0, 'loss': 0.0})
        f_stillborn = sb_by_farm.get(f_name, 0)
        reproduction_by_farm.append({
            'farm_name': f_name,
            'total': f_tot,
            'pregnant_count': fp['count'],
            'pregnant_pct': round((fp['count'] / max(f_tot, 1)) * 100, 1),
            'pregnant_death': fp['death'],
            'pregnant_culling': fp['cull'],
            'pregnant_loss_byn': round(fp['loss']),
            'stillborn_count': f_stillborn,
            'stillborn_pct': round((f_stillborn / max(f_tot + f_stillborn, 1)) * 100, 1)
        })
        
    # Сроки стельности выбывших коров (t1..t4 уже рассчитаны за 1 проход)
    structure_labels = [
        '1–90 дн (1-й триместр)',
        '91–180 дн (2-й триместр)',
        '181–240 дн (3-й триместр)',
        '241+ дн (сухостой перед отёлом)'
    ]
    structure_data = [t1_count, t2_count, t3_count, t4_count]
    structure_colors = ['#3B82F6', '#F59E0B', '#F97316', '#EF4444']

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
            'calf_disposals': calf_cnt,
            'calf_death_count': calf_deaths,
            'calf_death_pct': calf_mortality_pct,
            'youngstock_disposals': young_cnt,
            'youngstock_death_count': young_deaths,
            'youngstock_death_pct': youngstock_pct,
            'heifer_disposals': heifer_cnt,
            'heifer_death_count': heifer_deaths,
            'bull_disposals': bull_cnt,
            'bull_death_count': bull_deaths,
            'first_lact_disposals': first_lact_cnt,
            'first_lact_death_count': first_lact_deaths,
            'multiparous_disposals': multi_cnt,
            'multiparous_death_count': multi_deaths,
            'dry_disposals': dry_cnt,
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
        'farm_pathology_matrix': farm_pathology_matrix,
        'farm_pathology_headers': key_problem_systems,
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
                'death_data': [round(age_group_data[g]['death_loss']) for g in age_labels],
                'culling_data': [round(age_group_data[g]['culling_loss']) for g in age_labels]
            },
            'pathology': {
                'labels': [x[0] for x in sorted_pathology],
                'data': [x[1] for x in sorted_pathology],
                'colors': '#6366F1'
            },
            'farms': {
                'labels': [x[0] for x in sorted_farms],
                'data': [x[1] for x in sorted_farms],
                'death_data': [d['death'] for _, d in sorted_farms_rows],
                'culling_data': [d['culling'] for _, d in sorted_farms_rows],
                'sanitary_data': [d['sanitary'] for _, d in sorted_farms_rows],
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
