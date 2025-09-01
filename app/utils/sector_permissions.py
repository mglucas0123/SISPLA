from app.config_sectors import get_all_sectors, get_sector_info

SECTOR_PERMISSIONS = {
    'ENFERMAGEM': {
        'modules': ['nir', 'forms', 'training'],
        'courses': ['curso_enfermagem', 'curso_infeccao', 'curso_medicacao'],
        'description': 'Acesso a NIR, formulários de plantão e cursos de enfermagem'
    },
    'MEDICINA': {
        'modules': ['nir', 'forms', 'training'],
        'courses': ['curso_medicina', 'curso_diagnostico', 'curso_cirurgia'],
        'description': 'Acesso a NIR, formulários e cursos médicos'
    },
    'INTERNACAO': {
        'modules': ['nir', 'forms'],
        'courses': ['curso_internacao', 'curso_alta_hospitalar'],
        'description': 'Acesso a NIR e gestão de internações'
    },
    'FATURAMENTO': {
        'modules': ['nir', 'reports'],
        'courses': ['curso_faturamento', 'curso_sus'],
        'description': 'Acesso a NIR para faturamento e relatórios'
    },
    'CENTRO_CIRURGICO': {
        'modules': ['nir', 'forms', 'training'],
        'courses': ['curso_cirurgia', 'curso_anestesia', 'curso_esterilizacao'],
        'description': 'Acesso a NIR, formulários e cursos cirúrgicos'
    },
    'UTI': {
        'modules': ['nir', 'forms', 'training'],
        'courses': ['curso_uti', 'curso_ventilacao', 'curso_sedacao'],
        'description': 'Acesso a NIR, formulários e cursos de UTI'
    },
    'EMERGENCIA': {
        'modules': ['nir', 'forms', 'training'],
        'courses': ['curso_emergencia', 'curso_trauma', 'curso_reanimacao'],
        'description': 'Acesso a NIR, formulários e cursos de emergência'
    },
    'LABORATORIO': {
        'modules': ['forms', 'training'],
        'courses': ['curso_laboratorio', 'curso_biosseguranca'],
        'description': 'Acesso a formulários e cursos de laboratório'
    },
    'RADIOLOGIA': {
        'modules': ['forms', 'training'],
        'courses': ['curso_radiologia', 'curso_protecao_radiologica'],
        'description': 'Acesso a formulários e cursos de radiologia'
    },
    'FARMACIA': {
        'modules': ['forms', 'training'],
        'courses': ['curso_farmacia', 'curso_medicamentos'],
        'description': 'Acesso a formulários e cursos de farmácia'
    },
    'TI': {
        'modules': ['all'],
        'courses': ['all'],
        'description': 'Acesso total ao sistema'
    },
    'DIRETORIA': {
        'modules': ['all'],
        'courses': ['all'],
        'description': 'Acesso total ao sistema'
    },
    'RH': {
        'modules': ['training', 'reports'],
        'courses': ['all'],
        'description': 'Acesso a treinamentos e relatórios de RH'
    },
    'FISIOTERAPIA': {
        'modules': ['nir', 'forms', 'training'],
        'courses': ['curso_fisioterapia', 'curso_reabilitacao'],
        'description': 'Acesso a NIR, formulários e cursos de fisioterapia'
    },
    'NUTRICAO': {
        'modules': ['forms', 'training'],
        'courses': ['curso_nutricao', 'curso_dietas'],
        'description': 'Acesso a formulários e cursos de nutrição'
    },
    'PSICOLOGIA': {
        'modules': ['forms', 'training'],
        'courses': ['curso_psicologia', 'curso_saude_mental'],
        'description': 'Acesso a formulários e cursos de psicologia'
    },
    'SERVICO_SOCIAL': {
        'modules': ['forms', 'training'],
        'courses': ['curso_servico_social', 'curso_assistencia'],
        'description': 'Acesso a formulários e cursos de serviço social'
    }
}

def user_has_module_access(user, module_name):
    return user.has_module_access(module_name)

def user_has_course_access(user, course_id):
    return user.has_permission('acessar_treinamentos') or user.has_module_access('training')

def get_user_allowed_modules(user):
    return user.get_modules()

def get_user_allowed_courses(user):
    if 'ADMIN' in user.profile:
        return ['all']
    
    allowed_courses = set()
    user_sectors = user.sectors_list
    
    for sector in user_sectors:
        sector_perms = SECTOR_PERMISSIONS.get(sector, {})
        courses = sector_perms.get('courses', [])
        
        if 'all' in courses:
            return ['all']
        
        allowed_courses.update(courses)
    
    return list(allowed_courses)

def get_sector_permissions_info(sector_key):
    return SECTOR_PERMISSIONS.get(sector_key, {
        'modules': [],
        'courses': [],
        'description': 'Setor sem permissões definidas'
    })

def create_permission_decorator(required_permission):
    from functools import wraps
    from flask import flash, redirect, url_for
    from flask_login import current_user
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.has_permission(required_permission):
                flash("Acesso negado! Você não possui permissão para acessar esta funcionalidade.", "danger")
                return redirect(url_for('main.panel'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def create_sector_permission_decorator(required_sectors):
    from functools import wraps
    from flask import flash, redirect, url_for
    from flask_login import current_user
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.has_any_sector(required_sectors) and 'ADMIN' not in current_user.profile:
                flash("Acesso negado! Você não possui setor autorizado para acessar esta funcionalidade.", "danger")
                return redirect(url_for('main.panel'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def requires_clinical_sector(f):
    return create_sector_permission_decorator(['ENFERMAGEM', 'MEDICINA', 'FISIOTERAPIA'])(f)

def requires_administrative_sector(f):
    return create_sector_permission_decorator(['FATURAMENTO', 'RH', 'TI', 'DIRETORIA'])(f)

def requires_operational_sector(f):
    return create_sector_permission_decorator(['INTERNACAO', 'CENTRO_CIRURGICO', 'EMERGENCIA', 'UTI'])(f)
