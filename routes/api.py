# routes/api.py - Внутреннее JSON API для динамических интерфейсов
from flask import Blueprint, jsonify
from database import get_db_connection, get_reasons_for_category
from .auth import login_required

api_bp = Blueprint('api', __name__)

@api_bp.route('/get_farms')
@login_required
def get_farms():
    """Получение актуального списка ферм для выпадающих списков фильтров"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT farm_name FROM users WHERE farm_name IS NOT NULL AND farm_name != "" ORDER BY farm_name')
    farms = [r['farm_name'] for r in cursor.fetchall()]
    conn.close()
    return jsonify(farms)

@api_bp.route('/get_reasons/<path:category>')
@login_required
def get_reasons(category):
    """Динамическая подгрузка активных причин выбытия для выбранной категории"""
    reasons = get_reasons_for_category(category)
    return jsonify(reasons)
