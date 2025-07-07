import os
from flask import (
    Blueprint, current_app, redirect, render_template, 
    request, send_from_directory, abort, url_for, flash, jsonify
)
from flask_login import current_user, login_required
from sqlalchemy import or_
from werkzeug.utils import secure_filename
from db import db, File, Repository
import openpyxl

repository_bp = Blueprint('repository', __name__)

@repository_bp.route('/repository')
@login_required
def repository_page():
    accessible_repos_query = db.select(Repository).where(
        or_(
            Repository.access_type == 'public',
            Repository.owner_id == current_user.id,
            Repository.shared_with_users.any(id=current_user.id)
        )
    ).order_by(Repository.name)

    all_accessible_repos = db.session.execute(accessible_repos_query).scalars().all()

    return render_template("repository/repository_list.html", repositories=all_accessible_repos)


@repository_bp.route('/repository/<int:repo_id>/upload', methods=['POST'])
@login_required
def upload_file(repo_id):
    repo = Repository.query.get_or_404(repo_id)

    if 'file' not in request.files or request.files['file'].filename == '':
        flash("Nenhum arquivo selecionado.", "danger")
        return redirect(url_for('repository.repository_detail_page', repo_id=repo.id))

    file_get = request.files['file']
    filename_secure = secure_filename(file_get.filename)
    name_only, _ = os.path.splitext(filename_secure)

    repo_folder_path = get_repo_folder_path(repo)
    os.makedirs(repo_folder_path, exist_ok=True)
    file_path = os.path.join(repo_folder_path, filename_secure)
    file_get.save(file_path)

    new_file = File(
        name=name_only,
        filename=filename_secure,
        description=request.form.get('description', ''),
        repository_id=repo.id,
        owner_id=current_user.id
    )
    db.session.add(new_file)
    db.session.commit()
    flash("Arquivo enviado com sucesso!", "success")
    return redirect(url_for('repository.repository_detail_page', repo_id=repo.id))


def get_repo_folder_path(repo):
    return os.path.join(
        current_app.config['UPLOAD_FOLDER'],
        repo.access_type.capitalize(),
        repo.folder_name
    )

def get_file_and_validate_access(file_id):
    file_obj = File.query.get_or_404(file_id)
    repo = file_obj.repository
    has_access = (
        repo.access_type == 'public' or
        repo.owner_id == current_user.id or
        (repo.access_type == 'shared' and current_user in repo.shared_with_users)
    )
    if not has_access:
        abort(403)
    return file_obj

@repository_bp.route('/file/view/<int:file_id>')
@login_required
def view_file(file_id):
    file_obj = get_file_and_validate_access(file_id)
    repo_folder_path = get_repo_folder_path(file_obj.repository)
    return send_from_directory(repo_folder_path, file_obj.filename)


@repository_bp.route('/file/download/<int:file_id>')
@login_required
def download_file(file_id):
    file_obj = get_file_and_validate_access(file_id)
    repo_folder_path = get_repo_folder_path(file_obj.repository)
    return send_from_directory(repo_folder_path, file_obj.filename, as_attachment=True)

@repository_bp.route('/file/rename/<int:file_id>', methods=['POST'])
@login_required
def rename_file(file_id):
    file_obj = get_file_and_validate_access(file_id)
    new_name_from_prompt = request.json.get('new_name', '').strip()

    if not new_name_from_prompt:
        return jsonify({'success': False, 'error': 'Novo nome não fornecido.'}), 400

    new_name_base = os.path.splitext(new_name_from_prompt)[0]
    original_extension = os.path.splitext(file_obj.filename)[1]
    new_filename_secure = secure_filename(new_name_base + original_extension)

    repo_folder_path = get_repo_folder_path(file_obj.repository)
    old_path = os.path.join(repo_folder_path, file_obj.filename)
    new_path = os.path.join(repo_folder_path, new_filename_secure)
    
    if os.path.exists(new_path) and old_path.lower() != new_path.lower():
        return jsonify({'success': False, 'error': 'Já existe um arquivo com este nome.'}), 409
    
    try:
        os.rename(old_path, new_path)
        file_obj.name = new_name_base
        file_obj.filename = new_filename_secure
        db.session.commit()
        return jsonify({'success': True, 'new_name': new_name_base})
    except Exception as e:
        db.session.rollback()
        if os.path.exists(new_path):
            os.rename(new_path, old_path)
        return jsonify({'success': False, 'error': f"Erro de sistema: {str(e)}"}), 500

    
@repository_bp.route('/file/delete/<int:file_id>', methods=['POST'])
@login_required
def delete_file(file_id):
    file_obj = get_file_and_validate_access(file_id)
    repo_id_to_redirect = file_obj.repository_id

    try:
        repo_folder_path = get_repo_folder_path(file_obj.repository)
        file_path = os.path.join(repo_folder_path, file_obj.filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        db.session.delete(file_obj)
        db.session.commit()
        flash("Arquivo excluído com sucesso.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao deletar o arquivo: {str(e)}", "danger")
        
    return redirect(url_for('repository.repository_detail_page', repo_id=repo_id_to_redirect))



@repository_bp.route('/repository')
@login_required
def repository_list_page():
    accessible_repos_query = db.select(Repository).where(
        or_(
            Repository.access_type == 'public',
            Repository.owner_id == current_user.id,
            Repository.shared_with_users.any(id=current_user.id)
        )
    ).order_by(Repository.name)
    all_accessible_repos = db.session.execute(accessible_repos_query).scalars().all()
    return render_template("repository/repository_list.html", repositories=all_accessible_repos)

@repository_bp.route('/repository/<int:repo_id>/create_folder', methods=['POST'])
@login_required
def create_folder(repo_id):
    repo = Repository.query.get_or_404(repo_id)
    
    folder_name = request.json.get('folder_name', '').strip()
    if not folder_name:
        return jsonify({'success': False, 'error': 'O nome da pasta não pode ser vazio.'}), 400

    new_folder = File(
        name=folder_name,
        is_folder=True,
        repository_id=repo.id,
        owner_id=current_user.id,
    )
    db.session.add(new_folder)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Pasta criada com sucesso!'})

@repository_bp.route('/file/move', methods=['POST'])
@login_required
def move_file():
    data = request.get_json()
    file_id = data.get('file_id')
    target_folder_id = data.get('target_folder_id')

    file_to_move = get_file_and_validate_access(file_id)
    
    if target_folder_id:
        target_folder = get_file_and_validate_access(target_folder_id)
        if not target_folder.is_folder:
            return jsonify({'success': False, 'error': 'O destino selecionado não é uma pasta.'}), 400
        if target_folder.id == file_to_move.id:
            return jsonify({'success': False, 'error': 'Não é possível mover uma pasta para dentro dela mesma.'}), 400
    
    file_to_move.parent_id = target_folder_id
    db.session.commit()
    
    flash("Item movido com sucesso!", "success")
    return jsonify({'success': True})

# Em repository.py

# Rota para a raiz do repositório
@repository_bp.route('/repository/<int:repo_id>')
# Rota para uma subpasta dentro do repositório
@repository_bp.route('/repository/<int:repo_id>/folder/<int:folder_id>')
@login_required
def repository_detail_page(repo_id, folder_id=None):
    """
    Exibe o conteúdo (pastas e arquivos) de um repositório ou de uma subpasta.
    """
    repo = Repository.query.get_or_404(repo_id)
    
    # Valida o acesso ao repositório principal
    has_access = (
        repo.access_type == 'public' or
        repo.owner_id == current_user.id or
        (repo.access_type == 'shared' and current_user in repo.shared_with_users)
    )
    if not has_access:
        abort(403)

    current_folder = None
    if folder_id:
        current_folder = File.query.get_or_404(folder_id)
        if not current_folder.is_folder or current_folder.repository_id != repo.id:
            abort(404)

    breadcrumbs = []
    parent = current_folder
    while parent:
        breadcrumbs.append(parent)
        parent = parent.parent
    breadcrumbs.reverse()

    folders = File.query.filter_by(repository_id=repo.id, is_folder=True, parent_id=folder_id).order_by(File.name).all()
    files = File.query.filter_by(repository_id=repo.id, is_folder=False, parent_id=folder_id).order_by(File.name).all()
    
    files_with_details = []
    repo_folder_path = get_repo_folder_path(repo)
    for file_obj in files:
        full_path = os.path.join(repo_folder_path, file_obj.filename)
        try:
            size_in_bytes = os.path.getsize(full_path) if os.path.exists(full_path) else 0
        except OSError:
            size_in_bytes = 0

        _, extension = os.path.splitext(file_obj.filename)
        
        files_with_details.append({
            'id': file_obj.id,
            'name': file_obj.name,
            'filename': file_obj.filename,
            'description': file_obj.description,
            'date_uploaded': file_obj.date_uploaded,
            'extension': extension.lower(),
            'size': size_in_bytes
        })

    return render_template(
        "repository/repository_detail.html", 
        repository=repo,
        current_folder=current_folder,
        folders=folders,
        files=files_with_details,
        breadcrumbs=breadcrumbs
    )
    