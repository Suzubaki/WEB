# add_test_cows.py - Генератор реалистичных тестовых данных для проверки аналитики и графиков
import os
import random
import sqlite3
from datetime import datetime, timedelta


def _compute_phase(age_group, lactation_days):
    grp = (age_group or '').lower()
    if 'телят' in grp:
        return 'Молодняк (до 6 мес.)'
    if 'быч' in grp or 'откорм' in grp:
        return 'Бычки на откорме'
    if 'молодняк' in grp or 'ремонтн' in grp:
        return 'Молодняк (6–18 мес.)'
    if 'нетел' in grp:
        return 'Нетели'
    if 'сухосто' in grp:
        return 'Сухостой'
    if lactation_days is not None:
        if lactation_days <= 30:
            return 'Новотел (0–30 дн)'
        if lactation_days <= 100:
            return 'Раздой (31–100 дн)'
        if lactation_days <= 200:
            return 'Середина (101–200 дн)'
        return 'Спад (201–305+ дн)'
    return 'Фаза не указана'


def generate_test_cows(count=1000, stillborn_count=None, reset=False):
    from config import Config

    db_path = Config.DATABASE
    if not os.path.exists(db_path):
        from database import init_db
        init_db()

    if stillborn_count is None:
        stillborn_count = max(60, count // 10)

    conn = sqlite3.connect(db_path, timeout=15.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if reset:
        cursor.execute('DELETE FROM cows')
        cursor.execute('DELETE FROM stillbirth_records')
        cursor.execute('UPDATE farm_counters SET last_cow_number = 0, last_stillborn_number = 0')

    cursor.execute('SELECT id, farm_name FROM users WHERE farm_name IS NOT NULL AND farm_name != "" ORDER BY id')
    user_rows = cursor.fetchall()
    farm_users = {r['farm_name']: r['id'] for r in user_rows}
    farms = [r['farm_name'] for r in user_rows]

    if not farms:
        cursor.execute('SELECT DISTINCT farm_name FROM cows WHERE farm_name IS NOT NULL AND farm_name != ""')
        farms = [r['farm_name'] for r in cursor.fetchall()]
    if not farms:
        farms = ['Ферма 1', 'Ферма 2']

    # Получаем актуальные активные причины из БД, с откатом на Config.DISPOSAL_CATEGORIES
    reasons_by_cat = {}
    for cat in ('падёж', 'выбраковка', 'санитарный'):
        cursor.execute('SELECT name FROM disposal_reasons WHERE category = ? AND is_active = 1', (cat,))
        db_reasons = [r['name'] for r in cursor.fetchall()]
        reasons_by_cat[cat] = db_reasons if db_reasons else list(Config.DISPOSAL_CATEGORIES.get(cat, ['Другое']))

    # Существующие счетчики по фермам
    cow_counters = {}
    sb_counters = {}
    for f in farms:
        cursor.execute('SELECT last_cow_number, last_stillborn_number FROM farm_counters WHERE farm_name = ?', (f,))
        fc = cursor.fetchone()
        cursor.execute('SELECT COUNT(*) as cnt FROM cows WHERE farm_name = ?', (f,))
        c_cnt = cursor.fetchone()['cnt']
        cursor.execute('SELECT COUNT(*) as cnt FROM stillbirth_records WHERE farm_name = ?', (f,))
        s_cnt = cursor.fetchone()['cnt']
        cow_counters[f] = max(fc['last_cow_number'] if fc else 0, c_cnt)
        sb_counters[f] = max(fc['last_stillborn_number'] if fc else 0, s_cnt)

    today = datetime.now().date()
    rng = random.Random(42)

    # Распределение по времени: последние 7 дней, текущий месяц, прошлый месяц и 12 месяцев (строго <= today)
    def pick_date(idx, total):
        frac = idx / max(total, 1)
        if frac < 0.12:
            days_ago = rng.randint(0, 6)
        elif frac < 0.26:
            days_ago = rng.randint(7, 29)
        elif frac < 0.44:
            days_ago = rng.randint(30, 89)
        else:
            days_ago = rng.randint(90, 364)
        return (today - timedelta(days=days_ago)).strftime('%Y-%m-%d')

    # Профили диагнозов по ПВГ
    calf_death_reasons = [r for r in reasons_by_cat['падёж'] if any(k in r.lower() for k in ('диспепс', 'гипотроф', 'бронхопневм', 'тимпан', 'гастроэнтер', 'кровотеч'))] or reasons_by_cat['падёж']
    young_reasons_death = [r for r in reasons_by_cat['падёж'] if any(k in r.lower() for k in ('бронхопневм', 'тимпан', 'травм', 'перитон', 'интоксик', 'гастроэнтер'))] or reasons_by_cat['падёж']
    adult_death_reasons = [r for r in reasons_by_cat['падёж'] if not any(k in r.lower() for k in ('диспепс', 'гипотроф'))] or reasons_by_cat['падёж']

    # Шаблон распределения ПВГ
    age_group_weights = [
        ('Полновозрастные коровы (2+ лакт.)', 0.34),
        ('Коровы 1-й лактации (первотёлки)', 0.20),
        ('Новотельные коровы (0–30 дн DIM)', 0.13),
        ('Телята (до 6 мес.)', 0.11),
        ('Ремонтный молодняк (6–18 мес.)', 0.07),
        ('Сухостойные коровы', 0.07),
        ('Нетели (>18 мес.)', 0.05),
        ('Бычки на откорме', 0.03),
    ]
    ag_names = [x[0] for x in age_group_weights]
    ag_probs = [x[1] for x in age_group_weights]

    # Гарантированный стартовый профиль по всем 6 фазам DIM (0-15, 16-30, 31-100, 101-200, 201-305+, Сухостой)
    # для каждой фермы за последние 7 дней (падёж + выбраковка), чтобы графики фаз всегда были полностью заполнены
    dim_seed_templates = []
    for f_idx, f_name in enumerate(farms):
        phase_specs = [
            ('Новотельные коровы (0–30 дн DIM)', (1, 15), 'падёж'),
            ('Новотельные коровы (0–30 дн DIM)', (1, 15), 'выбраковка'),
            ('Новотельные коровы (0–30 дн DIM)', (16, 30), 'падёж'),
            ('Новотельные коровы (0–30 дн DIM)', (16, 30), 'выбраковка'),
            ('Коровы 1-й лактации (первотёлки)', (31, 100), 'падёж'),
            ('Коровы 1-й лактации (первотёлки)', (31, 100), 'выбраковка'),
            ('Полновозрастные коровы (2+ лакт.)', (101, 200), 'падёж'),
            ('Полновозрастные коровы (2+ лакт.)', (101, 200), 'выбраковка'),
            ('Полновозрастные коровы (2+ лакт.)', (201, 320), 'падёж'),
            ('Полновозрастные коровы (2+ лакт.)', (201, 320), 'выбраковка'),
            ('Сухостойные коровы', (295, 350), 'падёж'),
            ('Сухостойные коровы', (295, 350), 'выбраковка'),
        ]
        for s_idx, (s_ag, s_dim_rng, s_cat) in enumerate(phase_specs):
            dim_seed_templates.append((f_name, s_ag, s_dim_rng, s_cat, (s_idx + f_idx) % 6))

    cow_rows = []
    for i in range(count):
        forced_dim_rng = None
        if i < len(dim_seed_templates):
            farm, ag, forced_dim_rng, cat, d_ago = dim_seed_templates[i]
            disposal_d = (today - timedelta(days=d_ago)).strftime('%Y-%m-%d')
            cow_counters[farm] += 1
            cow_id = f"{farm}-{cow_counters[farm]:03d}"
            user_id = farm_users.get(farm, 1)
            reason = rng.choice(adult_death_reasons if cat == 'падёж' else reasons_by_cat[cat])
        else:
            # Небольшая асимметрия по фермам для наглядного сравнения в матрице
            farm = farms[0] if (len(farms) > 1 and i % 11 in (0, 2, 4, 6, 8, 10)) else farms[i % len(farms)]
            cow_counters[farm] += 1
            cow_id = f"{farm}-{cow_counters[farm]:03d}"
            user_id = farm_users.get(farm, 1)

            disposal_d = pick_date(i, count)
            days_from_today = (today - datetime.strptime(disposal_d, '%Y-%m-%d').date()).days

            # Сделаем компактный недавний кластер на первой ферме для проверки блока вет-алертов
            if farm == farms[0] and days_from_today <= 6 and i % 4 == 0:
                ag = 'Телята (до 6 мес.)' if (i % 8 == 0) else 'Новотельные коровы (0–30 дн DIM)'
                cat = 'падёж'
                reason = 'Диспепсия телят' if ag == 'Телята (до 6 мес.)' else 'Острая тимпания рубца'
            else:
                ag = rng.choices(ag_names, weights=ag_probs, k=1)[0]
                r_cat = rng.random()
                # Молодняк и телята чаще выбывают по падежу/санбраку, взрослые — чаще по выбраковке
                if ag == 'Телята (до 6 мес.)':
                    cat = 'падёж' if r_cat < 0.78 else ('санитарный' if r_cat < 0.92 else 'выбраковка')
                elif ag in ('Ремонтный молодняк (6–18 мес.)', 'Бычки на откорме'):
                    cat = 'падёж' if r_cat < 0.35 else ('санитарный' if r_cat < 0.60 else 'выбраковка')
                elif ag == 'Новотельные коровы (0–30 дн DIM)':
                    cat = 'падёж' if r_cat < 0.38 else ('выбраковка' if r_cat < 0.78 else 'санитарный')
                else:
                    # На Ферме 1 чуть выше доля маститов/метаболики, на Ферме 2 — ортопедии/падежа
                    death_cut = 0.24 if farm == farms[0] else 0.33
                    cull_cut = 0.82 if farm == farms[0] else 0.85
                    cat = 'падёж' if r_cat < death_cut else ('выбраковка' if r_cat < cull_cut else 'санитарный')

                if cat == 'падёж':
                    if ag == 'Телята (до 6 мес.)':
                        reason = rng.choice(calf_death_reasons)
                    elif ag in ('Ремонтный молодняк (6–18 мес.)', 'Бычки на откорме'):
                        reason = rng.choice(young_reasons_death)
                    else:
                        reason = rng.choice(adult_death_reasons)
                else:
                    pool = reasons_by_cat[cat]
                    if farm == farms[0] and cat == 'выбраковка' and rng.random() < 0.38:
                        mast = [r for r in pool if 'мастит' in r.lower() or 'вымен' in r.lower() or 'агалакти' in r.lower()]
                        reason = rng.choice(mast) if mast else rng.choice(pool)
                    elif farm != farms[0] and cat == 'выбраковка' and rng.random() < 0.35:
                        loco = [r for r in pool if 'копыт' in r.lower() or 'хромот' in r.lower() or 'сустав' in r.lower()]
                        reason = rng.choice(loco) if loco else rng.choice(pool)
                    else:
                        reason = rng.choice(pool)

        is_pregnant = 0
        gestation_days = 0

        if ag == 'Телята (до 6 мес.)':
            lact = 0
            dim = None
            weight = round(rng.uniform(34, 88), 1)
            milk_yield = None
            book_value = round(rng.uniform(420, 960), 2)
        elif ag == 'Ремонтный молодняк (6–18 мес.)':
            lact = 0
            dim = None
            weight = round(rng.uniform(195, 365), 1)
            milk_yield = None
            book_value = round(rng.uniform(1350, 1950), 2)
        elif ag == 'Бычки на откорме':
            lact = 0
            dim = None
            weight = round(rng.uniform(290, 520), 1)
            milk_yield = None
            book_value = round(rng.uniform(1450, 2350), 2)
        elif ag == 'Нетели (>18 мес.)':
            lact = 0
            dim = None
            weight = round(rng.uniform(405, 515), 1)
            milk_yield = None
            book_value = round(rng.uniform(2450, 3050), 2)
            if rng.random() < 0.65:
                is_pregnant = 1
                gestation_days = rng.randint(75, 258)
        elif ag == 'Новотельные коровы (0–30 дн DIM)':
            lact = rng.choices([1, 2, 3, 4], weights=[0.42, 0.28, 0.18, 0.12], k=1)[0]
            dim = rng.randint(1, 30)
            weight = round(rng.uniform(485, 650), 1)
            milk_yield = round(rng.uniform(4200, 9100), 0) if rng.random() < 0.90 else None
            book_value = round(rng.uniform(2700, 3450), 2)
        elif ag == 'Сухостойные коровы':
            lact = rng.randint(1, 5)
            dim = rng.randint(295, 355)
            weight = round(rng.uniform(560, 720), 1)
            milk_yield = round(rng.uniform(4900, 9000), 0)
            book_value = round(rng.uniform(2750, 3400), 2)
            if rng.random() < 0.85:
                is_pregnant = 1
                gestation_days = rng.randint(215, 276)
        elif ag == 'Коровы 1-й лактации (первотёлки)':
            lact = 1
            dim = rng.randint(31, 330)
            weight = round(rng.uniform(475, 610), 1)
            milk_yield = round(rng.uniform(3900, 8800), 0) if rng.random() < 0.92 else None
            book_value = round(rng.uniform(2600, 3350), 2)
            if dim > 80 and rng.random() < 0.28:
                is_pregnant = 1
                gestation_days = rng.randint(35, min(240, dim - 45))
        else:  # Полновозрастные коровы (2+ лакт.)
            lact = rng.choices([2, 3, 4, 5, 6], weights=[0.30, 0.28, 0.20, 0.14, 0.08], k=1)[0]
            dim = rng.randint(31, 360)
            weight = round(rng.uniform(520, 710), 1)
            # Разброс надоев по всем 4 когортам продуктивности (<4500, 4500-6500, 6500-8500, >8500)
            cohort_roll = rng.random()
            if cohort_roll < 0.18:
                milk_yield = round(rng.uniform(3200, 4450), 0)
            elif cohort_roll < 0.48:
                milk_yield = round(rng.uniform(4550, 6450), 0)
            elif cohort_roll < 0.78:
                milk_yield = round(rng.uniform(6550, 8450), 0)
            elif cohort_roll < 0.94:
                milk_yield = round(rng.uniform(8550, 10200), 0)
            else:
                milk_yield = None
            book_value = round(rng.uniform(2400, 3600), 2)
            if dim > 85 and rng.random() < 0.26:
                is_pregnant = 1
                gestation_days = rng.randint(35, min(245, dim - 50))

        if forced_dim_rng is not None:
            dim = rng.randint(forced_dim_rng[0], forced_dim_rng[1])

        lact_phase = _compute_phase(ag, dim)
        ear_tag = f"BY 04 {rng.randint(100000, 999999)}"
        breed = rng.choices(
            [Config.DEFAULT_BREED, 'Голштинская', 'Черно-пёстрая', 'Красная белорусская', 'Симментальская'],
            weights=[0.45, 0.25, 0.15, 0.08, 0.07],
            k=1
        )[0]
        notes = f"Тестовая запись ({cat}) — {ag}"

        cow_rows.append((
            cow_id, ear_tag, farm, cat, reason, disposal_d,
            lact, dim, lact_phase, weight, notes, ag, breed, milk_yield, book_value,
            is_pregnant, gestation_days, 0, user_id
        ))

    cursor.executemany('''
        INSERT INTO cows (
            cow_id, ear_tag, farm_name, category, reason, disposal_date,
            lactation, lactation_days, lactation_phase, weight, notes, age_group, breed, milk_yield, book_value,
            is_pregnant, gestation_days, is_stillborn, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', cow_rows)

    # Генерация записей мертворождений и абортов
    sb_rows = []
    for j in range(stillborn_count):
        farm = farms[j % len(farms)]
        sb_counters[farm] += 1
        rec_code = f"{farm}-М{sb_counters[farm]:03d}"
        user_id = farm_users.get(farm, 1)
        ev_date = pick_date(j, stillborn_count)
        ev_type = rng.choice(Config.STILLBIRTH_EVENT_TYPES)
        def_gest, def_w = Config.infer_stillborn_defaults(ev_type)
        gest_days = max(40, min(290, def_gest + rng.randint(-10, 10)))
        fetus_w = round(max(0.3, def_w + rng.uniform(-2.0, 3.0)), 1)
        fetus_sex = rng.choice(Config.FETUS_SEXES)
        mother_group = rng.choice(Config.MOTHER_GROUPS)
        cause = rng.choice(Config.STILLBIRTH_CAUSES)
        mother_cond = rng.choices(Config.MOTHER_CONDITIONS, weights=[0.55, 0.15, 0.12, 0.08, 0.06, 0.04], k=1)[0]
        mother_tag = f"BY 04 {rng.randint(100000, 999999)}"
        sb_rows.append((
            rec_code, farm, ev_date, mother_tag, mother_group,
            ev_type, fetus_sex, fetus_w, gest_days, cause,
            mother_cond, Config.DEFAULT_ATTENDANT, 'Тестовый акушерский акт', user_id
        ))

    cursor.executemany('''
        INSERT INTO stillbirth_records (
            record_code, farm_name, event_date, mother_tag, mother_group,
            event_type, fetus_sex, fetus_weight, gestation_days, cause,
            mother_condition, attendant, notes, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', sb_rows)

    for f in farms:
        if reset:
            cursor.execute('''
                INSERT INTO farm_counters (farm_name, last_cow_number, last_stillborn_number)
                VALUES (?, ?, ?)
                ON CONFLICT(farm_name) DO UPDATE SET
                    last_cow_number = excluded.last_cow_number,
                    last_stillborn_number = excluded.last_stillborn_number
            ''', (f, cow_counters[f], sb_counters[f]))
        else:
            cursor.execute('''
                INSERT INTO farm_counters (farm_name, last_cow_number, last_stillborn_number)
                VALUES (?, ?, ?)
                ON CONFLICT(farm_name) DO UPDATE SET
                    last_cow_number = MAX(last_cow_number, excluded.last_cow_number),
                    last_stillborn_number = MAX(last_stillborn_number, excluded.last_stillborn_number)
            ''', (f, cow_counters[f], sb_counters[f]))

    conn.commit()
    conn.close()
    print(f"Готово! Добавлено записей выбытия: {len(cow_rows)}, мертворождений/абортов: {len(sb_rows)}.")


if __name__ == '__main__':
    import sys
    generate_test_cows(1000, 100, reset=('--reset' in sys.argv))
