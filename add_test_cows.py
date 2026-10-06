# add_test_cows.py - Скрипт мгновенного наполнения базы данных 1 000 коровами
import sqlite3
import os
import random
import json
from datetime import datetime, timedelta

def generate_test_cows(count=1000):
    from config import Config
    db_path = Config.DATABASE
    
    if not os.path.exists(db_path):
        print(f"База данных не найдена по пути: {db_path}")
        print("Инициализация базы данных...")
        from database import init_db
        init_db()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Ищем существующие фермы в базе (например, МТК Цегельня, МТФ Хорск)
    cursor.execute('SELECT DISTINCT farm_name FROM users WHERE farm_name IS NOT NULL AND farm_name != ""')
    user_farms = [r['farm_name'] for r in cursor.fetchall()]
    cursor.execute('SELECT DISTINCT farm_name FROM cows WHERE farm_name IS NOT NULL AND farm_name != ""')
    cow_farms = [r['farm_name'] for r in cursor.fetchall()]

    farms = list(dict.fromkeys(user_farms + cow_farms))
    if not farms:
        farms = ['МТК Цегельня', 'МТФ Хорск', 'МТФ-1 Центральная']

    cursor.execute("SELECT id, farm_name FROM users WHERE user_type = 'farm'")
    farm_users = {r['farm_name']: r['id'] for r in cursor.fetchall()}

    print(f"Найдено ферм в системе: {len(farms)} ({', '.join(farms)})")
    print(f"Генерация {count} реалистичных записей выбытия КРС...")

    now = datetime.now()

    reasons_pad = [
        "Острая тимпания рубца", "Бронхопневмония", "Диспепсия телят",
        "Травматический ретикулит", "Кетоз (острая форма)", "Анаэробная энтеротоксемия",
        "Эшерихиоз (колибактериоз)", "Перитонит", "Послеродовой парез", "Разрыв маточной артерии",
        "Обширное повреждение мягких тканей", "Сальпингит", "Внутреннее кровотечение"
    ]
    reasons_vyb = [
        "Гнойный мастит", "Агалактия", "Хронический гнойный эндометрит",
        "Фолликулярная киста", "Лютеиновая киста", "Язва Рунхольца",
        "Флегмона венчика", "Атрофия долей вымени", "Атрофия яичников / яловость",
        "Возрастная выбраковка", "Фримартинизм"
    ]
    reasons_san = [
        "Травма конечностей", "Травма позвоночного столба", "Патологические роды",
        "Выпадение матки", "Стойкая атония преджелудков", "Кетоз"
    ]

    farm_counters = {}
    for f in farms:
        cursor.execute("SELECT COUNT(*) as cnt FROM cows WHERE farm_name = ?", (f,))
        farm_counters[f] = cursor.fetchone()['cnt']

    rows = []
    for i in range(count):
        farm = farms[i % len(farms)]
        farm_counters[farm] = farm_counters.get(farm, 0) + 1
        
        prefix = farm.split()[0] if farm else 'Ферма'
        cow_num = f"{prefix}-{farm_counters[farm]:03d}"
        
        r_cat = random.random()
        if r_cat < 0.28:
            cat = "падёж"
            reason = random.choice(reasons_pad)
        elif r_cat < 0.84:
            cat = "выбраковка"
            reason = random.choice(reasons_vyb)
        else:
            cat = "санитарный"
            reason = random.choice(reasons_san)

        # Распределение по месяцам (за 12 месяцев)
        month_offset = i % 12
        target_y = now.year
        target_m = now.month - month_offset
        if target_m <= 0:
            target_m += 12
            target_y -= 1
        target_d = 1 + ((i // 12) % 28)
        disposal_d = f"{target_y:04d}-{target_m:02d}-{target_d:02d}"

        tag = f"BY 04 {random.randint(10000, 99999)}"
        breed = random.choice(["Черно-пёстрая белорусской селекции", "Голштинская", "Лимузин"])
        
        ag = "Коровы дойного стада"
        lact = random.randint(1, 6)
        w = float(random.randint(480, 680))
        milk = float(random.randint(5500, 9200))
        bv = float(random.randint(1800, 3100))
        
        if "телят" in reason.lower() or "эшерихиоз" in reason.lower() or "диспепсия" in reason.lower():
            ag = "Телята (0–6 мес.)"
            lact = 0
            w = float(random.randint(32, 85))
            milk = 0.0
            bv = float(random.randint(260, 520))
        elif "роды" in reason.lower() or "матки" in reason.lower() or "фримартинизм" in reason.lower():
            ag = "Тёлки старше 1 года" if random.random() < 0.5 else "Нетели"
            lact = 0
            w = float(random.randint(410, 530))
            milk = 0.0
            bv = float(random.randint(2500, 3300))

        user_id = farm_users.get(farm, 1)
        protocol = None
        autopsy_vet = None
        autopsy_date = None
        if cat == 'падёж':
            protocol = json.dumps({
                'anamnesis': 'Животное находилось на стойловом содержании.',
                'external_exam': 'Упитанность средняя, трупные изменения выражены умеренно.',
                'respiratory': 'Легкие спавшиеся, бледно-розовые.',
                'cardiovascular': 'В полостях сердца сгустки темной крови.',
                'digestive': f'Патологические изменения: {reason}.',
                'liver_spleen': 'Печень кровенаполнена, селезенка нормальных размеров.',
                'pat_diagnosis': reason,
                'conclusion': f'Смерть наступила в результате патологии: {reason}',
                'lab_tests': 'Сибирская язва исключена.'
            }, ensure_ascii=False)
            autopsy_vet = 'Главный ветврач'
            autopsy_date = disposal_d

        rows.append((
            cow_num, tag, farm, cat, reason, disposal_d,
            lact, w, f"Выбытие скота ({cat})", ag, breed, milk, bv,
            protocol, autopsy_vet, autopsy_date, 'Да', user_id
        ))

    cursor.executemany('''
        INSERT INTO cows (cow_id, ear_tag, farm_name, category, reason, disposal_date, 
                          lactation, weight, notes, age_group, breed, milk_yield, book_value,
                          autopsy_protocol, autopsy_vet, autopsy_date, autopsy_lab_sample, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', rows)

    conn.commit()
    cursor.execute("SELECT COUNT(*) as cnt FROM cows")
    total_cnt = cursor.fetchone()['cnt']
    conn.close()

    print(f"Готово! Успешно добавлено {count} коров.")
    print(f"Всего в базе данных теперь: {total_cnt} записей.")

if __name__ == '__main__':
    generate_test_cows(1000)
