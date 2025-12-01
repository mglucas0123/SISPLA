from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app.models import db, User, EmployeeEvaluation
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
    q = db.session.query(
        EmployeeEvaluation.evaluated_id.label('user_id'),
        func.count(EmployeeEvaluation.id).label('evaluations'),
        func.avg(EmployeeEvaluation.rating).label('avg_rating')
    )
    if month:
        q = q.filter(EmployeeEvaluation.month_reference == month)

    q = q.group_by(EmployeeEvaluation.evaluated_id).order_by(desc('avg_rating'), desc('evaluations'))

    rows = q.all()

    # Build rankings with user metadata
    rankings = []
    for r in rows:
        user = User.query.get(r.user_id)
        rankings.append({
            'user_id': r.user_id,
            'name': user.name if user else '—',
            'email': user.email if user else '',
            'job_title': user.job_title if user else '',
            'evaluations': int(r.evaluations),
            'avg_rating': float(r.avg_rating) if r.avg_rating is not None else 0.0
        })

    # Top highlights
    top_manager = rankings[0] if len(rankings) > 0 else None
    top_employee = rankings[1] if len(rankings) > 1 else (rankings[0] if rankings else None)

    return render_template('avaliacao/funcionarios/dashboard.html',
                           top_manager=top_manager,
                           top_employee=top_employee,
                           rankings=rankings,
                           month=month)


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

            # Step navigation: to_step2, to_step3, submit
            if form_step == 'to_step2':
                # Validate step 1 required fields
                if not evaluated_id:
                    flash('Por favor, selecione um colaborador!', 'warning')
                    form_step = 'step1'
                elif not month_reference:
                    flash('Por favor, selecione o mês de referência!', 'warning')
                    form_step = 'step1'
                else:
                    form_step = 'step2'
                    # Render step 2 with submitted values preserved
                    users = User.query.filter(User.is_active == True, User.id != current_user.id).order_by(User.name).all()
                    return render_template('avaliacao/funcionarios/avaliar.html', users=users, form_step=form_step, evaluated_id=evaluated_id, month_reference=month_reference, evaluation_type=evaluation_type, form_data=request.form)

            elif form_step == 'to_step3':
                # Validate step 2 fields depending on evaluation_type
                if evaluation_type == 'mensal':
                    # Required monthly qualitative fields
                    required_fields = ['participation_score', 'innovation_suggestions', 'participation_activities', 'collaborator_goal', 'development_points', 'development_strategy', 'other_analyses']
                    missing = [f for f in required_fields if not request.form.get(f) or (request.form.get(f).strip() == '')]
                    if missing:
                        flash('Por favor, preencha todas as questões qualitativas mensais antes de continuar.', 'warning')
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
                # Final submission: perform existing save logic
                # Check if evaluation already exists for this month
                existing = EmployeeEvaluation.query.filter_by(
                    evaluator_id=current_user.id,
                    evaluated_id=evaluated_id,
                    month_reference=month_reference
                ).first()

                if existing:
                    flash('Você já avaliou este colaborador neste mês.', 'warning')
                    return redirect(url_for('employee_evaluation.evaluate'))

                evaluation = EmployeeEvaluation(
                    evaluator_id=current_user.id,
                    evaluated_id=evaluated_id,
                    month_reference=month_reference,
                    evaluation_type=evaluation_type,
                    rating=int(request.form.get('rating', 0)),
                    rating_justification=request.form.get('rating_justification')
                )

                if evaluation_type == 'mensal':
                    evaluation.participation_score = request.form.get('participation_score')
                    evaluation.innovation_suggestions = request.form.get('innovation_suggestions')
                    evaluation.improvement_proposals = request.form.get('improvement_proposals')
                    # New monthly fields
                    evaluation.participation_activities = request.form.get('participation_activities')
                    evaluation.collaborator_goal = request.form.get('collaborator_goal')
                    evaluation.development_points = request.form.get('development_points')
                    evaluation.development_strategy = request.form.get('development_strategy')
                    evaluation.other_analyses = request.form.get('other_analyses')
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
    
    # Fetch active users for selection (excluding current user)
    users = User.query.filter(User.is_active == True, User.id != current_user.id).order_by(User.name).all()
    
    return render_template('avaliacao/funcionarios/avaliar.html', users=users)
