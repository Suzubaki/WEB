# autopsy.py - Модуль патологоанатомического вскрытия трупов животных (РБ)
import sqlite3
import json
from datetime import datetime
from database import get_db_connection, log_audit_event

def get_cow_for_autopsy(cow_id):
    """Получение информации о животном для составления протокола вскрытия"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM cows WHERE cow_id = ? OR id = ?', (cow_id, cow_id))
    cow = cursor.fetchone()
    conn.close()
    return dict(cow) if cow else None

def save_autopsy_protocol(cow_id, data, username, ip_address=None):
    """
    Сохранение протокола вскрытия в БД
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Сериализуем детальные поля протокола в JSON
    protocol_details = {
        'anamnesis': data.get('anamnesis', ''),
        'external_exam': data.get('external_exam', ''),
        'respiratory': data.get('respiratory', ''),
        'cardiovascular': data.get('cardiovascular', ''),
        'digestive': data.get('digestive', ''),
        'liver_spleen': data.get('liver_spleen', ''),
        'urinary_genital': data.get('urinary_genital', ''),
        'pat_diagnosis': data.get('pat_diagnosis', ''),
        'conclusion': data.get('conclusion', ''),
        'lab_tests': data.get('lab_tests', 'Патматериал направлен в райветстанцию (сибирская язва исключена)'),
        'lab_doc_num': data.get('lab_doc_num', ''),
        'lab_date': data.get('lab_date', '')
    }
    protocol_json = json.dumps(protocol_details, ensure_ascii=False)
    
    autopsy_vet = data.get('autopsy_vet', username)
    autopsy_date = data.get('autopsy_date', datetime.now().strftime('%Y-%m-%d'))
    autopsy_lab_sample = data.get('autopsy_lab_sample', 'Да')
    
    cursor.execute('''
        UPDATE cows 
        SET autopsy_protocol = ?,
            autopsy_vet = ?,
            autopsy_date = ?,
            autopsy_lab_sample = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE cow_id = ? OR id = ?
    ''', (protocol_json, autopsy_vet, autopsy_date, autopsy_lab_sample, cow_id, cow_id))
    
    conn.commit()
    conn.close()
    
    log_audit_event(
        username=username,
        farm_name=data.get('farm_name', 'МТФ'),
        action='UPDATE',
        entity_type='COW',
        entity_id=cow_id,
        details=f"Оформлен протокол патологоанатомического вскрытия для животного {cow_id}",
        ip_address=ip_address
    )
    return True

def parse_autopsy_protocol(protocol_text):
    """Парсинг JSON протокола в словарь"""
    if not protocol_text:
        return {}
    try:
        return json.loads(protocol_text)
    except Exception:
        return {'raw_text': protocol_text}
