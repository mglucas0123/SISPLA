
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required
from sqlalchemy import or_
from werkzeug.security import generate_password_hash
from app.models import db, User, Repository
from app.utils.rbac_permissions import require_permission
from .utils import handle_database_error, validate_user_data, logger

users_bp = Blueprint('users', __name__, url_prefix='/users')

# ==========================================
# ROTAS DE LISTAGEM E CRIAÇÃO DE USUÁRIOS
# ==========================================

@users_bp.route("/", methods=["GET", "POST"])
@login_required
@require_permission('gerenciar-usuarios')
def list_users():
    if request.method == "POST":
        return create_user()
    
    return render_users_list()

@login_required
@require_permission('gerenciar-usuarios')
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
        email=email,
        profile="USER"
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
        
        from app.models import Role, Permission
        available_roles = Role.query.filter_by(is_active=True).all()
        # Monta agrupamento de permissões por módulo de forma dinâmica
        permissions = Permission.query.order_by(Permission.module.asc(), Permission.name.asc()).all()
        grouped_permissions = {}
        for perm in permissions:
            grouped_permissions.setdefault(perm.module, []).append(perm)
        
        return render_template(
            "users.html", 
            users=pagination.items, 
            pagination=pagination,
            available_roles=available_roles,
            grouped_permissions=grouped_permissions,
            current_filters={
                'search': search_query,
                'status': status_filter,
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
@require_permission('gerenciar-usuarios')
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
@require_permission('gerenciar-usuarios')
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

@users_bp.route("/change_roles/<int:user_id>", methods=["POST"])
@login_required
@require_permission('gerenciar-usuarios')
@handle_database_error("alterar roles")
def change_roles(user_id):
    """Alterar roles do usuário no sistema RBAC"""
    from app.models import Role
    
    user_to_edit = User.query.get_or_404(user_id)
    new_roles_list = request.form.getlist("roles_edit")
    
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
@require_permission('gerenciar-usuarios')
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


@users_bp.route("/change_rbac_permissions/<int:user_id>", methods=["POST"])
@login_required
@require_permission('gerenciar-usuarios')
@handle_database_error("alterar permissões RBAC")
def change_rbac_permissions(user_id):
    """Alterar permissões RBAC específicas do usuário"""
    from app.models import Permission
    
    user_to_edit = User.query.get_or_404(user_id)
    new_permissions_list = request.form.getlist("permissions_edit")
    
    # Limpa permissões diretas atuais
    user_to_edit.permissions.clear()
    
    for permission_name in new_permissions_list:
        permission = Permission.query.filter_by(name=permission_name).first()
        if permission:
            user_to_edit.permissions.append(permission)
    
    db.session.commit()
    
    logger.info(f"Permissões RBAC (diretas) alteradas para {user_to_edit.username}: {[p.name for p in user_to_edit.permissions]}")
    flash(f"Permissões do usuário '{user_to_edit.name}' foram atualizadas!", "success")
    return redirect(url_for("admin.users.list_users"))

@users_bp.route("/edit_basic_data/<int:user_id>", methods=["POST"])
@login_required
@require_permission('gerenciar-usuarios')
@handle_database_error("editar dados básicos")
def edit_basic_data(user_id):
    """Editar dados básicos do usuário (nome, username, email)"""
    from app.routes.admin.utils import validate_user_data
    
    user_to_edit = User.query.get_or_404(user_id)
    
    name = request.form.get("name", "").strip()
    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip()
    
    validation_errors = validate_user_data(name, username, email)
    if validation_errors:
        for error in validation_errors:
            flash(error, "warning")
        return redirect(url_for("admin.users.list_users"))
    
    from sqlalchemy import and_, or_
    existing_user = User.query.filter(
        and_(
            User.id != user_id,
            or_(User.username == username, User.email == email)
        )
    ).first()
    
    if existing_user:
        if existing_user.username == username:
            flash("Nome de usuário já cadastrado para outro usuário.", "warning")
        else:
            flash("E-mail já cadastrado para outro usuário.", "warning")
        return redirect(url_for("admin.users.list_users"))
    
    old_username = user_to_edit.username
    user_to_edit.name = name
    user_to_edit.username = username
    user_to_edit.email = email
    
    db.session.commit()
    
    logger.info(f"Dados básicos atualizados para usuário {old_username} -> {username} por {current_user.username}")
    flash(f"Dados do usuário '{name}' foram atualizados com sucesso!", "success")
    return redirect(url_for("admin.users.list_users"))


@users_bp.route("/create_private_repo/<int:user_id>", methods=['POST'])
@login_required
@require_permission('gerenciar-usuarios')
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
