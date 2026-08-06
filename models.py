from datetime import datetime

class Cow:
    """Модель данных коровы"""
    
    def __init__(self, cow_id, farm_name, category, reason, disposal_date, created_by=None):
        self.cow_id = cow_id
        self.farm_name = farm_name
        self.category = category
        self.reason = reason
        self.disposal_date = disposal_date
        self.created_by = created_by
        
    def to_dict(self):
        """Преобразование в словарь"""
        return {
            'cow_id': self.cow_id,
            'farm_name': self.farm_name,
            'category': self.category,
            'reason': self.reason,
            'disposal_date': self.disposal_date
        }
    
    @classmethod
    def from_form_data(cls, form_data):
        """Создание объекта из данных формы"""
        return cls(
            cow_id=form_data.get('cow_id'),
            farm_name=form_data.get('farm_name'),
            category=form_data.get('category'),
            reason=form_data.get('reason'),
            disposal_date=form_data.get('disposal_date')
        )

class Report:
    """Модель для генерации отчётов"""
    
    def __init__(self, data, farm_name=None, start_date=None, end_date=None):
        self.data = data
        self.farm_name = farm_name
        self.start_date = start_date
        self.end_date = end_date
        self.generated_at = datetime.now()
    
    def generate_summary(self):
        """Генерация сводки по отчёту"""
        summary = {
            'total_cows': len(self.data),
            'by_category': {},
            'by_reason': {},
            'by_farm': {}
        }
        
        for cow in self.data:
            # Статистика по категориям
            summary['by_category'][cow['category']] = summary['by_category'].get(cow['category'], 0) + 1
            
            # Статистика по причинам
            summary['by_reason'][cow['reason']] = summary['by_reason'].get(cow['reason'], 0) + 1
            
            # Статистика по фермам
            summary['by_farm'][cow['farm_name']] = summary['by_farm'].get(cow['farm_name'], 0) + 1
        
        return summary