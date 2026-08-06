# -*- coding: utf-8 -*-
"""
Заполнение оригинального Excel файла "2,3Выбытие скота Сводка.xlsx"
данными из базы livestock.db
Ячейка "Пало" заполняется как сумма: выбраковка + санитарный брак + падёж
Формулы не трогаем
"""
import sqlite3
import os
from datetime import datetime
from openpyxl import load_workbook


def analyze_excel_structure(filepath):
    """Анализирует структуру Excel файла чтобы понять где какие данные"""
    print(f"Анализирую файл: {filepath}")
    
    try:
        wb = load_workbook(filepath, data_only=False)  # data_only=False чтобы видеть формулы
        ws = wb.active
        
        print(f"Лист: {ws.title}")
        print(f"Кол-во строк: {ws.max_row}, кол-во колонок: {ws.max_column}")
        print()
        
        # Ищем заголовки и понимаем структуру
        print("Первые 7 строк файла:")
        for row in range(1, 8):
            row_data = []
            for col in range(1, 16):  # Первые 15 колонок
                cell = ws.cell(row=row, column=col)
                value = cell.value
                
                # Проверяем есть ли формула
                if cell.data_type == 'f':
                    value = f"ФОРМУЛА: {value}"
                
                row_data.append(f"({col})={value}")
            
            print(f"Строка {row}: {' | '.join(row_data[:10])}...")
        
        print("\nПоиск слова 'Пало' в файле:")
        for row in range(1, ws.max_row + 1):
            for col in range(1, ws.max_column + 1):
                cell_value = ws.cell(row=row, column=col).value
                if cell_value and isinstance(cell_value, str) and 'пало' in cell_value.lower():
                    print(f"  Найдено в строке {row}, колонка {col}: {cell_value}")
        
        print("\nПоиск ферм в файле (первые 15 строк):")
        for row in range(1, 20):
            cell_value = ws.cell(row=row, column=2).value  # Колонка B
            if cell_value and isinstance(cell_value, str) and len(cell_value.strip()) > 3:
                print(f"  Строка {row}, колонка B: {cell_value}")
        
        wb.close()
        return True
        
    except Exception as e:
        print(f"Ошибка при анализе файла: {e}")
        return False


def get_data_from_database():
    """Получает данные из базы данных"""
    conn = sqlite3.connect('livestock.db')
    conn.row_factory = sqlite3.Row
    
    # Получаем все данные
    cursor = conn.execute('''
        SELECT farm_name, category, reason, disposal_date, cow_id 
        FROM cows 
        ORDER BY farm_name, disposal_date
    ''')
    
    data = [dict(row) for row in cursor.fetchall()]
    
    if not data:
        print("Нет данных в базе")
        conn.close()
        return {}
    
    # Группируем данные по фермам
    farm_stats = {}
    for cow in data:
        farm = cow['farm_name']
        category = cow['category']
        
        if farm not in farm_stats:
            farm_stats[farm] = {
                'падёж': 0,
                'выбраковка': 0,
                'санитарный': 0,
                'всего': 0
            }
        
        if category in farm_stats[farm]:
            farm_stats[farm][category] += 1
            farm_stats[farm]['всего'] += 1
    
    conn.close()
    
    print(f"Из базы данных получено {len(farm_stats)} ферм:")
    for farm, stats in farm_stats.items():
        print(f"  {farm}: падёж={stats['падёж']}, выбраковка={stats['выбраковка']}, санитарный={stats['санитарный']}, всего={stats['всего']}")
    
    return farm_stats


def fill_excel_with_data(original_path, farm_stats):
    """Заполняет Excel файл данными из базы"""
    print(f"\nЗаполняю файл: {original_path}")
    
    try:
        # Создаем копию оригинального файла
        import shutil
        from datetime import datetime
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        new_filename = f"2,3Выбытие скота Сводка_заполненный_{timestamp}.xlsx"
        new_path = os.path.join(os.path.dirname(original_path), new_filename)
        
        # Копируем файл
        shutil.copy2(original_path, new_path)
        print(f"Создана копия: {new_path}")
        
        # Открываем копию для редактирования
        wb = load_workbook(new_path)
        ws = wb.active
        
        # Ищем где находятся фермы и колонка "Пало"
        # Обычно в таких файлах:
        # - Названия ферм в колонке B (2)
        # - "Пало" может быть в разных колонках
        
        # Сначала найдем строку где есть заголовок с "Пало"
        пало_col = None
        for col in range(1, ws.max_column + 1):
            for row in range(1, 10):  # Ищем в первых 10 строках
                cell_value = ws.cell(row=row, column=col).value
                if cell_value and isinstance(cell_value, str) and 'пало' in cell_value.lower():
                    пало_col = col
                    print(f"Найдена колонка 'Пало': колонка {col}, строка {row}: {cell_value}")
                    break
            if пало_col:
                break
        
        if not пало_col:
            print("Не удалось найти колонку 'Пало', предполагаю что это колонка 3")
            пало_col = 3
        
        # Ищем фермы в файле
        фермы_обработаны = 0
        
        for row in range(5, ws.max_row + 1):  # Данные обычно начинаются с 5 строки
            farm_name_cell = ws.cell(row=row, column=2)  # Колонка B - название фермы
            
            if not farm_name_cell.value or not isinstance(farm_name_cell.value, str):
                continue
            
            farm_name = farm_name_cell.value.strip()
            
            # Ищем соответствующую ферму в наших данных
            matching_farm = None
            for db_farm in farm_stats.keys():
                db_farm_clean = db_farm.strip()
                # Простое сравнение - если названия похожи
                if (db_farm_clean.lower() in farm_name.lower() or 
                    farm_name.lower() in db_farm_clean.lower()):
                    matching_farm = db_farm
                    break
            
            if matching_farm:
                stats = farm_stats[matching_farm]
                print(f"Заполняю ферму: {farm_name} (совпадение с: {matching_farm})")
                
                # Заполняем "Пало" как сумма: выбраковка + санитарный + падёж
                пало_value = stats['выбраковка'] + stats['санитарный'] + stats['падёж']
                
                # Записываем значение в колонку "Пало"
                ws.cell(row=row, column=пало_col).value = пало_value
                print(f"  'Пало' = {пало_value} (выбраковка:{stats['выбраковка']} + санитарный:{stats['санитарный']} + падёж:{stats['падёж']})")
                
                фермы_обработаны += 1
                
                # Удаляем из списка, чтобы не обрабатывать повторно
                del farm_stats[matching_farm]
        
        print(f"\nОбработано ферм в файле: {фермы_обработаны}")
        
        # Сохраняем изменения
        wb.save(new_path)
        wb.close()
        
        print(f"\n✅ Файл успешно заполнен и сохранен как: {new_path}")
        print(f"📏 Размер файла: {os.path.getsize(new_path)} байт")
        
        return new_path, фермы_обработаны
        
    except Exception as e:
        print(f"❌ Ошибка при заполнении файла: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Основная функция"""
    print("=" * 60)
    print("ЗАПОЛНЕНИЕ ОРИГИНАЛЬНОГО EXCEL ФАЙЛА ДАННЫМИ ИЗ БАЗЫ")
    print("=" * 60)
    
    # Путь к оригинальному файлу
    original_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '2,3Выбытие скота Сводка.xlsx'))
    
    if not os.path.exists(original_path):
        print(f"❌ Файл не найден: {original_path}")
        return
    
    # 1. Анализируем структуру файла
    print("\n📋 АНАЛИЗ СТРУКТУРЫ ФАЙЛА:")
    analyze_excel_structure(original_path)
    
    # 2. Получаем данные из базы
    print("\n📊 ПОЛУЧЕНИЕ ДАННЫХ ИЗ БАЗЫ:")
    farm_stats = get_data_from_database()
    
    if not farm_stats:
        print("❌ Нет данных для заполнения")
        return
    
    # 3. Заполняем файл данными
    print("\n🖊️ ЗАПОЛНЕНИЕ ФАЙЛА:")
    new_file, фермы_обработаны = fill_excel_with_data(original_path, farm_stats)
    
    if new_file:
        print("\n" + "=" * 60)
        print("✅ ВЫПОЛНЕНО УСПЕШНО!")
        print(f"📁 Создан файл: {new_file}")
        print("=" * 60)
        
        # Показываем статистику
        print("\n📈 СТАТИСТИКА ЗАПОЛНЕНИЯ:")
        print(f"- Всего ферм в базе: {len(farm_stats) + фермы_обработаны}")
        print(f"- Ферм обработано в файле: {фермы_обработаны}")
        print(f"- Ферм осталось в базе (не найдено в файле): {len(farm_stats)}")
        
        if farm_stats:
            print("\nФермы из базы, которых нет в файле:")
            for farm in farm_stats.keys():
                print(f"  - {farm}")
    else:
        print("\n❌ ЗАПОЛНЕНИЕ НЕ УДАЛОСЬ")


if __name__ == '__main__':
    main()