# fill_original_excel.py
import sqlite3
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill
from datetime import datetime
from database import get_db_connection

def generate_official_template_excel():
    """Генерация сводного официального отчета"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT DISTINCT farm_name FROM cows WHERE farm_name IS NOT NULL ORDER BY farm_name')
    farms = [r['farm_name'] for r in cursor.fetchall()]
    if not farms:
        cursor.execute('SELECT DISTINCT farm_name FROM users WHERE farm_name IS NOT NULL AND farm_name != ""')
        farms = [r['farm_name'] for r in cursor.fetchall()]
        
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Выбытие скота Сводка"
    
    ws.merge_cells('A1:G1')
    ws['A1'] = "ОФИЦИАЛЬНАЯ СВОДКА ВЫБЫТИЯ СКОТА"
    ws['A1'].font = Font(size=14, bold=True)
    ws['A1'].alignment = Alignment(horizontal='center')
    
    headers = ['Ферма', 'Падёж (гол.)', 'Выбраковка (гол.)', 'Санитарный брак (гол.)', 'Пало, всего (гол.)']
    ws.append([])
    ws.append(headers)
    
    for cell in ws[3]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="DC3545", end_color="DC3545", fill_type="solid")
        
    # Единый агрегирующий запрос со всеми категориями и фермами
    cursor.execute('''
        SELECT farm_name,
               SUM(CASE WHEN category = 'падёж' THEN 1 ELSE 0 END) as p,
               SUM(CASE WHEN category = 'выбраковка' THEN 1 ELSE 0 END) as v,
               SUM(CASE WHEN category = 'санитарный' THEN 1 ELSE 0 END) as s,
               COUNT(*) as total
        FROM cows
        WHERE farm_name IS NOT NULL AND farm_name != ''
        GROUP BY farm_name
        ORDER BY farm_name
    ''')
    data_rows = {r['farm_name']: r for r in cursor.fetchall()}
    conn.close()

    total_p = 0
    total_v = 0
    total_s = 0
    total_all = 0

    for farm in farms:
        stat = data_rows.get(farm)
        p = stat['p'] if stat else 0
        v = stat['v'] if stat else 0
        s = stat['s'] if stat else 0
        total = stat['total'] if stat else 0

        total_p += p
        total_v += v
        total_s += s
        total_all += total

        ws.append([farm, p, v, s, total])

    # Итоговая строка
    ws.append(['ИТОГО ПО ХОЗЯЙСТВУ', total_p, total_v, total_s, total_all])
    last_row = ws.max_row
    for cell in ws[last_row]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="FFE2E5", end_color="FFE2E5", fill_type="solid")

    ws.column_dimensions['A'].width = 24
    ws.column_dimensions['B'].width = 16
    ws.column_dimensions['C'].width = 18
    ws.column_dimensions['D'].width = 22
    ws.column_dimensions['E'].width = 18

    return wb
