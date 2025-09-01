import enum
from flask import url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

repository_access = db.Table('repository_access',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('repository_id', db.Integer, db.ForeignKey('repositories.id'), primary_key=True)
)

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
    
    notices = db.relationship('Notice', back_populates='author')
    forms = db.relationship('Form', back_populates='worker', lazy='dynamic')
    nir = db.relationship('Nir', back_populates='operator', lazy='dynamic')
    shared_repositories = db.relationship('Repository', secondary=repository_access, back_populates='shared_with_users')
    @property
    def has_private_repository(self): 
        return db.session.query(
            Repository.query.filter_by(owner_id=self.id, access_type='private').exists()
        ).scalar()

    def __repr__(self):
        return f'<User {self.username}>'


class Nir(db.Model):
    __tablename__ = 'nir'
    
    id = db.Column(db.Integer, primary_key=True)
    
    patient_name = db.Column(db.String(200), nullable=False)
    birth_date = db.Column(db.Date, nullable=False)
    gender = db.Column(db.String(1), nullable=False)
    susfacil = db.Column(db.String(50), nullable=True)
    
    admission_date = db.Column(db.Date, nullable=True)
    entry_type = db.Column(db.String(50), nullable=True)
    admission_type = db.Column(db.String(50), nullable=True)
    admitted_from_origin = db.Column(db.String(10), nullable=True)
    
    procedure_code = db.Column(db.String(20), nullable=True)
    surgical_description = db.Column(db.Text, nullable=True)
    
    responsible_doctor = db.Column(db.String(100), nullable=True)
    main_cid = db.Column(db.String(10), nullable=True)
    sus_number = db.Column(db.String(50), nullable=False)
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
    
    day = db.Column(db.Integer, nullable=True)
    month = db.Column(db.String(20), nullable=True)
    operator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    creation_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_modified = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    operator = db.relationship('User', back_populates='nir')
    
    def __repr__(self):
        return f'<Nir {self.id}: {self.patient_name}>'
    
        
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
