# extensions.py - Централизованная инициализация расширений Flask
"""
Предотвращает цикличные импорты (circular imports) между app.py и models.py.
Экземпляры db и migrate инициализируются здесь и связываются с app в фабрике или главном файле.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()
