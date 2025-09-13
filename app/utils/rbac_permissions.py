from functools import wraps
from flask import flash, redirect, url_for, abort
from flask_login import current_user
from app.models import db, Permission, Role

class RBACManager:
        
    @staticmethod
    def init_default_permissions():
        # Definição granular de permissões
        default_permissions = [
            # Módulo NIR
            {'name': 'ver-nir-todos', 'description': 'Visualizar todos os registros do NIR', 'module': 'nir'},
            {'name': 'ver-nir-setor', 'description': 'Visualizar apenas registros do seu setor (NIR)', 'module': 'nir'},
            {'name': 'criar-registro-nir', 'description': 'Criar um novo registro de internação', 'module': 'nir'},
            {'name': 'editar-registro-nir', 'description': 'Editar qualquer parte de um registro NIR', 'module': 'nir'},
            {'name': 'editar-secao-nir', 'description': 'Editar a seção do NIR de responsabilidade do seu setor', 'module': 'nir'},
            {'name': 'excluir-registro-nir', 'description': 'Excluir um registro do NIR', 'module': 'nir'},
            {'name': 'faturar-registro-nir', 'description': 'Realizar a ação de faturamento em um registro NIR', 'module': 'nir'},

            # Módulo Admin - Usuários
            {'name': 'gerenciar-usuarios', 'description': 'Acesso total ao gerenciamento de usuários', 'module': 'admin'},

            # Módulo Admin - Mural
            {'name': 'gerenciar-mural', 'description': 'Acesso total ao gerenciamento do mural de avisos', 'module': 'admin'},
            {'name': 'publicar-aviso-mural', 'description': 'Permissão para publicar um novo aviso no mural', 'module': 'admin'},

            # Módulo Admin - Repositórios
            {'name': 'gerenciar-repositorios-todos', 'description': 'Acesso total para gerenciar todos os repositórios', 'module': 'admin'},
            {'name': 'criar-repositorio', 'description': 'Permissão para criar um novo repositório', 'module': 'repository'},

            # Módulo Admin - Treinamentos
            {'name': 'gerenciar-treinamentos', 'description': 'Acesso total para gerenciar treinamentos e quizzes', 'module': 'admin'},
            {'name': 'criar-treinamento', 'description': 'Permissão para criar um novo treinamento', 'module': 'training'},

            # Acesso Geral
            {'name': 'acessar-treinamentos', 'description': 'Acesso geral para visualizar e realizar treinamentos', 'module': 'training'},
            {'name': 'acessar-repositorios', 'description': 'Acesso geral para visualizar repositórios', 'module': 'repository'},

            # Módulo Plantão
            {'name': 'criar-plantao', 'description': 'Criar um novo registro de plantão', 'module': 'forms'},
            {'name': 'ver-plantoes', 'description': 'Visualizar a lista de plantões', 'module': 'forms'},
            {'name': 'ver-detalhes-plantao', 'description': 'Visualizar detalhes de um plantão', 'module': 'forms'},
            {'name': 'excluir-plantao', 'description': 'Excluir um registro de plantão', 'module': 'forms'},

            # Módulo Repositório (Conteúdo)
            {'name': 'editar-conteudo-repositorio', 'description': 'Editar conteúdo de um repositório (renomear, mover)', 'module': 'repository'},
            {'name': 'excluir-conteudo-repositorio', 'description': 'Excluir conteúdo de um repositório (arquivos, pastas)', 'module': 'repository'},
            
            # Permissão de super-administrador
            {'name': 'admin-total', 'description': 'Acesso irrestrito a todas as funcionalidades do sistema', 'module': 'admin'},
        ]

        for perm_data in default_permissions:
            if not Permission.query.filter_by(name=perm_data['name']).first():
                permission = Permission(**perm_data)
                db.session.add(permission)

        db.session.commit()

    @staticmethod
    def init_default_roles():
        # Definição das Funções (Roles) e suas permissões
        default_roles = [
            {
                'name': 'Administrador do Sistema',
                'description': 'Acesso total ao sistema',
                'sector': 'TI',
                'permissions': ['admin-total'] # Permissão única que concede todos os acessos
            },
            {
                'name': 'Nir',
                'description': 'Núcleo Interno de Regulação',
                'sector': 'NIR',
                'permissions': [
                    'ver-nir-todos',
                    'criar-registro-nir',
                    'editar-secao-nir',
                    'acessar-treinamentos',
                    'acessar-repositorios',
                    'criar-plantao',
                    'ver-plantoes',
                    'ver-detalhes-plantao',
                    'criar-repositorio',
                    'editar-conteudo-repositorio',
                    'excluir-conteudo-repositorio'
                ]
            },
            {
                'name': 'Enfermeiro',
                'description': 'Profissional de enfermagem assistencial',
                'sector': 'ENFERMAGEM',
                'permissions': [
                    'ver-nir-setor',
                    'editar-secao-nir',
                    'acessar-treinamentos',
                    'acessar-repositorios',
                    'criar-plantao',
                    'ver-plantoes',
                    'ver-detalhes-plantao'
                ]
            },
            {
                'name': 'Enfermeiro CC (Centro Cirúrgico)',
                'description': 'Profissional de enfermagem do Centro Cirúrgico',
                'sector': 'CENTRO_CIRURGICO',
                'permissions': [
                    'ver-nir-setor',
                    'editar-secao-nir',
                    'acessar-treinamentos',
                    'acessar-repositorios'
                ]
            },
            {
                'name': 'Faturista',
                'description': 'Responsável pelo faturamento das contas hospitalares',
                'sector': 'FATURAMENTO',
                'permissions': [
                    'ver-nir-setor',
                    'editar-secao-nir',
                    'faturar-registro-nir',
                    'acessar-treinamentos',
                    'acessar-repositorios'
                ]
            },
            # Adicionando um papel base para usuários comuns
            {
                'name': 'Usuário Padrão',
                'description': 'Usuário com acesso básico aos módulos comuns',
                'sector': 'GERAL',
                'permissions': [
                    'acessar-treinamentos',
                    'acessar-repositorios',
                    'criar-repositorio'
                ]
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
