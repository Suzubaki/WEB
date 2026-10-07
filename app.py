# app.py - Главная точка входа и фабрика приложения Flask
import os
from flask import Flask, session, send_file, Response, url_for

from config import Config
from database import init_db
from auth import get_user_by_id

# Импорт Blueprint'ов новой модульной архитектуры
from routes import (
    main_bp,
    auth_bp,
    cows_bp,
    reports_bp,
    admin_bp,
    api_bp
)

app = Flask(__name__)
app.config.from_object(Config)

# Инициализация Flask-SQLAlchemy и Flask-Migrate
try:
    from extensions import db, migrate
    db.init_app(app)
    migrate.init_app(app, db)
except ImportError:
    db = None
    migrate = None

# Векторный логотип ОАО «Новая Припять» (Официальный золотой колос)
LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 240" width="100%" height="100%">
  <defs>
    <linearGradient id="wheatGrad1" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#fbbf24" />
      <stop offset="45%" stop-color="#f59e0b" />
      <stop offset="100%" stop-color="#d97706" />
    </linearGradient>
    <linearGradient id="wheatGrad2" x1="100%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#fde047" />
      <stop offset="50%" stop-color="#eab308" />
      <stop offset="100%" stop-color="#b45309" />
    </linearGradient>
    <linearGradient id="wheatTip" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#f59e0b" />
      <stop offset="100%" stop-color="#f97316" />
    </linearGradient>
    <filter id="softShadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="1.5" stdDeviation="1.5" flood-color="#b45309" flood-opacity="0.25" />
    </filter>
  </defs>
  <rect width="240" height="240" fill="#ffffff" rx="16" />
  <g id="wheat-ear" filter="url(#softShadow)">
    <path d="M42 120 C38 106, 52 92, 60 90 C66 94, 62 108, 48 122 Z" fill="url(#wheatGrad1)" />
    <path d="M44 118 Q54 100 60 92" stroke="#fef08a" stroke-width="1" fill="none" opacity="0.6" />
    <path d="M52 122 C56 112, 70 106, 78 108 C80 116, 68 126, 54 124 Z" fill="url(#wheatGrad2)" />
    <path d="M60 92 C62 80, 80 72, 90 72 C94 78, 88 92, 74 102 Z" fill="url(#wheatGrad1)" />
    <path d="M64 90 Q80 76 89 74" stroke="#fef08a" stroke-width="1.2" fill="none" opacity="0.6" />
    <path d="M76 104 C82 94, 98 90, 106 94 C108 102, 94 114, 80 110 Z" fill="url(#wheatGrad2)" />
    <path d="M90 73 C96 66, 116 64, 126 68 C128 76, 116 88, 102 92 Z" fill="url(#wheatGrad1)" />
    <path d="M96 72 Q114 66 124 70" stroke="#fef08a" stroke-width="1.2" fill="none" opacity="0.6" />
    <path d="M104 94 C112 86, 130 84, 138 90 C138 98, 124 106, 110 102 Z" fill="url(#wheatGrad2)" />
    <path d="M124 70 C134 68, 152 72, 160 80 C158 88, 142 94, 130 90 Z" fill="url(#wheatGrad1)" />
    <path d="M128 72 Q146 72 157 80" stroke="#fef08a" stroke-width="1.2" fill="none" opacity="0.6" />
    <path d="M136 90 C146 86, 160 88, 168 96 C164 104, 150 106, 138 98 Z" fill="url(#wheatGrad2)" />
    <path d="M156 82 C166 82, 180 88, 186 96 C182 102, 168 104, 158 96 Z" fill="url(#wheatGrad1)" />
    <path d="M168 96 C176 96, 192 100, 196 106 C190 110, 178 110, 170 102 Z" fill="url(#wheatTip)" />
    <path d="M184 92 C196 90, 206 91, 210 93" stroke="#eab308" stroke-width="1.5" stroke-linecap="round" fill="none" />
    <path d="M190 98 C202 96, 212 97, 216 100" stroke="#f59e0b" stroke-width="1.8" stroke-linecap="round" fill="none" />
    <path d="M194 104 C204 102, 214 105, 218 108" stroke="#d97706" stroke-width="1.6" stroke-linecap="round" fill="none" />
    <path d="M188 108 C198 108, 208 112, 212 116" stroke="#b45309" stroke-width="1.3" stroke-linecap="round" fill="none" />
    <path d="M174 104 C184 106, 196 112, 202 118" stroke="#d97706" stroke-width="1.2" stroke-linecap="round" fill="none" />
  </g>
  <text x="120" y="148" font-family="'Trebuchet MS', 'Segoe UI', Arial, sans-serif" font-size="25.5" font-weight="900" font-style="italic" fill="#212529" text-anchor="middle" letter-spacing="-0.3">Новая Припять</text>
  <text x="120" y="166" font-family="'Segoe UI', Roboto, Helvetica, Arial, sans-serif" font-size="8.2" font-weight="700" fill="#262a2e" text-anchor="middle" letter-spacing="1.2">ОТКРЫТОЕ АКЦИОНЕРНОЕ ОБЩЕСТВО</text>
</svg>"""

def _serve_logo(filename):
    search_dirs = [
        os.path.join(app.root_path, 'static', 'img'),
        os.path.join(app.root_path, 'public', 'img'),
        os.path.join(app.root_path, 'img')
    ]
    for d in search_dirs:
        candidate = os.path.join(d, filename)
        if os.path.exists(candidate) and os.path.isfile(candidate):
            mimetype = 'image/jpeg' if filename.endswith(('.jpg', '.jpeg')) else ('image/png' if filename.endswith('.png') else 'image/svg+xml')
            return send_file(candidate, mimetype=mimetype)
    return Response(LOGO_SVG, mimetype='image/svg+xml')

# Регистрация маршрутов раздачи статических ассетов
@app.route('/img/<path:filename>')
@app.route('/static/img/<path:filename>')
def serve_img(filename):
    return _serve_logo(filename)

@app.route('/favicon.ico')
@app.route('/favicon.png')
@app.route('/favicon.svg')
def serve_favicon():
    return Response(LOGO_SVG, mimetype='image/svg+xml')

@app.route('/logo.jpg')
@app.route('/logo.svg')
@app.route('/img/logo.jpg')
@app.route('/img/logo.svg')
def serve_logo_direct():
    return _serve_logo('logo.svg')

# -------------------- РЕГИСТРАЦИЯ BLUEPRINTS --------------------
app.register_blueprint(main_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(cows_bp)
app.register_blueprint(reports_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(api_bp)

# Синхронизация данных пользователя в сессии перед каждым запросом
@app.before_request
def sync_current_user_session():
    if 'user_id' in session:
        user = get_user_by_id(session['user_id'])
        if user:
            session['farm_name'] = user.farm_name
            session['username'] = user.username
            session['user_type'] = user.user_type

# Обратная совместимость вызовов url_for в существующих шаблонах
@app.context_processor
def override_url_for():
    def custom_url_for(endpoint, **values):
        aliases = {
            'index': 'main.index',
            'dashboard': 'main.dashboard',
            'login': 'auth.login',
            'logout': 'auth.logout',
            'register': 'auth.register',
            'user_management': 'auth.user_management',
            'edit_user': 'auth.edit_user',
            'delete_user': 'auth.delete_user',
            'view_cows': 'cows.view_cows',
            'cows': 'cows.view_cows',
            'add_cow': 'cows.add_cow',
            'edit_cow': 'cows.edit_cow',
            'delete_cow': 'cows.delete_cow',
            'bulk_delete_cows': 'cows.bulk_delete_cows',
            'delete_multiple_cows': 'cows.delete_multiple_cows',
            'add_cows_dynamic': 'cows.add_cows_dynamic',
            'add_multiple_cows': 'cows.add_multiple_cows',
            'import_cows': 'cows.import_cows',
            'download_import_template': 'cows.download_import_template',
            'reports': 'reports.reports',
            'generate_report': 'reports.generate_report',
            'generate_original_excel_route': 'reports.generate_original_excel',
            'generate_original_excel': 'reports.generate_original_excel',
            'manage_reasons': 'admin.manage_reasons',
            'reasons': 'admin.manage_reasons',
            'toggle_reason': 'admin.toggle_reason',
            'delete_reason': 'admin.delete_reason',
            'audit_log': 'admin.audit_log',
            'backup_page': 'admin.backup',
            'backup': 'admin.backup',
            'download_db_backup': 'admin.download_backup',
            'restore_db_backup': 'admin.restore_backup',
            'seed_test_data': 'admin.seed_test_data',
            'get_farms': 'api.get_farms',
            'get_reasons': 'api.get_reasons'
        }
        resolved = aliases.get(endpoint, endpoint)
        try:
            return url_for(resolved, **values)
        except Exception:
            return url_for(endpoint, **values)
    return dict(url_for=custom_url_for)

if __name__ == '__main__':
    init_db()
    from create_users import create_default_users
    create_default_users()
    app.run(host='0.0.0.0', port=3000, debug=True)
