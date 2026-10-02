# aits_export.py - Экспорт реестра выбытия скота для ГИС «AITS» (Республика Беларусь)
import sqlite3
import csv
import io
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
from database import get_db_connection, get_setting

# Коды событий выбытия по классификатору ГИС AITS (РБ)
AITS_EVENT_CODES = {
    'падёж': '01',        # Падёж (гибель) животного
    'санитарный': '02',   # Вынужденный прирез / убой на санбойне
    'выбраковка': '03'    # Выбраковка / снятие с основного стада
}

def generate_aits_csv_registry(start_date, end_date, farm_name=None):
    """
    Генерирует реестр выбытия животных в формате CSV для импорта в ГИС AITS (aits.by)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    where = "WHERE disposal_date BETWEEN ? AND ?"
    params = [start_date, end_date]
    if farm_name and farm_name != 'all':
        where += " AND farm_name = ?"
        params.append(farm_name)
        
    cursor.execute(f'''
        SELECT cow_id, ear_tag, farm_name, category, reason, disposal_date, lactation, weight, age_group 
        FROM cows 
        {where}
        ORDER BY disposal_date ASC
    ''', params)
    rows = cursor.fetchall()
    conn.close()
    
    unp = get_setting('farm_unp', '190000000')
    org_name = get_setting('farm_org_name', 'Сельхозорганизация РБ')
    
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    
    # Заголовок реестра по регламенту информационного взаимодействия с ГИС AITS
    writer.writerow([
        'УНП владельца',
        'Сельхозорганизация',
        'Подразделение (МТФ)',
        'Идентификационный номер животного (AITS)',
        'Код события выбытия',
        'Наименование события',
        'Дата выбытия (ДД.ММ.ГГГГ)',
        'Диагноз / Причина',
        'Живая масса (кг)',
        'Половозрастная группа',
        'Номер первичного акта (209-АПК)'
    ])
    
    for r in rows:
        tag = (r['ear_tag'] or '').strip()
        # Преобразуем дату в ДД.ММ.ГГГГ
        try:
            d_obj = datetime.strptime(r['disposal_date'], '%Y-%m-%d')
            formatted_date = d_obj.strftime('%d.%m.%Y')
        except Exception:
            formatted_date = r['disposal_date']
            
        event_code = AITS_EVENT_CODES.get(r['category'], '01')
        event_desc = 'Падёж' if r['category'] == 'падёж' else ('Санитарный убой' if r['category'] == 'санитарный' else 'Выбраковка')
        
        writer.writerow([
            unp,
            org_name,
            r['farm_name'],
            tag if tag else f"БЕЗ-БИРКИ-{r['cow_id']}",
            event_code,
            event_desc,
            formatted_date,
            r['reason'],
            r['weight'] or '',
            r['age_group'] or 'КРС',
            f"Акт 209-АПК от {formatted_date}"
        ])
        
    output.seek(0)
    return output.getvalue()

def generate_aits_xml_registry(start_date, end_date, farm_name=None):
    """
    Генерирует XML-документ реестра выбытия согласно спецификации обмена данными ГИС AITS
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    where = "WHERE disposal_date BETWEEN ? AND ?"
    params = [start_date, end_date]
    if farm_name and farm_name != 'all':
        where += " AND farm_name = ?"
        params.append(farm_name)
        
    cursor.execute(f'''
        SELECT cow_id, ear_tag, farm_name, category, reason, disposal_date, weight, age_group 
        FROM cows 
        {where}
        ORDER BY disposal_date ASC
    ''', params)
    rows = cursor.fetchall()
    conn.close()
    
    unp = get_setting('farm_unp', '190000000')
    org_name = get_setting('farm_org_name', 'Сельхозорганизация РБ')
    
    root = ET.Element('AitsDisposalRegistry', {
        'version': '1.0',
        'generatedAt': datetime.now().isoformat(),
        'unp': unp,
        'organization': org_name
    })
    
    period = ET.SubElement(root, 'ReportPeriod')
    ET.SubElement(period, 'StartDate').text = start_date
    ET.SubElement(period, 'EndDate').text = end_date
    
    items = ET.SubElement(root, 'AnimalDisposals', {'count': str(len(rows))})
    
    for r in rows:
        animal = ET.SubElement(items, 'DisposalRecord')
        ET.SubElement(animal, 'InternalId').text = str(r['cow_id'])
        ET.SubElement(animal, 'AnimalId').text = str(r['ear_tag'] or '')
        ET.SubElement(animal, 'HoldingUnit').text = str(r['farm_name'])
        
        event_code = AITS_EVENT_CODES.get(r['category'], '01')
        ET.SubElement(animal, 'EventCode').text = event_code
        ET.SubElement(animal, 'Category').text = str(r['category'])
        ET.SubElement(animal, 'EventDate').text = str(r['disposal_date'])
        ET.SubElement(animal, 'ReasonDiagnosis').text = str(r['reason'])
        if r['weight']:
            ET.SubElement(animal, 'LiveWeightKg').text = str(r['weight'])
        if r['age_group']:
            ET.SubElement(animal, 'AgeGroup').text = str(r['age_group'])
            
    xml_str = ET.tostring(root, encoding='utf-8')
    parsed = minidom.parseString(xml_str)
    return parsed.toprettyxml(indent="  ", encoding="utf-8")
