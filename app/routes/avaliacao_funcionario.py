from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from app.models import db, User, EmployeeEvaluation, CounterEvaluation, ValidationSession
from datetime import datetime
from sqlalchemy import text
from sqlalchemy import func, desc

employee_evaluation_bp = Blueprint(
    'employee_evaluation',
    __name__,
    url_prefix='/avaliacao/funcionarios'
)


@employee_evaluation_bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard de avaliacao de colaboradores"""
    # Allow optional month filter via querystring, default to latest month in evaluations
    month = request.args.get('month')

    # Determine latest month_reference if none provided
    if not month:
        latest = db.session.query(func.max(EmployeeEvaluation.month_reference)).scalar()
        month = latest

    # Base query filtered by month if available
    # Usar total_score (calculado baseado em Conforme/Não Conforme) em vez de rating (estrelas)
    q = db.session.query(
        EmployeeEvaluation.evaluated_id.label('user_id'),
        func.count(EmployeeEvaluation.id).label('evaluations'),
        func.avg(EmployeeEvaluation.total_score).label('avg_score')
    )
    if month:
        q = q.filter(EmployeeEvaluation.month_reference == month)

    q = q.group_by(EmployeeEvaluation.evaluated_id).order_by(desc('avg_score'), desc('evaluations'))

    rows = q.all()

    # Build rankings with user metadata
    rankings = []
    for r in rows:
        user = User.query.get(r.user_id)
        rankings.append({
            'user_id': r.user_id,
            'name': user.name if user else '—',
            'email': user.email if user else '',
            'job_title': user.cargo if user else '',
            'evaluations': int(r.evaluations),
            'avg_score': float(r.avg_score) if r.avg_score is not None else 0.0
        })

    # Top highlights
    top_manager = rankings[0] if len(rankings) > 0 else None
    top_employee = rankings[1] if len(rankings) > 1 else (rankings[0] if rankings else None)

    # =====================================
    # RANKING DE GESTORES (baseado em contra-avaliações)
    # =====================================
    # Buscar gestores que receberam contra-avaliações dos seus colaboradores
    manager_query = db.session.query(
        CounterEvaluation.evaluated_id.label('manager_id'),
        func.count(CounterEvaluation.id).label('counter_evaluations'),
        func.avg(CounterEvaluation.total_score).label('avg_score'),
        func.avg(CounterEvaluation.rating).label('avg_rating')
    ).group_by(CounterEvaluation.evaluated_id).order_by(desc('avg_score'), desc('counter_evaluations'))

    manager_rows = manager_query.all()

    # Build manager rankings
    manager_rankings = []
    for r in manager_rows:
        user = User.query.get(r.manager_id)
        if user:
            manager_rankings.append({
                'user_id': r.manager_id,
                'name': user.name,
                'email': user.email or '',
                'job_title': user.cargo or 'Gestor',
                'counter_evaluations': int(r.counter_evaluations),
                'avg_score': float(r.avg_score) if r.avg_score is not None else 0.0,
                'avg_rating': float(r.avg_rating) if r.avg_rating is not None else 0.0
            })

    return render_template('avaliacao/funcionarios/dashboard.html',
                           top_manager=top_manager,
                           top_employee=top_employee,
                           rankings=rankings,
                           manager_rankings=manager_rankings,
                           month=month)


@employee_evaluation_bp.route('/colaborador/<int:employee_id>')
@login_required
def employee_history(employee_id):
    """Histórico de avaliações de um colaborador específico"""
    employee = User.query.get_or_404(employee_id)
    
    # Verificar permissão para ver detalhes das avaliações
    # Usuário pode ver: suas próprias avaliações, avaliações de colaboradores que gerencia,
    # ou se tiver permissão admin-total / visualizar_todas_avaliacoes_funcionarios
    if not current_user.can_view_employee_evaluation_details(employee_id):
        flash('Você não tem permissão para visualizar o histórico de avaliações deste colaborador.', 'danger')
        return redirect(url_for('employee_evaluation.dashboard'))
    
    # Buscar todas as avaliações deste colaborador ordenadas por data
    evaluations = EmployeeEvaluation.query.filter_by(
        evaluated_id=employee_id
    ).order_by(desc(EmployeeEvaluation.created_at)).all()
    
    # Calcular estatísticas
    total_evaluations = len(evaluations)
    
    if total_evaluations > 0:
        avg_score = sum(e.total_score or 0 for e in evaluations) / total_evaluations
        conformes = sum(1 for e in evaluations if e.is_compliant)
        nao_conformes = total_evaluations - conformes
        
        # Contagem por tipo de avaliação
        mensal_count = sum(1 for e in evaluations if e.evaluation_type == 'mensal')
        exp_45_count = sum(1 for e in evaluations if e.evaluation_type == 'experiencia_45')
        exp_90_count = sum(1 for e in evaluations if e.evaluation_type == 'experiencia_90')
    else:
        avg_score = 0
        conformes = 0
        nao_conformes = 0
        mensal_count = 0
        exp_45_count = 0
        exp_90_count = 0
    
    return render_template('avaliacao/funcionarios/employee_history.html',
                           employee=employee,
                           evaluations=evaluations,
                           total_evaluations=total_evaluations,
                           avg_score=avg_score,
                           conformes=conformes,
                           nao_conformes=nao_conformes,
                           mensal_count=mensal_count,
                           exp_45_count=exp_45_count,
                           exp_90_count=exp_90_count)


@employee_evaluation_bp.route('/gestor/<int:manager_id>')
@login_required
def manager_profile(manager_id):
    """
    Perfil do gestor com feedbacks recebidos (contra-avaliações).
    Permite que a diretoria visualize os pontos fortes e a melhorar do gestor.
    """
    manager = User.query.get_or_404(manager_id)
    
    # Buscar todas as contra-avaliações recebidas por este gestor
    counter_evaluations = CounterEvaluation.query.filter_by(
        evaluated_id=manager_id
    ).order_by(desc(CounterEvaluation.created_at)).all()
    
    # Buscar sessões de validação onde este gestor participou (notas e itens de ação)
    validation_sessions = ValidationSession.query.filter_by(
        manager_id=manager_id,
        session_status='completed'
    ).order_by(desc(ValidationSession.completed_at)).all()
    
    # Calcular estatísticas
    total_counter_evals = len(counter_evaluations)
    
    if total_counter_evals > 0:
        avg_score = sum(c.total_score or 0 for c in counter_evaluations) / total_counter_evals
        avg_rating = sum(c.rating or 0 for c in counter_evaluations) / total_counter_evals
        
        # Contagem de critérios por status
        criteria_stats = {
            'communication': {'conforme': 0, 'nao_conforme': 0, 'total': 0},
            'clarity': {'conforme': 0, 'nao_conforme': 0, 'total': 0},
            'support': {'conforme': 0, 'nao_conforme': 0, 'total': 0},
            'recognition': {'conforme': 0, 'nao_conforme': 0, 'total': 0},
            'fairness': {'conforme': 0, 'nao_conforme': 0, 'total': 0},
            'development': {'conforme': 0, 'nao_conforme': 0, 'total': 0}
        }
        
        for ce in counter_evaluations:
            for criteria in criteria_stats.keys():
                value = getattr(ce, f'criteria_{criteria}', None)
                if value == 'conforme':
                    criteria_stats[criteria]['conforme'] += 1
                    criteria_stats[criteria]['total'] += 1
                elif value == 'nao_conforme':
                    criteria_stats[criteria]['nao_conforme'] += 1
                    criteria_stats[criteria]['total'] += 1
        
        # Coletar pontos fortes e sugestões de melhoria mencionados
        all_strong_points = [c.strong_points for c in counter_evaluations if c.strong_points]
        all_improvement_suggestions = [c.improvement_suggestions for c in counter_evaluations if c.improvement_suggestions]
        
        # Coletar notas e itens de ação das sessões de validação
        all_session_notes = [s.session_notes for s in validation_sessions if s.session_notes]
        all_action_items = [s.action_items for s in validation_sessions if s.action_items]
    else:
        avg_score = 0
        avg_rating = 0
        criteria_stats = {}
        all_strong_points = []
        all_improvement_suggestions = []
        all_session_notes = []
        all_action_items = []
    
    return render_template('avaliacao/funcionarios/manager_profile.html',
                           manager=manager,
                           counter_evaluations=counter_evaluations,
                           validation_sessions=validation_sessions,
                           total_counter_evals=total_counter_evals,
                           avg_score=avg_score,
                           avg_rating=avg_rating,
                           criteria_stats=criteria_stats,
                           all_strong_points=all_strong_points,
                           all_improvement_suggestions=all_improvement_suggestions,
                           all_session_notes=all_session_notes,
                           all_action_items=all_action_items)


@employee_evaluation_bp.route('/avaliacao/<int:evaluation_id>')
@login_required
def evaluation_details(evaluation_id):
    """Detalhes de uma avaliação específica de colaborador"""
    evaluation = EmployeeEvaluation.query.get_or_404(evaluation_id)
    
    # Verificar permissão para ver detalhes da avaliação
    # Usuário pode ver: suas próprias avaliações (se é o avaliado),
    # avaliações de colaboradores que gerencia, ou se tiver permissão especial
    if not current_user.can_view_employee_evaluation_details(evaluation.evaluated_id):
        flash('Você não tem permissão para visualizar os detalhes desta avaliação.', 'danger')
        return redirect(url_for('employee_evaluation.dashboard'))
    
    return render_template('avaliacao/funcionarios/evaluation_details.html',
                           evaluation=evaluation)


@employee_evaluation_bp.route('/api/check-evaluation', methods=['GET'])
@login_required
def check_evaluation():
    """API para verificar se um colaborador já foi avaliado em um determinado mês"""
    evaluated_id = request.args.get('evaluated_id')
    month_reference = request.args.get('month_reference')
    
    print(f"[DEBUG] check_evaluation - evaluated_id: {evaluated_id}, month_reference: {month_reference}, current_user.id: {current_user.id}")
    
    if not evaluated_id or not month_reference:
        return jsonify({'error': 'Parâmetros inválidos'}), 400
    
    # Buscar avaliações mensais deste colaborador neste mês pelo avaliador atual
    monthly_evaluations = EmployeeEvaluation.query.filter_by(
        evaluator_id=current_user.id,
        evaluated_id=int(evaluated_id),
        month_reference=month_reference,
        evaluation_type='mensal'
    ).all()
    
    print(f"[DEBUG] monthly_evaluations encontradas: {len(monthly_evaluations)}")
    for e in monthly_evaluations:
        print(f"[DEBUG]   - ID: {e.id}, month_ref: {e.month_reference}, type: {e.evaluation_type}")
    
    # Buscar avaliações de experiência (45/90 dias) - estas são globais (não dependem do mês)
    experience_evaluations = EmployeeEvaluation.query.filter(
        EmployeeEvaluation.evaluator_id == current_user.id,
        EmployeeEvaluation.evaluated_id == int(evaluated_id),
        EmployeeEvaluation.evaluation_type.in_(['experiencia_45', 'experiencia_90'])
    ).all()
    
    print(f"[DEBUG] experience_evaluations encontradas: {len(experience_evaluations)}")
    
    # Criar lista de tipos de avaliação já realizadas
    evaluated_types = [e.evaluation_type for e in monthly_evaluations]
    evaluated_types.extend([e.evaluation_type for e in experience_evaluations])
    
    print(f"[DEBUG] evaluated_types: {evaluated_types}, is_evaluated: {len(evaluated_types) > 0}")
    
    return jsonify({
        'evaluated_id': evaluated_id,
        'month_reference': month_reference,
        'is_evaluated': len(evaluated_types) > 0,
        'evaluation_types': evaluated_types
    })


@employee_evaluation_bp.route('/avaliar', methods=['GET', 'POST'])
@login_required
def evaluate():
    """Formulário de avaliacao de colaboradores e gestores"""
    # Determine current form step (server-side multi-step handling)
    form_step = request.form.get('form_action') if request.method == 'POST' else None

    # Ensure DB has the JSON column for experience details (backfill small migration)
    def ensure_experience_column_exists():
        try:
            # For SQLite, PRAGMA table_info returns rows with (cid, name, type, ...)
            res = db.session.execute(text("PRAGMA table_info('employee_evaluations')"))
            cols = [row[1] for row in res.fetchall()]
            if 'experience_details' not in cols:
                # Add the column with JSON affinity (SQLite accepts arbitrary type names)
                db.session.execute(text('ALTER TABLE employee_evaluations ADD COLUMN experience_details JSON'))
                db.session.commit()
        except Exception:
            # If anything goes wrong, don't block the request; logging could be added
            db.session.rollback()

    ensure_experience_column_exists()

    if request.method == 'POST' and form_step:
        # User is navigating between steps or submitting final
        try:
            # Gather basic fields persisted between steps
            evaluated_id = request.form.get('evaluated_id')
            month_reference = request.form.get('month_reference')
            evaluation_type = request.form.get('evaluation_type', 'mensal')
            
            # DEBUG: Log all form values
            print(f"[DEBUG] form_step: {form_step}")
            print(f"[DEBUG] evaluated_id: {evaluated_id}")
            print(f"[DEBUG] month_reference: {month_reference}")
            print(f"[DEBUG] evaluation_type: {evaluation_type}")
            print(f"[DEBUG] Full form keys: {list(request.form.keys())}")

            # Step navigation: to_step2, to_step3, submit
            if form_step == 'to_step2':
                # Validate step 1 required fields
                if not evaluated_id:
                    flash('Por favor, selecione um colaborador!', 'warning')
                    form_step = 'step1'
                elif not month_reference:
                    flash('Por favor, selecione o mês de referência!', 'warning')
                    form_step = 'step1'
                elif not current_user.can_evaluate_employee(int(evaluated_id)):
                    # Verificar se o usuário pode avaliar este colaborador
                    flash('Você não tem permissão para avaliar este colaborador. Apenas gestores responsáveis podem avaliar.', 'danger')
                    form_step = 'step1'
                else:
                    # Verificar se já existe avaliação deste tipo para este colaborador
                    # Para avaliações de experiência (45/90 dias), verificar se já existe QUALQUER avaliação desse tipo
                    # Para avaliações mensais, verificar apenas no mês selecionado
                    if evaluation_type in ['experiencia_45', 'experiencia_90']:
                        # Avaliação de experiência só pode ser feita UMA VEZ por colaborador (independente do mês)
                        existing = EmployeeEvaluation.query.filter_by(
                            evaluator_id=current_user.id,
                            evaluated_id=evaluated_id,
                            evaluation_type=evaluation_type
                        ).first()
                    else:
                        # Avaliação mensal - verificar apenas no mês selecionado
                        existing = EmployeeEvaluation.query.filter_by(
                            evaluator_id=current_user.id,
                            evaluated_id=evaluated_id,
                            month_reference=month_reference,
                            evaluation_type=evaluation_type
                        ).first()
                    
                    if existing:
                        type_names = {
                            'mensal': 'Avaliação Mensal',
                            'experiencia_45': 'Avaliação de Experiência (45 dias)',
                            'experiencia_90': 'Avaliação de Experiência (90 dias)'
                        }
                        if evaluation_type in ['experiencia_45', 'experiencia_90']:
                            flash(f'Este colaborador já possui uma {type_names.get(evaluation_type, evaluation_type)} registrada. Esta avaliação só pode ser realizada uma vez por colaborador.', 'warning')
                        else:
                            flash(f'Este colaborador já possui uma {type_names.get(evaluation_type, evaluation_type)} registrada para o mês selecionado. Selecione outro colaborador ou tipo de avaliação.', 'warning')
                        form_step = 'step1'
                        # Buscar dados para re-renderizar step 1
                        users = User.query.filter(User.is_active == True, User.id != current_user.id).order_by(User.name).all()
                        # Recalcular evaluated_this_month para o mês selecionado
                        # Avaliações mensais do mês selecionado
                        existing_evaluations = EmployeeEvaluation.query.filter_by(
                            evaluator_id=current_user.id,
                            month_reference=month_reference,
                            evaluation_type='mensal'
                        ).all()
                        # Avaliações de experiência (45/90 dias) - globais
                        experience_evaluations = EmployeeEvaluation.query.filter(
                            EmployeeEvaluation.evaluator_id == current_user.id,
                            EmployeeEvaluation.evaluation_type.in_(['experiencia_45', 'experiencia_90'])
                        ).all()
                        
                        evaluated_this_month = {}
                        for e in existing_evaluations + experience_evaluations:
                            user_id_str = str(e.evaluated_id)
                            if user_id_str not in evaluated_this_month:
                                evaluated_this_month[user_id_str] = []
                            if e.evaluation_type not in evaluated_this_month[user_id_str]:
                                evaluated_this_month[user_id_str].append(e.evaluation_type)
                        evaluated_this_month_str = {k: ','.join(v) for k, v in evaluated_this_month.items()}
                        return render_template('avaliacao/funcionarios/avaliar.html', users=users, form_step=form_step, evaluated_id=evaluated_id, month_reference=month_reference, evaluation_type=evaluation_type, form_data=request.form, evaluated_this_month=evaluated_this_month_str)
                    
                    form_step = 'step2'
                    # Render step 2 with submitted values preserved
                    users = User.query.filter(User.is_active == True, User.id != current_user.id).order_by(User.name).all()
                    return render_template('avaliacao/funcionarios/avaliar.html', users=users, form_step=form_step, evaluated_id=evaluated_id, month_reference=month_reference, evaluation_type=evaluation_type, form_data=request.form)

            elif form_step == 'to_step3':
                # Validate step 2 fields depending on evaluation_type
                if evaluation_type == 'mensal':
                    # Validar se todos os critérios foram preenchidos (seleção + justificativa)
                    criteria_names = ['punctuality', 'quality', 'productivity', 'teamwork', 
                                     'communication', 'initiative', 'compliance', 'development']
                    missing_selection = []
                    missing_justification = []
                    
                    for criteria in criteria_names:
                        selection = request.form.get(f'criteria_{criteria}')
                        justification = request.form.get(f'criteria_{criteria}_justification', '').strip()
                        
                        if not selection:
                            missing_selection.append(criteria)
                        if not justification:
                            missing_justification.append(criteria)
                    
                    if missing_selection or missing_justification:
                        if missing_selection:
                            flash('Por favor, selecione Conforme/Não Conforme/Não se Aplica para todos os critérios antes de continuar.', 'warning')
                        elif missing_justification:
                            flash('Por favor, preencha a justificativa para todos os critérios antes de continuar.', 'warning')
                        form_step = 'step2'
                        users = User.query.filter(User.is_active == True, User.id != current_user.id).order_by(User.name).all()
                        return render_template('avaliacao/funcionarios/avaliar.html', users=users, form_step=form_step, evaluated_id=evaluated_id, month_reference=month_reference, evaluation_type=evaluation_type, form_data=request.form)
                else:
                    # For experience evaluations, rely on existing client-side checks or leave server-side optional
                    pass

                form_step = 'step3'
                users = User.query.filter(User.is_active == True, User.id != current_user.id).order_by(User.name).all()
                return render_template('avaliacao/funcionarios/avaliar.html', users=users, form_step=form_step, evaluated_id=evaluated_id, month_reference=month_reference, evaluation_type=evaluation_type, form_data=request.form)

            elif form_step == 'submit':
                # Validação obrigatória do month_reference antes de salvar
                if not month_reference:
                    flash('Erro: Mês de referência não informado. Por favor, reinicie o formulário.', 'danger')
                    return redirect(url_for('employee_evaluation.evaluate'))
                
                # Verificar permissão para avaliar este colaborador
                if not current_user.can_evaluate_employee(int(evaluated_id)):
                    flash('Você não tem permissão para avaliar este colaborador.', 'danger')
                    return redirect(url_for('employee_evaluation.evaluate'))
                
                # Final submission: perform existing save logic
                # Check if evaluation already exists
                # Para avaliações de experiência (45/90 dias), verificar se já existe QUALQUER avaliação desse tipo
                # Para avaliações mensais, verificar apenas no mês selecionado
                if evaluation_type in ['experiencia_45', 'experiencia_90']:
                    existing = EmployeeEvaluation.query.filter_by(
                        evaluator_id=current_user.id,
                        evaluated_id=evaluated_id,
                        evaluation_type=evaluation_type
                    ).first()
                else:
                    existing = EmployeeEvaluation.query.filter_by(
                        evaluator_id=current_user.id,
                        evaluated_id=evaluated_id,
                        month_reference=month_reference,
                        evaluation_type=evaluation_type
                    ).first()

                if existing:
                    if evaluation_type in ['experiencia_45', 'experiencia_90']:
                        flash('Você já realizou esta avaliação de experiência para este colaborador. Esta avaliação só pode ser feita uma vez.', 'warning')
                    else:
                        flash('Você já realizou este tipo de avaliação para este colaborador neste mês.', 'warning')
                    return redirect(url_for('employee_evaluation.evaluate'))

                evaluation = EmployeeEvaluation(
                    evaluator_id=current_user.id,
                    evaluated_id=evaluated_id,
                    month_reference=month_reference,
                    evaluation_type=evaluation_type,
                    rating=int(request.form.get('rating', 0)),
                    rating_justification=request.form.get('rating_justification'),
                    validation_status='pending'  # Requer validação colaborativa
                )

                if evaluation_type == 'mensal':
                    # Novos campos de critérios com Conforme/Não Conforme/Não se Aplica
                    evaluation.criteria_punctuality = request.form.get('criteria_punctuality')
                    evaluation.criteria_punctuality_justification = request.form.get('criteria_punctuality_justification')
                    
                    evaluation.criteria_quality = request.form.get('criteria_quality')
                    evaluation.criteria_quality_justification = request.form.get('criteria_quality_justification')
                    
                    evaluation.criteria_productivity = request.form.get('criteria_productivity')
                    evaluation.criteria_productivity_justification = request.form.get('criteria_productivity_justification')
                    
                    evaluation.criteria_teamwork = request.form.get('criteria_teamwork')
                    evaluation.criteria_teamwork_justification = request.form.get('criteria_teamwork_justification')
                    
                    evaluation.criteria_communication = request.form.get('criteria_communication')
                    evaluation.criteria_communication_justification = request.form.get('criteria_communication_justification')
                    
                    evaluation.criteria_initiative = request.form.get('criteria_initiative')
                    evaluation.criteria_initiative_justification = request.form.get('criteria_initiative_justification')
                    
                    evaluation.criteria_compliance = request.form.get('criteria_compliance')
                    evaluation.criteria_compliance_justification = request.form.get('criteria_compliance_justification')
                    
                    evaluation.criteria_development = request.form.get('criteria_development')
                    evaluation.criteria_development_justification = request.form.get('criteria_development_justification')
                    
                    # Campos de observações adicionais
                    evaluation.strong_points = request.form.get('strong_points')
                    evaluation.development_points = request.form.get('development_points')
                    evaluation.action_plan = request.form.get('action_plan')
                    
                    # Campos de ausências e atestados
                    try:
                        evaluation.absence_count = int(request.form.get('absence_count') or 0)
                    except ValueError:
                        evaluation.absence_count = 0
                    try:
                        evaluation.medical_certificate_count = int(request.form.get('medical_certificate_count') or 0)
                    except ValueError:
                        evaluation.medical_certificate_count = 0
                    
                    # Calcular o score automaticamente
                    evaluation.calculate_score()
                else:
                    # Experience Evaluation Fields (map 45/90 depending on form names)
                    # Attempt to map both possible names
                    try:
                        evaluation.comm_verbal = int(request.form.get('comm_verbal') or request.form.get('comm_verbal_45') or request.form.get('comm_verbal_90') or 0)
                    except ValueError:
                        evaluation.comm_verbal = 0
                    try:
                        evaluation.comm_written = int(request.form.get('comm_written') or request.form.get('comm_written_45') or request.form.get('comm_written_90') or 0)
                    except ValueError:
                        evaluation.comm_written = 0
                    try:
                        evaluation.comm_listening = int(request.form.get('comm_listening') or request.form.get('comm_listening_45') or 0)
                    except ValueError:
                        evaluation.comm_listening = 0

                    evaluation.onboarding_unit_presentation = request.form.get('onboarding_unit_presentation') == 'true'
                    evaluation.onboarding_team_welcome = request.form.get('onboarding_team_welcome') == 'true'
                    evaluation.onboarding_expectations = request.form.get('onboarding_expectations') == 'true'
                    evaluation.onboarding_manuals = request.form.get('onboarding_manuals') == 'true'

                    # Keep existing text fields mapping (may come from 45/90 templates)
                    evaluation.strong_points = request.form.get('strong_points') or request.form.get('strong_points_90')
                    # development_notes_90 and post_experience_plan_90 are specific to 90-day flow
                    development_notes_90 = request.form.get('development_notes_90') or request.form.get('development_notes') or request.form.get('development_points')
                    post_plan_90 = request.form.get('post_experience_plan_90') or request.form.get('post_experience_plan') or request.form.get('action_plan')

                    evaluation.development_points = development_notes_90
                    evaluation.action_plan = post_plan_90

                    # approval field - some templates use approval_status_90
                    evaluation.approval_status = request.form.get('approval_status_90') or request.form.get('approval_status')

                    # If this is a 90-day evaluation, collect structured section responses into JSON
                    if evaluation_type and '90' in evaluation_type:
                        details = {
                            'orientation_results': [],
                            'planning': [],
                            'process_management': [],
                            'emotional_intelligence': []
                        }
                        # orientation_results_1..4
                        for i in range(1,5):
                            val = request.form.get(f'orientation_results_{i}')
                            try:
                                details['orientation_results'].append(int(val) if val else None)
                            except ValueError:
                                details['orientation_results'].append(None)

                        # planning_1..4
                        for i in range(1,5):
                            val = request.form.get(f'planning_{i}')
                            try:
                                details['planning'].append(int(val) if val else None)
                            except ValueError:
                                details['planning'].append(None)

                        # process_mgmt_1..4
                        for i in range(1,5):
                            val = request.form.get(f'process_mgmt_{i}')
                            try:
                                details['process_management'].append(int(val) if val else None)
                            except ValueError:
                                details['process_management'].append(None)

                        # emotional_intel_1..4
                        for i in range(1,5):
                            val = request.form.get(f'emotional_intel_{i}')
                            try:
                                details['emotional_intelligence'].append(int(val) if val else None)
                            except ValueError:
                                details['emotional_intelligence'].append(None)

                        # also store the communication group if present under 90 names
                        try:
                            comm_v = int(request.form.get('comm_verbal_90')) if request.form.get('comm_verbal_90') else (int(request.form.get('comm_verbal')) if request.form.get('comm_verbal') else None)
                        except Exception:
                            comm_v = None
                        try:
                            comm_w = int(request.form.get('comm_written_90')) if request.form.get('comm_written_90') else (int(request.form.get('comm_written')) if request.form.get('comm_written') else None)
                        except Exception:
                            comm_w = None
                        try:
                            comm_c = int(request.form.get('comm_collab_90')) if request.form.get('comm_collab_90') else (int(request.form.get('comm_collab')) if request.form.get('comm_collab') else None)
                        except Exception:
                            comm_c = None

                        details['communication'] = {
                            'verbal': comm_v,
                            'written': comm_w,
                            'collaboration': comm_c
                        }

                        evaluation.experience_details = details

                db.session.add(evaluation)
                db.session.commit()
                flash('Avaliação registrada com sucesso!', 'success')
                return redirect(url_for('employee_evaluation.dashboard'))

        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao registrar avaliação: {str(e)}', 'danger')
    
    # Fetch users for selection based on permissions:
    # - Admin/Diretoria (visualizar_todas_avaliacoes_funcionarios): pode avaliar qualquer um
    # - Gestores: só podem avaliar colaboradores que gerenciam
    if current_user.has_permission('admin-total') or current_user.has_permission('visualizar_todas_avaliacoes_funcionarios'):
        # Pode avaliar qualquer usuário ativo (exceto a si mesmo)
        users = User.query.filter(User.is_active == True, User.id != current_user.id).order_by(User.name).all()
    else:
        # Só pode avaliar colaboradores que gerencia
        managed_ids = current_user.get_managed_employees_list()
        if managed_ids:
            users = User.query.filter(
                User.is_active == True, 
                User.id.in_(managed_ids)
            ).order_by(User.name).all()
        else:
            users = []
    
    # Get reference month (previous month) - same logic as suppliers
    from datetime import datetime
    now = datetime.now()
    # Calculate previous month: if current month is January, go to December of previous year
    if now.month == 1:
        previous_month = datetime(now.year - 1, 12, 1)
    else:
        previous_month = datetime(now.year, now.month - 1, 1)
    reference_month = previous_month.strftime('%Y-%m')
    
    # Get all monthly evaluations done by current user for reference monthnce month
    existing_evaluations = EmployeeEvaluation.query.filter_by(
        evaluator_id=current_user.id,
        month_reference=reference_month,
        evaluation_type='mensal'
    ).all()
    
    # Get all experience evaluations (45/90 days) - these are global (not month-specific)
    experience_evaluations = EmployeeEvaluation.query.filter(
        EmployeeEvaluation.evaluator_id == current_user.id,
        EmployeeEvaluation.evaluation_type.in_(['experiencia_45', 'experiencia_90'])
    ).all()
    
    # Create dict of evaluated_id -> list of evaluation_types
    # Um colaborador pode ter múltiplas avaliações de tipos diferentes
    evaluated_this_month = {}
    for e in existing_evaluations + experience_evaluations:
        user_id_str = str(e.evaluated_id)
        if user_id_str not in evaluated_this_month:
            evaluated_this_month[user_id_str] = []
        if e.evaluation_type not in evaluated_this_month[user_id_str]:
            evaluated_this_month[user_id_str].append(e.evaluation_type)
    
    # Converter listas para strings separadas por vírgula para uso no template
    evaluated_this_month_str = {
        k: ','.join(v) for k, v in evaluated_this_month.items()
    }
    
    return render_template('avaliacao/funcionarios/avaliar.html', 
                           users=users, 
                           evaluated_this_month=evaluated_this_month_str,
                           reference_month=reference_month)


@employee_evaluation_bp.route('/avaliacao/<int:evaluation_id>/excluir', methods=['POST'])
@login_required
def delete_evaluation(evaluation_id):
    """Excluir uma avaliação de colaborador"""
    from app.models import CounterEvaluation, ValidationSession
    
    evaluation = EmployeeEvaluation.query.get_or_404(evaluation_id)
    employee_id = evaluation.evaluated_id
    employee_name = evaluation.evaluated.name if evaluation.evaluated else 'Colaborador'
    
    # Verificar permissão: apenas o avaliador original ou admin pode excluir
    # Para simplificar, permitimos que qualquer usuário logado exclua (pode-se adicionar RBAC depois)
    # Ou você pode descomentar a verificação abaixo:
    # if evaluation.evaluator_id != current_user.id and not current_user.has_permission('admin-total'):
    #     flash('Você não tem permissão para excluir esta avaliação.', 'danger')
    #     return redirect(url_for('employee_evaluation.employee_history', employee_id=employee_id))
    
    try:
        # Primeiro, excluir registros dependentes para evitar erro de integridade
        
        # Excluir sessões de validação associadas
        ValidationSession.query.filter_by(evaluation_id=evaluation_id).delete()
        
        # Excluir contra-avaliação associada (se existir)
        CounterEvaluation.query.filter_by(original_evaluation_id=evaluation_id).delete()
        
        # Agora excluir a avaliação principal
        db.session.delete(evaluation)
        db.session.commit()
        flash(f'Avaliação de {employee_name} excluída com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir avaliação: {str(e)}', 'danger')
    
    return redirect(url_for('employee_evaluation.employee_history', employee_id=employee_id))
