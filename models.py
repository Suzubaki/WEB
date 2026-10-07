# models.py - SQLAlchemy Модели данных предметной области
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db

class User(db.Model):
    """
    Модель пользователя информационной системы.
    Поддерживает роли:
    - 'admin': главный зоотехник / ветврач холдинга (доступ ко всем хозяйствам)
    - 'farm': зоотехник / ветврач конкретного подразделения МТФ
    """
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    user_type = db.Column(db.String(20), nullable=False, default='farm')  # 'admin' или 'farm'
    farm_name = db.Column(db.String(120), nullable=True)                  # МТФ / ферма
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Отношения (Relationships) с записями коров
    cows_created = db.relationship(
        'Cow',
        foreign_keys='Cow.created_by',
        backref=db.backref('creator', lazy='joined'),
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    cows_updated = db.relationship(
        'Cow',
        foreign_keys='Cow.updated_by',
        backref=db.backref('updater', lazy='joined'),
        lazy='dynamic'
    )

    def __init__(self, username=None, password_hash=None, user_type='farm', farm_name=None, id=None, created_at=None, **kwargs):
        if id is not None:
            self.id = id
        self.username = username
        self.password_hash = password_hash
        self.user_type = user_type
        self.farm_name = farm_name
        self.created_at = created_at or datetime.utcnow()

    def __repr__(self):
        return f"<User id={self.id} username='{self.username}' type='{self.user_type}' farm='{self.farm_name}'>"

    @staticmethod
    def create_password_hash(password):
        """Хеширование пароля с криптографической солью"""
        return generate_password_hash(password)

    def check_password(self, password):
        """Проверка введенного пароля против сохраненного хеша"""
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        """Проверка наличия административных полномочий"""
        return self.user_type == 'admin'

    def is_farm_user(self):
        """Проверка принадлежности к уровню хозяйства / фермы"""
        return self.user_type == 'farm'

    def to_dict(self):
        """Сериализация данных пользователя в словарь"""
        return {
            'id': self.id,
            'username': self.username,
            'user_type': self.user_type,
            'farm_name': self.farm_name,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if isinstance(self.created_at, datetime) else self.created_at
        }


class Cow(db.Model):
    """
    Модель карточки выбытия животного крупного рогатого скота (КРС).
    Содержит зоотехнические, ветеринарные, экономические и пат-данные.
    """
    __tablename__ = 'cows'
    __table_args__ = (
        db.Index('idx_cows_farm_date', 'farm_name', 'disposal_date'),
        db.Index('idx_cows_category_date', 'category', 'disposal_date'),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    cow_id = db.Column(db.String(50), nullable=False, index=True)         # Системный номер ('МТФ1-001')
    ear_tag = db.Column(db.String(50), nullable=True, index=True)         # Инвентарный / ушной номер AITS (РБ)
    farm_name = db.Column(db.String(120), nullable=False, index=True)     # Название МТФ / фермы
    category = db.Column(db.String(50), nullable=False, index=True)       # 'падёж', 'выбраковка', 'санитарный'
    reason = db.Column(db.String(255), nullable=False)                    # Причина выбытия (диагноз)
    disposal_date = db.Column(db.String(10), nullable=False, index=True)  # Дата выбытия (ГГГГ-ММ-ДД)
    lactation = db.Column(db.Integer, nullable=True)                      # Номер лактации
    weight = db.Column(db.Float, nullable=True)                           # Живая масса (кг)
    notes = db.Column(db.Text, nullable=True)                             # Особые отметки / примечания
    age_group = db.Column(db.String(80), nullable=True)                   # Половозрастная группа (ПВГ)
    breed = db.Column(db.String(80), nullable=True)                       # Порода
    milk_yield = db.Column(db.Float, nullable=True)                       # Надой за лактацию (кг)
    book_value = db.Column(db.Float, nullable=True)                       # Балансовая стоимость (BYN)
    
    # Системный аудит
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow, nullable=True)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    def __init__(self, id=None, cow_id=None, farm_name=None, category=None, reason=None, disposal_date=None,
                 ear_tag=None, lactation=None, weight=None, notes=None, age_group=None, breed=None,
                 milk_yield=None, book_value=None, created_at=None, created_by=None,
                 updated_at=None, updated_by=None, **kwargs):
        if id is not None:
            self.id = id
        self.cow_id = cow_id
        self.ear_tag = ear_tag
        self.farm_name = farm_name
        self.category = category
        self.reason = reason
        self.disposal_date = str(disposal_date) if disposal_date else None
        self.lactation = lactation
        self.weight = weight
        self.notes = notes
        self.age_group = age_group
        self.breed = breed
        self.milk_yield = milk_yield
        self.book_value = book_value
        self.created_at = created_at or datetime.utcnow()
        self.created_by = created_by
        self.updated_at = updated_at
        self.updated_by = updated_by

    def __repr__(self):
        return f"<Cow id={self.id} num='{self.cow_id}' tag='{self.ear_tag}' farm='{self.farm_name}' cat='{self.category}'>"

    def to_dict(self):
        """Сериализация модели в словарь для шаблонов и JSON API"""
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
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if isinstance(self.created_at, datetime) else str(self.created_at),
            'created_by': self.created_by,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if isinstance(self.updated_at, datetime) else str(self.updated_at) if self.updated_at else None,
            'updated_by': self.updated_by
        }
