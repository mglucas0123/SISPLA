from datetime import datetime
import os
from flask import Blueprint, current_app, json, render_template, request, redirect, url_for, session, flash
from flask_login import current_user, login_required
from sqlalchemy import select
from werkzeug.security import generate_password_hash
from functools import wraps
from db import AnswerOption, Course, Question, Quiz, UserCourseProgress, UserQuizAttempt, db, User, Notice, Repository, File, Form
import shutil
from werkzeug.utils import secure_filename

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'ADMIN' not in current_user.profile:
            flash("Acesso negado. Ação restrita a administradores.", "danger")
            return redirect(url_for('main.panel'))
        return f(*args, **kwargs)
    return decorated_function

#<-- CRIAR NOVO USUÁRIO -->
@admin_bp.route("/users", methods=["GET", "POST"])
@login_required
@admin_required
def users():
    if request.method == "POST":
        name_base = request.form["name"]
        username_base = request.form["username"]
        password_base = generate_password_hash(request.form["password"])
        email_base = request.form.get("email") 
        profile_base = request.form.getlist("profile")
        profile_str = ",".join(profile_base)
    
        (User.email == email_base)

        existing_user = User.query.filter((User.username == username_base)).first()
        if existing_user:
            flash("Nome de usuário já cadastrado no sistema.", "warning")
            return redirect(url_for("admin.users"))
        
        existing_email = User.query.filter((User.email == email_base)).first()
        if existing_email:
            flash("E-mail já cadastrado no sistema.", "warning")
            return redirect(url_for("admin.users"))

        new_user = User(
            name=name_base, 
            username=username_base, 
            password=password_base, 
            email=email_base,
            profile=profile_str
        )
                
        db.session.add(new_user)
        db.session.commit()
        flash("Usuário cadastrado com sucesso!", "success")
        return redirect(url_for("admin.users"))

    page_get = request.args.get('page', 1, type=int)
    pagination = User.query.order_by(User.name).paginate(page=page_get, per_page=10, error_out=False)
    users_in_page = pagination.items
    
    return render_template("users.html", users=users_in_page, pagination=pagination)

#<-- TROCAR SENHA -->
@admin_bp.route("/admin_change_password/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def admin_change_password(user_id):
    nova_senha = request.form.get("nova_senha")
    if not nova_senha:
        flash("Senha inválida.", "danger")
        return redirect(url_for("admin.users"))

    user = User.query.get(user_id)
    if user:
        user.password = generate_password_hash(nova_senha)
        db.session.commit()
        flash("Senha atualizada com sucesso.", "success")
    else:
        flash("Usuário não encontrado.", "danger")

    return redirect(url_for("admin.users"))

#<-- DELETAR USUARIO -->
@admin_bp.route("/users/delete_user/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    if user_id == current_user.id:
        flash("Você não pode deletar a si mesmo!", "danger")
        return redirect(url_for("admin.users"))
    
    user = db.session.get(User, user_id)
    if user:
        db.session.delete(user)
        db.session.commit()
        flash("Usuário deletado com sucesso.", "success")
    else:
        flash("Usuário não encontrado.", "danger")
    return redirect(url_for("admin.users"))

#<-- EDITAR PERMISSÕES -->
@admin_bp.route("/users/change_permissions/<int:user_id_to_edit>", methods=["POST"])
@login_required
@admin_required
def change_permissions(user_id_to_edit):
    user_to_edit = db.session.get(User, user_id_to_edit)
    if not user_to_edit:
        flash("Usuário não encontrado.", "danger")
        return redirect(url_for("admin.users"))

    new_permissions_list = request.form.getlist("profile_edit")

    if user_to_edit.id == current_user.id and "ADMIN" not in new_permissions_list:
        flash("Você não pode remover sua própria permissão de ADMIN.", "warning")
        return redirect(url_for("admin.users"))
    
    user_to_edit.profile = ",".join(new_permissions_list) if new_permissions_list else ""
    db.session.commit()
    flash(f"Permissões do usuário '{user_to_edit.name}' foram atualizadas!", "success")
    return redirect(url_for("admin.users"))

#<-- EDITAR STATUS DA CONTA -->
@admin_bp.route("/users/toggle_status/<int:user_id_to_toggle>", methods=["POST"])
@login_required
@admin_required
def toggle_user_status(user_id_to_toggle):
    if user_id_to_toggle == current_user.id:
        flash("Você não pode desativar sua própria conta.", "warning")
        return redirect(url_for("admin.users"))

    user_to_toggle = db.session.get(User, user_id_to_toggle)
    if not user_to_toggle:
        flash("Usuário não encontrado.", "danger")
        return redirect(url_for("admin.users"))

    user_to_toggle.is_active = not user_to_toggle.is_active
    action_text = "ativado" if user_to_toggle.is_active else "desativado"
    
    try:
        db.session.commit()
        flash(f"Usuário '{user_to_toggle.name}' foi {action_text} com sucesso.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao alterar o status do usuário: {str(e)}", "danger")
        
    return redirect(url_for("admin.users"))


@admin_bp.route("/notices", methods=["GET", "POST"])
@login_required
def manage_notices():
    if "ADMIN" not in current_user.profile:
        flash("Acesso negado.", "danger")
        return redirect(url_for("main.panel"))

    if request.method == "POST":
        title_base = request.form.get("title")
        content_base = request.form.get("content")

        if not title_base or not content_base:
            flash("Título e conteúdo são obrigatórios.", "warning")
        else:
            new_notice = Notice(title=title_base, content=content_base, author_id=current_user.id)
            db.session.add(new_notice)
            db.session.commit()
            flash("Aviso publicado com sucesso!", "success")
            return redirect(url_for("admin.manage_notices"))

    notices_query = db.select(Notice).order_by(Notice.date_registry.desc())
    notices_list = db.session.execute(notices_query).scalars().all()
    
    return render_template("manage_notices.html", notices=notices_list)



@admin_bp.route("/notices/delet/<int:notice_id>", methods=["POST"])
@login_required
def delet_notice(notice_id):
    if "ADMIN" not in current_user.profile:
        flash("Acesso negado.", "danger")
        return redirect(url_for("main.panel"))
        
    notice_to_delet = db.session.get(Notice, notice_id)
    if notice_to_delet:
        db.session.delete(notice_to_delet)
        db.session.commit()
        flash("Aviso deletado com sucesso.", "success")
    else:
        flash("Aviso não encontrado.", "warning")

    return redirect(url_for("admin.manage_notices"))

#<---- REPOSITÓRIO ---->
#<-- GERENCIAR REPOSITÓRIOS -->
@admin_bp.route("/repositories")
@login_required
@admin_required
def manage_repositories():
    all_repos = Repository.query.order_by(Repository.name).all()
    all_users = User.query.order_by(User.name).all()
    return render_template("repository/manage_repositories.html", repositories=all_repos, all_users=all_users)

def find_unique_foldername(repo_name, access_type, owner, upload_folder):    
    if access_type == 'private':
        base_foldername = secure_filename(owner.username)
    else:
        safe_owner_username = secure_filename(owner.username)
        safe_repo_name = secure_filename(repo_name)
        base_foldername = f"{safe_owner_username}_{safe_repo_name}_{access_type}"

    parent_dir = os.path.join(upload_folder, access_type.capitalize())
    
    final_foldername = base_foldername
    counter = 1
    while os.path.exists(os.path.join(parent_dir, final_foldername)):
        final_foldername = f"{base_foldername}_{counter}"
        counter += 1
        
    return final_foldername

@admin_bp.route("/repositories/create", methods=["POST"])
@login_required
@admin_required
def create_repository():
    name = request.form.get('name')
    description = request.form.get('description')
    access_type = request.form.get('access_type')
    owner_id = request.form.get('owner_id', current_user.id, type=int)

    if not name:
        flash("O nome do repositório é obrigatório.", "danger")
        return redirect(url_for('admin.manage_repositories'))

    if access_type != 'private':
        owner_id = current_user.id
    
    owner = User.query.get(owner_id)
    if not owner:
        flash("Usuário dono não encontrado.", "danger")
        return redirect(url_for('admin.manage_repositories'))

    upload_folder = current_app.config['UPLOAD_FOLDER']
    unique_folder_name = find_unique_foldername(name, access_type, owner, upload_folder)

    new_repo = Repository(
        name=name,
        description=description,
        access_type=access_type,
        owner_id=owner_id,
        folder_name=unique_folder_name
    )
    db.session.add(new_repo)
    db.session.commit()

    try:
        repo_folder_path = os.path.join(upload_folder, access_type.capitalize(), unique_folder_name)
        os.makedirs(repo_folder_path, exist_ok=True)
        flash(f"Repositório '{name}' criado com sucesso!", "success")
    except Exception as e:
        flash(f"Repositório salvo no banco, mas falha ao criar pasta: {e}", "danger")

    return redirect(url_for('admin.manage_repositories'))

#<-- EDITAR REPOSITÓRIO -->
@admin_bp.route("/repositories/edit/<int:repo_id>", methods=["GET", "POST"])
@login_required
@admin_required
def edit_repository(repo_id):
    repo = Repository.query.get_or_404(repo_id)
    all_users = User.query.filter(User.id != repo.owner_id).order_by(User.name).all()

    if request.method == "POST":
        original_access_type = repo.access_type
        new_access_type = request.form.get('access_type')

        if new_access_type != original_access_type:
            upload_folder = current_app.config['UPLOAD_FOLDER']
            old_parent_dir = os.path.join(upload_folder, original_access_type.capitalize())
            new_parent_dir = os.path.join(upload_folder, new_access_type.capitalize())
            
            old_folder_path = os.path.join(old_parent_dir, repo.folder_name)
            new_folder_path = os.path.join(new_parent_dir, repo.folder_name)

            try:
                os.makedirs(new_parent_dir, exist_ok=True)
                if os.path.exists(old_folder_path):
                    shutil.move(old_folder_path, new_folder_path)
            except Exception as e:
                flash(f"Não foi possível mover a pasta do repositório: {e}", "danger")
                return redirect(url_for('admin.edit_repository', repo_id=repo.id))

        repo.name = request.form.get('name')
        repo.description = request.form.get('description')
        repo.access_type = new_access_type
        
        if repo.access_type == 'shared':
            shared_user_ids = request.form.getlist('shared_users', type=int)
            repo.shared_with_users = User.query.filter(User.id.in_(shared_user_ids)).all()
        else:
            repo.shared_with_users = []
        
        db.session.commit()
        flash("Repositório atualizado com sucesso!", "success")
        return redirect(url_for('admin.manage_repositories'))
        
    return render_template("repository/edit_repository.html", repository=repo, all_users=all_users)

@admin_bp.route("/users/create_private_repo/<int:user_id>", methods=['POST'])
@login_required
@admin_required
def create_private_repo(user_id):
    user = User.query.get_or_404(user_id)

    existing_repo = Repository.query.filter_by(owner_id=user.id, access_type='private').first()
    if existing_repo:
        flash(f"O usuário '{user.name}' já possui um repositório privado.", "warning")
        return redirect(url_for('admin.users'))

    new_repo = Repository(
        name=f"Arquivos de {user.name}",
        description=f"Repositório pessoal para {user.name}.",
        access_type='private',
        owner_id=user.id
    )
    db.session.add(new_repo)
    db.session.commit()

    flash(f"Repositório privado criado com sucesso para '{user.name}'!", "success")
    return redirect(url_for('admin.users'))

@admin_bp.route("/repositories/delete/<int:repo_id>", methods=['POST'])
@login_required
@admin_required
def delete_repository(repo_id):
    repo_to_delete = Repository.query.get_or_404(repo_id)
    try:
        repo_folder_path = os.path.join(
            current_app.config['UPLOAD_FOLDER'], 
            repo_to_delete.access_type.capitalize(), 
            repo_to_delete.folder_name
        )

        if os.path.exists(repo_folder_path):
            shutil.rmtree(repo_folder_path)

        db.session.delete(repo_to_delete)
        db.session.commit()
        flash(f"Repositório '{repo_to_delete.name}' e todos os seus arquivos foram excluídos.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Ocorreu um erro ao excluir o repositório: {str(e)}", "danger")

    return redirect(url_for('admin.manage_repositories'))


#<!--- GERENCIAMENTO DE TREINAMENTOS --->
@admin_bp.route("/courses")
@login_required
@admin_required
def manage_courses():
    query = select(Course).order_by(Course.date_registry.desc())

    page_get = request.args.get('page', 1, type=int)
    pagination = db.paginate(query, page=page_get, per_page=10, error_out=False)

    return render_template(
        "training/manage_courses.html",
        courses=pagination.items, pagination=pagination
    )


# ROTA PARA ATIVAR/DESATIVAR UM CURSO
@admin_bp.route("/courses/toggle_status/<int:course_id>", methods=['POST'])
@login_required
@admin_required
def toggle_course_status(course_id):
    course = Course.query.get_or_404(course_id)
    course.is_active = not course.is_active
    db.session.commit()
    status = "ativado" if course.is_active else "desativado"
    flash(f'O curso "{course.title}" foi {status}.', 'info')
    return redirect(url_for('admin.manage_courses'))

# ROTA PARA VER O PROGRESSO DOS ALUNOS
@admin_bp.route("/courses/progress/<int:course_id>")
@login_required
@admin_required
def view_course_progress(course_id):
    course = Course.query.get_or_404(course_id)
    progress_data = UserCourseProgress.query.filter_by(course_id=course.id).all()
    return render_template("training/course_progress.html", course=course, progress_data=progress_data)

# ROTA PARA DELETAR UM CURSO
@admin_bp.route("/courses/delete/<int:course_id>", methods=['POST'])
@login_required
@admin_required
def delete_course(course_id):
    course_to_delete = Course.query.get_or_404(course_id)

    try:
        course_folder_name = secure_filename(course_to_delete.title)
        course_folder_path = os.path.join(current_app.root_path, 'uploads', 'courses', course_folder_name)

        if os.path.exists(course_folder_path):
            shutil.rmtree(course_folder_path)

        UserQuizAttempt.query.filter_by(quiz_id=course_to_delete.quiz.id if course_to_delete.quiz else None).delete()
        
        db.session.delete(course_to_delete)
        db.session.commit()
        
        flash(f'Curso "{course_to_delete.title}" e todos os seus arquivos foram excluídos com sucesso.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Ocorreu um erro ao excluir o curso: {e}', 'danger')

    return redirect(url_for('admin.manage_courses'))

@admin_bp.route("/courses/edit/<int:course_id>", methods=['POST'])
@login_required
@admin_required
def edit_course(course_id):
    course = Course.query.get_or_404(course_id)
    
    course.title = request.form['title']
    course.description = request.form.get('description', '')
    course.duration_seconds = int(request.form.get('duration_seconds', 0))

    course_folder_name = secure_filename(course.title)
    course_upload_path = os.path.join(current_app.root_path, 'uploads', 'courses', course_folder_name)
    os.makedirs(course_upload_path, exist_ok=True)

    if 'video' in request.files and request.files['video'].filename != '':
        video_file = request.files['video']
        video_filename = secure_filename(video_file.filename)
        video_file.save(os.path.join(course_upload_path, video_filename))
        course.video_filename = video_filename

    if 'image' in request.files and request.files['image'].filename != '':
        image_file = request.files['image']
        image_filename = secure_filename(image_file.filename)
        image_file.save(os.path.join(course_upload_path, image_filename))
        course.image_filename = image_filename
        
    db.session.commit()
    flash('Curso atualizado com sucesso!', 'success')
    return redirect(url_for('admin.manage_courses'))

@admin_bp.route("/courses/create", methods=["POST"])
@login_required
@admin_required
def create_course():
    if 'video' not in request.files or not request.form.get('title'):
        flash("Título e arquivo de vídeo são obrigatórios.", "danger")
        return redirect(url_for("admin.manage_courses"))

    title = request.form['title']
    
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
        title=request.form['title'],
        description=request.form.get('description', ''),
        video_filename=video_filename, 
        image_filename=image_filename,
        duration_seconds=int(request.form.get('duration_seconds', 0)),
        date_registry=datetime.utcnow()
    )
    db.session.add(new_course)
    db.session.commit()
    
    flash("Novo curso criado com sucesso!", "success")
    return redirect(url_for("admin.manage_courses"))

#<!-- PROVA -->
@admin_bp.route("/course/<int:course_id>/quiz", methods=['GET', 'POST'])
@login_required
@admin_required
def manage_quiz(course_id):
    course = Course.query.get_or_404(course_id)
    
    if not course.quiz:
        quiz = Quiz(title=f"Avaliação para {course.title}", course_id=course.id)
        db.session.add(quiz)
        db.session.commit()
    else:
        quiz = course.quiz

    if request.method == 'POST':
        try:
            old_questions = quiz.questions.all()

            for question in old_questions:
                db.session.delete(question)

            db.session.flush()

            questions_data = json.loads(request.form.get('questions_data'))
            
            for q_data in questions_data:
                new_question = Question(
                    quiz_id=quiz.id,
                    text=q_data['text'],
                    question_type=q_data['type']
                )
                db.session.add(new_question)
                
                if q_data['type'] == 'MULTIPLE_CHOICE':
                    db.session.flush()
                    for opt_data in q_data['options']:
                        new_option = AnswerOption(
                            question_id=new_question.id,
                            text=opt_data['text'],
                            is_correct=opt_data['is_correct']
                        )
                        db.session.add(new_option)

            db.session.commit()
            flash("Avaliação salva com sucesso!", "success")
            return redirect(url_for('admin.manage_courses'))

        except Exception as e:
            db.session.rollback()
            flash(f"Ocorreu um erro ao salvar a avaliação: {e}", "danger")
            return redirect(url_for('admin.manage_quiz', course_id=course_id))

    return render_template("training/manage_quiz.html", course=course, quiz=quiz)