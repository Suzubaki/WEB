# models.py - Модели данных приложения
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

class User:
    def __init__(self, id, username, password_hash, user_type, farm_name=None, created_at=None):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.user_type = user_type  # 'admin' или 'farm'
        self.farm_name = farm_name
        self.created_at = created_at or datetime.now()

    @staticmethod
    def create_password_hash(password):
        return generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.user_type == 'admin'

    def is_farm_user(self):
        return self.user_type == 'farm'

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'user_type': self.user_type,
            'farm_name': self.farm_name,
            'created_at': self.created_at
        }

class Cow:
    def __init__(self, id, cow_id, farm_name, category, reason, disposal_date, 
                 ear_tag=None, lactation=None, weight=None, notes=None,
                 age_group=None, breed=None, milk_yield=None, book_value=None,
                 autopsy_protocol=None, autopsy_vet=None, autopsy_date=None, autopsy_lab_sample=None,
                 created_at=None, created_by=None, updated_at=None, updated_by=None):
        self.id = id
        self.cow_id = cow_id              # Системный номер выбытия ('Farm1-001')
        self.ear_tag = ear_tag            # Инвентарный / ушной номер AITS (РБ)
        self.farm_name = farm_name
        self.category = category          # 'падёж', 'выбраковка', 'санитарный'
        self.reason = reason              # Причина выбытия
        self.disposal_date = disposal_date
        self.lactation = lactation        # Номер лактации / возраст
        self.weight = weight              # Живая масса (кг)
        self.notes = notes                # Примечание / заключение ветврача
        self.age_group = age_group        # Половозрастная группа скота (ПВГ)
        self.breed = breed                # Порода
        self.milk_yield = milk_yield      # Надой за лактацию (кг)
        self.book_value = book_value      # Балансовая стоимость (BYN)
        self.autopsy_protocol = autopsy_protocol  # Протокол вскрытия
        self.autopsy_vet = autopsy_vet    # Ветврач вскрытия
        self.autopsy_date = autopsy_date  # Дата вскрытия
        self.autopsy_lab_sample = autopsy_lab_sample  # Лабораторные пробы
        self.created_at = created_at or datetime.now()
        self.created_by = created_by
        self.updated_at = updated_at
        self.updated_by = updated_by

    def to_dict(self):
        return {
            'id': self.id,
            'cow_id': self.cow_id,
            'ear_tag': self.ear_tag,
            'farm_name': self.farm_name,
            'category': self.category,
            'reason': self.reason,
            'disposal_date': self.disposal_date,
            'lactation': self.lactation,
            'weight': self.weight,
            'notes': self.notes,
            'age_group': self.age_group,
            'breed': self.breed,
            'milk_yield': self.milk_yield,
            'book_value': self.book_value,
            'autopsy_protocol': self.autopsy_protocol,
            'autopsy_vet': self.autopsy_vet,
            'autopsy_date': self.autopsy_date,
            'autopsy_lab_sample': self.autopsy_lab_sample,
            'created_at': self.created_at,
            'created_by': self.created_by,
            'updated_at': self.updated_at,
            'updated_by': self.updated_by
        }
