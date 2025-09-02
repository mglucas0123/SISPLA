
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required
from sqlalchemy import or_
from werkzeug.security import generate_password_hash
from app.models import db, User, Repository
from .utils import admin_required, handle_database_error, validate_user_data, logger

users_bp = Blueprint('users', __name__, url_prefix='/users')

# ==========================================
# ROTAS DE LISTAGEM E CRIAÇÃO DE USUÁRIOS
# ==========================================

@users_bp.route("/", methods=["GET", "POST"])
@login_required
@admin_required
def list_users():
    if request.method == "POST":
        return create_user()
    
    return render_users_list()

@login_required
@admin_required
@handle_database_error("criar usuário")
def create_user():
    """Lógica para criar novo usuário"""
    name = request.form.get("name", "").strip()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    email = request.form.get("email", "").strip()
    validation_errors = validate_user_data(name, username, email)
    if validation_errors:
        for error in validation_errors:
            flash(error, "warning")
        return redirect(url_for("admin.users.list_users"))
    
    if len(password) < 8:
        flash("Senha deve ter pelo menos 8 caracteres.", "warning")
        return redirect(url_for("admin.users.list_users"))
    
    existing_user = User.query.filter(
        or_(User.username == username, User.email == email)
    ).first()
    
    if existing_user:
        if existing_user.username == username:
            flash("Nome de usuário já cadastrado no sistema.", "warning")
        else:
            flash("E-mail já cadastrado no sistema.", "warning")
        return redirect(url_for("admin.users.list_users"))
    
    password_hash = generate_password_hash(password)
    
    new_user = User(
        name=name,
        username=username,
        password=password_hash,
        email=email
    )
    
    db.session.add(new_user)
    db.session.commit()
    
    logger.info(f"Usuário criado: {username} por {current_user.username}")
    flash("Usuário cadastrado com sucesso!", "success")
    return redirect(url_for("admin.users.list_users"))

def render_users_list():
    """Renderiza lista de usuários com filtros"""
    search_query = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '')
    profile_filter = request.args.get('profile', '')
    sort_option = request.args.get('sort', 'date_desc')
    
    query = User.query
    
    if search_query:
        query = query.filter(
            or_(
                User.name.ilike(f'%{search_query}%'),
                User.username.ilike(f'%{search_query}%'),
                User.email.ilike(f'%{search_query}%')
            )
        )
    
    if status_filter == 'active':
        query = query.filter(User.is_active == True)
    elif status_filter == 'inactive':
        query = query.filter(User.is_active == False)
    
    if profile_filter:
        query = query.filter(User.profile.ilike(f'%{profile_filter}%'))
    
    sort_mapping = {
        'date_asc': User.id.asc(),
        'date_desc': User.id.desc(),
        'name_asc': User.name.asc(),
        'name_desc': User.name.desc(),
        'username_asc': User.username.asc(),
        'username_desc': User.username.desc()
    }
    
    if sort_option in sort_mapping:
        query = query.order_by(sort_mapping[sort_option])
    
    page_get = request.args.get('page', 1, type=int)
    per_page = 10
    
    try:
        pagination = query.paginate(
            page=page_get, 
            per_page=per_page, 
            error_out=False
        )
        
        from app.models import Role
        available_roles = Role.query.filter_by(is_active=True).all()
        
        return render_template(
            "users.html", 
            users=pagination.items, 
            pagination=pagination,
            available_roles=available_roles,
            current_filters={
                'search': search_query,
                'status': status_filter,
                'profile': profile_filter,
                'sort': sort_option
            }
        )
    except Exception as e:
        logger.error(f"Erro ao paginar usuários: {str(e)}")
        flash("Erro ao carregar usuários.", "danger")
        return render_template("users.html", users=[], pagination=None)

# ==========================================
# ROTAS DE AÇÕES DE GERENCIAMENTO DE USUÁRIOS
# ==========================================

@users_bp.route("/change_password/<int:user_id>", methods=["POST"])
@login_required
@admin_required
@handle_database_error("alterar senha")
def change_password(user_id):
    """Alterar senha de usuário"""
    nova_senha = request.form.get("nova_senha", "").strip()
    
    if len(nova_senha) < 8:
        flash("Senha deve ter pelo menos 8 caracteres.", "warning")
        return redirect(url_for("admin.users.list_users"))
    
    user = User.query.get_or_404(user_id)
    user.password = generate_password_hash(nova_senha)
    db.session.commit()
    
    logger.info(f"Senha alterada para usuário {user.username} por {current_user.username}")
    flash("Senha atualizada com sucesso.", "success")
    return redirect(url_for("admin.users.list_users"))

@users_bp.route("/delete/<int:user_id>", methods=["POST"])
@login_required
@admin_required
@handle_database_error("deletar usuário")
def delete_user(user_id):
    """Deletar usuário"""
    if user_id == current_user.id:
        flash("Você não pode deletar a si mesmo!", "danger")
        return redirect(url_for("admin.users.list_users"))
    
    user = User.query.get_or_404(user_id)
    username = user.username
    
    db.session.delete(user)
    db.session.commit()
    
    logger.info(f"Usuário {username} deletado por {current_user.username}")
    flash("Usuário deletado com sucesso.", "success")
    return redirect(url_for("admin.users.list_users"))

# Função removida - substituída pelo sistema RBAC

@users_bp.route("/change_roles/<int:user_id>", methods=["POST"])
@login_required
@admin_required
@handle_database_error("alterar roles")
def change_roles(user_id):
    """Alterar roles do usuário no sistema RBAC"""
    from app.models import Role
    
    user_to_edit = User.query.get_or_404(user_id)
    new_roles_list = request.form.getlist("roles_edit")
    
    # Adiciona as novas roles
    user_to_edit.roles.clear()
    for role_name in new_roles_list:
        role = Role.query.filter_by(name=role_name).first()
        if role:
            user_to_edit.roles.append(role)
    
    db.session.commit()
    
    logger.info(f"Roles alteradas para {user_to_edit.username}: {[r.name for r in user_to_edit.roles]}")
    flash(f"Roles do usuário '{user_to_edit.name}' foram atualizadas!", "success")
    return redirect(url_for("admin.users.list_users"))

@users_bp.route("/toggle_status/<int:user_id>", methods=["POST"])
@login_required
@admin_required
@handle_database_error("alterar status")
def toggle_status(user_id):
    """Ativar/desativar usuário"""
    if user_id == current_user.id:
        flash("Você não pode desativar sua própria conta.", "warning")
        return redirect(url_for("admin.users.list_users"))
    
    user_to_toggle = User.query.get_or_404(user_id)
    old_status = user_to_toggle.is_active
    user_to_toggle.is_active = not user_to_toggle.is_active
    action_text = "ativado" if user_to_toggle.is_active else "desativado"
    
    db.session.commit()
    
    logger.info(f"Status do usuário {user_to_toggle.username} alterado: {old_status} -> {user_to_toggle.is_active}")
    flash(f"Usuário '{user_to_toggle.name}' foi {action_text} com sucesso.", "success")
    return redirect(url_for("admin.users.list_users"))

@users_bp.route("/change_sectors/<int:user_id>", methods=["POST"])
@login_required
@admin_required
@handle_database_error("alterar setores")
def change_sectors(user_id):
    """Endpoint de compatibilidade - redireciona para change_roles"""
    return change_roles(user_id)

@users_bp.route("/create_private_repo/<int:user_id>", methods=['POST'])
@login_required
@admin_required
@handle_database_error("criar repositório privado")
def create_private_repo(user_id):
    """Criar repositório privado para usuário"""
    user = User.query.get_or_404(user_id)

    existing_repo = Repository.query.filter_by(owner_id=user.id, access_type='private').first()
    if existing_repo:
        flash(f"O usuário '{user.name}' já possui um repositório privado.", "warning")
        return redirect(url_for('admin.users.list_users'))

    new_repo = Repository(
        name=f"Arquivos de {user.name}",
        description=f"Repositório pessoal para {user.name}.",
        access_type='private',
        owner_id=user.id
    )
    db.session.add(new_repo)
    db.session.commit()

    logger.info(f"Repositório privado criado para {user.username} por {current_user.username}")
    flash(f"Repositório privado criado com sucesso para '{user.name}'!", "success")
    return redirect(url_for('admin.users.list_users'))
