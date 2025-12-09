"""
Relatórios Administrativos de Sessões Colaborativas
====================================================

Módulo para visualização de relatórios de sessões de feedback colaborativo
por administradores e diretores.
"""

from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import or_, and_, desc

from app.models import db, User, ValidationSession, EmployeeEvaluation, CounterEvaluation

collaborative_reports_bp = Blueprint('collaborative_reports', __name__, url_prefix='/admin/relatorios-colaborativos')


def require_admin_permission():
    """Verifica se o usuário tem permissão de admin para acessar relatórios"""
    if not current_user.has_permission('admin-total'):
        flash('Você não tem permissão para acessar relatórios administrativos.', 'danger')
        abort(403)


@collaborative_reports_bp.route('/')
@login_required
def list_reports():
    """
    Lista todos os relatórios de sessões colaborativas finalizadas.
    Acesso restrito a administradores.
    """
    require_admin_permission()
    
    # Filtros
    status_filter = request.args.get('status', 'all')
    manager_filter = request.args.get('manager_id', type=int)
    employee_filter = request.args.get('employee_id', type=int)
    month_filter = request.args.get('month', '')
    
    # Query base - apenas sessões completadas
    query = ValidationSession.query.filter_by(session_status='completed')
    
    # Aplicar filtros
    if manager_filter:
        query = query.filter_by(manager_id=manager_filter)
    
    if employee_filter:
        query = query.filter_by(employee_id=employee_filter)
    
    if month_filter:
        try:
            # Formato esperado: YYYY-MM
            year, month = month_filter.split('-')
            query = query.filter(
                db.extract('year', ValidationSession.completed_at) == int(year),
                db.extract('month', ValidationSession.completed_at) == int(month)
            )
        except ValueError:
            pass
    
    # Ordenar por data de conclusão (mais recentes primeiro)
    sessions = query.order_by(desc(ValidationSession.completed_at)).all()
    
    # Obter lista de gestores e colaboradores para filtros
    managers = db.session.query(User).join(
        ValidationSession, ValidationSession.manager_id == User.id
    ).filter(ValidationSession.session_status == 'completed').distinct().order_by(User.name).all()
    
    employees = db.session.query(User).join(
        ValidationSession, ValidationSession.employee_id == User.id
    ).filter(ValidationSession.session_status == 'completed').distinct().order_by(User.name).all()
    
    # Estatísticas
    total_sessions = len(sessions)
    sessions_with_notes = sum(1 for s in sessions if s.session_notes)
    sessions_with_actions = sum(1 for s in sessions if s.action_items)
    
    return render_template('admin/collaborative_reports/list.html',
                          sessions=sessions,
                          managers=managers,
                          employees=employees,
                          total_sessions=total_sessions,
                          sessions_with_notes=sessions_with_notes,
                          sessions_with_actions=sessions_with_actions,
                          current_filters={
                              'status': status_filter,
                              'manager_id': manager_filter,
                              'employee_id': employee_filter,
                              'month': month_filter
                          })


@collaborative_reports_bp.route('/<int:session_id>')
@login_required
def view_report(session_id):
    """
    Visualiza o relatório detalhado de uma sessão colaborativa específica.
    Acesso restrito a administradores.
    """
    require_admin_permission()
    
    session = ValidationSession.query.get_or_404(session_id)
    
    # Verificar se a sessão foi completada
    if session.session_status != 'completed':
        flash('Este relatório só está disponível para sessões completadas.', 'warning')
        return redirect(url_for('collaborative_reports.list_reports'))
    
    # Buscar avaliação e contra-avaliação
    evaluation = session.evaluation
    counter_evaluation = evaluation.counter_evaluation if evaluation else None
    
    return render_template('admin/collaborative_reports/view.html',
                          session=session,
                          evaluation=evaluation,
                          counter_evaluation=counter_evaluation,
                          manager=session.manager,
                          employee=session.employee)


@collaborative_reports_bp.route('/exportar')
@login_required
def export_reports():
    """
    Exporta relatórios em formato CSV.
    Acesso restrito a administradores.
    """
    require_admin_permission()
    
    # TODO: Implementar exportação CSV
    flash('Funcionalidade de exportação em desenvolvimento.', 'info')
    return redirect(url_for('admin.collaborative_reports.list_reports'))


@collaborative_reports_bp.route('/estatisticas')
@login_required
def statistics():
    """
    Dashboard com estatísticas das sessões colaborativas.
    Acesso restrito a administradores.
    """
    require_admin_permission()
    
    # Estatísticas gerais
    total_sessions = ValidationSession.query.filter_by(session_status='completed').count()
    
    # Sessões por mês (últimos 12 meses)
    from sqlalchemy import func
    sessions_by_month = db.session.query(
        func.strftime('%Y-%m', ValidationSession.completed_at).label('month'),
        func.count(ValidationSession.id).label('count')
    ).filter(
        ValidationSession.session_status == 'completed',
        ValidationSession.completed_at.isnot(None)
    ).group_by('month').order_by(desc('month')).limit(12).all()
    
    # Gestores mais ativos
    top_managers = db.session.query(
        User.id,
        User.name,
        func.count(ValidationSession.id).label('session_count')
    ).join(
        ValidationSession, ValidationSession.manager_id == User.id
    ).filter(
        ValidationSession.session_status == 'completed'
    ).group_by(User.id, User.name).order_by(desc('session_count')).limit(10).all()
    
    # Média de duração das sessões (da criação até conclusão)
    avg_duration = db.session.query(
        func.avg(
            func.extract('epoch', ValidationSession.completed_at - ValidationSession.created_at) / 60
        )
    ).filter(
        ValidationSession.session_status == 'completed',
        ValidationSession.completed_at.isnot(None)
    ).scalar()
    
    return render_template('admin/collaborative_reports/statistics.html',
                          total_sessions=total_sessions,
                          sessions_by_month=sessions_by_month,
                          top_managers=top_managers,
                          avg_duration=round(avg_duration, 1) if avg_duration else 0)
