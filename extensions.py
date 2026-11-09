# extensions.py - Централизованная инициализация расширений Flask
"""
Предотвращает цикличные импорты (circular imports) между app.py и models.py.
Содержит безопасный fallback при несовместимости SQLAlchemy с Python 3.13.
"""
try:
    from flask_sqlalchemy import SQLAlchemy
    from flask_migrate import Migrate
    db = SQLAlchemy()
    migrate = Migrate()
except Exception as _ext_err:
    class DummyDB:
        Model = object
        def Column(self, *args, **kwargs): return None
        def Integer(self, *args, **kwargs): return None
        def String(self, *args, **kwargs): return None
        def Float(self, *args, **kwargs): return None
        def DateTime(self, *args, **kwargs): return None
        def Text(self, *args, **kwargs): return None
        def ForeignKey(self, *args, **kwargs): return None
        def Index(self, *args, **kwargs): return None
        def relationship(self, *args, **kwargs): return None
        def backref(self, *args, **kwargs): return None
        def init_app(self, app): pass

    class DummyMigrate:
        def init_app(self, app, db): pass

    db = DummyDB()
    migrate = DummyMigrate()

