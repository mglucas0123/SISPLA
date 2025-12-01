from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import db, Role, PermissionCatalog
from functools import wraps

roles_bp = Blueprint('roles', __name__, url_prefix='/roles')


def admin_required(f):
    """Decorator para verificar se o usuário tem permissão admin-total"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Você precisa estar autenticado para acessar esta página.', 'warning')
            return redirect(url_for('auth.login'))
        
        if not current_user.has_permission('admin-total'):
            flash('Acesso negado! Você não possui permissão de administrador.', 'danger')
            return redirect(url_for('main.panel'))
        
        return f(*args, **kwargs)
    return decorated_function


def handle_database_error(operation_name):
    """Decorator para tratamento consistente de erros de banco"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception as e:
                db.session.rollback()
                flash(f"Erro ao {operation_name.lower()}: {str(e)}", "danger")
                return redirect(url_for('admin.roles.permissions_page'))
        return decorated_function
    return decorator


@roles_bp.route('/permissions', methods=['GET'])
@login_required
@admin_required
def permissions_page():
    """Página principal de gerenciamento de roles e permissões (sem alias)"""
    from app.models import Permission
    
    roles = Role.query.order_by(Role.name.asc()).all()
    catalog = PermissionCatalog.query.order_by(PermissionCatalog.name.asc()).all()
    
    # Criar um dicionário com informações completas das permissões
    catalog_details = {}
    catalog_names = []  # Lista simples de nomes para o JavaScript
    
    for cat_perm in catalog:
        perm_obj = Permission.query.filter_by(name=cat_perm.name).first()
        catalog_details[cat_perm.name] = {
            'name': cat_perm.name,
            'description': cat_perm.description or (perm_obj.description if perm_obj else ''),
            'module': perm_obj.module if perm_obj else 'custom'
        }
        catalog_names.append(cat_perm.name)
    
    return render_template('roles_permissions.html', 
                         roles=roles, 
                         catalog=catalog, 
                         catalog_details=catalog_details,
                         catalog_names=catalog_names)


@roles_bp.route('/roles-permissions', methods=['GET'])
@login_required
@admin_required
def roles_permissions():
    """Alias para permissions_page para compatibilidade"""
    return permissions_page()


@roles_bp.route('/permissions/<int:role_id>', methods=['POST'])
@login_required
@admin_required
@handle_database_error('atualizar permissões da role')
def update_role_permissions(role_id: int):
    """Atualiza as permissões de uma role específica"""
    role = Role.query.get_or_404(role_id)

    selected = request.form.getlist('permissions')

    normalized = []
    for p in selected:
        p = (p or '').strip()
        if p and p not in normalized:
            normalized.append(p)

    catalog_set = {p.name for p in PermissionCatalog.query.all()}
    normalized = [p for p in normalized if p in catalog_set]

    if role.name and role.name.lower() in ('administrador', 'admin'):
        normalized = ['admin-total'] if 'admin-total' in catalog_set else []

    role.permissions_list = normalized
    
    from app.models import Permission
    role.permissions.clear()
    for perm_name in normalized:
        perm_obj = Permission.query.filter_by(name=perm_name).first()
        if perm_obj:
            role.permissions.append(perm_obj)
    
    db.session.commit()

    flash(f"Permissões da role '{role.name}' atualizadas!", 'success')
    return redirect(url_for('admin.roles.permissions_page'))


@roles_bp.route('/permissions/<int:role_id>/manage', methods=['GET'])
@login_required
@admin_required
def manage_role_permissions(role_id: int):
    """Página dedicada para gerenciar permissões de uma role específica"""
    from app.models import Permission
    
    role = Role.query.get_or_404(role_id)
    catalog = PermissionCatalog.query.order_by(PermissionCatalog.name.asc()).all()
    
    permissions_by_module = {}
    module_names = {
        'nir': 'NIR - Núcleo Interno de Regulação',
        'passagem_plantao': 'Passagem de Plantão',
        'procedures': 'Procedimentos Médicos',
        'admin': 'Administração',
        'geral': 'Geral',
        'suppliers': 'Fornecedores',
        'training': 'Treinamentos',
        'repository': 'Repositório',
        'notices': 'Comunicados',
        'custom': 'Outras Permissões'
    }
    
    for cat_perm in catalog:
        perm_obj = Permission.query.filter_by(name=cat_perm.name).first()
        
        module = 'custom'
        if perm_obj and perm_obj.module:
            module = perm_obj.module
        else:
            perm_name = cat_perm.name.lower()
            if '-nir' in perm_name or 'registro-nir' in perm_name:
                module = 'nir'
            elif '-plantao' in perm_name:
                module = 'passagem_plantao'
            elif 'procedure' in perm_name:
                module = 'procedures'
            elif 'manage-' in perm_name or 'admin-' in perm_name:
                module = 'admin'
            elif 'fornecedor' in perm_name or 'supplier' in perm_name:
                module = 'suppliers'
            elif 'training' in perm_name or 'treinamento' in perm_name:
                module = 'training'
            elif 'repository' in perm_name or 'repositorio' in perm_name:
                module = 'repository'
            elif 'notice' in perm_name or 'comunicado' in perm_name:
                module = 'notices'
            elif 'access-' in perm_name or 'change-' in perm_name:
                module = 'geral'
        
        if module not in permissions_by_module:
            permissions_by_module[module] = []
        permissions_by_module[module].append(cat_perm.name)
    
    sorted_modules = dict(sorted(permissions_by_module.items()))
    
    current_permissions = role.permissions_list or []
    
    return render_template('manage_role_permissions.html',
                         role=role,
                         permissions_by_module=sorted_modules,
                         module_names=module_names,
                         current_permissions=current_permissions)


@roles_bp.route('/create', methods=['POST'])
@login_required
@admin_required
@handle_database_error('criar role')
def create_role():
    """Cria uma nova role no sistema"""
    name = (request.form.get('role_name') or '').strip()
    description = (request.form.get('role_description') or '').strip()
    sector = (request.form.get('role_sector') or '').strip()
    initial_perms = request.form.getlist('role_permissions')

    if not name:
        flash('Nome da role é obrigatório.', 'warning')
        return redirect(url_for('admin.roles.permissions_page'))

    if Role.query.filter_by(name=name).first():
        flash('Já existe uma role com este nome.', 'warning')
        return redirect(url_for('admin.roles.permissions_page'))

    perms_norm = []
    for p in initial_perms:
        p = (p or '').strip()
        if p and p not in perms_norm:
            perms_norm.append(p)

    catalog_set = {p.name for p in PermissionCatalog.query.all()}
    perms_norm = [p for p in perms_norm if p in catalog_set]

    role = Role(name=name, description=description or None, sector=sector or None)
    
    role.permissions_list = perms_norm
    
    from app.models import Permission
    for perm_name in perms_norm:
        perm_obj = Permission.query.filter_by(name=perm_name).first()
        if perm_obj:
            role.permissions.append(perm_obj)
    
    db.session.add(role)
    db.session.commit()

    flash(f"Role '{name}' criada com sucesso!", 'success')
    return redirect(url_for('admin.roles.permissions_page'))


@roles_bp.route('/<int:role_id>/delete', methods=['POST'])
@login_required
@admin_required
@handle_database_error('excluir role')
def delete_role(role_id: int):
    """Exclui uma role do sistema"""
    role = Role.query.get_or_404(role_id)

    if role.name.lower() in ('administrador', 'admin'):
        flash('Não é permitido excluir a role Administrador.', 'warning')
        return redirect(url_for('admin.roles.permissions_page'))

    for u in list(role.users):
        u.roles.remove(role)

    db.session.delete(role)
    db.session.commit()
    flash(f"Role '{role.name}' excluída com sucesso!", 'success')
    return redirect(url_for('admin.roles.permissions_page'))


@roles_bp.route('/catalog/add', methods=['POST'])
@login_required
@admin_required
@handle_database_error('adicionar permissão no catálogo')
def add_permission_to_catalog():
    """Adiciona uma nova permissão ao catálogo e opcionalmente às roles selecionadas"""
    name = (request.form.get('permission_name') or '').strip()
    description = (request.form.get('permission_description') or '').strip()
    initial_roles = request.form.getlist('initial_roles')
    
    if name == 'admin-total':
        if not PermissionCatalog.query.filter_by(name=name).first():
            db.session.add(PermissionCatalog(name=name, description='Acesso total ao sistema'))
            db.session.commit()
        flash('Permissão admin-total já é obrigatória no catálogo.', 'info')
        return redirect(url_for('admin.roles.permissions_page'))
    
    if not name:
        flash('Informe um nome de permissão.', 'warning')
        return redirect(url_for('admin.roles.permissions_page'))

    import re
    if not re.fullmatch(r'^[a-z0-9]+(?:-[a-z0-9]+)*$', name):
        flash('Permissão inválida. Use kebab-case (letras minúsculas, números e hífen).', 'warning')
        return redirect(url_for('admin.roles.permissions_page'))

    if PermissionCatalog.query.filter_by(name=name).first():
        flash('Já existe essa permissão no catálogo.', 'info')
        return redirect(url_for('admin.roles.permissions_page'))

    # Inferir módulo baseado na primeira role selecionada ou usar 'custom'
    module = 'custom'
    if initial_roles:
        first_role = Role.query.filter_by(name=initial_roles[0]).first()
        if first_role and first_role.sector:
            # Mapear setor da role para módulo
            sector_to_module = {
                'nir': 'nir',
                'administrativo': 'admin',
                'treinamento': 'training',
                'repositorio': 'repository',
                'formulario': 'form'
            }
            module = sector_to_module.get(first_role.sector.lower(), 'custom')
        else:
            # Inferir do nome da role
            role_name_lower = first_role.name.lower() if first_role else ''
            if 'nir' in role_name_lower:
                module = 'nir'
            elif 'admin' in role_name_lower:
                module = 'admin'
            elif 'treinamento' in role_name_lower or 'training' in role_name_lower:
                module = 'training'
            elif 'repositorio' in role_name_lower or 'repository' in role_name_lower:
                module = 'repository'
    
    # Adicionar ao catálogo
    catalog_entry = PermissionCatalog(
        name=name,
        description=description if description else f'Permissão {name}'
    )
    db.session.add(catalog_entry)
    
    # Criar permissão na tabela de permissões
    from app.models import Permission
    permission_entry = Permission(
        name=name,
        description=description if description else f'Permissão {name}',
        module=module
    )
    db.session.add(permission_entry)
    
    # Adicionar às roles selecionadas
    roles_updated = []
    if initial_roles:
        for role_name in initial_roles:
            role = Role.query.filter_by(name=role_name).first()
            if role:
                # Adicionar à lista de permissões da role
                if role.permissions_list is None:
                    role.permissions_list = []
                if name not in role.permissions_list:
                    role.permissions_list = role.permissions_list + [name]
                
                # Adicionar ao relacionamento many-to-many
                if permission_entry not in role.permissions:
                    role.permissions.append(permission_entry)
                
                roles_updated.append(role.name)
    
    db.session.commit()
    
    if roles_updated:
        flash(f"Permissão '{name}' criada no módulo '{module.upper()}' e atribuída às roles: {', '.join(roles_updated)}.", 'success')
    else:
        flash(f"Permissão '{name}' criada no módulo '{module.upper()}'. Atribua às roles conforme necessário.", 'success')
    
    return redirect(url_for('admin.roles.permissions_page'))


@roles_bp.route('/catalog/<string:name>/delete', methods=['POST'])
@login_required
@admin_required
@handle_database_error('excluir permissão do catálogo')
def delete_permission_from_catalog(name: str):
    """Remove uma permissão do catálogo e de todas as roles"""
    name = (name or '').strip()
    
    if name == 'admin-total':
        flash('A permissão admin-total é obrigatória e não pode ser excluída.', 'warning')
        return redirect(url_for('admin.roles.permissions_page'))
    
    perm = PermissionCatalog.query.filter_by(name=name).first()
    if not perm:
        flash('Permissão não encontrada no catálogo.', 'warning')
        return redirect(url_for('admin.roles.permissions_page'))

    roles = Role.query.all()
    for r in roles:
        if r.permissions_list and name in r.permissions_list:
            r.permissions_list = [p for p in r.permissions_list if p != name]
    
    db.session.delete(perm)
    
    from app.models import Permission
    old_perm = Permission.query.filter_by(name=name).first()
    if old_perm:
        for r in roles:
            if old_perm in r.permissions:
                r.permissions.remove(old_perm)
        db.session.delete(old_perm)
    
    db.session.commit()
    flash(f"Permissão '{name}' removida do catálogo e desatribuída das roles.", 'success')
    return redirect(url_for('admin.roles.permissions_page'))
