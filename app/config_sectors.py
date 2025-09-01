
SECTORS_CONFIG = {
    'ENFERMAGEM': {
        'name': 'Enfermagem',
        'description': 'Setor de enfermagem e cuidados diretos ao paciente',
        'icon': 'bi bi-heart-pulse',
        'color': '#28a745'
    },
    'MEDICINA': {
        'name': 'Medicina',
        'description': 'Corpo médico e especialistas',
        'icon': 'bi bi-stethoscope',
        'color': '#007bff'
    },
    'FISIOTERAPIA': {
        'name': 'Fisioterapia',
        'description': 'Setor de fisioterapia e reabilitação',
        'icon': 'bi bi-person-arms-up',
        'color': '#17a2b8'
    },
    
    'LABORATORIO': {
        'name': 'Laboratório',
        'description': 'Análises clínicas e patológicas',
        'icon': 'bi bi-clipboard2-pulse',
        'color': '#6f42c1'
    },
    'RADIOLOGIA': {
        'name': 'Radiologia',
        'description': 'Diagnóstico por imagem',
        'icon': 'bi bi-camera-reels',
        'color': '#fd7e14'
    },
    'FARMACIA': {
        'name': 'Farmácia',
        'description': 'Gestão de medicamentos e farmácia clínica',
        'icon': 'bi bi-capsule',
        'color': '#20c997'
    },
    
    'FATURAMENTO': {
        'name': 'Faturamento',
        'description': 'Faturamento e cobrança hospitalar',
        'icon': 'bi bi-receipt',
        'color': '#ffc107'
    },
    'RH': {
        'name': 'Recursos Humanos',
        'description': 'Gestão de pessoas e recursos humanos',
        'icon': 'bi bi-people',
        'color': '#6c757d'
    },
    'TI': {
        'name': 'Tecnologia da Informação',
        'description': 'Suporte técnico e sistemas',
        'icon': 'bi bi-laptop',
        'color': '#343a40'
    },
    'DIRETORIA': {
        'name': 'Diretoria',
        'description': 'Direção e coordenação geral',
        'icon': 'bi bi-building',
        'color': '#dc3545'
    },
    'INTERNACAO': {
        'name': 'Internação',
        'description': 'Gestão de leitos e internações',
        'icon': 'bi bi-house-heart',
        'color': '#e83e8c'
    },
    'CENTRO_CIRURGICO': {
        'name': 'Centro Cirúrgico',
        'description': 'Procedimentos cirúrgicos',
        'icon': 'bi bi-scissors',
        'color': '#fd7e14'
    },
    'EMERGENCIA': {
        'name': 'Emergência',
        'description': 'Atendimento de emergência e urgência',
        'icon': 'bi bi-truck-front',
        'color': '#dc3545'
    },
    'NUTRICAO': {
        'name': 'Nutrição',
        'description': 'Nutrição clínica e dietética',
        'icon': 'bi bi-apple',
        'color': '#28a745'
    },
    'PSICOLOGIA': {
        'name': 'Psicologia',
        'description': 'Apoio psicológico e saúde mental',
        'icon': 'bi bi-brain',
        'color': '#6f42c1'
    },
    'SERVICO_SOCIAL': {
        'name': 'Serviço Social',
        'description': 'Assistência social aos pacientes',
        'icon': 'bi bi-people-fill',
        'color': '#17a2b8'
    }
}

def get_all_sectors():
    """Retorna todos os setores disponíveis"""
    return SECTORS_CONFIG

def get_sector_info(sector_key):
    """Retorna informações de um setor específico"""
    return SECTORS_CONFIG.get(sector_key, {
        'name': sector_key,
        'description': 'Setor não definido',
        'icon': 'bi bi-building',
        'color': '#6c757d'
    })

def get_sectors_by_category():
    """Retorna setores organizados por categoria"""
    return {
        'Clínicos': ['ENFERMAGEM', 'MEDICINA', 'FISIOTERAPIA'],
        'Apoio Diagnóstico': ['LABORATORIO', 'RADIOLOGIA', 'FARMACIA'],
        'Administrativos': ['FATURAMENTO', 'RH', 'TI', 'DIRETORIA'],
        'Operacionais': ['INTERNACAO', 'CENTRO_CIRURGICO', 'EMERGENCIA'],
        'Suporte': ['NUTRICAO', 'PSICOLOGIA', 'SERVICO_SOCIAL']
    }
