from functools import wraps
from flask import flash, redirect, url_for, abort
from flask_login import current_user
from app.models import db, Permission, Role, PermissionCatalog

class RBACManager:
        
    @staticmethod
    def init_default_permissions():
        """Inicializa permissões padrão no sistema antigo E no novo catálogo"""
        default_permissions = [
            # Módulo NIR - Internações
            {'name': 'criar-registro-nir', 'description': 'Criar um novo registro de internação', 'module': 'nir'},
            {'name': 'editar-registro-nir', 'description': 'Editar qualquer parte de um registro NIR', 'module': 'nir'},
            {'name': 'salvar-registro-nir', 'description': 'Salvar um registro do NIR', 'module': 'nir'},
            {'name': 'excluir-registro-nir', 'description': 'Excluir um registro do NIR', 'module': 'nir'},
            
            # Módulo Passagem de Plantão
            {'name': 'criar-registro-plantao', 'description': 'Criar um novo registro de plantão', 'module': 'passagem_plantao'},
            {'name': 'excluir-registro-plantao', 'description': 'Excluir um registro de plantão', 'module': 'passagem_plantao'},

            # Módulo de Procedimentos
            {'name': 'manage_procedures', 'description': 'Gerenciar procedimentos médicos (criar, editar, remover)', 'module': 'procedures'},

            # Módulo de Usuários e Permissões
            {'name': 'manage-users', 'description': 'Gerenciar usuários do sistema', 'module': 'admin'},
            {'name': 'view-users', 'description': 'Visualizar lista de usuários', 'module': 'admin'},
            {'name': 'manage-roles', 'description': 'Gerenciar roles e permissões', 'module': 'admin'},

            # Permissões Gerais
            {'name': 'access-panel', 'description': 'Acessar o painel principal', 'module': 'geral'},
            {'name': 'change-password', 'description': 'Alterar a própria senha', 'module': 'geral'},

            {'name': 'admin-total', 'description': 'Acesso irrestrito a todas as funcionalidades do sistema', 'module': 'admin'},
        ]

        for perm_data in default_permissions:
            if not Permission.query.filter_by(name=perm_data['name']).first():
                permission = Permission(**perm_data)
                db.session.add(permission)

        for perm_data in default_permissions:
            if not PermissionCatalog.query.filter_by(name=perm_data['name']).first():
                catalog_perm = PermissionCatalog(
                    name=perm_data['name'],
                    description=perm_data.get('description')
                )
                db.session.add(catalog_perm)

        db.session.commit()

    @staticmethod
    def init_default_roles():
        """Inicializa roles padrão com permissões no sistema antigo E novo"""
        default_roles = [
            {'name': 'Administrador', 'description': 'Acesso total ao sistema', 'sector': 'TI',
                'permissions': ['admin-total']},
            
            {'name': 'Coordenação', 'description': 'Responsável pela coordenação geral', 'sector': 'COORDENACAO',
                'permissions': ['excluir-registro-nir', 'excluir-registro-plantao', 'editar-registro-nir', 'salvar-registro-nir', 'manage_procedures', 'manage-users', 'view-users']},
            
            {'name': 'Nir', 'description': 'Núcleo Interno de Regulação', 'sector': 'NIR',
                'permissions': ['criar-registro-nir', 'editar-registro-nir', 'salvar-registro-nir', 'access-panel', 'change-password']},
            
            {'name': 'Enfermagem', 'description': 'Profissional de enfermagem assistencial', 'sector': 'ENFERMAGEM',
                'permissions': ['criar-registro-plantao', 'access-panel', 'change-password']},
            
            {'name': 'Enfermagem CC', 'description': 'Profissional de enfermagem do Centro Cirúrgico', 'sector': 'CENTRO_CIRURGICO',
                'permissions': ['salvar-registro-nir', 'criar-registro-plantao', 'access-panel', 'change-password']},
            
            {'name': 'Faturamento', 'description': 'Responsável pelo faturamento das contas hospitalares', 'sector': 'FATURAMENTO',
                'permissions': ['editar-registro-nir', 'salvar-registro-nir', 'manage_procedures', 'access-panel', 'change-password']}
        ]
        
        for role_data in default_roles:
            role = Role.query.filter_by(name=role_data['name']).first()
            
            if not role:
                # Criar nova role
                role = Role(
                    name=role_data['name'],
                    description=role_data['description'],
                    sector=role_data['sector']
                )
                db.session.add(role)
                db.session.flush()  # Garante que o role.id está disponível
            
            # Atualizar sistema antigo (relationship permissions)
            for perm_name in role_data['permissions']:
                permission = Permission.query.filter_by(name=perm_name).first()
                if permission and permission not in role.permissions:
                    role.permissions.append(permission)
            
            # Atualizar novo sistema (permissions_list)
            if role.permissions_list is None:
                role.permissions_list = []
            
            for perm_name in role_data['permissions']:
                if perm_name not in role.permissions_list:
                    role.permissions_list.append(perm_name)
        
        db.session.commit()

def require_permission(permission_name):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            
            if current_user.has_permission('admin-total'):
                return f(*args, **kwargs)
            
            if not current_user.has_permission(permission_name):
                flash(f"Acesso negado! Você não possui a permissão '{permission_name}' necessária.", "danger")
                return redirect(url_for('main.panel'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_module_access(module_name):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            
            if current_user.has_permission('admin-total'):
                return f(*args, **kwargs)
            
            if not current_user.has_module_access(module_name):
                flash(f"Acesso negado! Você não possui acesso ao módulo '{module_name}'.", "danger")
                return redirect(url_for('main.panel'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_any_permission(permission_list):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            
            if current_user.has_permission('admin-total'):
                return f(*args, **kwargs)
            
            has_permission = any(current_user.has_permission(perm) for perm in permission_list)
            
            if not has_permission:
                flash("Acesso negado! Você não possui as permissões necessárias.", "danger")
                return redirect(url_for('main.panel'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_sector(sector_name):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))

            if current_user.has_permission('admin-total'):
                return f(*args, **kwargs)

            user_sectors = [role.sector for role in getattr(current_user, 'roles', []) if getattr(role, 'sector', None)]
            if sector_name in user_sectors:
                return f(*args, **kwargs)

            flash(f"Acesso negado! Esta área é exclusiva do setor '{sector_name}'.", "danger")
            return redirect(url_for('main.panel'))
        return decorated_function
    return decorator

def get_user_permissions(user):
    if user.has_permission('admin-total'):
        return Permission.query.all()
    
    permissions = set()
    for role in user.roles:
        permissions.update(role.permissions)
    
    return list(permissions)

def get_user_modules(user):
    if user.has_permission('admin-total'):
        return ['all']
    
    modules = set()
    for role in user.roles:
        for permission in role.permissions:
            modules.add(permission.module)
    
    return list(modules)

def assign_role_to_user(user, role_name):
    role = Role.query.filter_by(name=role_name).first()
    if role and role not in user.roles:
        user.roles.append(role)
        db.session.commit()
        return True
    return False

def remove_role_from_user(user, role_name):
    role = Role.query.filter_by(name=role_name).first()
    if role and role in user.roles:
        user.roles.remove(role)
        db.session.commit()
        return True
    return False

def create_custom_role(name, description, sector, permission_names):
    if Role.query.filter_by(name=name).first():
        return None
    
    role = Role(name=name, description=description, sector=sector)
    
    for perm_name in permission_names:
        permission = Permission.query.filter_by(name=perm_name).first()
        if permission:
            role.permissions.append(permission)
    
    db.session.add(role)
    db.session.commit()
    return role

def initialize_rbac():
    try:
        RBACManager.init_default_permissions()
        RBACManager.init_default_roles()
        print("Sistema RBAC inicializado com sucesso!")
    except Exception as e:
        print(f"Erro ao inicializar RBAC: {e}")
        db.session.rollback()