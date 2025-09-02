import os
import logging
from functools import wraps
from flask import flash, redirect, url_for, request
from flask_login import current_user
from sqlalchemy import or_
from app.models import db, User
import logging

logger = logging.getLogger(__name__)

# ==========================================
# DECORATORS
# ==========================================


def admin_required(f):
    """Decorator para verificar se o usuário é admin"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'ADMIN' not in current_user.profile:
            flash("Acesso negado. Ação restrita a administradores.", "danger")
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
                logger.error(f"Erro em {operation_name}: {str(e)}")
                flash(f"Erro ao {operation_name.lower()}: {str(e)}", "danger")
                return redirect(request.referrer
                                or url_for('admin.users.list_users'))

        return decorated_function

    return decorator


# ==========================================
# UTILITÁRIOS DE VALIDAÇÃO
# ==========================================


def validate_user_data(name, username, email):
    """Valida dados do usuário"""
    errors = []

    if not name:
        errors.append("Nome é obrigatório.")
    if not username:
        errors.append("Nome de usuário é obrigatório.")
    if not email:
        errors.append("E-mail é obrigatório.")

    return errors


def check_user_uniqueness(username, email, user_id=None):
    """Verificar se username e email são únicos"""
    errors = []

    username_query = User.query.filter(User.username == username)
    if user_id:
        username_query = username_query.filter(User.id != user_id)

    if username_query.first():
        errors.append("Nome de usuário já está em uso.")

    email_query = User.query.filter(User.email == email)
    if user_id:
        email_query = email_query.filter(User.id != user_id)

    if email_query.first():
        errors.append("Email já está em uso.")

    return errors


def build_user_filter_query(search_term, status_filter, profile_filter):
    """Construir query com filtros para usuários"""
    query = db.select(User).order_by(User.creation_date.desc())

    if search_term:
        query = query.where(
            or_(User.name.ilike(f'%{search_term}%'),
                User.username.ilike(f'%{search_term}%'),
                User.email.ilike(f'%{search_term}%')))

    if status_filter == 'active':
        query = query.where(User.is_active == True)
    elif status_filter == 'inactive':
        query = query.where(User.is_active == False)

    if profile_filter:
        query = query.where(User.profile.ilike(f'%{profile_filter}%'))

    return query


def get_user_statistics():
    """Obter estatísticas dos usuários"""
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    inactive_users = total_users - active_users

    profile_stats = {}
    profiles = ['ADMIN', 'CREATE', 'VIEW']

    for profile in profiles:
        count = User.query.filter(User.profile.like(f'%{profile}%')).count()
        profile_stats[profile] = count

    return {
        'total': total_users,
        'active': active_users,
        'inactive': inactive_users,
        'profiles': profile_stats
    }


# ==========================================
# UTILITÁRIOS DE ARQUIVO
# ==========================================


def create_secure_folder(folder_path):
    """Cria pasta de forma segura"""
    try:
        os.makedirs(folder_path, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Erro ao criar pasta {folder_path}: {str(e)}")
        return False


def generate_unique_filename(base_name, extension, target_directory):
    """Gera nome único para arquivo"""
    counter = 1
    filename = f"{base_name}.{extension}"

    while os.path.exists(os.path.join(target_directory, filename)):
        filename = f"{base_name}_{counter}.{extension}"
        counter += 1

    return filename


def get_file_size_human_readable(file_path):
    """Retorna tamanho do arquivo em formato legível"""
    try:
        size = os.path.getsize(file_path)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    except:
        return "Desconhecido"


def validate_file_extension(filename, allowed_extensions):
    """Valida se a extensão do arquivo está na lista de extensões permitidas"""
    if not filename:
        return False

    file_extension = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return file_extension in allowed_extensions


# ==========================================
# UTILITÁRIOS DE PAGINAÇÃO
# ==========================================


def get_pagination_params(request):
    """Extrai parâmetros de paginação da request"""
    return {
        'page': request.args.get('page', 1, type=int),
        'per_page': request.args.get('per_page', 10, type=int),
        'search': request.args.get('search', '').strip(),
        'sort': request.args.get('sort', 'date_desc')
    }


def build_filter_params(request, allowed_filters):
    """Constrói parâmetros de filtro baseado na request"""
    filters = {}
    for filter_name in allowed_filters:
        value = request.args.get(filter_name, '').strip()
        if value:
            filters[filter_name] = value
    return filters