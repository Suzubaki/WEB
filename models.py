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
    lactation_days = db.Column(db.Integer, nullable=True)                 # Дни лактации (DIM - Days in Milk)
    lactation_phase = db.Column(db.String(80), nullable=True)             # Фаза лактации (Новотел, Раздой, Середина, Спад, Сухостой, Молодняк)
    breed = db.Column(db.String(80), nullable=True)                       # Порода
    milk_yield = db.Column(db.Float, nullable=True)                       # Надой за лактацию (кг)
    book_value = db.Column(db.Float, nullable=True)                       # Балансовая стоимость (BYN)
    is_pregnant = db.Column(db.Integer, default=0, nullable=True)         # Стельность (1: да, 0: нет)
    gestation_days = db.Column(db.Integer, default=0, nullable=True)      # Срок стельности (дней/месяцев)
    
    # Системный аудит
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow, nullable=True)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    def __init__(self, id=None, cow_id=None, farm_name=None, category=None, reason=None, disposal_date=None,
                 ear_tag=None, lactation=None, weight=None, notes=None, age_group=None,
                 lactation_days=None, lactation_phase=None, breed=None,
                 milk_yield=None, book_value=None, is_pregnant=0, gestation_days=0, created_at=None, created_by=None,
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
        self.lactation_days = lactation_days
        self.lactation_phase = lactation_phase
        self.breed = breed
        self.milk_yield = milk_yield
        self.book_value = book_value
        self.created_at = created_at or datetime.utcnow()
        self.created_by = created_by
        self.updated_at = updated_at
        self.updated_by = updated_by

    def __repr__(self):
        return f"<Cow id={self.id} num='{self.cow_id}' tag='{self.ear_tag}' farm='{self.farm_name}' cat='{self.category}' dim={self.lactation_days}>"

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
            'lactation_days': self.lactation_days,
            'lactation_phase': self.lactation_phase,
            'breed': self.breed,
            'milk_yield': self.milk_yield,
            'book_value': self.book_value,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if isinstance(self.created_at, datetime) else str(self.created_at),
            'created_by': self.created_by,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if isinstance(self.updated_at, datetime) else str(self.updated_at) if self.updated_at else None,
            'updated_by': self.updated_by
        }


class StillbirthRecord(db.Model):
    """
    Модель учёта мертворождений и абортов (Акушерско-гинекологический журнал).
    Не смешивается с выбытием взрослых коров!
    """
    __tablename__ = 'stillbirth_records'
    __table_args__ = (
        db.Index('idx_stillbirth_farm_date', 'farm_name', 'event_date'),
        db.Index('idx_stillbirth_event_type', 'event_type'),
        db.Index('idx_stillbirth_mother_tag', 'mother_tag'),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    record_code = db.Column(db.String(50), nullable=False, index=True)   # Системный номер ('МТК Цегельня-М001')
    farm_name = db.Column(db.String(120), nullable=False, index=True)   # Название МТФ
    event_date = db.Column(db.String(10), nullable=False, index=True)   # Дата события (ГГГГ-ММ-ДД)
    mother_tag = db.Column(db.String(50), nullable=True, index=True)    # Инвентарный / AITS номер матери (мать жива!)
    mother_group = db.Column(db.String(80), nullable=True)              # Половозрастная группа матери
    event_type = db.Column(db.String(100), nullable=False)              # Мертворождение в срок / Аборт / др.
    fetus_sex = db.Column(db.String(40), nullable=True)                 # Пол плода
    fetus_weight = db.Column(db.Float, nullable=True)                   # Масса плода (кг)
    gestation_days = db.Column(db.Integer, default=0, nullable=True)    # Срок стельности на момент события (дней)
    cause = db.Column(db.String(255), nullable=False)                   # Причина гибели плода
    mother_condition = db.Column(db.String(120), nullable=True)         # Состояние матери после отёла
    attendant = db.Column(db.String(120), nullable=True)                # Принял отёл (ветврач / техник)
    notes = db.Column(db.Text, nullable=True)                           # Заключение / примечания
    
    # Системный аудит
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow, nullable=True)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'record_code': self.record_code,
            'farm_name': self.farm_name,
            'event_date': self.event_date,
            'mother_tag': self.mother_tag,
            'mother_group': self.mother_group,
            'event_type': self.event_type,
            'fetus_sex': self.fetus_sex,
            'fetus_weight': self.fetus_weight,
            'gestation_days': self.gestation_days,
            'cause': self.cause,
            'mother_condition': self.mother_condition,
            'attendant': self.attendant,
            'notes': self.notes,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if isinstance(self.created_at, datetime) else str(self.created_at),
            'created_by': self.created_by,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if isinstance(self.updated_at, datetime) else str(self.updated_at) if self.updated_at else None,
            'updated_by': self.updated_by
        }

