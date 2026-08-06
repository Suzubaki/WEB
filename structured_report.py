from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
import sqlite3
from datetime import datetime
from config import Config
import os

def generate_structured_report(start_date, end_date, farm_filter='all'):
    """Создание отчёта по готовой структуре Excel"""
    
    # Подключаемся к базе данных
    conn = sqlite3.connect('livestock.db')
    conn.row_factory = sqlite3.Row
    
    # Получаем данные
    query = '''
        SELECT farm_name, category, reason, disposal_date 
        FROM cows 
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
    
    # Анализируем структуру файла для понимания колонок
    print("Анализирую данные для заполнения отчёта...")
    
    # Группируем данные по фермам и категориям
    farm_stats = {}
    
    for cow in data:
        farm = cow['farm_name']
        category = cow['category']
        
        if farm not in farm_stats:
            farm_stats[farm] = {
                'падёж': 0,
                'выбраковка': 0,
                'санитарный': 0,
                'всего': 0,
                'мертворожденные': 0,  # Пока 0
                'стельный_скот': 0      # Пока 0
            }
        
        farm_stats[farm][category] += 1
        farm_stats[farm]['всего'] += 1
    
    print(f"Найдено {len(farm_stats)} ферм")
    
    # Создаём Excel файл на основе существующей структуры
    # Вместо создания с нуля, буду использовать существующую структуру
    # и заполнять данные ферм
    
    wb = Workbook()
    ws = wb.active
    ws.title = 'Отчёт по выбытию скота'
    
    # Создаём заголовки по образцу
    ws.merge_cells('B1:H1')
    ws['B1'] = 'ОПЕРАТИВНАЯ ИНФОРМАЦИЯ'
    ws['B1'].font = Font(name='Times New Roman', size=16.0, bold=False)
    ws['B1'].alignment = Alignment(horizontal='center')
    
    ws.merge_cells('B2:H2')
    ws['B2'] = f'О ВЫБЫТИИ СКОТА ПО КАТЕГОРИЯМ за период {start_date} - {end_date}'
    ws['B2'].font = Font(name='Times New Roman', size=14.0, bold=True)
    ws['B2'].alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    
    # Заголовки таблицы
    headers = [
        'Наименование хозяйств',
        'Падёж', 'Выбраковка', 'Санитарный блок', 
        'ВСЕГО выбыло',
        'Мертворожденные телята',
        'Выбытие стельного скота',
        'Примечания'
    ]
    
    # Записываем заголовки
    for col, header in enumerate(headers, start=2):
        cell = ws.cell(row=5, column=col, value=header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
        cell.border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
    
    # Заполняем данные ферм
    row = 6
    for farm, stats in farm_stats.items():
        # Для каждой фермы заполняем все колонки
        ws.cell(row=row, column=2, value=farm).border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        ws.cell(row=row, column=3, value=stats['падёж']).border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        ws.cell(row=row, column=4, value=stats['выбраковка']).border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        ws.cell(row=row, column=5, value=stats['санитарный']).border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        ws.cell(row=row, column=6, value=stats['всего']).border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        ws.cell(row=row, column=7, value=stats['мертворожденные']).border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        ws.cell(row=row, column=8, value=stats['стельный_скот']).border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        ws.cell(row=row, column=9, value='').border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        row += 1
    
    # Итоговая строка
    ws.cell(row=row, column=2, value='ИТОГО:').font = Font(bold=True)
    ws.cell(row=row, column=2).border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Формулы для итогов
    for col in range(3, 10):
        col_letter = chr(64 + col)  # A=65, B=66, ...
        start_cell = f'{col_letter}6'
        end_cell = f'{col_letter}{row-1}'
        formula = f'=СУММ({start_cell}:{end_cell})'
        ws.cell(row=row, column=col, value=formula).font = Font(bold=True)
        ws.cell(row=row, column=col).border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
    
    # Настраиваем ширину колонок
    column_widths = {
        'B': 30,  # Наименование хозяйств
        'C': 12,  # Падёж
        'D': 15,  # Выбраковка
        'E': 15,  # Санитарный блок
        'F': 12,  # Всего
        'G': 20,  # Мертворожденные
        'H': 20,  # Выбытие стельного скота
        'I': 25   # Примечания
    }
    
    for col, width in column_widths.items():
        ws.column_dimensions[col].width = width
    
    # Создаём второй лист с детализацией
    ws2 = wb.create_sheet(title='Детализация')
    
    ws2.merge_cells('B1:H1')
    ws2['B1'] = 'ДЕТАЛИЗАЦИЯ ПРИЧИН ВЫБЫТИЯ'
    ws2['B1'].font = Font(bold=True, size=14)
    ws2['B1'].alignment = Alignment(horizontal='center')
    
    detail_row = 3
    for farm, stats in farm_stats.items():
        ws2.cell(row=detail_row, column=2, value=f'Хозяйство: {farm}').font = Font(bold=True)
        detail_row += 1
        
        for category in ['падёж', 'выбраковка', 'санитарный']:
            if stats[category] > 0:
                ws2.cell(row=detail_row, column=2, value=f'  Категория: {category}').font = Font(bold=True, italic=True)
                detail_row += 1
                
                # Получаем все причины для этой фермы и категории
                conn = sqlite3.connect('livestock.db')
                cursor = conn.execute('''
                    SELECT reason, COUNT(*) as count 
                    FROM cows 
                    WHERE farm_name = ? AND category = ? AND disposal_date BETWEEN ? AND ?
                    GROUP BY reason
                    ORDER BY reason
                ''', (farm, category, start_date, end_date))
                
                reasons = cursor.fetchall()
                conn.close()
                
                for reason in reasons:
                    ws2.cell(row=detail_row, column=3, value=f'    {reason[0]}')
                    ws2.cell(row=detail_row, column=4, value=reason[1])
                    detail_row += 1
        
        detail_row += 1  # Пустая строка
    
    # Настраиваем ширину
    ws2.column_dimensions['B'].width = 40
    ws2.column_dimensions['C'].width = 40
    ws2.column_dimensions['D'].width = 15
    
    # Сохраняем файл в папке reports
    if not os.path.exists('reports'):
        os.makedirs('reports')
    
    filename = f'reports/структурированный_отчет_{start_date}_по_{end_date}.xlsx'
    wb.save(filename)
    
    # Полный абсолютный путь
    full_path = os.path.abspath(filename)
    
    print(f"Отчёт сохранён как: {filename}")
    print(f"Полный путь: {full_path}")
    print(f"Всего ферм: {len(farm_stats)}")
    print(f"Всего записей: {len(data)}")
    
    return full_path

# Тестовая функция
if __name__ == '__main__':
    # Тестовые данные - все фермы за последний месяц
    from datetime import datetime, timedelta
    
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    filename = generate_structured_report(start_date, end_date)
    if filename:
        print(f"Тестовый отчёт создан: {filename}")
    else:
        print("Нет данных для создания отчёта")