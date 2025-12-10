
import os
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
from app.models import db, Notice
from .utils import admin_required, handle_database_error, create_secure_folder, validate_file_extension, logger

notices_bp = Blueprint('notices', __name__, url_prefix='/notices')

# ==========================================
# ROTAS DE GESTÃO DE AVISOS
# ==========================================

@notices_bp.route("/", methods=["GET", "POST"])
@login_required
@admin_required
def manage_notices():
    if request.method == "POST":
        return create_notice()
    
    return list_notices()

@login_required
@admin_required
@handle_database_error("criar aviso")
def create_notice():
    """Criar novo aviso"""
    notice_type = request.form.get("notice_type")
    
    if notice_type == "TEXT":
        return create_text_notice()
    elif notice_type == "IMAGE":
        return create_image_notice()
    else:
        flash("Tipo de aviso inválido.", "warning")
        return redirect(url_for("admin.notices.manage_notices"))

def create_text_notice():
    """Criar aviso de texto"""
    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    
    if not title or not content:
        flash("Para avisos de texto, título e conteúdo são obrigatórios.", "warning")
        return redirect(url_for("admin.notices.manage_notices"))
    
    new_notice = Notice(
        title=title, 
        content=content, 
        notice_type='TEXT', 
        author_id=current_user.id
    )
    db.session.add(new_notice)
    db.session.commit()
    
    logger.info(f"Aviso de texto criado por {current_user.username}: {title}")
    flash("Aviso em texto publicado com sucesso!", "success")
    return redirect(url_for("admin.notices.manage_notices"))

def create_image_notice():
    """Criar aviso de imagem"""
    if 'image_file' not in request.files or request.files['image_file'].filename == '':
        flash("Nenhum arquivo de imagem selecionado.", "warning")
        return redirect(url_for("admin.notices.manage_notices"))
    
    image_file = request.files['image_file']
    filename = secure_filename(image_file.filename)
    
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    if not validate_file_extension(filename, allowed_extensions):
        flash("Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF, WEBP", "warning")
        return redirect(url_for("admin.notices.manage_notices"))
    
    upload_path = os.path.join(current_app.root_path, 'uploads', 'notices')
    if not create_secure_folder(upload_path):
        flash("Erro ao criar diretório de upload.", "danger")
        return redirect(url_for("admin.notices.manage_notices"))
    
    unique_filename = f"{uuid.uuid4().hex}_{filename}"
    image_file.save(os.path.join(upload_path, unique_filename))
    
    new_notice = Notice(
        image_filename=unique_filename, 
        notice_type='IMAGE', 
        author_id=current_user.id
    )
    db.session.add(new_notice)
    db.session.commit()
    
    logger.info(f"Aviso de imagem criado por {current_user.username}: {unique_filename}")
    flash("Imagem publicada com sucesso no mural!", "success")
    return redirect(url_for("admin.notices.manage_notices"))

#<--- Listar Avisos --->
@login_required
@admin_required
def list_notices():
    try:
        notices_query = db.select(Notice).order_by(Notice.date_registry.desc())
        notices_list = db.session.execute(notices_query).scalars().all()
        return render_template("manage_notices.html", notices=notices_list)
    except Exception as e:
        logger.error(f"Erro ao carregar avisos: {str(e)}")
        flash("Erro ao carregar avisos.", "danger")
        return render_template("manage_notices.html", notices=[])

#<--- Rota para Deletar Aviso --->
@notices_bp.route("/delete/<int:notice_id>", methods=["POST"])
@login_required
@admin_required
@handle_database_error("deletar aviso")
def delete_notice(notice_id):
    """Deletar aviso"""
    notice_to_delete = Notice.query.get_or_404(notice_id)
    
    if notice_to_delete.notice_type == 'IMAGE' and notice_to_delete.image_filename:
        try:
            image_path = os.path.join(
                current_app.root_path, 
                'uploads', 
                'notices', 
                notice_to_delete.image_filename
            )
            if os.path.exists(image_path):
                os.remove(image_path)
        except Exception as e:
            logger.warning(f"Erro ao remover arquivo de imagem: {str(e)}")
    
    notice_title = notice_to_delete.title or notice_to_delete.image_filename
    db.session.delete(notice_to_delete)
    db.session.commit()
    
    logger.info(f"Aviso deletado por {current_user.username}: {notice_title}")
    flash("Aviso deletado com sucesso.", "success")
    return redirect(url_for("admin.notices.manage_notices"))

#<--- Rota para Servir Imagens --->
@notices_bp.route('/image/<path:filename>')
@login_required
def serve_notice_image(filename):
    try:
        notice_upload_path = '/app/uploads/notices'
        file_path = os.path.join(notice_upload_path, filename)
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            flash("Arquivo não encontrado.", "warning")
            return redirect(url_for('admin.notices.manage_notices'))
        
        return send_from_directory(notice_upload_path, filename)
    except Exception as e:
        logger.error(f"Erro ao servir imagem: {str(e)}")
        return redirect(url_for('admin.notices.manage_notices'))
