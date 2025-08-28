from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from sqlalchemy import or_
from werkzeug.utils import secure_filename
from app.models import db, Repository, User
from .utils import admin_required, handle_database_error
import os
import logging
import shutil

logger = logging.getLogger(__name__)

repositories_bp = Blueprint('repositories', __name__, url_prefix='/repositories')

# ==========================================
# ROTAS DE GERENCIAMENTO DE REPOSITÓRIOS
# ==========================================

@repositories_bp.route('/')
@login_required
@admin_required
@handle_database_error("listar repositórios")
def manage_repositories():
    """Gerenciar repositórios"""
    search = request.args.get('search', '').strip()
    access_type_filter = request.args.get('access_type', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10

    query = db.select(Repository).order_by(Repository.date_created.desc())

    if search:
        query = query.where(
            or_(
                Repository.name.ilike(f'%{search}%'),
                Repository.description.ilike(f'%{search}%'),
                Repository.folder_name.ilike(f'%{search}%')
            )
        )

    if access_type_filter:
        query = query.where(Repository.access_type == access_type_filter)

    repositories = db.paginate(
        query,
        page=page,
        per_page=per_page,
        error_out=False
    )

    all_users = db.session.execute(db.select(User).order_by(User.name)).scalars().all()

    return render_template(
        'repository/manage_repositories.html',
        repositories=repositories,
        search=search,
        access_type_filter=access_type_filter,
        all_users=all_users
    )

@repositories_bp.route('/create', methods=['POST'])
@login_required
@admin_required
@handle_database_error("criar repositório")
def create_repository():
    """Criar novo repositório"""
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    access_type = request.form.get('access_type', 'private')
    owner_id = request.form.get('owner_id', type=int)

    if not name:
        flash('Nome do repositório é obrigatório.', 'warning')
        return redirect(url_for('admin.repositories.manage_repositories'))

    if not owner_id:
        flash('Proprietário do repositório é obrigatório.', 'warning')
        return redirect(url_for('admin.repositories.manage_repositories'))

    owner = User.query.get(owner_id)
    if not owner:
        flash('Usuário proprietário não encontrado.', 'danger')
        return redirect(url_for('admin.repositories.manage_repositories'))

    base_folder_name = secure_filename(name)
    folder_name = base_folder_name
    counter = 1

    while Repository.query.filter_by(folder_name=folder_name).first():
        folder_name = f"{base_folder_name}_{counter}"
        counter += 1

    repo_path = os.path.join(
        current_app.config['UPLOAD_FOLDER'],
        access_type.capitalize(),
        folder_name
    )
    os.makedirs(repo_path, exist_ok=True)

    new_repo = Repository(
        name=name,
        description=description,
        folder_name=folder_name,
        access_type=access_type,
        owner_id=owner_id
    )

    db.session.add(new_repo)
    db.session.flush()

    if access_type == 'shared':
        shared_user_ids = request.form.getlist('shared_users')
        if shared_user_ids:
            shared_users = User.query.filter(User.id.in_(shared_user_ids)).all()
            new_repo.shared_with_users = shared_users

    db.session.commit()

    logger.info(f"Repositório criado por {current_user.username}: {name}")
    flash(f'Repositório "{name}" criado com sucesso!', 'success')
    return redirect(url_for('admin.repositories.manage_repositories'))

@repositories_bp.route('/<int:repo_id>/edit', methods=['POST'])
@login_required
@admin_required
@handle_database_error("editar repositório")
def edit_repository(repo_id):
    """Editar repositório existente"""
    repo = Repository.query.get_or_404(repo_id)
    
    new_name = request.form.get('name', '').strip()
    new_description = request.form.get('description', '').strip()
    new_access_type = request.form.get('access_type', repo.access_type)
    new_owner_id = request.form.get('owner_id', type=int)

    if not new_name:
        flash('Nome do repositório é obrigatório.', 'warning')
        return redirect(url_for('admin.repositories.manage_repositories'))

    if new_owner_id and new_owner_id != repo.owner_id:
        new_owner = User.query.get(new_owner_id)
        if not new_owner:
            flash('Novo proprietário não encontrado.', 'danger')
            return redirect(url_for('admin.repositories.manage_repositories'))
        repo.owner_id = new_owner_id

    if new_access_type != repo.access_type:
        old_path = os.path.join(
            current_app.config['UPLOAD_FOLDER'],
            repo.access_type.capitalize(),
            repo.folder_name
        )
        new_path = os.path.join(
            current_app.config['UPLOAD_FOLDER'],
            new_access_type.capitalize(),
            repo.folder_name
        )

        if os.path.exists(old_path):
            os.makedirs(os.path.dirname(new_path), exist_ok=True)
            shutil.move(old_path, new_path)

        repo.access_type = new_access_type

    repo.name = new_name
    repo.description = new_description

    if new_access_type == 'shared':
        shared_user_ids = request.form.getlist('shared_users')
        if shared_user_ids:
            shared_users = User.query.filter(User.id.in_(shared_user_ids)).all()
            repo.shared_with_users = shared_users
        else:
            repo.shared_with_users = []
    else:
        repo.shared_with_users = []

    db.session.commit()

    logger.info(f"Repositório editado por {current_user.username}: {repo.name}")
    flash(f'Repositório "{repo.name}" atualizado com sucesso!', 'success')
    return redirect(url_for('admin.repositories.manage_repositories'))

@repositories_bp.route('/<int:repo_id>/delete', methods=['POST'])
@login_required
@admin_required
@handle_database_error("deletar repositório")
def delete_repository(repo_id):
    """Deletar repositório"""
    repo_to_delete = Repository.query.get_or_404(repo_id)
    repo_name = repo_to_delete.name

    repo_folder_path = os.path.join(
        current_app.config['UPLOAD_FOLDER'],
        repo_to_delete.access_type.capitalize(),
        repo_to_delete.folder_name
    )

    if os.path.exists(repo_folder_path):
        shutil.rmtree(repo_folder_path)

    db.session.delete(repo_to_delete)
    db.session.commit()

    logger.info(f"Repositório deletado por {current_user.username}: {repo_name}")
    flash(f'Repositório "{repo_name}" e todos os seus arquivos foram excluídos.', 'success')
    return redirect(url_for('admin.repositories.manage_repositories'))

@repositories_bp.route('/create-private-for-user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
@handle_database_error("criar repositório privado")
def create_private_repository_for_user(user_id):
    """Criar repositório privado para usuário específico"""
    user = User.query.get_or_404(user_id)

    if user.has_private_repository:
        flash(f'Usuário {user.name} já possui um repositório privado.', 'warning')
        return redirect(url_for('admin.users.list_users'))

    base_folder_name = secure_filename(f"{user.username}_private")
    folder_name = base_folder_name
    counter = 1

    while Repository.query.filter_by(folder_name=folder_name).first():
        folder_name = f"{base_folder_name}_{counter}"
        counter += 1

    repo_path = os.path.join(
        current_app.config['UPLOAD_FOLDER'],
        'Private',
        folder_name
    )
    os.makedirs(repo_path, exist_ok=True)

    private_repo = Repository(
        name=f"Repositório Privado - {user.name}",
        description=f"Repositório privado do usuário {user.name}",
        folder_name=folder_name,
        access_type='private',
        owner_id=user.id
    )

    db.session.add(private_repo)
    db.session.commit()

    logger.info(f"Repositório privado criado por {current_user.username} para usuário: {user.name}")
    flash(f'Repositório privado criado para {user.name}!', 'success')
    return redirect(url_for('admin.users.list_users'))
