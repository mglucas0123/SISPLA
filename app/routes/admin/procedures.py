from flask import Blueprint, jsonify, request, render_template, flash, redirect, url_for
from flask_login import login_required, current_user
from app.procedures_models import Procedure
from app.models import db
from functools import wraps

procedures_bp = Blueprint('procedures', __name__, url_prefix='/procedures')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Acesso negado'}), 403
        if not current_user.has_permission('manage_procedures'):
            return jsonify({'error': 'Permissão insuficiente'}), 403
        return f(*args, **kwargs)
    return decorated_function

@procedures_bp.route('/list', methods=['GET'])
@login_required
def list_procedures():
    if not current_user.has_permission('manage_procedures') and not current_user.has_permission('admin-total'):
        return jsonify({'error': 'Permissão insuficiente'}), 403
    
    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    
    query = Procedure.query.filter_by(is_active=True)
    
    if search:
        search_pattern = f'%{search}%'
        query = query.filter(
            db.or_(
                Procedure.code.ilike(search_pattern),
                Procedure.description.ilike(search_pattern)
            )
        )
    
    query = query.order_by(Procedure.code.asc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    procedures = [p.to_dict() for p in pagination.items]
    
    return jsonify({
        'procedures': procedures,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page,
        'has_next': pagination.has_next,
        'has_prev': pagination.has_prev
    })

@procedures_bp.route('/search', methods=['GET'])
@login_required
def search_procedures():
    query_text = request.args.get('q', '').strip()
    limit = request.args.get('limit', 15, type=int)
    
    if not query_text:
        return jsonify({'procedures': []})
    
    search_pattern = f'%{query_text}%'
    procedures = Procedure.query.filter(
        Procedure.is_active == True,
        db.or_(
            Procedure.code.ilike(search_pattern),
            Procedure.description.ilike(search_pattern)
        )
    ).order_by(Procedure.code.asc()).limit(limit).all()
    
    return jsonify({
        'procedures': [p.to_dict() for p in procedures]
    })

@procedures_bp.route('/create', methods=['POST'])
@login_required
@admin_required
def create_procedure():
    data = request.get_json()
    
    if not data:
        flash('Dados não fornecidos', 'danger')
        return jsonify({'success': False, 'reload': True}), 400
    
    code = data.get('code', '').strip()
    description = data.get('description', '').strip()
    
    if not code or not description:
        flash('Código e descrição são obrigatórios', 'warning')
        return jsonify({'success': False, 'reload': True}), 400
    
    existing = Procedure.query.filter_by(code=code).first()
    
    if existing:
        if not existing.is_active:
            existing.description = description
            existing.is_active = True
            db.session.commit()
            flash(f'Procedimento "{code}" reativado com sucesso!', 'success')
            return jsonify({'success': True, 'reload': True}), 201
        else:
            flash(f'Procedimento com código "{code}" já existe e está ativo', 'danger')
            return jsonify({'success': False, 'reload': True}), 409
    
    procedure = Procedure(code=code, description=description)
    db.session.add(procedure)
    db.session.commit()
    
    flash(f'Procedimento "{code}" criado com sucesso!', 'success')
    return jsonify({'success': True, 'reload': True}), 201

@procedures_bp.route('/update/<int:procedure_id>', methods=['PUT'])
@login_required
@admin_required
def update_procedure(procedure_id):
    procedure = Procedure.query.get_or_404(procedure_id)
    data = request.get_json()
    
    if not data:
        flash('Dados não fornecidos', 'danger')
        return jsonify({'success': False, 'reload': True}), 400
    
    code = data.get('code', '').strip()
    description = data.get('description', '').strip()
    
    if not code or not description:
        flash('Código e descrição são obrigatórios', 'warning')
        return jsonify({'success': False, 'reload': True}), 400
    
    if code != procedure.code:
        existing = Procedure.query.filter_by(code=code).first()
        if existing:
            flash(f'Outro procedimento já possui o código "{code}"', 'danger')
            return jsonify({'success': False, 'reload': True}), 409
    
    old_code = procedure.code
    procedure.code = code
    procedure.description = description
    db.session.commit()
    
    flash(f'Procedimento "{old_code}" atualizado com sucesso!', 'success')
    return jsonify({'success': True, 'reload': True})

@procedures_bp.route('/delete/<int:procedure_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_procedure(procedure_id):
    procedure = Procedure.query.get_or_404(procedure_id)
    
    code = procedure.code
    procedure.is_active = False
    db.session.commit()
    
    flash(f'Procedimento "{code}" removido com sucesso!', 'success')
    return jsonify({'success': True, 'reload': True})

@procedures_bp.route('/restore/<int:procedure_id>', methods=['POST'])
@login_required
@admin_required
def restore_procedure(procedure_id):
    procedure = Procedure.query.get_or_404(procedure_id)
    
    procedure.is_active = True
    db.session.commit()
    
    return jsonify({
        'message': 'Procedimento restaurado com sucesso',
        'procedure': procedure.to_dict()
    })
