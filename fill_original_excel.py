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
        
    for farm in farms:
        cursor.execute("SELECT COUNT(*) as c FROM cows WHERE farm_name = ? AND category = 'падёж'", (farm,))
        p = cursor.fetchone()['c']
        cursor.execute("SELECT COUNT(*) as c FROM cows WHERE farm_name = ? AND category = 'выбраковка'", (farm,))
        v = cursor.fetchone()['c']
        cursor.execute("SELECT COUNT(*) as c FROM cows WHERE farm_name = ? AND category = 'санитарный'", (farm,))
        s = cursor.fetchone()['c']
        total = p + v + s
        ws.append([farm, p, v, s, total])
        
    conn.close()
    return wb
