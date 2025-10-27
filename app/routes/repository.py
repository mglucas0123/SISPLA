import os
import shutil
from flask import (
    Blueprint, current_app, redirect, render_template, 
    request, send_from_directory, abort, url_for, flash, jsonify
)
from flask_login import current_user, login_required
from sqlalchemy import or_
from werkzeug.utils import secure_filename
from app.models import db, File, Repository

repository_bp = Blueprint('repository', __name__, template_folder='../templates')

# =========================================================================
#                           FUNÇÕES AUXILIARES
# =========================================================================

def get_repo_folder_path(repo):
    return os.path.join(
        current_app.config['UPLOAD_FOLDER'],
        repo.access_type.capitalize(),
        repo.folder_name
    )

def has_repo_access(repo, user):
    return (
        repo.access_type == 'public' or
        repo.owner_id == user.id or
        (repo.access_type == 'shared' and user in repo.shared_with_users)
    )

def get_file_and_validate_access(file_id):
    file_obj = File.query.get_or_404(file_id)
    if not has_repo_access(file_obj.repository, current_user):
        abort(403)
    return file_obj

def get_folder_full_path(folder: File) -> str:
    if folder.parent:
        return os.path.join(get_folder_full_path(folder.parent), folder.name)
    else:
        return folder.name
    

def get_folder_physical_path(folder_obj):
    repo_root_path = get_repo_folder_path(folder_obj.repository)
    
    path_parts = []
    current_folder = folder_obj
    while current_folder:
        path_parts.append(current_folder.name)
        current_folder = current_folder.parent
    
    return os.path.join(repo_root_path, *reversed(path_parts))
    
def get_item_physical_path(item):
    repo = item.repository
    repo_root_path = get_repo_folder_path(repo)
    
    path_parts = []
    parent = item.parent
    while parent:
        path_parts.append(parent.name)
        parent = parent.parent
    path_parts.reverse()

    subfolder_path = os.path.join(*path_parts) if path_parts else ''
    if not item.is_folder:
        return os.path.join(repo_root_path, subfolder_path, item.filename)
    else:
        return os.path.join(repo_root_path, subfolder_path, item.name)
    
def recursively_delete_item(item):
    if item.is_folder:
        for child in item.children:
            recursively_delete_item(child)
            
        folder_physical_path = get_item_physical_path(item)
        if os.path.exists(folder_physical_path):
            shutil.rmtree(folder_physical_path)

    else:
        file_physical_path = get_item_physical_path(item)
        if os.path.exists(file_physical_path):
            os.remove(file_physical_path)

    db.session.delete(item)
    
def get_item_directory_path(file_obj):
    repo_folder_path = get_repo_folder_path(file_obj.repository)
    
    if file_obj.parent_id:
        path_parts = []
        parent = file_obj.parent
        while parent:
            path_parts.append(parent.name)
            parent = parent.parent

        return os.path.join(repo_folder_path, *reversed(path_parts))
    else:
        return repo_folder_path
    
#<!--- EXIBIR LISTA DE REPOSITÓRIOS ACESSIVEIS --->
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

#<!--- EXIBE O CONTEÚDO DE UM REPOSITÓRIO OU SUBPASTA --->
@repository_bp.route('/repository/<int:repo_id>')
@repository_bp.route('/repository/<int:repo_id>/folder/<int:folder_id>')
@login_required
def repository_detail_page(repo_id, folder_id=None):
    repo = Repository.query.get_or_404(repo_id)
    if not has_repo_access(repo, current_user):
        abort(403)

    current_folder = File.query.get_or_404(folder_id) if folder_id else None
    if current_folder and (not current_folder.is_folder or current_folder.repository_id != repo.id):
        abort(404)

    breadcrumbs = []
    if current_folder:
        parent = current_folder.parent
        while parent:
            breadcrumbs.append(parent)
            parent = parent.parent
    breadcrumbs.reverse()
    
    folders = File.query.filter_by(repository_id=repo.id, is_folder=True, parent_id=folder_id).order_by(File.name).all()
    files = File.query.filter_by(repository_id=repo.id, is_folder=False, parent_id=folder_id).order_by(File.name).all()

    if current_folder:
        current_physical_path = get_folder_physical_path(current_folder)
    else:
        current_physical_path = get_repo_folder_path(repo)
    
    files_with_details = []
    for file_obj in files:
        caminho_da_subpasta = ""
        full_path = os.path.join(current_physical_path, file_obj.filename)
        size_in_bytes = os.path.getsize(full_path) if os.path.exists(full_path) else 0
        _, extension = os.path.splitext(file_obj.filename)
        
        for pasta in breadcrumbs:
            caminho_da_subpasta += pasta.name + "/"
            full_path = os.path.join(current_physical_path, caminho_da_subpasta, file_obj.filename)
            size_in_bytes = os.path.getsize(full_path) if os.path.exists(full_path) else 0
        
        files_with_details.append({
            'id': file_obj.id, 'name': file_obj.name, 'filename': file_obj.filename,
            'description': file_obj.description, 'date_uploaded': file_obj.date_uploaded,
            'extension': extension.lower(), 'size': size_in_bytes
        })
        
    all_folders_for_moving = File.query.filter_by(
            repository_id=repo.id, 
            is_folder=True
        ).order_by(File.name).all()
        
    
    return render_template("repository/repository_detail.html", repository=repo, current_folder=current_folder, folders=folders, files=files_with_details, breadcrumbs=breadcrumbs, all_folders=all_folders_for_moving)

#<!--- UPLOAD DE ARQUIVO --->
from app.utils.rbac_permissions import require_permission

@repository_bp.route('/repository/<int:repo_id>/upload', methods=['POST'])
@login_required
@require_permission('admin-total')
def upload_file(repo_id):
    repo = Repository.query.get_or_404(repo_id)
    if not has_repo_access(repo, current_user):
        abort(403)

    uploaded_files = request.files.getlist('file')
    parent_id_str = request.form.get('parent_id')
    parent_id = int(parent_id_str) if parent_id_str else None

    if not uploaded_files or uploaded_files[0].filename == '':
        flash("Nenhum arquivo selecionado.", "danger")
        return redirect(request.referrer)

    destination_path = get_repo_folder_path(repo)
    if parent_id:
        parent_folder = File.query.get(parent_id)
        if parent_folder:
            destination_path = get_folder_physical_path(parent_folder)

    os.makedirs(destination_path, exist_ok=True)
    
    for file_get in uploaded_files:
        filename_secure = secure_filename(file_get.filename)
        name_only, _ = os.path.splitext(filename_secure)
        
        file_get.save(os.path.join(destination_path, filename_secure))

        new_file = File(
            name=name_only,
            filename=filename_secure,
            repository_id=repo.id,
            owner_id=current_user.id,
            parent_id=parent_id
        )
        db.session.add(new_file)

    db.session.commit()
    flash(f"{len(uploaded_files)} arquivo(s) enviados com sucesso!", "success")
    
    if parent_id:
        return redirect(url_for('repository.repository_detail_page', repo_id=repo.id, folder_id=parent_id))
    else:
        return redirect(url_for('repository.repository_detail_page', repo_id=repo.id))
    

#<!--- CRIAR PASTA --->
@repository_bp.route('/repository/<int:repo_id>/create_folder', methods=['POST'])
@login_required
@require_permission('admin-total')
def create_folder(repo_id):
    repo = Repository.query.get_or_404(repo_id)
    if not has_repo_access(repo, current_user):
        abort(403)

    data = request.get_json()
    parent_id = data.get('parent_id') 
    folder_name = data.get('folder_name', '').strip()
    if not folder_name:
        return jsonify({'success': False, 'error': 'O nome da pasta não pode ser vazio.'}), 400

    base_path = get_repo_folder_path(repo)

    if parent_id:
        parent_folder = File.query.get_or_404(parent_id)
        parent_full_path = get_folder_full_path(parent_folder)
        current_path = os.path.join(base_path, parent_full_path, folder_name)
    else:
        current_path = os.path.join(base_path, folder_name)

    try:
        if os.path.exists(current_path):
            return jsonify({'success': False, 'error': 'Uma pasta com este nome já existe neste local.'}), 409

        os.makedirs(current_path)

        new_folder = File(
            name=folder_name,
            is_folder=True,
            repository_id=repo.id,
            owner_id=current_user.id,
            filename=folder_name,
            parent_id=parent_id
        )
        db.session.add(new_folder)
        db.session.commit()
        
        flash('Pasta criada com sucesso!', 'success')

        folder_data = {
            'id': new_folder.id,
            'name': new_folder.name,
            'is_folder': new_folder.is_folder,
            'date_uploaded': new_folder.date_uploaded.strftime('%d/%m/%Y %H:%M'),
            'type': 'Pasta'
        }
        return jsonify({'success': True, 'folder': folder_data})
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao criar pasta: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

#<!--- VISUALIZAR ARQUIVO --->
@repository_bp.route('/file/view/<int:file_id>')
@login_required
def view_file(file_id):
    file_obj = get_file_and_validate_access(file_id)
    directory_path = get_item_directory_path(file_obj)
    return send_from_directory(directory_path, file_obj.filename)

#<!--- BAIXAR ARQUIVO --->
@repository_bp.route('/file/download/<int:file_id>')
@login_required
def download_file(file_id):
    file_obj = get_file_and_validate_access(file_id)
    directory_path = get_item_directory_path(file_obj)
    return send_from_directory(directory_path, file_obj.filename, as_attachment=True)

#<!--- RENOMEAR ARQUIVOS/PASTAS --->
@repository_bp.route('/file/rename/<int:file_id>', methods=['POST'])
@login_required
def rename_file(file_id):
    file_obj = get_file_and_validate_access(file_id)
    new_name_from_prompt = request.json.get('new_name', '').strip()

    if not new_name_from_prompt:
        return jsonify({'success': False, 'error': 'Novo nome não fornecido.'}), 400

    is_folder = file_obj.is_folder
    
    if is_folder:
        new_name_base = new_name_from_prompt
        new_filename_secure = new_name_base 
    else:
        new_name_base = os.path.splitext(new_name_from_prompt)[0]
        original_extension = os.path.splitext(file_obj.filename)[1]
        new_filename_secure = secure_filename(new_name_base + original_extension)

    repo_root_path = get_repo_folder_path(file_obj.repository)
    
    if file_obj.parent_id:
        parent_folder_obj = File.query.get(file_obj.parent_id)
        current_dir_path = os.path.join(repo_root_path, parent_folder_obj.name)
    else:
        current_dir_path = repo_root_path

    old_path = os.path.join(current_dir_path, file_obj.filename)
    new_path = os.path.join(current_dir_path, new_filename_secure)

    if os.path.exists(new_path) and old_path.lower() != new_path.lower():
        return jsonify({'success': False, 'error': 'Um item com este nome já existe neste local.'}), 409
    
    try:
        if os.path.exists(old_path):
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

#<!--- DELETAR ARQUIVOS --->
@repository_bp.route('/file/delete/<int:file_id>', methods=['POST'])
@login_required
def delete_file(file_id):
    item_to_delete = get_file_and_validate_access(file_id)
    repo_id_to_redirect = item_to_delete.repository_id

    try:
        recursively_delete_item(item_to_delete)
        
        db.session.commit()
        flash("Item e seu conteúdo foram excluídos com sucesso.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao deletar o item: {str(e)}", "danger")
        
    return redirect(url_for('repository.repository_detail_page', repo_id=repo_id_to_redirect))


#<!--- MOVER ARQUIVOS/PASTAS --->
@repository_bp.route('/file/move', methods=['POST'])
@login_required
def move_file():
    data = request.get_json()
    file_id = data.get('file_id')
    target_folder_id = data.get('target_folder_id')

    item_to_move = get_file_and_validate_access(file_id)
    
    old_path = get_item_physical_path(item_to_move)

    if target_folder_id:
        target_folder = get_file_and_validate_access(target_folder_id)
        if not target_folder.is_folder:
            return jsonify({'success': False, 'error': 'O destino não é uma pasta válida.'}), 400
        destination_folder_path = get_item_physical_path(target_folder)
        new_path = os.path.join(destination_folder_path, item_to_move.filename)
    else:
        repo_root_path = get_repo_folder_path(item_to_move.repository)
        new_path = os.path.join(repo_root_path, item_to_move.filename)
    
    try:
        if os.path.exists(old_path):
            os.makedirs(os.path.dirname(new_path), exist_ok=True) 
            shutil.move(old_path, new_path)
        else:
            return jsonify({'success': False, 'error': 'Arquivo de origem não encontrado no disco.'}), 404
        
        item_to_move.parent_id = target_folder_id
        db.session.commit()
        
        flash("Item movido com sucesso!", "success")
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        if os.path.exists(new_path):
            shutil.move(new_path, old_path)
        return jsonify({'success': False, 'error': str(e)}), 500


#<!--- BUSCAR TODOS OS ARQUIVOS RECURSIVAMENTE NO REPOSITÓRIO --->
@repository_bp.route('/repository/<int:repo_id>/all-files', methods=['GET'])
@login_required
def get_all_repository_files(repo_id):
    """Retorna todos os arquivos e pastas do repositório em formato hierárquico"""
    repo = Repository.query.get_or_404(repo_id)
    if not has_repo_access(repo, current_user):
        abort(403)

    def get_file_tree(parent_id=None):
        """Recursivamente obtém todos os arquivos e pastas"""
        items = []
        
        # Obter pastas
        folders = File.query.filter_by(
            repository_id=repo.id,
            is_folder=True,
            parent_id=parent_id
        ).order_by(File.name).all()
        
        # Obter arquivos
        files = File.query.filter_by(
            repository_id=repo.id,
            is_folder=False,
            parent_id=parent_id
        ).order_by(File.name).all()
        
        # Adicionar pastas
        for folder in folders:
            folder_data = {
                'id': folder.id,
                'name': folder.name,
                'type': 'folder',
                'parent_id': folder.parent_id,
                'date': folder.date_uploaded.isoformat() if folder.date_uploaded else None,
            }
            items.append(folder_data)
            # Recursivamente adicionar subitens
            items.extend(get_file_tree(folder.id))
        
        # Adicionar arquivos
        for file_obj in files:
            _, extension = os.path.splitext(file_obj.filename)
            file_data = {
                'id': file_obj.id,
                'name': file_obj.name,
                'type': 'file',
                'extension': extension.lower(),
                'parent_id': file_obj.parent_id,
                'date': file_obj.date_uploaded.isoformat() if file_obj.date_uploaded else None,
            }
            items.append(file_data)
        
        return items
    
    all_items = get_file_tree()
    return jsonify({'success': True, 'items': all_items})