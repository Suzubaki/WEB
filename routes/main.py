# routes/main.py - Главная страница и дашборд
import os
from flask import Blueprint, render_template, request, redirect, url_for, session, send_file, Response
from config import Config
from .auth import login_required
from charts import (
    get_anomaly_alerts, get_user_statistics, get_dashboard_full_data
)

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Главный входной маршрут - перенаправление на дашборд или логин"""
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')

@main_bp.route('/dashboard')
@login_required
def dashboard():
    """Аналитический дашборд мониторинга выбытия КРС"""
    user_type = session.get('user_type')
    farm_name = session.get('farm_name')
    
    period = request.args.get('period', 'all')
    custom_start = request.args.get('custom_start')
    custom_end = request.args.get('custom_end')
    
    selected_farm = farm_name
    if user_type == 'admin':
        selected_farm = request.args.get('farm', 'all')
        
    dashboard_data = get_dashboard_full_data(
        user_type=user_type,
        farm_name=selected_farm,
        period=period,
        custom_start=custom_start,
        custom_end=custom_end
    )
    alerts = get_anomaly_alerts(user_type, selected_farm)
    user_stats_data = get_user_statistics() if user_type == 'admin' else None
    
    return render_template('dashboard.html',
                           user_type=user_type,
                           farm_name=farm_name,
                           selected_farm=selected_farm,
                           d=dashboard_data,
                           alerts=alerts,
                           user_stats_data=user_stats_data)
