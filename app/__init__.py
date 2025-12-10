import os
import subprocess
import datetime

from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

from config import config as app_config
from app.models import db, User, Role
from app.routes.admin import create_admin_blueprint
from app.utils.rbac_permissions import initialize_rbac, assign_role_to_user
from app.routes.auth import auth_bp
from app.routes.main import main_bp
from app.routes.util import util_bp, format_date_filter
from app.routes.user import user_bp
from app.routes.shift_handover import shift_handover_bp
from app.routes.repository import repository_bp
from app.routes.training import training_bp
from app.routes.nir import nir_bp
from app.routes.feedback.suppliers import suppliers_bp
from app.routes.avaliacao_funcionario import employee_evaluation_bp
from app.routes.collaborative_validation import collaborative_bp

load_dotenv()

def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")

    config_name = os.getenv('FLASK_CONFIG', 'default')
    app.config.from_object(app_config.get(config_name, app_config['default']))

    basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    instance_path = os.path.join(basedir, 'instance')
    os.makedirs(instance_path, exist_ok=True)

    default_sqlite = 'sqlite:///' + os.path.join(instance_path, 'database.db')
    postgres_url = os.getenv('POSTGRES_URL') or os.getenv('DATABASE_URL')
    app.config['SQLALCHEMY_DATABASE_URI'] = postgres_url or default_sqlite

    app.config.setdefault('SQLALCHEMY_BINDS', {
        'procedures': 'sqlite:///' + os.path.join(instance_path, 'procedures.db')
    })

    app.config.setdefault('UPLOAD_FOLDER', '/app/uploads')
    app.config.setdefault('MAX_CONTENT_LENGTH', 500 * 1024 * 1024)
    app.config.setdefault('WTF_CSRF_ENABLED', True)
    app.config.setdefault('WTF_CSRF_TIME_LIMIT', 3600)

    app.secret_key = app.config.get('SECRET_KEY', os.getenv('SECRET_KEY', ''))

    db.init_app(app)
    Migrate(app, db)
    csrf = CSRFProtect(app)
 
    login_config(app)
    registry_routes(app)
    registry_filters(app)
    initdb(app)
    return app

def registry_routes(app):
    admin_bp = create_admin_blueprint()
    app.register_blueprint(admin_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(util_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(shift_handover_bp)
    app.register_blueprint(repository_bp)
    app.register_blueprint(training_bp)
    app.register_blueprint(nir_bp)
    app.register_blueprint(suppliers_bp)
    app.register_blueprint(employee_evaluation_bp)
    app.register_blueprint(collaborative_bp)

def login_config(app):
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = "Por favor, realize o login para acessar esta página."
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(id):
        return db.session.get(User, int(id))

def registry_filters(app):
    app.jinja_env.filters['format_date'] = format_date_filter
    app.jinja_env.filters['format_date_short'] = lambda val: format_date_filter(val, format_str='%d/%m/%Y')
    app.jinja_env.filters['format_date_time'] = lambda val: format_date_filter(val, format_str='%d/%m/%Y %H:%M')
    app.jinja_env.filters['format_time'] = lambda val: format_date_filter(val, format_str='%H:%M')

def initdb(app):
    @app.cli.command("init-db")
    def init_db_command():
        with app.app_context():
            db.create_all()
            initialize_rbac()
            
            admin_usuario = db.session.execute(db.select(User).filter_by(username="admin")).scalar_one_or_none()
            if not admin_usuario:
                admin_pass = os.getenv('ADMIN_DEFAULT_PASSWORD', "admin")
                admin = User(
                    name="Administrador",
                    username="admin",
                    email="lucasiturama2013@gmail.com",
                    password=generate_password_hash(admin_pass),
                    profile="LEGACY_ADMIN"
                )
                db.session.add(admin)
                db.session.commit()
                
                assign_role_to_user(admin, 'Administrador')
                print("Usuário Administrador padrão criado com sucesso e papel 'Administrador' atribuído.")
            else:
                admin_role = Role.query.filter_by(name='Administrador').first()
                if admin_role and admin_role not in admin_usuario.roles:
                    assign_role_to_user(admin_usuario, 'Administrador')
                    print("Papel 'Administrador' atribuído ao usuário admin existente.")
                else:
                    print("Usuário admin padrão já existe com papel apropriado no RBAC.")
        print("Banco de dados inicializado com sistema RBac.")

    @app.cli.command("assign-enfermagem-role")
    def assign_enfermagem_role():
        with app.app_context():
            initialize_rbac()

            role = Role.query.filter_by(name='Enfermagem').first()
            if not role:
                print("Role 'Enfermagem' não encontrada e não pôde ser criada. Abortando.")
                return

            users = db.session.execute(db.select(User)).scalars().all()
            updated = 0
            already = 0
            skipped = 0
            affected_usernames = []

            for u in users:
                legacy = (u.profile or '')
                tokens = [t.strip().lower() for t in legacy.split(',') if t.strip()]

                has_flag = ('criar_relatorios' in tokens) or ('enfermagem' in tokens)
                if not has_flag:
                    skipped += 1
                    continue

                if role in u.roles:
                    already += 1
                    continue

                u.roles.append(role)
                affected_usernames.append(u.username)
                updated += 1

            if updated:
                db.session.commit()

            print("Resumo da atribuição da Role 'Enfermagem':")
            print(f" - Atualizados: {updated}")
            print(f" - Já possuíam a role: {already}")
            print(f" - Ignorados (sem flags no profile): {skipped}")
            if affected_usernames:
                print("Usuários atualizados:")
                preview = ', '.join(affected_usernames[:50])
                print(preview + (" ..." if len(affected_usernames) > 50 else ""))
    @app.cli.command("migrate-upgrade")
    def migrate_upgrade():
        msg = f"Auto migration - {datetime.datetime.now().strftime('%d-%m-%Y_%H-%M-%S')}"
        subprocess.run(["flask", "db", "migrate", "-m", msg], check=True)
        subprocess.run(["flask", "db", "upgrade"], check=True)
        print("Migração e upgrade aplicados com sucesso.")
