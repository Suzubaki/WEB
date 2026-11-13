# economics.py - Расчет экономического ущерба и финансовых потерь от выбытия скота (РБ)
import sqlite3
from database import get_db_connection, get_setting

def calculate_economic_losses(start_date=None, end_date=None, farm_name=None):
    """
    Расчет прямых и косвенных экономических потерь от выбытия скота (в BYN)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    where_parts = []
    params = []
    if start_date and end_date:
        where_parts.append("disposal_date BETWEEN ? AND ?")
        params.extend([start_date, end_date])
    if farm_name and farm_name != 'all':
        where_parts.append("farm_name = ?")
        params.append(farm_name)
        
    where_clause = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
    
    cursor.execute(f'''
        SELECT cow_id, ear_tag, farm_name, category, reason, disposal_date, 
               lactation, weight, milk_yield, book_value, age_group 
        FROM cows 
        {where_clause}
        ORDER BY disposal_date DESC
    ''', params)
    
    rows = cursor.fetchall()
    conn.close()
    
    # Считываем нормативы цен из настроек
    meat_price = float(get_setting('meat_price_per_kg', 6.20))
    milk_price = float(get_setting('milk_price_per_kg', 1.18))
    replacement_cost = float(get_setting('replacement_cost', 2950.00))
    
    total_head_count = len(rows)
    total_meat_loss_byn = 0.0
    total_book_value_loss_byn = 0.0
    total_milk_loss_byn = 0.0
    total_loss_byn = 0.0
    
    by_category_loss = {'падёж': 0.0, 'выбраковка': 0.0, 'санитарный': 0.0}
    by_category_heads = {'падёж': 0, 'выбраковка': 0, 'санитарный': 0}
    by_farm_loss = {}
    by_reason_loss = {}
    
    detailed_cows = []
    
    for r in rows:
        cat = r['category']
        weight = float(r['weight']) if r['weight'] else 0.0
        book_val = float(r['book_value']) if r['book_value'] else 0.0
        lactation = int(r['lactation']) if r['lactation'] else 1
        farm = r['farm_name']
        reason = r['reason']
        
        # Если вес не указан, берем нормативный по половозрастной группе
        if weight <= 0:
            ag = r['age_group'] or ''
            if 'телята' in ag.lower():
                weight = 65.0
            elif 'молодняк' in ag.lower() or 'телки' in ag.lower():
                weight = 280.0
            elif 'быч' in ag.lower():
                weight = 420.0
            else:
                weight = 530.0  # стандартная дойная корова
                
        # Если балансовая стоимость не указана в карточке, берем норматив
        if book_val <= 0:
            ag = r['age_group'] or ''
            if 'телята' in ag.lower():
                book_val = 350.0
            elif 'телки' in ag.lower() or 'молодняк' in ag.lower():
                book_val = 1450.0
            else:
                # Амортизация коровы в зависимости от лактации
                depreciation_factor = max(0.2, 1.0 - (lactation - 1) * 0.18)
                book_val = replacement_cost * depreciation_factor
                
        # Расчет в зависимости от категории:
        cow_loss = 0.0
        meat_loss = 0.0
        milk_loss = 0.0
        
        if cat == 'падёж':
            # При падеже теряется 100% стоимости животного (и мясо утилизируется, и баланс утрачен)
            meat_loss = weight * meat_price
            cow_loss = max(book_val, meat_loss)
            total_meat_loss_byn += meat_loss
            total_book_value_loss_byn += book_val
        elif cat == 'санитарный':
            # Санитарный убой: реализация на санбойню со скидкой (уценка 35-50%)
            realization = weight * meat_price * 0.55
            cow_loss = max(0.0, book_val - realization)
        elif cat == 'выбраковка':
            # Преждевременная выбраковка: разница между ценностью продуктивного животного и мясом
            meat_revenue = weight * meat_price * 0.90
            direct_deprec = max(0.0, book_val - meat_revenue)
            # Недополученное молоко (если корова выбыла до 3-4 лактации)
            if lactation < 4:
                lost_lactations = 4 - lactation
                milk_yield_est = float(r['milk_yield']) if r['milk_yield'] else 6000.0
                milk_loss = lost_lactations * milk_yield_est * milk_price * 0.12  # маржинальная упущенная прибыль
                total_milk_loss_byn += milk_loss
            cow_loss = direct_deprec + milk_loss
            
        total_loss_byn += cow_loss
        by_category_loss[cat] = by_category_loss.get(cat, 0.0) + cow_loss
        by_category_heads[cat] = by_category_heads.get(cat, 0) + 1
        
        by_farm_loss[farm] = by_farm_loss.get(farm, 0.0) + cow_loss
        by_reason_loss[reason] = by_reason_loss.get(reason, 0.0) + cow_loss
        
        detailed_cows.append({
            'cow_id': r['cow_id'],
            'ear_tag': r['ear_tag'],
            'farm_name': farm,
            'category': cat,
            'reason': reason,
            'disposal_date': r['disposal_date'],
            'weight': weight,
            'book_value': round(book_val, 2),
            'calculated_loss': round(cow_loss, 2)
        })
        
    # Сортируем топ-причины по убыванию ущерба
    top_reasons = sorted(by_reason_loss.items(), key=lambda x: x[1], reverse=True)[:8]
    
    return {
        'total_head_count': total_head_count,
        'total_loss_byn': round(total_loss_byn, 2),
        'avg_loss_per_head': round(total_loss_byn / total_head_count, 2) if total_head_count > 0 else 0.0,
        'by_category_loss': {k: round(v, 2) for k, v in by_category_loss.items()},
        'by_category_heads': by_category_heads,
        'by_farm_loss': {k: round(v, 2) for k, v in by_farm_loss.items()},
        'top_reasons': [{'reason': r, 'loss': round(l, 2)} for r, l in top_reasons],
        'prices_used': {
            'meat_price': meat_price,
            'milk_price': milk_price,
            'replacement_cost': replacement_cost
        },
        'cows': detailed_cows
    }
