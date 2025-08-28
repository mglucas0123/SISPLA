from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import or_
from app.models import db, Form, User
from .utils import admin_required, handle_database_error
import logging

logger = logging.getLogger(__name__)

duty_bp = Blueprint('duty', __name__, url_prefix='/duty')

# ==========================================
# ROTAS DE GERENCIAMENTO DE FORMULÁRIOS
# ==========================================

@duty_bp.route('/<int:form_id>')
@login_required
@admin_required
def view_form_details(form_id):
    """Ver detalhes do formulário"""
    form = Form.query.get_or_404(form_id)
    return render_template('form/form_details.html', form=form)

@duty_bp.route('/<int:form_id>/delete', methods=['POST'])
@login_required
@admin_required
@handle_database_error("deletar formulário")
def delete_form(form_id):
    """Deletar formulário"""
    form_to_delete = Form.query.get_or_404(form_id)
    
    db.session.delete(form_to_delete)
    db.session.commit()
    
    logger.info(f"Formulário deletado por {current_user.username} - ID: {form_id}")
    flash('Formulário excluído com sucesso!', 'success')
    return redirect(url_for('form.forms'))

@duty_bp.route('/export')
@login_required
@admin_required
def export_forms():
    """Exportar formulários (funcionalidade futura)"""
    flash('Funcionalidade de exportação em desenvolvimento.', 'info')
    return redirect(url_for('form.forms'))

@duty_bp.route('/statistics')
@login_required
@admin_required
def forms_statistics():
    """Estatísticas dos formulários"""
    total_forms = Form.query.count()
    
    sector_stats = db.session.execute(
        db.text("""
            SELECT sector, COUNT(*) as count 
            FROM forms 
            GROUP BY sector 
            ORDER BY count DESC
        """)
    ).fetchall()
    
    user_stats = db.session.execute(
        db.text("""
            SELECT u.name, COUNT(f.id) as count 
            FROM forms f 
            JOIN users u ON f.worker_id = u.id 
            GROUP BY u.name 
            ORDER BY count DESC 
            LIMIT 10
        """)
    ).fetchall()
    
    monthly_stats = db.session.execute(
        db.text("""
            SELECT 
                strftime('%Y-%m', date_registry) as month,
                COUNT(*) as count
            FROM forms 
            WHERE date_registry >= date('now', '-12 months')
            GROUP BY strftime('%Y-%m', date_registry)
            ORDER BY month
        """)
    ).fetchall()
    
    return render_template(
        'form/forms_statistics.html',
        total_forms=total_forms,
        sector_stats=sector_stats,
        user_stats=user_stats,
        monthly_stats=monthly_stats
    )
