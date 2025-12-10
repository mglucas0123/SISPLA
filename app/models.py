import enum
import os
from flask import url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timezone
from sqlalchemy.ext.mutable import MutableList, MutableDict
from sqlalchemy import JSON

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

supplier_evaluators = db.Table('supplier_evaluators',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('supplier_id', db.Integer, db.ForeignKey('suppliers.id'), primary_key=True),
    db.Column('assigned_at', db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False),
    db.Column('assigned_by_id', db.Integer, db.ForeignKey('users.id'), nullable=True)
)

user_managers = db.Table('user_managers',
    db.Column('employee_id', db.Integer, db.ForeignKey('users.id'), primary_key=True), 
    db.Column('manager_id', db.Integer, db.ForeignKey('users.id'), primary_key=True), 
    db.Column('assigned_at', db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False),
    db.Column('assigned_by_id', db.Integer, db.ForeignKey('users.id'), nullable=True) 
)

class Permission(db.Model):
    __tablename__ = 'permissions'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(200), nullable=True)
    module = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<Permission {self.name}>'


class PermissionCatalog(db.Model):
    """CatÃ¡logo centralizado de permissÃµes disponÃ­veis no sistema"""
    __tablename__ = 'permission_catalog'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f'<PermissionCatalog {self.name}>'


class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(200), nullable=True)
    sector = db.Column(db.String(50), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    permissions = db.relationship('Permission', secondary=role_permissions, backref='roles')
    
    permissions_list = db.Column(MutableList.as_mutable(JSON), nullable=True, default=list)
    
    def has_permission(self, permission_name):
        if self.permissions_list and permission_name in set(self.permissions_list):
            return True
        return any(perm.name == permission_name for perm in self.permissions)
    
    def has_module_access(self, module_name):
        return any(perm.module == module_name for perm in self.permissions)
    
    def __repr__(self):
        return f'<Role {self.name}>'


class JobPosition(db.Model):
    """Cargos predefinidos da empresa"""
    __tablename__ = 'job_positions'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    sector = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    users = db.relationship('User', back_populates='job_position', lazy='dynamic')
    
    def __repr__(self):
        return f'<JobPosition {self.name}>'


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    profile = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    job_title = db.Column(db.String(100), nullable=True)
    job_position_id = db.Column(db.Integer, db.ForeignKey('job_positions.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    creation_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime, nullable=True)
    totp_secret = db.Column(db.String(32), nullable=True)
    
    job_position = db.relationship('JobPosition', back_populates='users')
    
    roles = db.relationship('Role', secondary=user_roles, backref='users')
    permissions = db.relationship('Permission', secondary=user_permissions, backref='users_direct')
    notices = db.relationship('Notice', back_populates='author')
    forms = db.relationship('Form', back_populates='worker', lazy='dynamic')
    nir = db.relationship('Nir', back_populates='operator', lazy='dynamic')
    shared_repositories = db.relationship('Repository', secondary=repository_access, back_populates='shared_with_users')
    course_enrollments = db.relationship('CourseEnrollmentTerm', back_populates='user', lazy='dynamic')

    assigned_managers = db.relationship('User',
                                        secondary='user_managers',
                                        primaryjoin='User.id==user_managers.c.employee_id',
                                        secondaryjoin='User.id==user_managers.c.manager_id',
                                        backref=db.backref('managed_employees', lazy='dynamic'),
                                        lazy='dynamic')
    
    @property
    def has_private_repository(self): 
        return db.session.query(
            Repository.query.filter_by(owner_id=self.id, access_type='private').exists()
        ).scalar()
    
    def has_permission(self, permission_name):
        """Verifica se o usuÃ¡rio tem uma permissÃ£o especÃ­fica (direto ou via role)"""
        if any(p.name == 'admin-total' for p in self.permissions):
            return True
        
        if any(p.name == permission_name for p in self.permissions):
            return True
        
        for role in self.roles:
            if role.has_permission(permission_name):
                return True
            if role.has_permission('admin-total'):
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
        """Retorna todas as permissÃµes do usuÃ¡rio (diretas + atravÃ©s de roles)"""
        permissions = set()
        
        for permission in self.permissions:
            permissions.add(permission.name)
        
        for role in self.roles:
            if role.permissions_list:
                for perm_name in role.permissions_list:
                    permissions.add(perm_name)
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
    
    def is_manager_of(self, employee_id):
        """
        Verifica se este usuário é gestor responsável por um colaborador específico.
        
        Args:
            employee_id: ID do colaborador a verificar
            
        Returns:
            bool: True se é gestor responsável, False caso contrário
        """
        return self.managed_employees.filter_by(id=employee_id).first() is not None
    
    def can_evaluate_employee(self, employee_id):

        if self.has_permission('admin-total'):
            return True
        
        if self.has_permission('visualizar_todas_avaliacoes_funcionarios'):
            return True
            
        return self.is_manager_of(employee_id)
    
    def can_view_employee_evaluation_details(self, employee_id):
        if self.id == employee_id:
            return True
            
        if self.has_permission('admin-total'):
            return True
        
        if self.has_permission('visualizar_todas_avaliacoes_funcionarios'):
            return True
            
        return self.is_manager_of(employee_id)
    
    @property
    def cargo(self):
        if self.job_position:
            return self.job_position.name
        return self.job_title or ''
    
    @property
    def cargo_com_setor(self):
        if self.job_position:
            return f"{self.job_position.name} ({self.job_position.sector})"
        return self.job_title or ''
    
    def get_managers_list(self):
        return [m.id for m in self.assigned_managers.all()]
    
    def get_managers_names(self):
        return [m.name for m in self.assigned_managers.all()]
    
    def get_managed_employees_list(self):
        return [e.id for e in self.managed_employees.all()]

    def __repr__(self):
        return f'<User {self.username}>'


class NirSectionStatus(db.Model):
    __tablename__ = 'nir_section_status'
    
    id = db.Column(db.Integer, primary_key=True)
    nir_id = db.Column(db.Integer, db.ForeignKey('nir.id'), nullable=False)
    section_name = db.Column(db.String(50), nullable=False)
    responsible_sector = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='PENDENTE')
    filled_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    filled_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
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
    is_palliative = db.Column(db.Boolean, default=False, nullable=True)
    
    admission_date = db.Column(db.DateTime, nullable=True)
    entry_type = db.Column(db.String(50), nullable=True)
    admission_type = db.Column(db.String(50), nullable=True)
    admitted_from_origin = db.Column(db.String(100), nullable=True)
    recurso = db.Column(db.String(50), nullable=True)
    
    procedure_code = db.Column(db.String(20), nullable=True)
    surgical_description = db.Column(db.Text, nullable=True)
    
    responsible_doctor = db.Column(db.String(100), nullable=True)
    main_cid = db.Column(db.String(10), nullable=True)
    aih = db.Column(db.String(50), nullable=True)
    
    susfacil_accepted = db.Column(db.Boolean, default=False, nullable=True)
    susfacil_accept_datetime = db.Column(db.DateTime, nullable=True)
    susfacil_protocol = db.Column(db.String(50), nullable=True)
    
    scheduling_date = db.Column(db.Date, nullable=True)
    discharge_type = db.Column(db.String(50), nullable=True)
    discharge_date = db.Column(db.DateTime, nullable=True)
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
    
    observation_start_time = db.Column(db.DateTime, nullable=True)
    fa_datetime = db.Column(db.DateTime, nullable=True)
    
    creation_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_modified = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    operator = db.relationship('User', back_populates='nir')
    section_statuses = db.relationship('NirSectionStatus', back_populates='nir', cascade='all, delete-orphan')
    
    def get_section_control_config(self):
        if self.admission_type == 'CLINICO':
            return {
                'dados_paciente': 'NIR',
                'dados_internacao_iniciais': 'NIR',
                'agendamento_inicial': 'NIR',
                'procedimentos': 'NIR',
                'informacoes_medicas': 'NIR',
                'dados_alta_finais': 'NIR',
                'status_controle': 'FATURAMENTO'
            }
        
        effective_entry = 'URGENCIA' if self.entry_type == 'CIRURGICO' else (self.entry_type or '')
        
        if self.admission_type == 'CIRURGICO' or effective_entry in ('URGENCIA', 'ELETIVO') or not self.entry_type:
            return {
                'dados_paciente': 'NIR',
                'dados_internacao_iniciais': 'NIR',
                'agendamento_inicial': 'NIR',
                'procedimentos': 'CENTRO_CIRURGICO',
                'informacoes_medicas': 'CENTRO_CIRURGICO',
                'dados_alta_finais': 'NIR',
                'status_controle': 'FATURAMENTO'
            }
        else:
            return {
                'dados_paciente': 'NIR',
                'dados_internacao_iniciais': 'NIR',
                'agendamento_inicial': 'NIR',
                'procedimentos': 'NIR',
                'informacoes_medicas': 'NIR',
                'dados_alta_finais': 'NIR',
                'status_controle': 'FATURAMENTO'
            }
    
    def can_edit_section(self, section_name, user):
        """Verifica se o usuÃ¡rio pode editar uma seÃ§Ã£o especÃ­fica"""
        from app.routes.nir import get_user_sector
        
        config = self.get_section_control_config()
        responsible_sector = config.get(section_name)
        
        user_sector = get_user_sector(user)
        return user_sector == responsible_sector
    
    def get_section_status(self, section_name):
        """Retorna o objeto NirSectionStatus de uma seÃ§Ã£o especÃ­fica"""
        section_status = NirSectionStatus.query.filter_by(
            nir_id=self.id,
            section_name=section_name
        ).first()
        
        return section_status
    
    def get_effective_entry_type(self):
        if self.entry_type == 'CIRURGICO':
            return 'URGENCIA'
        elif not self.entry_type:
            return 'URGENCIA'
        else:
            return self.entry_type

    def get_sector_sections(self):
        config = self.get_section_control_config()
        sector_map = {}
        for section, sector in config.items():
            sector_map.setdefault(sector, []).append(section)
        return sector_map

    def get_sector_progress(self):
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
        
        progress = self.get_sector_progress()
        
        total_filled = sum(p['filled'] for p in progress.values())
        if total_filled == 0:
            return 'PENDENTE'
        
        faturamento_status = progress.get('FATURAMENTO', {}).get('status')
        if faturamento_status == 'CONCLUIDO':
            return 'CONCLUIDO'
        
        return 'EM_ANDAMENTO'
    
    def is_ready_for_sector(self, sector):
        if sector == 'NIR':
            return True

        progress = self.get_sector_progress()
        effective_entry = self.get_effective_entry_type()
        config = self.get_section_control_config()
        nir_sections = [s for s, sec in config.items() if sec == 'NIR']
        section_status_map = { (s.section_name): s.status for s in self.section_statuses }

        def sections_complete(section_list):
            if not section_list:
                return True
            return all(section_status_map.get(sec) == 'PREENCHIDO' for sec in section_list)

        if sector == 'CENTRO_CIRURGICO':
            if self.admission_type == 'CLINICO':
                return False
            
            if effective_entry in ('URGENCIA', 'ELETIVO'):
                final_nir_sections = [s for s in nir_sections if 'alta' in s]
                initial_nir_sections = [s for s in nir_sections if s not in final_nir_sections]
                return sections_complete(initial_nir_sections)
            else:
                nir_progress = progress.get('NIR', {})
                return nir_progress.get('status') == 'CONCLUIDO'

        if sector == 'FATURAMENTO':
            if self.admission_type == 'CLINICO':
                return sections_complete(nir_sections)
            
            if not sections_complete(nir_sections):
                return False
            surgery_progress = progress.get('CENTRO_CIRURGICO')
            if surgery_progress and surgery_progress.get('status') != 'CONCLUIDO':
                return False
            return True

        return False
        
    def get_next_available_sector(self):
        progress = self.get_sector_progress()
        effective_entry = self.get_effective_entry_type()
        config = self.get_section_control_config()

        nir_sections = [s for s, sec in config.items() if sec == 'NIR']
        section_status_map = { (s.section_name): s.status for s in self.section_statuses }

        def sections_complete(section_list):
            if not section_list:
                return True
            return all(section_status_map.get(sec) == 'PREENCHIDO' for sec in section_list)

        if self.admission_type == 'CLINICO':
            if not sections_complete(nir_sections):
                return 'NIR'
            
            billing_progress = progress.get('FATURAMENTO', {})
            if billing_progress.get('status') != 'CONCLUIDO':
                return 'FATURAMENTO'
            
            return None

        if effective_entry in ('URGENCIA', 'ELETIVO') or self.admission_type == 'CIRURGICO':
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
    
    def is_in_observation(self):
        return self.status == 'EM_OBSERVACAO' and self.fa_datetime is not None
    
    def observation_hours_elapsed(self):
        """Retorna quantas horas se passaram desde o HorÃ¡rio FA (entrada na Fila de Atendimento)"""
        if not self.fa_datetime:
            return 0
        delta = datetime.now() - self.fa_datetime
        return delta.total_seconds() / 3600
    
    def should_transition_to_decision(self):
        return self.is_in_observation() and self.observation_hours_elapsed() > 24
    
    def evolve_to_admission(self):
        if self.status in ('EM_OBSERVACAO', 'AGUARDANDO_DECISAO'):
            self.status = 'PENDENTE'
            if not self.admission_date and self.fa_datetime:
                self.admission_date = self.fa_datetime.date()
            self.observation_start_time = None
            self.fa_datetime = None
            return True
        return False
    
    def cancel_observation(self, reason):
        if self.status in ('EM_OBSERVACAO', 'AGUARDANDO_DECISAO'):
            self.cancelled = 'SIM'
            self.cancellation_reason = reason
            self.status = 'CANCELADO'
            return True
        return False

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
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f'<NirProcedure {self.code}>'

Nir.procedures = db.relationship(
    'NirProcedure', backref='nir', cascade='all, delete-orphan', order_by='NirProcedure.sequence.asc()'
)
        
class Form(db.Model):
    __tablename__ = 'forms'
    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    worker_name = db.Column(db.String(100), nullable=True)
    sector = db.Column(db.String(100), nullable=False)
    date_registry = db.Column(db.DateTime, nullable=False)
    observation = db.Column(db.Text, nullable=False)
    worker = db.relationship('User', back_populates='forms')
    
    @property
    def display_worker_name(self):
        if self.worker:
            return self.worker.name
        return self.worker_name or 'Usuário excluído'
    
    def __repr__(self):
        return f'<Form id={self.id}>'

class Notice(db.Model):
    __tablename__ = 'notices'
    id = db.Column(db.Integer, primary_key=True)
    notice_type = db.Column(db.String(20), nullable=False, default='TEXT')
    title = db.Column(db.String(100), nullable=True)
    content = db.Column(db.Text, nullable=True)
    image_filename = db.Column(db.String(200), nullable=True)
    date_registry = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
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
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    sources = db.Column(db.Text, nullable=True)
    scope = db.Column(db.String(100), nullable=True)

    @property
    def content_type(self):
        if not self.video_filename:
            return None
        _, extension = os.path.splitext(self.video_filename)
        extension = extension.lower()
        return 'pdf' if extension == '.pdf' else 'video'

    @property
    def is_pdf(self):
        return self.content_type == 'pdf'

    @property
    def is_video(self):
        return self.content_type == 'video'

    quiz = db.relationship('Quiz', backref='course', uselist=False, cascade="all, delete-orphan")

    progress_records = db.relationship('UserCourseProgress', back_populates='course', cascade="all, delete-orphan", lazy='dynamic')
    enrollment_terms = db.relationship('CourseEnrollmentTerm', back_populates='course', cascade="all, delete-orphan", lazy='dynamic')
    created_by = db.relationship('User', foreign_keys=[created_by_id], backref='created_courses')

class UserCourseProgress(db.Model):
    __tablename__ = 'user_course_progress'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    last_watched_timestamp = db.Column(db.Float, default=0.0, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship('User', backref=db.backref('course_progress', lazy='dynamic'))
    
    course = db.relationship('Course', back_populates='progress_records')

    __table_args__ = (db.UniqueConstraint('user_id', 'course_id', name='_user_course_uc'),)

class CourseEnrollmentTerm(db.Model):
    __tablename__ = 'course_enrollment_terms'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    department = db.Column(db.String(100), nullable=True)
    role = db.Column(db.String(100), nullable=True)
    observations = db.Column(db.Text, nullable=True)
    accepted_terms = db.Column(db.Boolean, default=False, nullable=False)
    accepted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship('User', back_populates='course_enrollments')
    course = db.relationship('Course', back_populates='enrollment_terms')

    __table_args__ = (db.UniqueConstraint('user_id', 'course_id', name='_user_course_enrollment_uc'),)

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
    MULTIPLE_CHOICE = "MÃºltipla Escolha"
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
    submitted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    answers = db.Column(db.Text, nullable=True) 

    user = db.relationship('User', backref='quiz_attempts')
    quiz = db.relationship('Quiz', backref=db.backref('attempts', cascade="all, delete-orphan"))


# ============================================
# MÓDULO DE AVALIAÇÃO DE FORNECEDORES/PRESTADORES
# ============================================

class Supplier(db.Model):
    __tablename__ = 'suppliers'
    
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(200), nullable=False, unique=True)
    trade_name = db.Column(db.String(200), nullable=True)
    cnpj = db.Column(db.String(18), nullable=True)
    contact_name = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    service_type = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    issue_verified = db.Column(db.Boolean, default=False, nullable=False)
    verified_at = db.Column(db.DateTime, nullable=True)
    verified_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    verified_by = db.relationship('User', foreign_keys=[verified_by_id])
    evaluations = db.relationship('SupplierEvaluation', back_populates='supplier', lazy='dynamic', cascade='all, delete-orphan')
    
    assigned_evaluators = db.relationship('User', 
                                         secondary='supplier_evaluators',
                                         primaryjoin='Supplier.id==supplier_evaluators.c.supplier_id',
                                         secondaryjoin='User.id==supplier_evaluators.c.user_id',
                                         backref=db.backref('assigned_suppliers', lazy='dynamic'))
    
    def get_display_name(self):
        """Retorna o nome fantasia se disponível, senão a razão social"""
        return self.trade_name if self.trade_name else self.company_name
    
    def get_average_score(self):
        evals = [e for e in self.evaluations.all() if e.had_service_last_month]
        if not evals:
            return 0
        return round(sum(e.total_score for e in evals) / len(evals), 2)
    
    def get_last_evaluation_date(self):
        last_eval = self.evaluations.order_by(SupplierEvaluation.evaluation_date.desc()).first()
        return last_eval.evaluation_date if last_eval else None
    
    def get_evaluations_count(self):
        return self.evaluations.count()
    
    def __repr__(self):
        return f'<Supplier {self.company_name}>'


class SupplierEvaluation(db.Model):
    """Modelo para armazenar avaliações mensais de fornecedores"""
    __tablename__ = 'supplier_evaluations'
    
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    evaluator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    evaluation_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    month_reference = db.Column(db.String(7), nullable=False)
    
    had_service_last_month = db.Column(db.Boolean, nullable=False)
    service_justification = db.Column(db.Text, nullable=True)
    
    contract_compliance = db.Column(db.String(20), nullable=True) 
    contract_compliance_justification = db.Column(db.Text, nullable=True)
    
    equipment_adequacy = db.Column(db.String(20), nullable=True)
    equipment_adequacy_justification = db.Column(db.Text, nullable=True)
    
    invoice_validation = db.Column(db.String(20), nullable=True)
    invoice_validation_justification = db.Column(db.Text, nullable=True)
    
    service_timeliness = db.Column(db.String(20), nullable=True)
    service_timeliness_justification = db.Column(db.Text, nullable=True)
    
    quantity_description_compliance = db.Column(db.String(20), nullable=True)
    quantity_description_justification = db.Column(db.Text, nullable=True)
    
    support_quality = db.Column(db.String(20), nullable=True)
    support_quality_justification = db.Column(db.Text, nullable=True)
    
    overall_rating = db.Column(db.Integer, nullable=False)
    rating_justification = db.Column(db.Text, nullable=True)
    
    total_score = db.Column(db.Float, nullable=False)
    
    is_compliant = db.Column(db.Boolean, nullable=False)
    follow_up_status = db.Column(db.String(20), nullable=False, default='not_required')
    follow_up_closed_at = db.Column(db.DateTime, nullable=True)
    
    general_observations = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    supplier = db.relationship('Supplier', back_populates='evaluations')
    evaluator = db.relationship('User', foreign_keys=[evaluator_id])
    follow_up_entries = db.relationship('SupplierIssueTracking', back_populates='evaluation', lazy='dynamic')

    FOLLOW_UP_STATUS_MAP = {
        'not_required': ('Sem acompanhamento', 'secondary'),
        'open': ('Pendente', 'danger'),
        'in_progress': ('Em andamento', 'warning'),
        'resolved': ('Resolvido', 'success')
    }
    
    def calculate_score(self):
        if not self.had_service_last_month:
            self.is_compliant = False
            return 0
        
        score = 0
        total_questions = 6
        
        compliance_fields = [
            self.contract_compliance,
            self.equipment_adequacy,
            self.invoice_validation,
            self.service_timeliness,
            self.quantity_description_compliance,
            self.support_quality
        ]
        
        conformes = sum(1 for field in compliance_fields if field == 'conforme')
        compliance_score = (conformes / total_questions) * 60
        
        rating_score = (self.overall_rating / 10) * 40
        
        total_score = compliance_score + rating_score
        
        self.is_compliant = self.overall_rating >= 7 and total_score >= 70
        
        return round(total_score, 2)
    
    def get_status_badge(self):
        """Retorna classe CSS para badge de status"""
        if self.total_score >= 80:
            return 'badge-success'
        elif self.total_score >= 60:
            return 'badge-warning'
        else:
            return 'badge-danger'
    
    def get_status_text(self):
        """Retorna texto do status"""
        if self.total_score >= 80:
            return 'Excelente'
        elif self.total_score >= 60:
            return 'Satisfatório'
        else:
            return 'Insatisfatório'

    def get_follow_up_label(self):
        return self.FOLLOW_UP_STATUS_MAP.get(self.follow_up_status, ('Sem acompanhamento', 'secondary'))[0]

    def get_follow_up_color(self):
        return self.FOLLOW_UP_STATUS_MAP.get(self.follow_up_status, ('Sem acompanhamento', 'secondary'))[1]
    
    def __repr__(self):
        return f'<SupplierEvaluation {self.supplier.company_name} - {self.month_reference}>'


class SupplierIssueTracking(db.Model):
    """Modelo para rastrear histórico de ações sobre problemas de fornecedores"""
    __tablename__ = 'supplier_issue_tracking'
    
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id', ondelete='CASCADE'), nullable=False)
    evaluation_id = db.Column(db.Integer, db.ForeignKey('supplier_evaluations.id', ondelete='SET NULL'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    action_type = db.Column(db.String(50), nullable=False)
    
    description = db.Column(db.Text, nullable=False)
    
    deadline = db.Column(db.Date, nullable=True)
    priority = db.Column(db.String(20), nullable=True)
    
    attachments = db.Column(JSON, nullable=True)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    
    supplier = db.relationship('Supplier', backref=db.backref('issue_history', lazy='dynamic', cascade='all, delete-orphan', order_by='SupplierIssueTracking.created_at.desc()'))
    evaluation = db.relationship('SupplierEvaluation', back_populates='follow_up_entries')
    user = db.relationship('User', foreign_keys=[user_id])
    
    def get_action_icon(self):
        """Retorna ícone apropriado para o tipo de ação"""
        icons = {
            'opened': 'bi-exclamation-triangle-fill',
            'contact': 'bi-telephone-fill',
            'follow_up': 'bi-clock-history',
            'resolved': 'bi-check-circle-fill',
            'reopened': 'bi-arrow-counterclockwise',
            'escalated': 'bi-arrow-up-circle-fill',
            'note': 'bi-sticky-fill'
        }
        return icons.get(self.action_type, 'bi-circle-fill')
    
    def get_action_color(self):
        """Retorna cor apropriada para o tipo de ação"""
        colors = {
            'opened': 'danger',
            'contact': 'primary',
            'follow_up': 'warning',
            'resolved': 'success',
            'reopened': 'danger',
            'escalated': 'danger',
            'note': 'info'
        }
        return colors.get(self.action_type, 'secondary')
    
    def get_action_label(self):
        """Retorna label traduzido para o tipo de ação"""
        labels = {
            'opened': 'Problema Identificado',
            'contact': 'Contato com Fornecedor',
            'follow_up': 'Acompanhamento',
            'resolved': 'Problema Resolvido',
            'reopened': 'Problema Reaberto',
            'escalated': 'Escalado',
            'note': 'Observação'
        }
        return labels.get(self.action_type, 'Ação')
    
    def __repr__(self):
        return f'<SupplierIssueTracking {self.supplier.company_name} - {self.action_type}>'

# ============================================
# MÓDULO DE AVALIAÇÃO DE COLABORADORES
# ============================================

class EmployeeEvaluation(db.Model):
    __tablename__ = 'employee_evaluations'
    
    id = db.Column(db.Integer, primary_key=True)
    evaluator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    evaluated_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    month_reference = db.Column(db.String(7), nullable=False)
    
    innovation_suggestions = db.Column(db.Text, nullable=True)
    improvement_proposals = db.Column(db.Text, nullable=True)
    participation_score = db.Column(db.String(20), nullable=True)
    
    rating = db.Column(db.Integer, nullable=False)
    rating_justification = db.Column(db.Text, nullable=True)
    
    evaluation_type = db.Column(db.String(50), default='mensal', nullable=False)

    
    criteria_punctuality = db.Column(db.String(20), nullable=True) 
    criteria_punctuality_justification = db.Column(db.Text, nullable=True)
    
    criteria_quality = db.Column(db.String(20), nullable=True)
    criteria_quality_justification = db.Column(db.Text, nullable=True)
    
    criteria_productivity = db.Column(db.String(20), nullable=True)
    criteria_productivity_justification = db.Column(db.Text, nullable=True)
    
    # Critério 4: Trabalho em Equipe
    criteria_teamwork = db.Column(db.String(20), nullable=True)
    criteria_teamwork_justification = db.Column(db.Text, nullable=True)
    
    criteria_communication = db.Column(db.String(20), nullable=True)
    criteria_communication_justification = db.Column(db.Text, nullable=True)
    
    criteria_initiative = db.Column(db.String(20), nullable=True)
    criteria_initiative_justification = db.Column(db.Text, nullable=True)
    
    # Critério 7: Cumprimento de Normas
    criteria_compliance = db.Column(db.String(20), nullable=True)
    criteria_compliance_justification = db.Column(db.Text, nullable=True)
    
    criteria_development = db.Column(db.String(20), nullable=True)
    criteria_development_justification = db.Column(db.Text, nullable=True)
    
    total_score = db.Column(db.Float, nullable=True)
    
    is_compliant = db.Column(db.Boolean, nullable=True)
    
    absence_count = db.Column(db.Integer, default=0, nullable=False)
    medical_certificate_count = db.Column(db.Integer, default=0, nullable=False)
    
    comm_verbal = db.Column(db.Integer, nullable=True)
    comm_written = db.Column(db.Integer, nullable=True)
    comm_listening = db.Column(db.Integer, nullable=True)
    comm_simple_lang = db.Column(db.Integer, nullable=True)
    comm_effective = db.Column(db.Integer, nullable=True)
    
    onboarding_unit_presentation = db.Column(db.Boolean, nullable=True)
    onboarding_team_welcome = db.Column(db.Boolean, nullable=True)
    onboarding_expectations = db.Column(db.Boolean, nullable=True)
    onboarding_manuals = db.Column(db.Boolean, nullable=True)
    
    strong_points = db.Column(db.Text, nullable=True)
    development_points = db.Column(db.Text, nullable=True)
    action_plan = db.Column(db.Text, nullable=True)
    
    approval_status = db.Column(db.String(50), nullable=True)

    experience_details = db.Column(MutableDict.as_mutable(JSON), nullable=True)

    is_jointly_viewed = db.Column(db.Boolean, default=False, nullable=False)
    viewed_at = db.Column(db.DateTime, nullable=True)
    
    validation_status = db.Column(db.String(20), default='pending', nullable=False)
    validated_at = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    evaluator = db.relationship('User', foreign_keys=[evaluator_id], 
                                backref=db.backref('evaluations_given', cascade='all, delete-orphan'))
    evaluated = db.relationship('User', foreign_keys=[evaluated_id], 
                                backref=db.backref('evaluations_received', cascade='all, delete-orphan'))
    
    def calculate_score(self):
        criteria_fields = [
            self.criteria_punctuality,
            self.criteria_quality,
            self.criteria_productivity,
            self.criteria_teamwork,
            self.criteria_communication,
            self.criteria_initiative,
            self.criteria_compliance,
            self.criteria_development
        ]
        
        conforme_count = 0
        applicable_count = 0
        
        for field in criteria_fields:
            if field == 'conforme':
                conforme_count += 1
                applicable_count += 1
            elif field == 'nao_conforme':
                applicable_count += 1
        
        if applicable_count > 0:
            criteria_score = (conforme_count / applicable_count) * 60
        else:
            criteria_score = 0
        
        rating = self.rating if self.rating is not None else 0
        rating_score = (rating / 10) * 40
        
        base_score = criteria_score + rating_score
        
        absence_deduction = (self.absence_count or 0) * 5 
        medical_deduction = (self.medical_certificate_count or 0) * 3 
        total_deduction = absence_deduction + medical_deduction
        
        score = max(0, round(base_score - total_deduction, 2))
        
        self.is_compliant = score >= 60
        self.total_score = score
        
        return score
    
    def get_status_badge(self):
        """Retorna classe CSS para badge de status"""
        if self.total_score is None:
            return 'badge-secondary'
        if self.total_score >= 80:
            return 'badge-success'
        elif self.total_score >= 60:
            return 'badge-primary'
        elif self.total_score >= 40:
            return 'badge-warning'
        else:
            return 'badge-danger'
    
    def get_status_text(self):
        """Retorna texto do status"""
        if self.total_score is None:
            return 'Não calculado'
        if self.total_score >= 80:
            return 'Excelente'
        elif self.total_score >= 60:
            return 'Satisfatório'
        elif self.total_score >= 40:
            return 'Regular'
        else:
            return 'Insatisfatório'
    
    def __repr__(self):
        return f'<EmployeeEvaluation {self.evaluator.username} -> {self.evaluated.username} ({self.month_reference})>'


class CounterEvaluation(db.Model):
    __tablename__ = 'counter_evaluations'
    
    id = db.Column(db.Integer, primary_key=True)
    
    original_evaluation_id = db.Column(db.Integer, db.ForeignKey('employee_evaluations.id'), nullable=False)
    
    evaluator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    evaluated_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    criteria_communication = db.Column(db.String(20), nullable=True)  # 'conforme', 'nao_conforme', 'nao_aplica'
    criteria_communication_justification = db.Column(db.Text, nullable=True)
    
    criteria_clarity = db.Column(db.String(20), nullable=True)
    criteria_clarity_justification = db.Column(db.Text, nullable=True)
    
    criteria_support = db.Column(db.String(20), nullable=True)
    criteria_support_justification = db.Column(db.Text, nullable=True)
    
    criteria_recognition = db.Column(db.String(20), nullable=True)
    criteria_recognition_justification = db.Column(db.Text, nullable=True)
    
    criteria_fairness = db.Column(db.String(20), nullable=True)
    criteria_fairness_justification = db.Column(db.Text, nullable=True)
    
    criteria_development = db.Column(db.String(20), nullable=True)
    criteria_development_justification = db.Column(db.Text, nullable=True)
    
    rating = db.Column(db.Integer, nullable=False)
    rating_justification = db.Column(db.Text, nullable=True)
    
    strong_points = db.Column(db.Text, nullable=True)
    
    improvement_suggestions = db.Column(db.Text, nullable=True)
    
    total_score = db.Column(db.Float, nullable=True)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    original_evaluation = db.relationship('EmployeeEvaluation', backref=db.backref('counter_evaluation', uselist=False, cascade='all, delete-orphan'))
    evaluator = db.relationship('User', foreign_keys=[evaluator_id], 
                                backref=db.backref('counter_evaluations_given', cascade='all, delete-orphan'))
    evaluated = db.relationship('User', foreign_keys=[evaluated_id], 
                                backref=db.backref('counter_evaluations_received', cascade='all, delete-orphan'))
    
    def calculate_score(self):
        """Calcula o score da contra-avaliação"""
        criteria_fields = [
            self.criteria_communication,
            self.criteria_clarity,
            self.criteria_support,
            self.criteria_recognition,
            self.criteria_fairness,
            self.criteria_development
        ]
        
        conforme_count = 0
        applicable_count = 0
        
        for field in criteria_fields:
            if field == 'conforme':
                conforme_count += 1
                applicable_count += 1
            elif field == 'nao_conforme':
                applicable_count += 1
        
        if applicable_count > 0:
            criteria_score = (conforme_count / applicable_count) * 60
        else:
            criteria_score = 0
        
        rating = self.rating if self.rating is not None else 0
        rating_score = (rating / 10) * 40
        
        score = round(criteria_score + rating_score, 2)
        self.total_score = score
        
        return score
    
    def __repr__(self):
        return f'<CounterEvaluation {self.evaluator.username} -> {self.evaluated.username}>'


class ValidationSession(db.Model):
    __tablename__ = 'validation_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    
    evaluation_id = db.Column(db.Integer, db.ForeignKey('employee_evaluations.id'), nullable=False)
    
    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    manager_authenticated = db.Column(db.Boolean, default=False, nullable=False)
    manager_auth_at = db.Column(db.DateTime, nullable=True)
    
    employee_authenticated = db.Column(db.Boolean, default=False, nullable=False)
    employee_auth_at = db.Column(db.DateTime, nullable=True)
    
    session_status = db.Column(db.String(20), default='pending', nullable=False) 
    session_token = db.Column(db.String(64), unique=True, nullable=False) 
    
    expires_at = db.Column(db.DateTime, nullable=False)
    
    session_notes = db.Column(db.Text, nullable=True)
    action_items = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    evaluation = db.relationship('EmployeeEvaluation', backref=db.backref('validation_sessions', cascade='all, delete-orphan'))
    manager = db.relationship('User', foreign_keys=[manager_id], 
                              backref=db.backref('validation_sessions_as_manager', cascade='all, delete-orphan'))
    employee = db.relationship('User', foreign_keys=[employee_id], 
                               backref=db.backref('validation_sessions_as_employee', cascade='all, delete-orphan'))
    
    def is_expired(self):
        """Verifica se a sessão expirou"""
        now = datetime.now(timezone.utc)
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return now > expires
    
    def is_fully_authenticated(self):
        """Verifica se ambos os participantes autenticaram"""
        return self.manager_authenticated and self.employee_authenticated
    
    def __repr__(self):
        return f'<ValidationSession {self.session_token[:8]}... ({self.session_status})>'


class CareerPlan(db.Model):
    __tablename__ = 'career_plans'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    
    current_role = db.Column(db.String(100), nullable=False)
    target_role = db.Column(db.String(100), nullable=False)
    target_sector = db.Column(db.String(100), nullable=False)
    
    goals = db.Column(db.Text, nullable=True) 
    readiness_score = db.Column(db.Integer, default=0)
    
    last_updated = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    user = db.relationship('User', backref=db.backref('career_plan', uselist=False, cascade='all, delete-orphan'))
    
    def __repr__(self):
        return f'<CareerPlan {self.user.username}>'
