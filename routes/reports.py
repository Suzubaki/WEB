# routes/reports.py - Генерация отраслевых и ведомственных отчётов (РБ)
import io
from datetime import datetime
from flask import (
    Blueprint, render_template, request, session, 
    send_file, Response
)
from database import get_db_connection, get_setting
from matrix_report import generate_matrix_excel_report
from report_generator import (
    generate_csv_report, generate_simple_excel_report, 
    generate_form_209_apk_excel
)
from form_210_apk import generate_form_210_apk_excel
from aits_export import generate_aits_csv_registry, generate_aits_xml_registry
from structured_report import generate_structured_excel_report
from fill_original_excel import generate_official_template_excel
from .auth import login_required, admin_required

reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/reports')
@login_required
def reports():
    """Центр формирования зооветеринарной отчетности"""
    return render_template('reports.html', user_type=session.get('user_type'))

@reports_bp.route('/generate_report', methods=['POST'])
@login_required
def generate_report():
    """Формирование сводных актов, списков и выгрузок в различных форматах"""
    report_type = request.form.get('report_type')
    report_format = request.form.get('format')
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    farm_filter = request.form.get('farm_filter')
    report_category = request.form.get('report_category')
    
    if session.get('user_type') == 'farm':
        farm_filter = session.get('farm_name')
        
    # 1. Акт на выбытие животных и птицы (Форма № 209-АПК / СП-54)
    if report_type in ['form_209_apk', 'sp54']:
        wb = generate_form_209_apk_excel(start_date, end_date, farm_filter)
        filename = f"akt_209_apk_RB_{start_date}_{end_date}.xlsx"
        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        return send_file(out, download_name=filename, as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    # 2. Акт на выбраковку продуктивных животных из основного стада (Форма № 210-АПК)
    if report_type == 'form_210_apk':
        if report_format == 'preview':
            conn = get_db_connection()
            cursor = conn.cursor()
            where = "WHERE disposal_date BETWEEN ? AND ? AND category IN ('выбраковка', 'санитарный')"
            params = [start_date, end_date]
            if farm_filter and farm_filter != 'all':
                where += " AND farm_name = ?"
                params.append(farm_filter)
            cursor.execute(f"SELECT * FROM cows {where} ORDER BY disposal_date ASC", params)
            cows_list = [dict(r) for r in cursor.fetchall()]
            conn.close()
            
            total_weight = sum(float(c['weight'] or 0) for c in cows_list)
            total_value = sum(float(c['book_value'] or 0) for c in cows_list)
            org_name = get_setting('farm_org_name', 'ОАО «Новая Припять»')
            return render_template('form_210_preview.html', cows=cows_list, total_weight=f"{total_weight:.1f}", 
                                   total_value=f"{total_value:.2f}", start_date=start_date, end_date=end_date, 
                                   farm_filter=farm_filter, org_name=org_name)
        else:
            wb = generate_form_210_apk_excel(start_date, end_date, farm_filter)
            filename = f"akt_210_apk_RB_{start_date}_{end_date}.xlsx"
            out = io.BytesIO()
            wb.save(out)
            out.seek(0)
            return send_file(out, download_name=filename, as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    # 3. Реестр снятия с учета в государственной информационной системе ГИС AITS
    if report_type == 'aits_registry':
        if report_format == 'xml':
            xml_data = generate_aits_xml_registry(start_date, end_date, farm_filter)
            return Response(
                xml_data,
                mimetype="application/xml; charset=utf-8",
                headers={"Content-disposition": f"attachment; filename=aits_registry_{start_date}_{end_date}.xml"}
            )
        else:
            csv_data = generate_aits_csv_registry(start_date, end_date, farm_filter)
            return Response(
                '\ufeff' + csv_data,
                mimetype="text/csv; charset=utf-8",
                headers={"Content-disposition": f"attachment; filename=aits_registry_{start_date}_{end_date}.csv"}
            )

    # 4. Выгрузка в CSV
    if report_format == 'csv':
        csv_data = generate_csv_report(start_date, end_date, farm_filter)
        return Response(
            '\ufeff' + csv_data,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-disposition": f"attachment; filename=report_{start_date}_{end_date}.csv"}
        )
        
    # 5. Экранный интерактивный предпросмотр
    elif report_format == 'preview':
        conn = get_db_connection()
        cursor = conn.cursor()
        where = "WHERE disposal_date BETWEEN ? AND ?"
        params = [start_date, end_date]
        if farm_filter and farm_filter != 'all':
            where += " AND farm_name = ?"
            params.append(farm_filter)
        cursor.execute(f"SELECT * FROM cows {where} ORDER BY disposal_date DESC", params)
        cows_list = [dict(r) for r in cursor.fetchall()]
        conn.close()
        
        summary = {
            'total_cows': len(cows_list),
            'by_category': {
                'падёж': sum(1 for c in cows_list if c['category'] == 'падёж'),
                'выбраковка': sum(1 for c in cows_list if c['category'] == 'выбраковка'),
                'санитарный': sum(1 for c in cows_list if c['category'] == 'санитарный')
            },
            'total_weight': sum(float(c['weight'] or 0) for c in cows_list)
        }
        return render_template('report_preview.html', data=cows_list, summary=summary, start_date=start_date, end_date=end_date, farm_filter=farm_filter)
        
    # 6. Аналитические таблицы Excel (Матрица / Структурированный / Простой)
    else:
        if report_type == 'matrix':
            wb = generate_matrix_excel_report(report_category or 'падёж', start_date, end_date)
            filename = f"matrix_{report_category}_{start_date}_{end_date}.xlsx"
        elif report_type == 'structured':
            wb = generate_structured_excel_report(start_date, end_date, farm_filter)
            filename = f"structured_report_{start_date}_{end_date}.xlsx"
        else:
            wb = generate_simple_excel_report(start_date, end_date, farm_filter)
            filename = f"simple_report_{start_date}_{end_date}.xlsx"
            
        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        return send_file(out, download_name=filename, as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@reports_bp.route('/generate_original_excel', methods=['POST'])
@admin_required
def generate_original_excel():
    """Генерация сводного ведомственного отчета по официальному шаблону"""
    wb = generate_official_template_excel()
    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return send_file(out, download_name=f"svodka_{datetime.now().strftime('%Y-%m-%d')}.xlsx", as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
