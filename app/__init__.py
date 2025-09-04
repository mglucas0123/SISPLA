import os
import subprocess
import datetime

from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

from app.models import db, User, Role
from app.routes.admin import create_admin_blueprint
from app.utils.rbac_permissions import initialize_rbac, assign_role_to_user
from app.routes.auth import auth_bp
from app.routes.main import main_bp
from app.routes.util import util_bp, format_date_filter
from app.routes.form import form_bp
from app.routes.repository import repository_bp
from app.routes.training import training_bp
from app.routes.nir import nir_bp

load_dotenv()

def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.secret_key = os.getenv('SECRET_KEY', '')
    basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'app', 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024
    db.init_app(app)
    Migrate(app, db)

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
    app.register_blueprint(form_bp)
    app.register_blueprint(repository_bp)
    app.register_blueprint(training_bp)
    app.register_blueprint(nir_bp)

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
                print("Usuário Administrador padrão criado com sucesso e papel RBac atribuído.")
            else:
                admin_role = Role.query.filter_by(name='Administrador').first()
                if admin_role and admin_role not in admin_usuario.roles:
                    assign_role_to_user(admin_usuario, 'Administrador')
                    print("Papel RBac atribuído ao usuário admin existente.")
                else:
                    print("Usuário admin padrão já existe com papel RBac.")
        print("Banco de dados inicializado com sistema RBac.")
    @app.cli.command("migrate-upgrade")
    def migrate_upgrade():
        msg = f"Auto migration - {datetime.datetime.now().strftime('%d-%m-%Y_%H-%M-%S')}"
        subprocess.run(["flask", "db", "migrate", "-m", msg], check=True)
        subprocess.run(["flask", "db", "upgrade"], check=True)
        print("Migração e upgrade aplicados com sucesso.")