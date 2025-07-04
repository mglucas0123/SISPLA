import os
from flask import (
    Blueprint, current_app, redirect, render_template, 
    request, send_from_directory, abort, url_for, flash, jsonify
)
from flask_login import current_user, login_required
from sqlalchemy import or_
from werkzeug.utils import secure_filename
from db import db, File, Repository

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
    description_get = request.form.get('description', '')
    filename_secure = secure_filename(file_get.filename)
    name_only, _ = os.path.splitext(filename_secure)

    repo_folder_path = os.path.join(current_app.config['UPLOAD_FOLDER'], f"repo_{repo.id}")
    os.makedirs(repo_folder_path, exist_ok=True)
    file_path = os.path.join(repo_folder_path, filename_secure)
    file_get.save(file_path)

    new_file = File(
        name=name_only,
        filename=filename_secure,
        description=description_get,
        repository_id=repo.id,
        owner_id=current_user.id
    )
    db.session.add(new_file)
    db.session.commit()
    flash("Arquivo enviado com sucesso!", "success")
    return redirect(url_for('repository.repository_detail_page', repo_id=repo.id))


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
    repo_folder_path = os.path.join(current_app.config['UPLOAD_FOLDER'], f"repo_{file_obj.repository_id}")
    return send_from_directory(repo_folder_path, file_obj.filename)

@repository_bp.route('/file/download/<int:file_id>')
@login_required
def download_file(file_id):
    file_obj = get_file_and_validate_access(file_id)
    repo_folder_path = os.path.join(current_app.config['UPLOAD_FOLDER'], f"repo_{file_obj.repository_id}")
    return send_from_directory(repo_folder_path, file_obj.filename, as_attachment=True)


@repository_bp.route('/repository/rename/<int:file_id>', methods=['POST'])
@login_required
def rename_file(file_id):
    file_obj = get_file_and_validate_access(file_id)
    new_name_from_prompt = request.json.get('new_name', '').strip()

    if not new_name_from_prompt:
        return jsonify({'success': False, 'error': 'Novo nome não fornecido.'}), 400

    new_name_base = os.path.splitext(new_name_from_prompt)[0]
    original_extension = os.path.splitext(file_obj.filename)[1]
    new_filename_secure = secure_filename(new_name_base + original_extension)

    safe_username_folder = secure_filename(file_obj.owner.username)
    user_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], safe_username_folder)
    
    old_path = os.path.join(user_folder, file_obj.filename)
    new_path = os.path.join(user_folder, new_filename_secure)

    if os.path.exists(new_path):
        return jsonify({'success': False, 'error': 'Já existe um arquivo com este nome.'}), 409
    
    try:
        os.rename(old_path, new_path)
        file_obj.name = new_name_base
        file_obj.filename = new_filename_secure
        db.session.commit()
        return jsonify({'success': True, 'new_name': new_name_base})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': f"Erro de sistema: {str(e)}"}), 500
    
@repository_bp.route('/file/delete/<int:file_id>', methods=['POST'])
@login_required
def delete_file(file_id):
    file_obj = get_file_and_validate_access(file_id)
    
    repo_id_to_redirect = file_obj.repository_id

    try:
        repo_folder_path = os.path.join(current_app.config['UPLOAD_FOLDER'], f"repo_{file_obj.repository_id}")
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
    return render_template("repository_list.html", repositories=all_accessible_repos)




@repository_bp.route('/repository/<int:repo_id>')
@login_required
def repository_detail_page(repo_id):
    repo = Repository.query.get_or_404(repo_id)
    
    has_access = (
        repo.access_type == 'public' or
        repo.owner_id == current_user.id or
        (repo.access_type == 'shared' and current_user in repo.shared_with_users)
    )
    if not has_access:
        abort(403)

    files_with_ext = []
    for file_obj in repo.files:
        _, extension = os.path.splitext(file_obj.filename)
        files_with_ext.append({
            'id': file_obj.id,
            'name': file_obj.name,
            'description': file_obj.description,
            'date_uploaded': file_obj.date_uploaded,
            'extension': extension.lower()
        })
    files_with_ext.sort(key=lambda x: x['date_uploaded'], reverse=True)
    
    return render_template("repository/repository_detail.html", repository=repo, files=files_with_ext)
