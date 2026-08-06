from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from datetime import datetime
import sqlite3
from config import Config

def generate_comprehensive_report(start_date, end_date, farm_filter='all'):
    """Создание комплексного отчёта по образцу Excel файла"""
    
    # Подключаемся к базе данных
    conn = sqlite3.connect('livestock.db')
    conn.row_factory = sqlite3.Row
    
    # Получаем данные
    query = '''
        SELECT * FROM cows 
        WHERE disposal_date BETWEEN ? AND ?
    '''
    params = [start_date, end_date]
    
    if farm_filter != 'all':
        query += ' AND farm_name = ?'
        params.append(farm_filter)
    
    query += ' ORDER BY farm_name, disposal_date'
    
    cursor = conn.execute(query, params)
    data = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    if not data:
        return None
    
    # Создаём Excel файл по образцу
    wb = Workbook()
    ws = wb.active
    ws.title = "Отчёт по выбытию скота"
    
    # Стили
    header_font = Font(bold=True, size=12)
    title_font = Font(bold=True, size=14)
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    header_fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
    center_alignment = Alignment(horizontal='center', vertical='center')
    
    # Заголовок отчёта (по образцу Excel файла)
    ws.merge_cells('B1:H1')
    ws['B1'] = "ОПЕРАТИВНАЯ ИНФОРМАЦИЯ"
    ws['B1'].font = title_font
    ws['B1'].alignment = center_alignment
    
    ws.merge_cells('B2:H2')
    ws['B2'] = "О ВЫБЫТИИ СКОТА ПО КАТЕГОРИЯМ"
    ws['B2'].font = Font(bold=True, size=12)
    ws['B2'].alignment = center_alignment
    
    ws.merge_cells('B3:H3')
    ws['B3'] = f"В СЕЛЬСКОХОЗЯЙСТВЕННЫХ ОРГАНИЗАЦИЯХ"
    ws['B3'].alignment = center_alignment
    
    ws.merge_cells('B4:H4')
    ws['B4'] = f"Период: с {start_date} по {end_date}"
    ws['B4'].alignment = center_alignment
    
    # Пустая строка
    ws.row_dimensions[6].height = 20
    
    # Заголовки таблицы (как в оригинальном файле)
    headers = [
        "Наименование хозяйств",
        "Падёж", "Выбраковка", "Санитарный блок", 
        "ВСЕГО выбыло",
        "Мертворожденные телята",
        "Выбытие стельного скота",
        "Примечания"
    ]
    
    # Записываем заголовки
    for col, header in enumerate(headers, start=2):
        cell = ws.cell(row=7, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = border
        cell.alignment = center_alignment
    
    # Получаем список всех ферм
    conn = sqlite3.connect('livestock.db')
    cursor = conn.execute('SELECT DISTINCT farm_name FROM cows ORDER BY farm_name')
    farms = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    # Заполняем данные по фермам
    current_row = 8
    
    for farm in farms:
        # Фильтруем данные по ферме
        farm_data = [cow for cow in data if cow['farm_name'] == farm]
        
        if not farm_data:
            continue
        
        # Подсчитываем статистику по категориям
        stats = {
            'падёж': 0,
            'выбраковка': 0,
            'санитарный': 0,
            'всего': len(farm_data),
            'мертворожденные': 0,  # Пока заглушка
            'стельный_скот': 0,     # Пока заглушка
            'примечания': ''
        }
        
        for cow in farm_data:
            category = cow['category']
            if category in stats:
                stats[category] += 1
        
        # Записываем данные фермы
        ws.cell(row=current_row, column=2, value=farm).border = border
        ws.cell(row=current_row, column=3, value=stats['падёж']).border = border
        ws.cell(row=current_row, column=4, value=stats['выбраковка']).border = border
        ws.cell(row=current_row, column=5, value=stats['санитарный']).border = border
        ws.cell(row=current_row, column=6, value=stats['всего']).border = border
        ws.cell(row=current_row, column=7, value=stats['мертворожденные']).border = border
        ws.cell(row=current_row, column=8, value=stats['стельный_скот']).border = border
        ws.cell(row=current_row, column=9, value=stats['примечания']).border = border
        
        current_row += 1
    
    # Итоговая строка
    ws.cell(row=current_row, column=2, value="ИТОГО:").font = Font(bold=True)
    ws.cell(row=current_row, column=2).border = border
    
    # Подсчитываем итоги
    for col in range(3, 10):
        col_letter = get_column_letter(col)
        start_cell = f"{col_letter}8"
        end_cell = f"{col_letter}{current_row-1}"
        formula = f"=СУММ({start_cell}:{end_cell})"
        ws.cell(row=current_row, column=col, value=formula).font = Font(bold=True)
        ws.cell(row=current_row, column=col).border = border
    
    # Настраиваем ширину колонок
    column_widths = {
        'B': 30,  # Наименование хозяйств
        'C': 15,  # Падёж
        'D': 15,  # Выбраковка
        'E': 15,  # Санитарный блок
        'F': 15,  # Всего
        'G': 20,  # Мертворожденные
        'H': 20,  # Выбытие стельного скота
        'I': 25   # Примечания
    }
    
    for col, width in column_widths.items():
        ws.column_dimensions[col].width = width
    
    # Вторая часть отчёта - детализация по причинам
    ws2 = wb.create_sheet(title="Детализация по причинам")
    
    # Заголовок
    ws2.merge_cells('B1:H1')
    ws2['B1'] = "ДЕТАЛИЗАЦИЯ ПРИЧИН ВЫБЫТИЯ"
    ws2['B1'].font = title_font
    ws2['B1'].alignment = center_alignment
    
    # Группируем данные по фермам и категориям
    detail_row = 3
    for farm in farms:
        farm_data = [cow for cow in data if cow['farm_name'] == farm]
        if not farm_data:
            continue
        
        # Заголовок фермы
        ws2.cell(row=detail_row, column=2, value=f"Хозяйство: {farm}").font = Font(bold=True)
        detail_row += 1
        
        # Группируем по категориям
        for category in Config.DISPOSAL_CATEGORIES.keys():
            category_data = [cow for cow in farm_data if cow['category'] == category]
            if not category_data:
                continue
            
            ws2.cell(row=detail_row, column=2, value=f"  Категория: {category}").font = Font(bold=True, italic=True)
            detail_row += 1
            
            # Группируем по причинам
            reasons = {}
            for cow in category_data:
                reason = cow['reason']
                reasons[reason] = reasons.get(reason, 0) + 1
            
            for reason, count in sorted(reasons.items()):
                ws2.cell(row=detail_row, column=3, value=f"    {reason}")
                ws2.cell(row=detail_row, column=4, value=count)
                detail_row += 1
        
        detail_row += 1  # Пустая строка между фермами
    
    # Настраиваем ширину колонок
    ws2.column_dimensions['B'].width = 40
    ws2.column_dimensions['C'].width = 40
    ws2.column_dimensions['D'].width = 15
    
    # Третья часть - месячная статистика
    ws3 = wb.create_sheet(title="Месячная статистика")
    
    # Сохраняем файл в папке reports
    import os
    if not os.path.exists('reports'):
        os.makedirs('reports')
    
    filename = f'reports/комплексный_отчет_{start_date}_по_{end_date}.xlsx'
    wb.save(filename)
    
    # Полный абсолютный путь
    full_path = os.path.abspath(filename)
    
    return full_path