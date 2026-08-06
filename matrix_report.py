"""Матричный отчёт: фермы × подкатегории"""
import sqlite3
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from datetime import datetime, timedelta
import os

def generate_matrix_report(start_date, end_date, category, farm_filter='all'):
    """Создание матричного отчёта: фермы × подкатегории"""
    
    print(f"Создание матричного отчёта для категории: {category}")
    print(f"Период: {start_date} - {end_date}")
    
    # Подключаемся к базе данных
    conn = sqlite3.connect('livestock.db')
    conn.row_factory = sqlite3.Row
    
    # Получаем все фермы
    query = '''
        SELECT DISTINCT farm_name 
        FROM cows 
        WHERE disposal_date BETWEEN ? AND ?
    '''
    params = [start_date, end_date]
    
    if farm_filter != 'all':
        query += ' AND farm_name = ?'
        params.append(farm_filter)
    
    query += ' ORDER BY farm_name'
    
    cursor = conn.execute(query, params)
    farms = [row['farm_name'] for row in cursor.fetchall()]
    
    if not farms:
        print("Нет ферм с данными за выбранный период")
        conn.close()
        return None
    
    # Получаем все подкатегории для выбранной категории
    # Будем использовать предопределённые подкатегории из config
    from config import Config
    
    if category not in Config.DISPOSAL_CATEGORIES:
        print(f"Неизвестная категория: {category}")
        conn.close()
        return None
    
    subcategories = Config.DISPOSAL_CATEGORIES[category]
    
    # Создаём Excel файл
    wb = Workbook()
    ws = wb.active
    ws.title = f"Матрица {category}"
    
    # Стили
    title_font = Font(name='Times New Roman', size=14, bold=True)
    header_font = Font(bold=True)
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    header_fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
    center_alignment = Alignment(horizontal='center', vertical='center')
    
    # Заголовок документа
    ws.merge_cells('A1:H1')
    ws['A1'] = f'ОТЧЁТ ПО ВЫБЫТИЮ СКОТА'
    ws['A1'].font = title_font
    ws['A1'].alignment = center_alignment
    
    ws.merge_cells('A2:H2')
    ws['A2'] = f'Категория: {category.upper()}'
    ws['A2'].font = Font(bold=True, size=12)
    ws['A2'].alignment = center_alignment
    
    ws.merge_cells('A3:H3')
    ws['A3'] = f'Период: с {start_date} по {end_date}'
    ws['A3'].alignment = center_alignment
    
    ws.row_dimensions[5].height = 20  # Пустая строка
    
    # Заголовки таблицы
    # Первый столбец - подкатегории
    ws['A6'] = 'ПРИЧИНЫ ВЫБЫТИЯ'
    ws['A6'].font = header_font
    ws['A6'].fill = header_fill
    ws['A6'].border = border
    ws['A6'].alignment = center_alignment
    
    # Остальные столбцы - фермы
    for col, farm in enumerate(farms, start=2):
        col_letter = get_column_letter(col)
        cell = ws.cell(row=6, column=col, value=farm)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = border
        cell.alignment = center_alignment
    
    # Последний столбец - ИТОГО
    total_col = len(farms) + 2
    total_col_letter = get_column_letter(total_col)
    ws.cell(row=6, column=total_col, value='ИТОГО')
    ws[f'{total_col_letter}6'].font = header_font
    ws[f'{total_col_letter}6'].fill = PatternFill(start_color="FF9999", end_color="FF9999", fill_type="solid")
    ws[f'{total_col_letter}6'].border = border
    ws[f'{total_col_letter}6'].alignment = center_alignment
    
    # Заполняем данные
    current_row = 7
    
    for subcategory in subcategories:
        # Название подкатегории
        ws.cell(row=current_row, column=1, value=subcategory).border = border
        
        # Считаем данные для каждой фермы
        total_for_subcategory = 0
        
        for col, farm in enumerate(farms, start=2):
            # Получаем количество для этой фермы и подкатегории
            query = '''
                SELECT COUNT(*) as count 
                FROM cows 
                WHERE farm_name = ? 
                AND category = ? 
                AND reason = ?
                AND disposal_date BETWEEN ? AND ?
            '''
            cursor = conn.execute(query, (farm, category, subcategory, start_date, end_date))
            result = cursor.fetchone()
            count = result['count'] if result else 0
            
            # Записываем в ячейку
            cell = ws.cell(row=current_row, column=col, value=count)
            cell.border = border
            cell.alignment = center_alignment
            
            total_for_subcategory += count
        
        # Итог по строке
        total_cell = ws.cell(row=current_row, column=total_col, value=total_for_subcategory)
        total_cell.border = border
        total_cell.font = Font(bold=True)
        total_cell.alignment = center_alignment
        
        current_row += 1
    
    # Строка итогов по колонкам
    ws.cell(row=current_row, column=1, value='ИТОГО').font = Font(bold=True)
    ws.cell(row=current_row, column=1).border = border
    ws.cell(row=current_row, column=1).fill = PatternFill(start_color="FF9999", end_color="FF9999", fill_type="solid")
    
    # Считаем итоги по колонкам (фермам)
    for col in range(2, total_col + 1):
        col_letter = get_column_letter(col)
        start_cell = f'{col_letter}7'
        end_cell = f'{col_letter}{current_row-1}'
        
        if col == total_col:  # Итоговая колонка
            # Сумма уже подсчитана в строках
            pass
        else:
            formula = f'=СУММ({start_cell}:{end_cell})'
            cell = ws.cell(row=current_row, column=col, value=formula)
            cell.font = Font(bold=True)
            cell.border = border
            cell.fill = PatternFill(start_color="FF9999", end_color="FF9999", fill_type="solid")
    
    # Настраиваем ширину колонок
    ws.column_dimensions['A'].width = 40  # Причины
    for col in range(2, total_col + 1):
        col_letter = get_column_letter(col)
        ws.column_dimensions[col_letter].width = 15  # Фермы
    
    conn.close()
    
    # Сохраняем файл в папке reports
    if not os.path.exists('reports'):
        os.makedirs('reports')
    
    filename = f'reports/матричный_отчет_{category}_{start_date}_по_{end_date}.xlsx'
    wb.save(filename)
    
    # Полный абсолютный путь
    full_path = os.path.abspath(filename)
    
    print(f"Матричный отчёт создан: {filename}")
    print(f"Полный путь: {full_path}")
    print(f"Размер матрицы: {len(subcategories)} подкатегорий × {len(farms)} ферм")
    
    return full_path

# Тестовая функция
if __name__ == '__main__':
    # Тестовые данные
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    # Тестируем для категории "падёж"
    filename = generate_matrix_report(start_date, end_date, 'падёж')
    if filename:
        print(f"Тестовый матричный отчёт создан: {filename}")
    else:
        print("Не удалось создать отчёт")