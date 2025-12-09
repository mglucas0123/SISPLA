"""
Sistema de Validação Colaborativa de Avaliações
================================================

Este módulo implementa o fluxo de feedback 360° onde:
1. Gestor avalia colaborador
2. Colaborador deve contra-avaliar o gestor antes de ver sua avaliação
3. Ambos inserem códigos 2FA lado a lado para sessão de validação
4. Visualizam as duas avaliações simultaneamente para discussão
"""

import secrets
from datetime import datetime, timezone, timedelta
from functools import wraps

import pyotp
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from app.models import db, User, EmployeeEvaluation, CounterEvaluation, ValidationSession

collaborative_bp = Blueprint('collaborative', __name__, url_prefix='/avaliacao/colaborativa')


def require_2fa_enabled(f):
    """Decorator que exige que o usuário tenha 2FA ativo"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.totp_secret:
            flash('Você precisa ativar a autenticação de dois fatores (2FA) no seu perfil para acessar esta funcionalidade.', 'warning')
            return redirect(url_for('user.profile'))
        return f(*args, **kwargs)
    return decorated_function


# ============================================
# DASHBOARD DO COLABORADOR - Avaliações Pendentes
# ============================================

@collaborative_bp.route('/minhas-avaliacoes')
@login_required
def my_evaluations():
    """
    Dashboard do colaborador mostrando:
    - Avaliações recebidas pendentes de contra-avaliação
    - Avaliações já contra-avaliadas aguardando validação
    - Avaliações já validadas conjuntamente
    """
    # Avaliações que recebi e ainda não contra-avaliei
    pending_counter = EmployeeEvaluation.query.filter(
        EmployeeEvaluation.evaluated_id == current_user.id,
        EmployeeEvaluation.validation_status == 'pending'
    ).order_by(EmployeeEvaluation.created_at.desc()).all()
    
    # Avaliações que já contra-avaliei, aguardando sessão de validação
    awaiting_validation = EmployeeEvaluation.query.filter(
        EmployeeEvaluation.evaluated_id == current_user.id,
        EmployeeEvaluation.validation_status == 'counter_evaluated'
    ).order_by(EmployeeEvaluation.created_at.desc()).all()
    
    # Avaliações já validadas conjuntamente
    validated = EmployeeEvaluation.query.filter(
        EmployeeEvaluation.evaluated_id == current_user.id,
        EmployeeEvaluation.validation_status == 'validated'
    ).order_by(EmployeeEvaluation.validated_at.desc()).all()
    
    return render_template('avaliacao/colaborativa/minhas_avaliacoes.html',
                          pending_counter=pending_counter,
                          awaiting_validation=awaiting_validation,
                          validated=validated)


# ============================================
# CONTRA-AVALIAÇÃO DO GESTOR
# ============================================

@collaborative_bp.route('/contra-avaliar/<int:evaluation_id>', methods=['GET', 'POST'])
@login_required
@require_2fa_enabled
def counter_evaluate(evaluation_id):
    """
    Formulário para o colaborador avaliar o gestor que o avaliou.
    Só pode ser acessado pelo colaborador que foi avaliado.
    """
    evaluation = EmployeeEvaluation.query.get_or_404(evaluation_id)
    
    # Verificar se o usuário atual é quem foi avaliado
    if evaluation.evaluated_id != current_user.id:
        flash('Você não tem permissão para acessar esta avaliação.', 'danger')
        return redirect(url_for('collaborative.my_evaluations'))
    
    # Verificar se já existe contra-avaliação
    existing_counter = CounterEvaluation.query.filter_by(original_evaluation_id=evaluation_id).first()
    if existing_counter:
        flash('Você já realizou a contra-avaliação para esta avaliação.', 'info')
        return redirect(url_for('collaborative.my_evaluations'))
    
    if request.method == 'POST':
        try:
            counter_eval = CounterEvaluation(
                original_evaluation_id=evaluation_id,
                evaluator_id=current_user.id,  # Colaborador que está avaliando
                evaluated_id=evaluation.evaluator_id,  # Gestor que será avaliado
                
                # Critérios
                criteria_communication=request.form.get('criteria_communication'),
                criteria_communication_justification=request.form.get('criteria_communication_justification'),
                
                criteria_clarity=request.form.get('criteria_clarity'),
                criteria_clarity_justification=request.form.get('criteria_clarity_justification'),
                
                criteria_support=request.form.get('criteria_support'),
                criteria_support_justification=request.form.get('criteria_support_justification'),
                
                criteria_recognition=request.form.get('criteria_recognition'),
                criteria_recognition_justification=request.form.get('criteria_recognition_justification'),
                
                criteria_fairness=request.form.get('criteria_fairness'),
                criteria_fairness_justification=request.form.get('criteria_fairness_justification'),
                
                criteria_development=request.form.get('criteria_development'),
                criteria_development_justification=request.form.get('criteria_development_justification'),
                
                rating=int(request.form.get('rating', 5)),
                rating_justification=request.form.get('rating_justification'),
                strong_points=request.form.get('strong_points'),
                improvement_suggestions=request.form.get('improvement_suggestions')
            )
            
            # Calcular score
            counter_eval.calculate_score()
            
            # Atualizar status da avaliação original
            evaluation.validation_status = 'counter_evaluated'
            
            db.session.add(counter_eval)
            db.session.commit()
            
            flash('Contra-avaliação registrada com sucesso! Agora você pode solicitar uma sessão de validação com seu gestor.', 'success')
            return redirect(url_for('collaborative.my_evaluations'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao salvar contra-avaliação: {str(e)}', 'danger')
    
    return render_template('avaliacao/colaborativa/contra_avaliar.html',
                          evaluation=evaluation,
                          manager=evaluation.evaluator)


# ============================================
# SESSÃO DE VALIDAÇÃO COM 2FA DUPLO
# ============================================

@collaborative_bp.route('/iniciar-validacao/<int:evaluation_id>', methods=['POST'])
@login_required
@require_2fa_enabled
def start_validation_session(evaluation_id):
    """
    Inicia uma sessão de validação conjunta.
    Pode ser iniciada pelo colaborador ou pelo gestor.
    """
    evaluation = EmployeeEvaluation.query.get_or_404(evaluation_id)
    
    # Verificar se o usuário é participante
    if current_user.id not in [evaluation.evaluator_id, evaluation.evaluated_id]:
        flash('Você não tem permissão para iniciar esta sessão.', 'danger')
        return redirect(url_for('collaborative.my_evaluations'))
    
    # Verificar se já existe contra-avaliação
    if evaluation.validation_status != 'counter_evaluated':
        flash('Esta avaliação ainda não possui contra-avaliação.', 'warning')
        return redirect(url_for('collaborative.my_evaluations'))
    
    # Verificar se existe sessão ativa não expirada
    existing_session = ValidationSession.query.filter(
        ValidationSession.evaluation_id == evaluation_id,
        ValidationSession.session_status.in_(['pending', 'active']),
        ValidationSession.expires_at > datetime.now(timezone.utc)
    ).first()
    
    if existing_session:
        # Redirecionar para sessão existente
        return redirect(url_for('collaborative.validation_session', token=existing_session.session_token))
    
    # Criar nova sessão
    session_token = secrets.token_urlsafe(32)
    new_session = ValidationSession(
        evaluation_id=evaluation_id,
        manager_id=evaluation.evaluator_id,
        employee_id=evaluation.evaluated_id,
        session_token=session_token,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30)
    )
    
    db.session.add(new_session)
    db.session.commit()
    
    flash('Sessão de validação iniciada! Ambos os participantes devem inserir seus códigos 2FA.', 'info')
    return redirect(url_for('collaborative.validation_session', token=session_token))


@collaborative_bp.route('/validacao/<token>')
@login_required
@require_2fa_enabled
def validation_session(token):
    """
    Página da sessão de validação com dupla autenticação 2FA.
    """
    session = ValidationSession.query.filter_by(session_token=token).first_or_404()
    
    # Verificar se o usuário é participante
    if current_user.id not in [session.manager_id, session.employee_id]:
        flash('Você não tem permissão para acessar esta sessão.', 'danger')
        return redirect(url_for('collaborative.my_evaluations'))
    
    # Verificar expiração
    if session.is_expired():
        flash('Esta sessão expirou. Inicie uma nova sessão de validação.', 'warning')
        return redirect(url_for('collaborative.my_evaluations'))
    
    # Se ambos já autenticaram, mostrar as avaliações
    if session.is_fully_authenticated() and session.session_status == 'active':
        return render_template('avaliacao/colaborativa/visualizacao_conjunta.html',
                              session=session,
                              evaluation=session.evaluation,
                              counter_evaluation=session.evaluation.counter_evaluation,
                              manager=session.manager,
                              employee=session.employee)
    
    # Calcular tempo restante
    now = datetime.now(timezone.utc)
    expires = session.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    remaining = expires - now
    remaining_minutes = max(0, int(remaining.total_seconds() // 60))
    
    return render_template('avaliacao/colaborativa/validacao_2fa.html',
                          session=session,
                          remaining_time=remaining_minutes,
                          is_manager=(current_user.id == session.manager_id),
                          is_employee=(current_user.id == session.employee_id))


@collaborative_bp.route('/validacao/<token>/autenticar', methods=['POST'])
@login_required
@require_2fa_enabled
def authenticate_2fa(token):
    """
    Endpoint para autenticação 2FA na sessão de validação.
    """
    session = ValidationSession.query.filter_by(session_token=token).first_or_404()
    
    # Verificar se o usuário é participante
    if current_user.id not in [session.manager_id, session.employee_id]:
        return jsonify({'success': False, 'message': 'Acesso não autorizado'}), 403
    
    # Verificar expiração
    if session.is_expired():
        return jsonify({'success': False, 'message': 'Sessão expirada'}), 400
    
    # Verificar código 2FA
    otp_code = request.form.get('otp_code', '')
    
    if not current_user.totp_secret:
        return jsonify({'success': False, 'message': '2FA não configurado'}), 400
    
    totp = pyotp.TOTP(current_user.totp_secret)
    if not totp.verify(otp_code):
        return jsonify({'success': False, 'message': 'Código 2FA inválido'}), 400
    
    # Marcar autenticação do usuário
    now = datetime.now(timezone.utc)
    if current_user.id == session.manager_id:
        session.manager_authenticated = True
        session.manager_auth_at = now
    else:
        session.employee_authenticated = True
        session.employee_auth_at = now
    
    # Se ambos autenticaram, ativar sessão
    if session.is_fully_authenticated():
        session.session_status = 'active'
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'fully_authenticated': session.is_fully_authenticated(),
        'manager_authenticated': session.manager_authenticated,
        'employee_authenticated': session.employee_authenticated
    })


@collaborative_bp.route('/validacao/<token>/autenticar-ambos', methods=['POST'])
@login_required
@require_2fa_enabled
def authenticate_both(token):
    """
    Endpoint para autenticação simultânea de ambos os participantes (gestor e colaborador).
    Ambos inserem seus códigos 2FA na mesma tela, lado a lado.
    """
    session = ValidationSession.query.filter_by(session_token=token).first_or_404()
    
    # Verificar se o usuário é participante
    if current_user.id not in [session.manager_id, session.employee_id]:
        flash('Você não tem permissão para acessar esta sessão.', 'danger')
        return redirect(url_for('collaborative.my_evaluations'))
    
    # Verificar expiração
    if session.is_expired():
        flash('Esta sessão expirou. Inicie uma nova sessão de validação.', 'warning')
        return redirect(url_for('collaborative.my_evaluations'))
    
    # Obter os códigos do formulário
    manager_code = request.form.get('manager_code', '').strip()
    employee_code = request.form.get('employee_code', '').strip()
    
    errors = []
    now = datetime.now(timezone.utc)
    
    # Verificar código do gestor (se ainda não autenticado)
    if not session.manager_authenticated:
        if not manager_code:
            errors.append('Código do gestor é obrigatório.')
        else:
            manager = User.query.get(session.manager_id)
            if not manager or not manager.totp_secret:
                errors.append('Gestor não possui 2FA configurado.')
            else:
                totp = pyotp.TOTP(manager.totp_secret)
                if totp.verify(manager_code):
                    session.manager_authenticated = True
                    session.manager_auth_at = now
                else:
                    errors.append('Código 2FA do gestor inválido.')
    
    # Verificar código do colaborador (se ainda não autenticado)
    if not session.employee_authenticated:
        if not employee_code:
            errors.append('Código do colaborador é obrigatório.')
        else:
            employee = User.query.get(session.employee_id)
            if not employee or not employee.totp_secret:
                errors.append('Colaborador não possui 2FA configurado.')
            else:
                totp = pyotp.TOTP(employee.totp_secret)
                if totp.verify(employee_code):
                    session.employee_authenticated = True
                    session.employee_auth_at = now
                else:
                    errors.append('Código 2FA do colaborador inválido.')
    
    # Se houver erros, exibir e retornar à página de validação
    if errors:
        for error in errors:
            flash(error, 'danger')
        return redirect(url_for('collaborative.validation_session', token=token))
    
    # Se ambos autenticaram, ativar sessão
    if session.is_fully_authenticated():
        session.session_status = 'active'
        db.session.commit()
        flash('Autenticação bem-sucedida! Ambos os participantes foram verificados.', 'success')
        return redirect(url_for('collaborative.view_session', token=token))
    
    db.session.commit()
    return redirect(url_for('collaborative.validation_session', token=token))


@collaborative_bp.route('/validacao/<token>/visualizar')
@login_required
@require_2fa_enabled
def view_session(token):
    """
    Página de visualização conjunta das avaliações após autenticação 2FA de ambos.
    """
    session = ValidationSession.query.filter_by(session_token=token).first_or_404()
    
    # Verificar se o usuário é participante
    if current_user.id not in [session.manager_id, session.employee_id]:
        flash('Você não tem permissão para acessar esta sessão.', 'danger')
        return redirect(url_for('collaborative.my_evaluations'))
    
    # Verificar expiração
    if session.is_expired():
        flash('Esta sessão expirou. Inicie uma nova sessão de validação.', 'warning')
        return redirect(url_for('collaborative.my_evaluations'))
    
    # Verificar se ambos estão autenticados
    if not session.is_fully_authenticated():
        flash('Ambos os participantes precisam se autenticar.', 'warning')
        return redirect(url_for('collaborative.validation_session', token=token))
    
    return render_template('avaliacao/colaborativa/visualizacao_conjunta.html',
                          session=session,
                          evaluation=session.evaluation,
                          counter_evaluation=session.evaluation.counter_evaluation,
                          manager=session.manager,
                          employee=session.employee)


@collaborative_bp.route('/validacao/<token>/status')
@login_required
def session_status(token):
    """
    Endpoint para polling do status da sessão (para atualização em tempo real).
    """
    session = ValidationSession.query.filter_by(session_token=token).first_or_404()
    
    if current_user.id not in [session.manager_id, session.employee_id]:
        return jsonify({'error': 'Acesso não autorizado'}), 403
    
    return jsonify({
        'manager_authenticated': session.manager_authenticated,
        'employee_authenticated': session.employee_authenticated,
        'fully_authenticated': session.is_fully_authenticated(),
        'session_status': session.session_status,
        'expired': session.is_expired()
    })


@collaborative_bp.route('/validacao/<token>/finalizar', methods=['POST'])
@login_required
@require_2fa_enabled
def complete_validation(token):
    """
    Finaliza a sessão de validação, salvando notas e itens de ação.
    """
    session = ValidationSession.query.filter_by(session_token=token).first_or_404()
    
    # Verificar se o usuário é participante
    if current_user.id not in [session.manager_id, session.employee_id]:
        flash('Você não tem permissão para finalizar esta sessão.', 'danger')
        return redirect(url_for('collaborative.my_evaluations'))
    
    # Verificar se a sessão está ativa
    if session.session_status != 'active':
        flash('Esta sessão não está ativa.', 'warning')
        return redirect(url_for('collaborative.my_evaluations'))
    
    # Salvar notas e itens de ação
    session.session_notes = request.form.get('session_notes', '')
    session.action_items = request.form.get('action_items', '')
    session.session_status = 'completed'
    session.completed_at = datetime.now(timezone.utc)
    
    # Atualizar status da avaliação original
    evaluation = session.evaluation
    evaluation.validation_status = 'validated'
    evaluation.validated_at = datetime.now(timezone.utc)
    evaluation.is_jointly_viewed = True
    evaluation.viewed_at = datetime.now(timezone.utc)
    
    db.session.commit()
    
    flash('Sessão de validação concluída com sucesso! As avaliações foram validadas.', 'success')
    return redirect(url_for('collaborative.my_evaluations'))


# ============================================
# API ENDPOINTS
# ============================================

@collaborative_bp.route('/api/avaliacoes-pendentes')
@login_required
def api_pending_evaluations():
    """
    Retorna contagem de avaliações pendentes para o usuário atual.
    """
    pending_count = EmployeeEvaluation.query.filter(
        EmployeeEvaluation.evaluated_id == current_user.id,
        EmployeeEvaluation.validation_status == 'pending'
    ).count()
    
    awaiting_count = EmployeeEvaluation.query.filter(
        EmployeeEvaluation.evaluated_id == current_user.id,
        EmployeeEvaluation.validation_status == 'counter_evaluated'
    ).count()
    
    return jsonify({
        'pending_counter_evaluation': pending_count,
        'awaiting_validation': awaiting_count,
        'total_pending': pending_count + awaiting_count
    })
