
import enum
from flask import url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

user_roles = db.Table('user_roles',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True)
)

role_permissions = db.Table('role_permissions',
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permissions.id'), primary_key=True)
)

user_permissions = db.Table('user_permissions',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permissions.id'), primary_key=True)
)

repository_access = db.Table('repository_access',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('repository_id', db.Integer, db.ForeignKey('repositories.id'), primary_key=True)
)

class Permission(db.Model):
    __tablename__ = 'permissions'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(200), nullable=True)
    module = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Permission {self.name}>'

class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(200), nullable=True)
    sector = db.Column(db.String(50), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    permissions = db.relationship('Permission', secondary=role_permissions, backref='roles')
    
    def has_permission(self, permission_name):
        return any(perm.name == permission_name for perm in self.permissions)
    
    def has_module_access(self, module_name):
        return any(perm.module == module_name for perm in self.permissions)
    
    def __repr__(self):
        return f'<Role {self.name}>'

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    profile = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    creation_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    roles = db.relationship('Role', secondary=user_roles, backref='users')
    permissions = db.relationship('Permission', secondary=user_permissions, backref='users_direct')
    notices = db.relationship('Notice', back_populates='author')
    forms = db.relationship('Form', back_populates='worker', lazy='dynamic')
    nir = db.relationship('Nir', back_populates='operator', lazy='dynamic')
    shared_repositories = db.relationship('Repository', secondary=repository_access, back_populates='shared_with_users')
    
    @property
    def has_private_repository(self): 
        return db.session.query(
            Repository.query.filter_by(owner_id=self.id, access_type='private').exists()
        ).scalar()
    
    def has_permission(self, permission_name):
        if any(p.name == permission_name for p in self.permissions):
            return True
        for role in self.roles:
            if role.has_permission(permission_name):
                return True
        return False
    
    def has_module_access(self, module_name):
        if any(p.module == module_name for p in self.permissions):
            return True
        for role in self.roles:
            if role.has_module_access(module_name):
                return True
        return False
    
    def get_permissions(self):
        permissions = set()
        for permission in self.permissions:
            permissions.add(permission.name)
        for role in self.roles:
            for permission in role.permissions:
                permissions.add(permission.name)
        return list(permissions)
    
    def get_modules(self):
        modules = set()
        for permission in self.permissions:
            modules.add(permission.module)
        for role in self.roles:
            for permission in role.permissions:
                modules.add(permission.module)
        return list(modules)
    

    def __repr__(self):
        return f'<User {self.username}>'


class NirSectionStatus(db.Model):
    """Controla o status de preenchimento de cada seção do NIR"""
    __tablename__ = 'nir_section_status'
    
    id = db.Column(db.Integer, primary_key=True)
    nir_id = db.Column(db.Integer, db.ForeignKey('nir.id'), nullable=False)
    section_name = db.Column(db.String(50), nullable=False)
    responsible_sector = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='PENDENTE')
    filled_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    filled_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    nir = db.relationship('Nir', back_populates='section_statuses')
    filled_by = db.relationship('User')
    
    def __repr__(self):
        return f'<NirSectionStatus {self.nir_id}:{self.section_name}:{self.status}>'

class Nir(db.Model):
    __tablename__ = 'nir'
    
    id = db.Column(db.Integer, primary_key=True)
    
    patient_name = db.Column(db.String(200), nullable=False)
    birth_date = db.Column(db.Date, nullable=False)
    gender = db.Column(db.String(1), nullable=False)
    susfacil = db.Column(db.String(50), nullable=True)
    sus_number = db.Column(db.String(50), nullable=False)
    
    admission_date = db.Column(db.Date, nullable=True)
    entry_type = db.Column(db.String(50), nullable=True)
    admission_type = db.Column(db.String(50), nullable=True)
    admitted_from_origin = db.Column(db.String(10), nullable=True)
    
    procedure_code = db.Column(db.String(20), nullable=True)
    surgical_description = db.Column(db.Text, nullable=True)
    
    responsible_doctor = db.Column(db.String(100), nullable=True)
    main_cid = db.Column(db.String(10), nullable=True)
    aih = db.Column(db.String(50), nullable=True)
    
    scheduling_date = db.Column(db.Date, nullable=True)
    discharge_type = db.Column(db.String(50), nullable=True)
    discharge_date = db.Column(db.Date, nullable=True)
    total_days_admitted = db.Column(db.Integer, nullable=True)
    
    cancelled = db.Column(db.String(10), nullable=True)
    cancellation_reason = db.Column(db.Text, nullable=True)
    criticized = db.Column(db.String(10), nullable=True)
    billed = db.Column(db.String(10), nullable=True)
    status = db.Column(db.String(50), nullable=True)
    observation = db.Column(db.Text, nullable=True)
    
    surgical_specialty = db.Column(db.String(100), nullable=True)
    auxiliary = db.Column(db.String(100), nullable=True)
    anesthetist = db.Column(db.String(100), nullable=True)
    anesthesia = db.Column(db.String(100), nullable=True)
    pediatrics = db.Column(db.String(100), nullable=True)
    surgical_type = db.Column(db.String(100), nullable=True)

    day = db.Column(db.Integer, nullable=True)
    month = db.Column(db.String(20), nullable=True)
    operator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    creation_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_modified = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    operator = db.relationship('User', back_populates='nir')
    section_statuses = db.relationship('NirSectionStatus', back_populates='nir', cascade='all, delete-orphan')
    
    def get_section_control_config(self):
        """Retorna a configuração de controle baseada no tipo de entrada"""
        effective_entry = 'URGENCIA' if self.entry_type == 'CIRURGICO' else (self.entry_type or '')

        if effective_entry in ('URGENCIA', 'ELETIVO'):
            return {
                'dados_paciente': 'NIR',
                'dados_internacao_iniciais': 'NIR',
                'procedimentos': 'CENTRO_CIRURGICO',
                'informacoes_medicas': 'CENTRO_CIRURGICO',
                'dados_alta_finais': 'NIR',
                'status_controle': 'FATURAMENTO'
            }
        else:
            return {
                'dados_paciente': 'NIR',
                'dados_internacao_iniciais': 'NIR',
                'procedimentos': 'NIR',
                'informacoes_medicas': 'NIR',
                'dados_alta_finais': 'NIR',
                'status_controle': 'FATURAMENTO'
            }
    
    def can_edit_section(self, section_name, user):
        """Verifica se o usuário pode editar uma seção específica"""
        from app.routes.nir import get_user_sector
        
        config = self.get_section_control_config()
        responsible_sector = config.get(section_name)
        
        user_sector = get_user_sector(user)
        return user_sector == responsible_sector
    
    def get_section_status(self, section_name):
        """Retorna o objeto NirSectionStatus de uma seção específica"""
        section_status = NirSectionStatus.query.filter_by(
            nir_id=self.id,
            section_name=section_name
        ).first()
        
        return section_status
    
    def get_effective_entry_type(self):
        """Retorna o tipo de entrada considerando valores legados."""
        return 'URGENCIA' if self.entry_type == 'CIRURGICO' else (self.entry_type or '')

    def get_sector_sections(self):
        """Mapeia setores para as seções que são de responsabilidade deles."""
        config = self.get_section_control_config()
        sector_map = {}
        for section, sector in config.items():
            sector_map.setdefault(sector, []).append(section)
        return sector_map

    def get_sector_progress(self):
        """Resumo de progresso por setor: total, preenchidos, pendentes e status."""
        sector_sections = self.get_sector_sections()
        statuses = { (s.section_name, s.responsible_sector): s.status for s in self.section_statuses }
        progress = {}
        for sector, sections in sector_sections.items():
            total = len(sections)
            filled = 0
            pending = 0
            for sec in sections:
                st = statuses.get((sec, sector), 'PENDENTE')
                if st == 'PREENCHIDO':
                    filled += 1
                else:
                    pending += 1
            if total == 0:
                status = 'PENDENTE'
            elif filled == 0:
                status = 'PENDENTE'
            elif filled < total:
                status = 'EM_ANDAMENTO'
            else:
                status = 'CONCLUIDO'
            progress[sector] = {
                'total': total,
                'filled': filled,
                'pending': pending,
                'status': status,
                'sections': sections
            }
        return progress

    def compute_overall_status(self):
        if not self.section_statuses:
            return 'PENDENTE'
        total = len(self.section_statuses)
        filled = sum(1 for s in self.section_statuses if s.status == 'PREENCHIDO')
        if filled == 0:
            return 'PENDENTE'
        if filled < total:
            return 'EM_ANDAMENTO'
        return 'CONCLUIDO'
    
    def is_ready_for_sector(self, sector):
        if sector == 'NIR':
            return True

        progress = self.get_sector_progress()

        effective_entry = self.get_effective_entry_type()
        config = self.get_section_control_config()

        nir_sections = [s for s, sec in config.items() if sec == 'NIR']

        if effective_entry in ('URGENCIA', 'ELETIVO'):
            final_nir_sections = [s for s in nir_sections if 'alta' in s]
            initial_nir_sections = [s for s in nir_sections if s not in final_nir_sections]
        else:
            initial_nir_sections = nir_sections
            final_nir_sections = []

        section_status_map = { (s.section_name): s.status for s in self.section_statuses }

        def sections_complete(section_list):
            if not section_list:
                return True
            return all(section_status_map.get(sec) == 'PREENCHIDO' for sec in section_list)

        if sector == 'CENTRO_CIRURGICO':
            if effective_entry in ('URGENCIA', 'ELETIVO'):
                return sections_complete(initial_nir_sections)
            else:
                nir_progress = progress.get('NIR', {})
                return nir_progress.get('status') == 'CONCLUIDO'

        if sector == 'FATURAMENTO':
            if not sections_complete(nir_sections):
                return False
            surgery_progress = progress.get('CENTRO_CIRURGICO')
            if surgery_progress and surgery_progress.get('status') != 'CONCLUIDO':
                return False
            return True

        return False
        
    def get_next_available_sector(self):
        """Retorna o próximo setor que pode trabalhar no registro."""
        progress = self.get_sector_progress()
        effective_entry = self.get_effective_entry_type()
        config = self.get_section_control_config()

        nir_sections = [s for s, sec in config.items() if sec == 'NIR']
        section_status_map = { (s.section_name): s.status for s in self.section_statuses }

        def sections_complete(section_list):
            if not section_list:
                return True
            return all(section_status_map.get(sec) == 'PREENCHIDO' for sec in section_list)

        if effective_entry in ('URGENCIA', 'ELETIVO'):
            final_nir_sections = [s for s in nir_sections if 'alta' in s]
            initial_nir_sections = [s for s in nir_sections if s not in final_nir_sections]

            if not sections_complete(initial_nir_sections):
                return 'NIR'

            surgery_progress = progress.get('CENTRO_CIRURGICO', {})
            if surgery_progress.get('status') != 'CONCLUIDO':
                return 'CENTRO_CIRURGICO'

            if not sections_complete(final_nir_sections):
                return 'NIR'

            billing_progress = progress.get('FATURAMENTO', {})
            if billing_progress.get('status') != 'CONCLUIDO':
                return 'FATURAMENTO'

            return None
        else:
            if not sections_complete(nir_sections):
                return 'NIR'
            billing_progress = progress.get('FATURAMENTO', {})
            if billing_progress.get('status') != 'CONCLUIDO':
                return 'FATURAMENTO'
            return None

    def __repr__(self):
        return f'<Nir {self.id}: {self.patient_name}>'

class NirProcedure(db.Model):
    __tablename__ = 'nir_procedures'
    id = db.Column(db.Integer, primary_key=True)
    nir_id = db.Column(db.Integer, db.ForeignKey('nir.id', ondelete='CASCADE'), nullable=False, index=True)
    code = db.Column(db.String(20), nullable=False)
    description = db.Column(db.Text, nullable=False)
    sequence = db.Column(db.Integer, nullable=True)
    is_primary = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<NirProcedure {self.code}>'

Nir.procedures = db.relationship(
    'NirProcedure', backref='nir', cascade='all, delete-orphan', order_by='NirProcedure.sequence.asc()'
)
        
class Form(db.Model):
    __tablename__ = 'forms'
    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    sector = db.Column(db.String(100), nullable=False)
    date_registry = db.Column(db.DateTime, nullable=False)
    observation = db.Column(db.Text, nullable=False)
    worker = db.relationship('User', back_populates='forms')
    def __repr__(self):
        return f'<Form id={self.id}>'

class Notice(db.Model):
    __tablename__ = 'notices'
    id = db.Column(db.Integer, primary_key=True)
    notice_type = db.Column(db.String(20), nullable=False, default='TEXT')
    title = db.Column(db.String(100), nullable=True)
    content = db.Column(db.Text, nullable=True)
    image_filename = db.Column(db.String(200), nullable=True)
    date_registry = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    author = db.relationship('User', back_populates='notices')

    def __repr__(self):
        return f'<notices {self.title}>'
    
class Repository(db.Model):
    __tablename__ = 'repositories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    folder_name = db.Column(db.String(120), unique=True, nullable=False)
    access_type = db.Column(db.String(20), nullable=False, default='private')
    date_created = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    owner = db.relationship('User', backref=db.backref('owned_repositories', lazy=True))
    files = db.relationship('File', back_populates='repository', cascade="all, delete-orphan")
    shared_with_users = db.relationship('User', secondary=repository_access, back_populates='shared_repositories')

class File(db.Model):
    __tablename__ = 'files'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=True)
    name = db.Column(db.String(100), nullable=False)   
    description = db.Column(db.Text, nullable=True)
    date_uploaded = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    is_folder = db.Column(db.Boolean, default=False, nullable=False)
    
    parent_id = db.Column(db.Integer, db.ForeignKey('files.id'), nullable=True)
    repository_id = db.Column(db.Integer, db.ForeignKey('repositories.id'), nullable=False)

    repository = db.relationship('Repository', back_populates='files')
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    owner = db.relationship('User', backref=db.backref('owned_files', lazy=True))
    children = db.relationship('File', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')
    
class Course(db.Model):
    __tablename__ = 'courses'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    video_filename = db.Column(db.String(200), nullable=False) 
    image_filename = db.Column(db.String(200), nullable=True)
    duration_seconds = db.Column(db.Integer, nullable=False, default=0)
    date_registry = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    quiz = db.relationship('Quiz', backref='course', uselist=False, cascade="all, delete-orphan")

    progress_records = db.relationship('UserCourseProgress', back_populates='course', cascade="all, delete-orphan", lazy='dynamic')

class UserCourseProgress(db.Model):
    __tablename__ = 'user_course_progress'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    last_watched_timestamp = db.Column(db.Float, default=0.0, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref=db.backref('course_progress', lazy='dynamic'))
    
    course = db.relationship('Course', back_populates='progress_records')

    __table_args__ = (db.UniqueConstraint('user_id', 'course_id', name='_user_course_uc'),)

class Quiz(db.Model):
    __tablename__ = 'quizzes'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), unique=True, nullable=False)
    support_text = db.Column(db.Text)
    
    questions = db.relationship('Question', backref='quiz', cascade="all, delete-orphan", lazy=True)
    attachments = db.relationship('QuizAttachment', backref='quiz', lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        sorted_questions = sorted(self.questions, key=lambda q: q.id)
        return {
            "id": self.id,
            "title": self.title,
            "questions": [q.to_dict() for q in sorted_questions]
        }
    
class QuizAttachment(db.Model):
    __tablename__ = 'quiz_attachments'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False) 
    filepath = db.Column(db.String(255), nullable=False, unique=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False)

    def __repr__(self):
        return f'<QuizAttachment {self.filename}>'

    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'url': url_for('training.download_attachment', attachment_id=self.id, _external=True)
        }

class QuestionType(enum.Enum):
    MULTIPLE_CHOICE = "Múltipla Escolha"
    TEXT_INPUT = "Resposta de Texto"

class Question(db.Model):
    __tablename__ = 'questions'
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    
    question_type = db.Column(db.Enum(QuestionType), nullable=False, default=QuestionType.MULTIPLE_CHOICE)
    
    options = db.relationship('AnswerOption', backref='question', cascade="all, delete-orphan", lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'text': self.text,
            'question_type': self.question_type.name,
            'options': [opt.to_dict() for opt in self.options]
        }

class AnswerOption(db.Model):
    __tablename__ = 'answer_options'
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    text = db.Column(db.String(500), nullable=False)
    is_correct = db.Column(db.Boolean, default=False, nullable=False)
    def to_dict(self):
        return {
            'id': self.id,
            'text': self.text,
            'is_correct': self.is_correct
        }

class UserQuizAttempt(db.Model):
    __tablename__ = 'user_quiz_attempts'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False)
    score = db.Column(db.Float, nullable=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    answers = db.Column(db.Text, nullable=True) 

    user = db.relationship('User', backref='quiz_attempts')
    quiz = db.relationship('Quiz', backref=db.backref('attempts', cascade="all, delete-orphan"))
