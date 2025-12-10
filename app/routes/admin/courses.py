from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models import db, Course, UserCourseProgress, Quiz, UserQuizAttempt, CourseEnrollmentTerm
from app.utils.rbac_permissions import require_permission
from .utils import handle_database_error
import os
import logging
import shutil
from datetime import datetime

courses_bp = Blueprint('courses', __name__, url_prefix='/courses')

logger = logging.getLogger(__name__)
ALLOWED_CONTENT_TYPES = {
    'video': {'.mp4'},
    'pdf': {'.pdf'}
}


def _validate_course_file(file_storage, expected_type):
    """Validate uploaded course file according to expected type."""
    if not file_storage or file_storage.filename == '':
        return False, "O arquivo do curso é obrigatório."

    extension = os.path.splitext(file_storage.filename)[1].lower()
    allowed_extensions = ALLOWED_CONTENT_TYPES.get(expected_type, set())
    if extension not in allowed_extensions:
        if expected_type == 'video':
            return False, "Formato de vídeo inválido. Utilize arquivos MP4."
        if expected_type == 'pdf':
            return False, "Formato inválido. Apenas arquivos PDF são permitidos."
        return False, "Formato de arquivo inválido."

    return True, ""

@courses_bp.route('/<int:course_id>/all-attendance')
@login_required
@require_permission('admin-total')
@handle_database_error("visualizar lista de todos os alunos do curso")
def view_course_all_attendance(course_id):
    from app.models import User
    from sqlalchemy.orm import joinedload
    course = Course.query.options(joinedload(Course.created_by)).get_or_404(course_id)

    all_users = User.query.filter_by(is_active=True).all()
    progress_map = {p.user_id: p for p in UserCourseProgress.query.filter_by(course_id=course_id).all()}
    enrollment_map = {e.user_id: e for e in CourseEnrollmentTerm.query.filter_by(course_id=course_id).all()}

    completed = []
    in_progress = []
    not_started = []
    for user in all_users:
        progress = progress_map.get(user.id)
        enrollment = enrollment_map.get(user.id)
        if progress and progress.completed_at:
            best_score = None
            if course.quiz:
                attempt = UserQuizAttempt.query.filter_by(quiz_id=course.quiz.id, user_id=user.id).order_by(UserQuizAttempt.score.desc().nullslast()).first()
                if attempt and attempt.score is not None:
                    best_score = attempt.score
            completed.append({
                'user': user,
                'full_name': enrollment.full_name if enrollment else user.name,
                'email': enrollment.email if enrollment else user.email,
                'accepted_at': enrollment.accepted_at if enrollment else None,
                'score': best_score,
                'progress': progress
            })
        elif progress and progress.last_watched_timestamp > 0:
            in_progress.append({
                'user': user,
                'full_name': enrollment.full_name if enrollment else user.name,
                'email': enrollment.email if enrollment else user.email,
                'accepted_at': enrollment.accepted_at if enrollment else None,
                'score': None,
                'progress': progress
            })
        else:
            not_started.append({
                'user': user,
                'full_name': enrollment.full_name if enrollment else user.name,
                'email': enrollment.email if enrollment else user.email,
                'accepted_at': enrollment.accepted_at if enrollment else None,
                'score': None,
                'progress': None
            })

    completed.sort(key=lambda e: (e['full_name'] or '').lower())
    in_progress.sort(key=lambda e: (e['full_name'] or '').lower())
    not_started.sort(key=lambda e: (e['full_name'] or '').lower())

    enrollments = completed + in_progress + not_started

    start_date = request.args.get('start_date', '________________')
    start_time = request.args.get('start_time', '________')
    end_time = request.args.get('end_time', '________')
    location = request.args.get('location', 'CENTRAL DO COLABORADOR PLATAFORMA DE TREINAMENTOS ONLINE')
    delivery_mode = request.args.get('mode', 'online').lower()
    is_online = delivery_mode != 'presencial'

    return render_template(
        'training/course_attendance_print.html',
        course=course,
        enrollments=enrollments,
        start_date=start_date,
        start_time=start_time,
        end_time=end_time,
        location=location,
        is_online=is_online,
        show_status_column=True,
        participants_title='Todos os participantes'
    )

@courses_bp.route('/<int:course_id>/not-started-attendance')
@login_required
@require_permission('admin-total')
@handle_database_error("visualizar lista de alunos não iniciaram do curso")
def view_course_not_started(course_id):
    from app.models import User
    from sqlalchemy.orm import joinedload
    course = Course.query.options(joinedload(Course.created_by)).get_or_404(course_id)

    all_users = User.query.filter_by(is_active=True).all()
    progressed_users = set(
        p.user_id for p in UserCourseProgress.query.filter_by(course_id=course_id).all()
    )
    not_started_users = [u for u in all_users if u.id not in progressed_users]

    enrollments = []
    for user in not_started_users:
        enrollment_term = CourseEnrollmentTerm.query.filter_by(course_id=course_id, user_id=user.id).first()
        enrollments.append(
            {
                'user': user,
                'full_name': enrollment_term.full_name if enrollment_term else user.name,
                'email': enrollment_term.email if enrollment_term else user.email,
                'accepted_at': enrollment_term.accepted_at if enrollment_term else None,
                'score': None,
                'progress': None
            }
        )

    enrollments.sort(key=lambda e: (e['full_name'] or '').lower())

    start_date = request.args.get('start_date', '________________')
    start_time = request.args.get('start_time', '________')
    end_time = request.args.get('end_time', '________')
    location = request.args.get('location', 'CENTRAL DO COLABORADOR PLATAFORMA DE TREINAMENTOS ONLINE')
    delivery_mode = request.args.get('mode', 'online').lower()
    is_online = delivery_mode != 'presencial'

    return render_template(
        'training/course_attendance_print.html',
        course=course,
        enrollments=enrollments,
        start_date=start_date,
        start_time=start_time,
        end_time=end_time,
        location=location,
        is_online=is_online,
        hide_score_column=True,
        hide_accept_column=True,
        participants_title='Participantes que não iniciaram'
    )
    
@courses_bp.route('/<int:course_id>/in-progress-attendance')
@login_required
@require_permission('admin-total')
@handle_database_error("visualizar lista de alunos em andamento do curso")
def view_course_in_progress(course_id):
    from sqlalchemy.orm import joinedload
    course = Course.query.options(joinedload(Course.created_by)).get_or_404(course_id)

    in_progress = UserCourseProgress.query.filter(
        UserCourseProgress.course_id == course_id,
        UserCourseProgress.completed_at == None,
        UserCourseProgress.last_watched_timestamp > 0
    ).all()

    enrollments = []
    for prog in in_progress:
        user = prog.user
        enrollment_term = CourseEnrollmentTerm.query.filter_by(course_id=course_id, user_id=prog.user_id).first()

        best_score = None
        if course.quiz:
            attempt = UserQuizAttempt.query.filter_by(quiz_id=course.quiz.id, user_id=prog.user_id).order_by(UserQuizAttempt.score.desc().nullslast()).first()
            if attempt and attempt.score is not None:
                best_score = attempt.score

        enrollments.append(
            {
                'user': user,
                'full_name': enrollment_term.full_name if enrollment_term else (user.name if user else ''),
                'email': enrollment_term.email if enrollment_term else (user.email if user else '---'),
                'accepted_at': enrollment_term.accepted_at if enrollment_term else None,
                'score': best_score,
                'progress': prog
            }
        )

    enrollments.sort(key=lambda e: (e['full_name'] or '').lower())

    start_date = request.args.get('start_date', '________________')
    start_time = request.args.get('start_time', '________')
    end_time = request.args.get('end_time', '________')
    location = request.args.get('location', 'CENTRAL DO COLABORADOR PLATAFORMA DE TREINAMENTOS ONLINE')
    delivery_mode = request.args.get('mode', 'online').lower()
    is_online = delivery_mode != 'presencial'

    return render_template(
        'training/course_attendance_print.html',
        course=course,
        enrollments=enrollments,
        start_date=start_date,
        start_time=start_time,
        end_time=end_time,
        location=location,
        is_online=is_online,
        hide_score_column=True,
        participants_title='Participantes em andamento'
    )

# ==========================================
# ROTAS DE GESTÃO DE CURSOS
# ==========================================

@courses_bp.route('/')
@login_required
@require_permission('admin-total')
@handle_database_error("listar cursos")
def manage_courses():
    """Gerenciar cursos"""
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10

    query = Course.query.order_by(Course.date_registry.desc())

    if search:
        query = query.filter(
            db.or_(
                Course.title.ilike(f'%{search}%'),
                Course.description.ilike(f'%{search}%')
            )
        )

    if status_filter:
        is_active = status_filter == 'active'
        query = query.filter(Course.is_active == is_active)

    courses = query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )

    return render_template(
        'training/manage_courses.html',
        courses=courses,
        search=search,
        status_filter=status_filter
    )

@courses_bp.route('/create', methods=['POST'])
@login_required
@require_permission('admin-total')
@handle_database_error("criar curso")
def create_course():
    """Criar novo curso"""
    title = request.form.get('title', '').strip()
    content_type = request.form.get('content_type', 'video')

    if not title:
        flash("Título do curso é obrigatório.", "danger")
        return redirect(url_for("admin.courses.manage_courses"))

    course_file = request.files.get('video')
    is_valid, error_message = _validate_course_file(course_file, content_type)
    if not is_valid:
        flash(error_message, "danger")
        return redirect(url_for("admin.courses.manage_courses"))

    description = request.form.get('description', '').strip()
    duration_seconds = request.form.get('duration_seconds', 0, type=int)
    sources = request.form.get('sources', '').strip()
    scope = request.form.get('scope', '').strip()

    course_folder_name = secure_filename(title)
    course_upload_path = os.path.join('/app/uploads/courses', course_folder_name)
    os.makedirs(course_upload_path, exist_ok=True)

    course_filename = secure_filename(course_file.filename)
    course_file.save(os.path.join(course_upload_path, course_filename))

    image_filename = None
    image_field = request.files.get('image')
    if image_field and image_field.filename:
        image_filename = secure_filename(image_field.filename)
        image_field.save(os.path.join(course_upload_path, image_filename))

    new_course = Course(
        title=title,
        description=description,
        video_filename=course_filename,
        image_filename=image_filename,
        duration_seconds=duration_seconds,
        date_registry=datetime.utcnow(),
        created_by_id=current_user.id,
        sources=sources if sources else None,
        scope=scope if scope else None
    )

    db.session.add(new_course)
    db.session.commit()

    logger.info(f"Curso criado por {current_user.username}: {title}")
    flash("Novo curso criado com sucesso!", "success")
    return redirect(url_for("admin.courses.manage_courses"))

@courses_bp.route('/<int:course_id>/edit', methods=['POST'])
@login_required
@require_permission('admin-total')
@handle_database_error("editar curso")
def edit_course(course_id):
    """Editar curso existente"""
    course = Course.query.get_or_404(course_id)
    
    old_title = course.title
    new_title = request.form.get('title', '').strip()
    
    if not new_title:
        flash('Título do curso é obrigatório.', 'warning')
        return redirect(url_for('admin.courses.manage_courses'))

    course.title = new_title
    course.description = request.form.get('description', '').strip()
    course.duration_seconds = request.form.get('duration_seconds', course.duration_seconds, type=int)
    course.sources = request.form.get('sources', '').strip() or None
    course.scope = request.form.get('scope', '').strip() or None

    old_folder_name = secure_filename(old_title)
    new_folder_name = secure_filename(new_title)
    old_course_path = os.path.join('/app/uploads/courses', old_folder_name)
    new_course_path = os.path.join('/app/uploads/courses', new_folder_name)

    if old_title != new_title and os.path.exists(old_course_path):
        try:
            os.makedirs(os.path.dirname(new_course_path), exist_ok=True)
            shutil.move(old_course_path, new_course_path)
            logger.info(f"Pasta do curso renomeada de '{old_folder_name}' para '{new_folder_name}'")
        except Exception as e:
            logger.error(f"Erro ao renomear pasta do curso: {str(e)}")
            flash('Erro ao atualizar arquivos do curso.', 'warning')
    
    os.makedirs(new_course_path, exist_ok=True)

    new_file = request.files.get('video')
    if new_file and new_file.filename:
        requested_type = request.form.get('content_type', course.content_type or 'video')
        is_valid, error_message = _validate_course_file(new_file, requested_type)
        if not is_valid:
            flash(error_message, "danger")
            return redirect(url_for("admin.courses.manage_courses"))

        if course.video_filename:
            old_file_path = os.path.join(new_course_path, course.video_filename)
            if os.path.exists(old_file_path):
                try:
                    os.remove(old_file_path)
                except Exception as e:
                    logger.warning(f"Não foi possível remover arquivo antigo do curso: {str(e)}")

        new_filename = secure_filename(new_file.filename)
        new_file.save(os.path.join(new_course_path, new_filename))
        course.video_filename = new_filename

    if 'image' in request.files and request.files['image'].filename != '':
        image_file = request.files['image']
        if image_file:
            if course.image_filename:
                old_image_path = os.path.join(new_course_path, course.image_filename)
                if os.path.exists(old_image_path):
                    try:
                        os.remove(old_image_path)
                    except Exception as e:
                        logger.warning(f"Não foi possível remover imagem antiga: {str(e)}")

            image_filename = secure_filename(image_file.filename)
            image_file.save(os.path.join(new_course_path, image_filename))
            course.image_filename = image_filename

    db.session.commit()

    logger.info(f"Curso editado por {current_user.username}: {course.title}")
    flash(f'Curso "{course.title}" atualizado com sucesso!', 'success')
    return redirect(url_for('admin.courses.manage_courses'))

@courses_bp.route('/<int:course_id>/toggle-status', methods=['POST'])
@login_required
@require_permission('admin-total')
@handle_database_error("alterar status do curso")
def toggle_course_status(course_id):
    """Ativar/desativar curso"""
    course = Course.query.get_or_404(course_id)
    course.is_active = not course.is_active

    db.session.commit()

    status_text = "ativado" if course.is_active else "desativado"
    logger.info(f"Curso {status_text} por {current_user.username}: {course.title}")
    flash(f'Curso "{course.title}" foi {status_text} com sucesso!', 'success')
    return redirect(url_for('admin.courses.manage_courses'))

@courses_bp.route('/<int:course_id>/delete', methods=['POST'])
@login_required
@require_permission('admin-total')
@handle_database_error("deletar curso")
def delete_course(course_id):
    """Deletar curso"""
    course_to_delete = Course.query.get_or_404(course_id)
    course_title = course_to_delete.title

    course_folder_name = secure_filename(course_title)
    course_folder_path = os.path.join('/app/uploads/courses', course_folder_name)

    if os.path.exists(course_folder_path):
        shutil.rmtree(course_folder_path)

    db.session.delete(course_to_delete)
    db.session.commit()

    logger.info(f"Curso deletado por {current_user.username}: {course_title}")
    flash(f'Curso "{course_title}" foi excluído com sucesso.', "success")
    return redirect(url_for("admin.courses.manage_courses"))

@courses_bp.route('/<int:course_id>/progress')
@login_required
@require_permission('admin-total')
def view_course_progress(course_id):
    from app.models import User
    course = Course.query.get_or_404(course_id)

    all_users = User.query.filter_by(is_active=True).all()
    
    progress_map = {}
    progress_records = UserCourseProgress.query.filter_by(course_id=course_id).all()
    for progress in progress_records:
        progress_map[progress.user_id] = progress

    enrollment_map = {}
    enrollment_records = CourseEnrollmentTerm.query.filter_by(course_id=course_id).all()
    for enrollment in enrollment_records:
        enrollment_map[enrollment.user_id] = enrollment

    all_progress_data = []
    for user in all_users:
        if user.id in progress_map:
            all_progress_data.append({
                'user': user,
                'progress': progress_map[user.id],
                'has_progress': True,
                'enrollment_term': enrollment_map.get(user.id)
            })
        else:
            all_progress_data.append({
                'user': user,
                'progress': None,
                'has_progress': False,
                'enrollment_term': enrollment_map.get(user.id)
            })

    all_progress_data.sort(key=lambda x: (not x['has_progress'], x['user'].name.lower()))

    total_users = len(all_users)
    users_completed = len([x for x in all_progress_data if x['progress'] and x['progress'].completed_at])
    users_with_progress = len([x for x in all_progress_data if x['has_progress']])
    users_not_started = total_users - users_with_progress
    users_not_completed = len([x for x in all_progress_data if x['progress'] and not x['progress'].completed_at])

    total_score = 0
    quiz_attempts = 0
    attempts_map = {}

    if course.quiz:
        from app.models import UserQuizAttempt
        attempts = UserQuizAttempt.query.filter_by(quiz_id=course.quiz.id).all()
        for attempt in attempts:
            if attempt.score is not None:
                total_score += attempt.score
                quiz_attempts += 1
            
            user_id = attempt.user_id
            if user_id not in attempts_map or (attempt.score and attempt.score > attempts_map[user_id].get('score', 0)):
                attempts_map[user_id] = {
                    'score': attempt.score,
                    'submitted_at': attempt.submitted_at,
                    'answers': attempt.answers
                }

    average_score = (total_score / quiz_attempts) if quiz_attempts > 0 else 0

    chart_data = {'labels': [], 'data': []}
    if course.quiz and quiz_attempts > 0:
        score_ranges = {
            '0-20%': 0,
            '21-40%': 0,
            '41-60%': 0,
            '61-80%': 0,
            '81-100%': 0
        }
        for user_id, attempt_data in attempts_map.items():
            score = attempt_data.get('score', 0)
            if score <= 20:
                score_ranges['0-20%'] += 1
            elif score <= 40:
                score_ranges['21-40%'] += 1
            elif score <= 60:
                score_ranges['41-60%'] += 1
            elif score <= 80:
                score_ranges['61-80%'] += 1
            else:
                score_ranges['81-100%'] += 1
        
        chart_data = {
            'labels': list(score_ranges.keys()),
            'data': list(score_ranges.values())
        }

    import json
    chart_data_json = json.dumps(chart_data)

    return render_template(
        'training/course_progress.html',
        course=course,
        progress_data=all_progress_data,
        average_score=average_score,
        attempts_map=attempts_map,
        chart_data_json=chart_data_json,
        total_users=total_users,
        users_completed=users_completed,
        users_not_started=users_not_started,
        users_not_completed=users_not_completed
    )


@courses_bp.route('/<int:course_id>/enrollment-term/<int:user_id>')
@login_required
@require_permission('admin-total')
@handle_database_error("visualizar termo de inscricao do curso")
def view_course_enrollment_term(course_id, user_id):
    from app.models import User
    from sqlalchemy.orm import joinedload

    # Carregar o criador do curso explicitamente
    course = Course.query.options(joinedload(Course.created_by)).get_or_404(course_id)
    user = User.query.get_or_404(user_id)

    enrollment = CourseEnrollmentTerm.query.filter_by(
        course_id=course_id,
        user_id=user_id
    ).first_or_404()

    return render_template(
        'training/course_enrollment_term_print.html',
        course=course,
        user=user,
        enrollment=enrollment
    )


@courses_bp.route('/<int:course_id>/enrollment-attendance')
@login_required
@require_permission('admin-total')
@handle_database_error("visualizar lista de presenca do curso")
def view_course_attendance(course_id):
    from sqlalchemy.orm import joinedload
    course = Course.query.options(joinedload(Course.created_by)).get_or_404(course_id)

    completed_progress = UserCourseProgress.query.filter(
        UserCourseProgress.course_id == course_id,
        UserCourseProgress.completed_at != None
    ).all()

    enrollments = []
    for prog in completed_progress:
        user = prog.user
        enrollment_term = CourseEnrollmentTerm.query.filter_by(course_id=course_id, user_id=prog.user_id).first()

        best_score = None
        if course.quiz:
            attempt = UserQuizAttempt.query.filter_by(quiz_id=course.quiz.id, user_id=prog.user_id).order_by(UserQuizAttempt.score.desc().nullslast()).first()
            if attempt and attempt.score is not None:
                best_score = attempt.score

        enrollments.append(
            {
                'user': user,
                'full_name': enrollment_term.full_name if enrollment_term else (user.name if user else ''),
                'email': enrollment_term.email if enrollment_term else (user.email if user else '---'),
                'accepted_at': enrollment_term.accepted_at if enrollment_term else None,
                'score': best_score,
                'progress': prog
            }
        )

    enrollments.sort(key=lambda e: (e['full_name'] or '').lower())

    start_date = request.args.get('start_date', '________________')
    start_time = request.args.get('start_time', '________')
    end_time = request.args.get('end_time', '________')
    location = request.args.get('location', 'CENTRAL DO COLABORADOR PLATAFORMA DE TREINAMENTOS ONLINE')
    delivery_mode = request.args.get('mode', 'online').lower()

    is_online = delivery_mode != 'presencial'

    return render_template(
        'training/course_attendance_print.html',
        course=course,
        enrollments=enrollments,
        start_date=start_date,
        start_time=start_time,
        end_time=end_time,
        location=location,
        is_online=is_online
    )


@courses_bp.route('/<int:course_id>/reset-progress', methods=['POST'])
@login_required
@require_permission('admin-total')
@handle_database_error("resetar progresso")
def reset_course_progress(course_id):
    course = Course.query.get_or_404(course_id)

    UserCourseProgress.query.filter_by(course_id=course_id).delete()
    db.session.commit()

    logger.info(f"Progresso resetado por {current_user.username} no curso: {course.title}")
    flash(f'Progresso de todos os usuários no curso "{course.title}" foi resetado.', 'success')
    return redirect(url_for('admin.courses.view_course_progress', course_id=course_id))

@courses_bp.route('/<int:course_id>/reset-user-progress/<int:user_id>', methods=['POST'])
@login_required
@require_permission('admin-total')
@handle_database_error("resetar progresso do usuário")
def reset_user_course_progress(course_id, user_id):
    course = Course.query.get_or_404(course_id)
    from app.models import User
    user = User.query.get_or_404(user_id)

    UserCourseProgress.query.filter_by(course_id=course_id, user_id=user_id).delete()
    
    if course.quiz:
        UserQuizAttempt.query.filter_by(quiz_id=course.quiz.id, user_id=user_id).delete()
    
    db.session.commit()

    logger.info(f"Progresso resetado por {current_user.username} para usuário {user.username} no curso: {course.title}")
    flash(f'Progresso do usuário "{user.username}" no curso "{course.title}" foi resetado.', 'success')
    return redirect(url_for('admin.courses.view_course_progress', course_id=course_id))

# ==========================================
# ROTAS DE SERVIÇO DE ARQUIVOS
# ==========================================

@courses_bp.route('/<int:course_id>/video')
@login_required
def serve_course_video(course_id):
    """Servir conteúdo principal dos cursos"""
    try:
        course = Course.query.get_or_404(course_id)
        if not course.video_filename:
            flash("Arquivo do curso não encontrado.", "warning")
            return redirect(url_for('admin.courses.manage_courses'))

        course_folder_name = secure_filename(course.title)
        content_path = os.path.join('/app/uploads/courses', course_folder_name)
        file_path = os.path.join(content_path, course.video_filename)

        if not os.path.exists(file_path):
            flash("Arquivo do curso não encontrado no servidor.", "warning")
            return redirect(url_for('admin.courses.manage_courses'))

        return send_from_directory(content_path, course.video_filename)
    except Exception as e:
        logger.error(f"Erro ao servir arquivo do curso: {str(e)}")
        return redirect(url_for('admin.courses.manage_courses'))

@courses_bp.route('/<int:course_id>/user/<int:user_id>/certificate')
@login_required
@require_permission('view_courses')
def view_user_certificate(course_id, user_id):
    """Rota para o gestor visualizar o certificado de um usuário específico"""
    from app.models import User
    from sqlalchemy.orm import joinedload
    
    course = Course.query.options(joinedload(Course.created_by)).get_or_404(course_id)
    user = User.query.get_or_404(user_id)
    
    # Buscar progresso do usuário
    progress = UserCourseProgress.query.filter_by(
        user_id=user_id,
        course_id=course_id
    ).first()
    
    # Verificar se o curso foi concluído
    if not progress or not progress.completed_at:
        flash(f"O usuário {user.name} ainda não concluiu este treinamento.", "warning")
        return redirect(url_for('admin.courses.view_course_progress', course_id=course_id))
    
    # Buscar termo de inscrição
    enrollment = CourseEnrollmentTerm.query.filter_by(
        user_id=user_id,
        course_id=course_id
    ).first()
    
    # Buscar melhor tentativa do quiz (se houver)
    attempt = None
    if course.quiz:
        attempt = UserQuizAttempt.query.filter_by(
            user_id=user_id,
            quiz_id=course.quiz.id
        ).order_by(UserQuizAttempt.score.desc()).first()
    
    return render_template(
        'training/course_certificate.html',
        course=course,
        user=user,
        progress=progress,
        enrollment=enrollment,
        attempt=attempt
    )

@courses_bp.route('/<int:course_id>/image')
@login_required
def serve_course_image(course_id):
    """Servir imagens dos cursos"""
    try:
        course = Course.query.get_or_404(course_id)
        if not course.image_filename:
            return redirect(url_for('static', filename='images/default_course.png'))

        course_folder_name = secure_filename(course.title)
        image_path = os.path.join('/app/uploads/courses', course_folder_name)

        return send_from_directory(image_path, course.image_filename)
    except Exception as e:
        logger.error(f"Erro ao servir imagem do curso: {str(e)}")
        return redirect(url_for('static', filename='images/default_course.png'))




