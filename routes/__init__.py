# routes/__init__.py
"""
Пакет маршрутов Flask Blueprints приложения учёта выбытия крупного рогатого скота (РБ).
Модульная архитектура:
- main: стартовая страница и главный аналитический дашборд
- auth: авторизация, профили, управление пользователями
- cows: реестр коров, добавление, редактирование, удаление, импорт Excel/CSV
- reports: официальные акты (форма 209-АПК, 210-АПК, реестры AITS, сводки)
- admin: справочник причин выбытия, журнал аудита, бэкапы БД, тест-данные
- api: JSON API для динамической подгрузки ферм и причин
"""

from .main import main_bp
from .auth import auth_bp
from .cows import cows_bp
from .reports import reports_bp
from .admin import admin_bp
from .api import api_bp

__all__ = [
    'main_bp',
    'auth_bp',
    'cows_bp',
    'reports_bp',
    'admin_bp',
    'api_bp'
]
