from functools import wraps
from flask import flash, redirect, url_for, abort
from flask_login import current_user
from app.models import db, Permission, Role

class RBACManager:
        
    @staticmethod
    def init_default_permissions():
        default_permissions = [
            {'name': 'criar_nir', 'description': 'Criar registros NIR', 'module': 'nir'},
            {'name': 'editar_nir', 'description': 'Editar registros NIR', 'module': 'nir'},
            {'name': 'excluir_nir', 'description': 'Excluir registros NIR', 'module': 'nir'},
            {'name': 'visualizar_nir', 'description': 'Visualizar registros NIR', 'module': 'nir'},
            
            {'name': 'criar_formulario', 'description': 'Criar formulários', 'module': 'forms'},
            {'name': 'editar_formulario', 'description': 'Editar formulários', 'module': 'forms'},
            {'name': 'visualizar_formulario', 'description': 'Visualizar formulários', 'module': 'forms'},
            
            {'name': 'acessar_treinamentos', 'description': 'Acessar módulo de treinamentos', 'module': 'training'},
            {'name': 'gerenciar_cursos', 'description': 'Gerenciar cursos', 'module': 'training'},
            
            {'name': 'visualizar_relatorios', 'description': 'Visualizar relatórios', 'module': 'reports'},
            {'name': 'gerar_relatorios', 'description': 'Gerar relatórios', 'module': 'reports'},
            
            {'name': 'gerenciar_usuarios', 'description': 'Gerenciar usuários', 'module': 'admin'},
            {'name': 'visualizar_usuarios', 'description': 'Visualizar usuários', 'module': 'admin'},
            
            {'name': 'gerenciar_farmacia', 'description': 'Gerenciar farmácia', 'module': 'farmacia'},
            {'name': 'dispensar_medicamento', 'description': 'Dispensar medicamentos', 'module': 'farmacia'},
            
            {'name': 'gerenciar_laboratorio', 'description': 'Gerenciar laboratório', 'module': 'laboratorio'},
            {'name': 'liberar_exames', 'description': 'Liberar resultados de exames', 'module': 'laboratorio'},
            
            {'name': 'gerenciar_faturamento', 'description': 'Gerenciar faturamento', 'module': 'faturamento'},
            {'name': 'aprovar_contas', 'description': 'Aprovar contas médicas', 'module': 'faturamento'},
        ]
        
        for perm_data in default_permissions:
            if not Permission.query.filter_by(name=perm_data['name']).first():
                permission = Permission(**perm_data)
                db.session.add(permission)
        
        db.session.commit()
    
    @staticmethod
    def init_default_roles():
        default_roles = [
            {
                'name': 'Enfermeiro',
                'description': 'Profissional de enfermagem',
                'sector': 'ENFERMAGEM',
                'permissions': ['criar_nir', 'editar_nir', 'visualizar_nir', 'criar_formulario', 'editar_formulario', 'visualizar_formulario', 'acessar_treinamentos']
            },
            {
                'name': 'Médico',
                'description': 'Médico assistente',
                'sector': 'MEDICINA',
                'permissions': ['criar_nir', 'editar_nir', 'visualizar_nir', 'criar_formulario', 'visualizar_formulario', 'acessar_treinamentos', 'visualizar_relatorios']
            },
            {
                'name': 'Faturista',
                'description': 'Responsável pelo faturamento',
                'sector': 'FATURAMENTO',
                'permissions': ['visualizar_nir', 'editar_nir', 'gerenciar_faturamento', 'aprovar_contas', 'visualizar_relatorios', 'gerar_relatorios']
            },
            {
                'name': 'Farmacêutico',
                'description': 'Responsável pela farmácia',
                'sector': 'FARMACIA',
                'permissions': ['gerenciar_farmacia', 'dispensar_medicamento', 'acessar_treinamentos', 'criar_formulario', 'visualizar_formulario']
            },
            {
                'name': 'Técnico Laboratório',
                'description': 'Técnico de laboratório',
                'sector': 'LABORATORIO',
                'permissions': ['gerenciar_laboratorio', 'liberar_exames', 'acessar_treinamentos', 'criar_formulario', 'visualizar_formulario']
            },
            {
                'name': 'Recepcionista',
                'description': 'Atendimento e recepção',
                'sector': 'RECEPCAO',
                'permissions': ['criar_nir', 'visualizar_nir', 'acessar_treinamentos']
            },
            {
                'name': 'Gestor RH',
                'description': 'Gestão de recursos humanos',
                'sector': 'RH',
                'permissions': ['gerenciar_usuarios', 'visualizar_usuarios', 'gerenciar_cursos', 'acessar_treinamentos', 'visualizar_relatorios', 'gerar_relatorios']
            },
            {
                'name': 'Administrador TI',
                'description': 'Administrador do sistema',
                'sector': 'TI',
                'permissions': ['gerenciar_usuarios', 'visualizar_usuarios', 'gerenciar_cursos', 'acessar_treinamentos', 'visualizar_relatorios', 'gerar_relatorios']
            },
            {
                'name': 'Diretor',
                'description': 'Direção hospitalar',
                'sector': 'DIRETORIA',
                'permissions': ['visualizar_relatorios', 'gerar_relatorios', 'visualizar_usuarios', 'acessar_treinamentos']
            }
        ]
        
        for role_data in default_roles:
            if not Role.query.filter_by(name=role_data['name']).first():
                role = Role(
                    name=role_data['name'],
                    description=role_data['description'],
                    sector=role_data['sector']
                )
                
                for perm_name in role_data['permissions']:
                    permission = Permission.query.filter_by(name=perm_name).first()
                    if permission:
                        role.permissions.append(permission)
                
                db.session.add(role)
        
        db.session.commit()

def require_permission(permission_name):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            
            if 'ADMIN' in current_user.profile:
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
            
            if 'ADMIN' in current_user.profile:
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
            
            if 'ADMIN' in current_user.profile:
                return f(*args, **kwargs)
            
            has_permission = any(current_user.has_permission(perm) for perm in permission_list)
            
            if not has_permission:
                flash("Acesso negado! Você não possui as permissões necessárias.", "danger")
                return redirect(url_for('main.panel'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def get_user_permissions(user):
    if 'ADMIN' in user.profile:
        return Permission.query.all()
    
    permissions = set()
    for role in user.roles:
        permissions.update(role.permissions)
    
    return list(permissions)

def get_user_modules(user):
    if 'ADMIN' in user.profile:
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
