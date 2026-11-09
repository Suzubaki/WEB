# test_suite.py - Комплексный тест системы учета выбытия скота ОАО «Новая Припять»
import sys
import unittest
from datetime import datetime, timedelta
from app import app
from database import get_db_connection, init_db, set_setting, get_setting
from charts import get_dashboard_full_data

class CattleSystemTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        init_db()
        cls.client = app.test_client()

    def login(self, username, password):
        return self.client.post('/login', data={
            'username': username,
            'password': password
        }, follow_redirects=True)

    def logout(self):
        return self.client.get('/logout', follow_redirects=True)

    # 1. ТЕСТЫ АВТОРИЗАЦИИ И ДОСТУПА
    def test_01_public_and_auth_protection(self):
        print("\n[ТЕСТ 1] Проверка защиты маршрутов и авторизации...")
        # Неавторизованный запрос к защищенным маршрутам должен перенаправлять на /login
        for route in ['/dashboard', '/cows', '/pricing', '/stillborn', '/reports']:
            res = self.client.get(route, follow_redirects=False)
            self.assertIn(res.status_code, [302, 401], f"Маршрут {route} должен быть защищен")

        # Неверный логин
        res_fail = self.login('admin', 'wrong_pass')
        self.assertIn(b'\xd0\x9d\xd0\xb5\xd0\xb2\xd0\xb5\xd1\x80\xd0\xbd', res_fail.data) # "Неверн..."

        # Успешный логин admin
        res_ok = self.login('admin', 'admin123')
        self.assertEqual(res_ok.status_code, 200)
        self.assertIn(b'admin', res_ok.data)
        self.logout()
        print("  -> Авторизация и декораторы доступа работают корректно.")

    # 2. ТЕСТЫ РАБОТЫ ДАШБОРДА И СКОРКАРДА
    def test_02_dashboard_and_scorecard(self):
        print("\n[ТЕСТ 2] Проверка генерации дашборда и скоркарда...")
        self.login('admin', 'admin123')
        res = self.client.get('/dashboard')
        self.assertEqual(res.status_code, 200, "Дашборд должен возвращать 200 OK")
        self.assertIn(b'dashboard', res.data.lower())
        
        # Проверка прямого вызова get_dashboard_full_data
        data = get_dashboard_full_data(user_type='admin', farm_name='all', period='all')
        self.assertIn('kpi', data)
        self.assertIn('charts', data)
        self.assertIn('scorecard', data)
        
        # Проверка 5 ключевых индикаторов в скоркарде (структура выбытия)
        sc_keys = [item['key'] for item in data['scorecard']]
        expected_keys = [
            'norm_fresh_cow_disposal',
            'norm_first_lactation_culling',
            'norm_mortality_rate',
            'norm_locomotor_disorders',
            'norm_mastitis_disorders'
        ]
        for ek in expected_keys:
            self.assertIn(ek, sc_keys, f"Индикатор {ek} должен присутствовать в скоркарде")
        self.logout()
        print("  -> Дашборд, графики и 5 индикаторов скоркарда сформированы успешно.")

    # 3. ТЕСТЫ ДИНАМИЧЕСКИХ НАСТРОЕК PRICING
    def test_03_pricing_and_settings(self):
        print("\n[ТЕСТ 3] Проверка настройки нормативов цен (/pricing)...")
        self.login('admin', 'admin123')
        
        # Обновляем через POST /pricing
        test_payload = {
            'meat_price_per_kg': '6.80',
            'milk_price_per_kg': '1.25',
            'replacement_cost': '3050.0',
            'price_calves': '950.0',
            'norm_mortality_rate': '24.0'
        }
        res = self.client.post('/pricing', data=test_payload, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        
        # Проверяем, что в базе значения обновились
        self.assertAlmostEqual(float(get_setting('meat_price_per_kg')), 6.80)
        self.assertAlmostEqual(float(get_setting('milk_price_per_kg')), 1.25)
        self.assertAlmostEqual(float(get_setting('replacement_cost')), 3050.0)
        
        # Проверяем JSON-ответ при AJAX сохранении
        ajax_res = self.client.post('/pricing', 
                                   json={'meat_price_per_kg': '6.50'}, 
                                   headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(ajax_res.status_code, 200)
        self.assertEqual(ajax_res.get_json().get('status'), 'success')
        self.logout()
        print("  -> Настройки цен и порогов тревог успешно сохраняются и считываются.")

    # 4. ТЕСТЫ ЦИКЛА УЧЁТА КОРОВ (CRUD И ВАЛИДАЦИЯ)
    def test_04_cows_crud_lifecycle(self):
        print("\n[ТЕСТ 4] Проверка добавления, отображения, фильтрации и удаления выбытия скота...")
        # Первичный акт выбытия вносит ветврач фермы (farm1)
        self.login('farm1', 'farm123')
        
        cow_payload = {
            'ear_tag': 'BY999888777',
            'category': 'выбраковка',
            'reason': 'Мастит серозный',
            'disposal_date': datetime.now().strftime('%Y-%m-%d'),
            'lactation': '1',
            'lactation_days': '45',
            'lactation_phase': 'Раздой (31-100 дн)',
            'weight': '540',
            'age_group': 'Коровы 1-й лактации (первотёлки)',
            'milk_yield': '6500',
            'book_value': '3200'
        }
        res_add = self.client.post('/add_cow', data=cow_payload, follow_redirects=True)
        self.assertEqual(res_add.status_code, 200)
        self.assertIn(b'BY999888777', res_add.data)
        self.logout()
        
        # Администратор видит запись в общем реестре и может управлять
        self.login('admin', 'admin123')
        res_search = self.client.get('/cows?search=BY999888777')
        self.assertEqual(res_search.status_code, 200)
        self.assertIn(b'BY999888777', res_search.data)
        
        # Удаление тестовой коровы
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM cows WHERE ear_tag = 'BY999888777'")
        row = cursor.fetchone()
        self.assertIsNotNone(row, "Корова должна быть в базе данных")
        cow_id = row['id']
        conn.close()
        
        res_del = self.client.post(f'/delete_cow/{cow_id}', follow_redirects=True)
        self.assertEqual(res_del.status_code, 200)
        
        # Проверяем, что корова удалена
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM cows WHERE ear_tag = 'BY999888777'")
        row_deleted = cursor.fetchone()
        conn.close()
        self.assertIsNone(row_deleted, "Корова должна быть удалена из базы")
        self.logout()
        print("  -> Полный жизненный цикл записи выбытия проверен успешно.")

    # 5. ТЕСТЫ ЖУРНАЛА МЕРТВОРОЖДЕНИЙ
    def test_05_stillbirth_module(self):
        print("\n[ТЕСТ 5] Проверка отдельного журнала мертворождений...")
        # Первичный акт мертворождения регистрирует ветврач фермы (farm1)
        self.login('farm1', 'farm123')
        
        sb_payload = {
            'event_date': datetime.now().strftime('%Y-%m-%d'),
            'mother_tag': 'BY777666555',
            'mother_group': 'Полновозрастные',
            'event_type': 'Мертворождение',
            'cause': 'Патология родов',
            'fetus_sex': 'Тёлочки',
            'fetus_weight': '28.5',
            'gestation_days': '278',
            'notes': 'Тестовая запись аудита'
        }
        res_add = self.client.post('/add_stillborn', data=sb_payload, follow_redirects=True)
        self.assertEqual(res_add.status_code, 200)
        self.assertIn(b'BY777666555', res_add.data)
        self.logout()
        
        # Администратор видит и может удалить тестовую запись
        self.login('admin', 'admin123')
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM stillbirth_records WHERE mother_tag = 'BY777666555'")
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        sb_id = row['id']
        conn.close()
        
        res_del = self.client.post(f'/delete_stillborn/{sb_id}', follow_redirects=True)
        self.assertEqual(res_del.status_code, 200)
        self.logout()
        print("  -> Журнал мертворождений и абортов функционирует штатно.")

    # 6. ТЕСТЫ ОТЧЁТОВ И ЭКСПОРТА (EXCEL, 210-АПК, AITS)
    def test_06_reports_and_export(self):
        print("\n[ТЕСТ 6] Проверка генератора отчётов и экспорта Excel...")
        self.login('admin', 'admin123')
        
        # Страница отчётов
        res_rep = self.client.get('/reports')
        self.assertEqual(res_rep.status_code, 200)
        
        # Экспорт официального акта Форма 210-АПК в Excel
        today_str = datetime.now().strftime('%Y-%m-%d')
        res_210 = self.client.post('/generate_report', data={
            'report_type': 'form_210_apk',
            'report_format': 'excel',
            'start_date': '2026-01-01',
            'end_date': today_str,
            'farm_filter': 'all'
        })
        self.assertEqual(res_210.status_code, 200)
        self.assertEqual(res_210.content_type, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            
        # Экспорт Excel мертворождений
        res_sb_excel = self.client.get('/export_stillborn_excel')
        self.assertEqual(res_sb_excel.status_code, 200)
        self.assertEqual(res_sb_excel.content_type, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            
        self.logout()
        print("  -> Генерация отчётов и Excel-экспорт работают без сбоев.")

    # 7. ТЕСТЫ БЕЗОПАСНОСТИ CSRF И АТОМАРНОСТИ ID
    def test_07_csrf_and_security(self):
        print("\n[ТЕСТ 7] Проверка CSRF-защиты и атомарности ID...")
        from database import generate_cow_id, generate_stillborn_code
        
        # Проверка атомарной генерации cow_id
        id1 = generate_cow_id("МТФ-1")
        id2 = generate_cow_id("МТФ-1")
        self.assertTrue(id1.startswith("МТФ-1-") or id1.startswith("COW-"))
        self.assertTrue(id2.startswith("МТФ-1-") or id2.startswith("COW-"))
        self.assertNotEqual(id1, id2)
        
        # Проверка генерации кода мертворождения
        sb_code = generate_stillborn_code("МТК-2")
        self.assertTrue(sb_code.startswith("МТК-2-М") or sb_code.startswith("МТК-2-SB-"))
        
        # Проверка срабатывания CSRF-защиты при включенном режиме
        app.config['WTF_CSRF_ENABLED'] = True
        try:
            # POST без CSRF токена должен получить 400 Bad Request
            res_csrf = self.client.post('/login', data={'username': 'admin', 'password': '123'})
            self.assertEqual(res_csrf.status_code, 400, "POST без CSRF должен отклоняться кодом 400")
        finally:
            app.config['WTF_CSRF_ENABLED'] = False
        print("  -> CSRF-защита и генераторы уникальных идентификаторов работают корректно.")

if __name__ == '__main__':
    unittest.main(verbosity=2)
