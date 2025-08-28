from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models import db, Course, UserCourseProgress, Quiz
from .utils import admin_required, handle_database_error
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
@admin_required
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
@admin_required
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
@admin_required
@handle_database_error("editar curso")
def edit_course(course_id):
    """Editar curso existente"""
    course = Course.query.get_or_404(course_id)
    
    course.title = request.form.get('title', '').strip()
    course.description = request.form.get('description', '').strip()
    course.duration_seconds = request.form.get('duration_seconds', course.duration_seconds, type=int)

    if not course.title:
        flash('Título do curso é obrigatório.', 'warning')
        return redirect(url_for('admin.courses.manage_courses'))

    db.session.commit()

    logger.info(f"Curso editado por {current_user.username}: {course.title}")
    flash(f'Curso "{course.title}" atualizado com sucesso!', 'success')
    return redirect(url_for('admin.courses.manage_courses'))

@courses_bp.route('/<int:course_id>/toggle-status', methods=['POST'])
@login_required
@admin_required
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
@admin_required
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
@admin_required
def view_course_progress(course_id):
    """Ver progresso dos usuários no curso"""
    course = Course.query.get_or_404(course_id)
    
    progress_records = UserCourseProgress.query.filter_by(course_id=course_id).all()
    
    return render_template(
        'training/course_progress.html',
        course=course,
        progress_records=progress_records
    )

@courses_bp.route('/<int:course_id>/reset-progress', methods=['POST'])
@login_required
@admin_required
@handle_database_error("resetar progresso")
def reset_course_progress(course_id):
    """Resetar progresso de todos os usuários no curso"""
    course = Course.query.get_or_404(course_id)
    
    UserCourseProgress.query.filter_by(course_id=course_id).delete()
    db.session.commit()
    
    logger.info(f"Progresso resetado por {current_user.username} no curso: {course.title}")
    flash(f'Progresso de todos os usuários no curso "{course.title}" foi resetado.', 'success')
    return redirect(url_for('admin.courses.view_course_progress', course_id=course_id))

# ==========================================
# ROTAS DE SERVIÇO DE ARQUIVOS
# ==========================================

@courses_bp.route('/<int:course_id>/video')
@login_required
@admin_required
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
@admin_required
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
