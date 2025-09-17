from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models import db, Course, UserCourseProgress, Quiz, UserQuizAttempt
from app.utils.rbac_permissions import require_permission
from .utils import handle_database_error
import os
import logging
import shutil
from datetime import datetime

logger = logging.getLogger(__name__)

courses_bp = Blueprint('courses', __name__, url_prefix='/courses')

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
    if 'video' not in request.files or not request.form.get('title'):
        flash("Título e arquivo de vídeo são obrigatórios.", "danger")
        return redirect(url_for("admin.courses.manage_courses"))

    title = request.form['title'].strip()
    description = request.form.get('description', '').strip()
    duration_seconds = request.form.get('duration_seconds', 0, type=int)

    course_folder_name = secure_filename(title)
    course_upload_path = os.path.join(current_app.root_path, 'uploads', 'courses', course_folder_name)
    os.makedirs(course_upload_path, exist_ok=True)

    video_file = request.files['video']
    video_filename = secure_filename(video_file.filename)
    video_file.save(os.path.join(course_upload_path, video_filename))

    image_filename = None
    if 'image' in request.files and request.files['image'].filename != '':
        image_file = request.files['image']
        image_filename = secure_filename(image_file.filename)
        image_file.save(os.path.join(course_upload_path, image_filename))

    new_course = Course(
        title=title,
        description=description,
        video_filename=video_filename,
        image_filename=image_filename,
        duration_seconds=duration_seconds,
        date_registry=datetime.utcnow()
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

    old_folder_name = secure_filename(old_title)
    new_folder_name = secure_filename(new_title)
    old_course_path = os.path.join(current_app.root_path, 'uploads', 'courses', old_folder_name)
    new_course_path = os.path.join(current_app.root_path, 'uploads', 'courses', new_folder_name)

    if old_title != new_title and os.path.exists(old_course_path):
        try:
            os.makedirs(os.path.dirname(new_course_path), exist_ok=True)
            shutil.move(old_course_path, new_course_path)
            logger.info(f"Pasta do curso renomeada de '{old_folder_name}' para '{new_folder_name}'")
        except Exception as e:
            logger.error(f"Erro ao renomear pasta do curso: {str(e)}")
            flash('Erro ao atualizar arquivos do curso.', 'warning')
    
    os.makedirs(new_course_path, exist_ok=True)

    if 'video' in request.files and request.files['video'].filename != '':
        video_file = request.files['video']
        if video_file:
            if course.video_filename:
                old_video_path = os.path.join(new_course_path, course.video_filename)
                if os.path.exists(old_video_path):
                    try:
                        os.remove(old_video_path)
                    except Exception as e:
                        logger.warning(f"Não foi possível remover vídeo antigo: {str(e)}")
            
            video_filename = secure_filename(video_file.filename)
            video_file.save(os.path.join(new_course_path, video_filename))
            course.video_filename = video_filename

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
    course_folder_path = os.path.join(current_app.root_path, 'uploads', 'courses', course_folder_name)

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
    """Ver progresso dos usuários no curso"""
    course = Course.query.get_or_404(course_id)

    progress_records = UserCourseProgress.query.filter_by(course_id=course_id).all()

    total_users = UserCourseProgress.query.filter_by(course_id=course_id).count()
    users_completed = UserCourseProgress.query.filter(
        UserCourseProgress.course_id == course_id,
        UserCourseProgress.completed_at.isnot(None)
    ).count()
    completion_rate = (users_completed / total_users * 100) if total_users > 0 else 0
    users_with_progress = UserCourseProgress.query.filter(
        UserCourseProgress.course_id == course_id,
        UserCourseProgress.last_watched_timestamp > 0
    ).count()

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

    return render_template(
        'training/course_progress.html',
        course=course,
        progress_data=progress_records,
        average_score=average_score,
        attempts_map=attempts_map,
        progress_stats={
            'total_users': total_users,
            'users_completed': users_completed,
            'completion_rate': completion_rate,
            'users_with_progress': users_with_progress
        }
    )


@courses_bp.route('/<int:course_id>/reset-progress', methods=['POST'])
@login_required
@require_permission('admin-total')
@handle_database_error("resetar progresso")
def reset_course_progress(course_id):
    """Resetar progresso de todos os usuários no curso"""
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
    """Resetar progresso de um usuário específico no curso"""
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
    """Servir vídeos dos cursos"""
    try:
        course = Course.query.get_or_404(course_id)
        if not course.video_filename:
            flash("Vídeo não encontrado.", "warning")
            return redirect(url_for('admin.courses.manage_courses'))

        course_folder_name = secure_filename(course.title)
        video_path = os.path.join(current_app.root_path, 'uploads', 'courses', course_folder_name)

        return send_from_directory(video_path, course.video_filename)
    except Exception as e:
        logger.error(f"Erro ao servir vídeo: {str(e)}")
        return redirect(url_for('admin.courses.manage_courses'))

@courses_bp.route('/<int:course_id>/image')
@login_required
def serve_course_image(course_id):
    """Servir imagens dos cursos"""
    try:
        course = Course.query.get_or_404(course_id)
        if not course.image_filename:
            return redirect(url_for('static', filename='images/default_course.png'))

        course_folder_name = secure_filename(course.title)
        image_path = os.path.join(current_app.root_path, 'uploads', 'courses', course_folder_name)

        return send_from_directory(image_path, course.image_filename)
    except Exception as e:
        logger.error(f"Erro ao servir imagem do curso: {str(e)}")
        return redirect(url_for('static', filename='images/default_course.png'))