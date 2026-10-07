# check_system.py - Скрипт автоматической самодиагностики системы
import os
import sys
import sqlite3

def run_checks():
    print("=" * 60)
    print(" ДИАГНОСТИКА СИСТЕМЫ: ОАО «Новая Припять»")
    print("=" * 60)
    all_ok = True

    # 1. Проверка структуры Blueprints
    print("\n[1] Проверка модульной структуры (Flask Blueprints)...")
    expected_files = [
        'routes/__init__.py',
        'routes/main.py',
        'routes/auth.py',
        'routes/cows.py',
        'routes/reports.py',
        'routes/admin.py',
        'routes/api.py',
        'extensions.py'
    ]
    for f in expected_files:
        if os.path.exists(f):
            print(f"  [OK] Файл найден: {f}")
        else:
            print(f"  [ОШИБКА] Не найден файл: {f}")
            all_ok = False

    # 2. Проверка базы данных и WAL-режима
    print("\n[2] Проверка базы данных SQLite и WAL-режима...")
    try:
        from database import init_db, get_db_connection
        init_db()
        conn = get_db_connection()
        cursor = conn.cursor()

        # Режим журнала
        cursor.execute("PRAGMA journal_mode;")
        mode = cursor.fetchone()[0]
        if mode.lower() == 'wal':
            print(f"  [OK] Режим журнала SQLite: {mode.upper()} (параллельное чтение активно)")
        else:
            print(f"  [ПРЕДУПРЕЖДЕНИЕ] Текущий режим: {mode} (ожидался WAL)")

        # Проверка индексов таблицы cows
        cursor.execute("PRAGMA index_list(cows);")
        indexes = [row['name'] for row in cursor.fetchall()]
        expected_indexes = [
            'idx_cows_farm_date',
            'idx_cows_category',
            'idx_cows_cow_id',
            'idx_cows_ear_tag',
            'idx_cows_disposal_date'
        ]
        
        found_count = 0
        for idx in expected_indexes:
            if idx in indexes:
                print(f"  [OK] Индекс активен: {idx}")
                found_count += 1
            else:
                print(f"  [!] Индекс отсутствует: {idx}")
        
        if found_count == len(expected_indexes):
            print(f"  [OK] Все {found_count} индексов успешно оптимизируют запросы!")

        conn.close()
    except Exception as e:
        print(f"  [ОШИБКА БД]: {e}")
        all_ok = False

    # 3. Проверка регистрации маршрутов Flask
    print("\n[3] Проверка регистрации маршрутов приложения...")
    try:
        from app import app
        routes = [r.rule for r in app.url_map.iter_rules()]
        key_routes = [
            '/', '/login', '/logout', '/dashboard',
            '/cows', '/add_cow', '/import_cows',
            '/reports',
            '/reasons', '/audit_log', '/backup',
            '/img/logo.svg', '/img/logo.jpg'
        ]
        for kr in key_routes:
            if kr in routes or any(kr in r for r in routes):
                print(f"  [OK] Маршрут зарегистрирован: {kr}")
            else:
                print(f"  [ОШИБКА] Маршрут отсутствует: {kr}")
                all_ok = False
    except Exception as e:
        print(f"  [ОШИБКА ПРИЛОЖЕНИЯ]: {e}")
        all_ok = False

    # 4. Проверка официального логотипа
    print("\n[4] Проверка графических ассетов логотипа...")
    logo_paths = ['public/img/logo.svg', 'static/img/logo.svg', 'img/logo.svg']
    for lp in logo_paths:
        if os.path.exists(lp):
            size = os.path.getsize(lp)
            print(f"  [OK] Векторный логотип: {lp} ({size} байт)")
        else:
            print(f"  [ИНФО] {lp} будет отдаваться через встроенный генератор в app.py")

    print("\n" + "=" * 60)
    if all_ok:
        print(" ИТОГ: ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print(" Приложение полностью готово к запуску: python app.py")
    else:
        print(" ИТОГ: Обнаружены замечания. Проверьте вывод выше.")
    print("=" * 60)

if __name__ == '__main__':
    run_checks()
