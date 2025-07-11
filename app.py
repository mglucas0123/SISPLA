import os

from flask import Flask, current_app
from flask_login import LoginManager
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

from db import db, User, Form
from routes.admin import admin_bp
from routes.auth import auth_bp
from routes.main import main_bp
from routes.util import util_bp
from routes.form import form_bp
from routes.repository import repository_bp
from routes.training import training_bp

from routes.util import format_date_filter

load_dotenv()

def create_app():
    app = Flask(__name__)

    app.secret_key = os.getenv('SECRET_KEY', '')

    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'uploads')
        
    db.init_app(app)
        
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = "Por favor, realize o login para acessar esta página."
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # <--- Registro dos Blueprints --->
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(util_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(form_bp)
    app.register_blueprint(repository_bp)
    app.register_blueprint(training_bp)

    # <--- Registro dos Filtros --->
    app.jinja_env.filters['format_date'] = format_date_filter
    app.jinja_env.filters['format_date_short'] = lambda val: format_date_filter(val, format_str='%d/%m/%Y')
    app.jinja_env.filters['format_date_time'] = lambda val: format_date_filter(val, format_str='%d/%m/%Y %H:%M')
    app.jinja_env.filters['format_time'] = lambda val: format_date_filter(val, format_str='%H:%M')


    # <-- Criação/Verificação do Usuário Admin -->
    @app.cli.command("init-db")
    def init_db_command():
        with app.app_context():
            db.create_all()
            admin_usuario = db.session.execute(db.select(User).filter_by(username="admin")).scalar_one_or_none()
            
            if not admin_usuario:
                admin_pass = os.getenv('ADMIN_DEFAULT_PASSWORD', "admin")
                admin = User(
                    name="Administrador",
                    username="admin",
                    email="lucasiturama2013@gmail.com",
                    password=generate_password_hash(admin_pass),
                    profile="ADMIN,CRIAR_RELATORIOS,VER_RELATORIOS"
                )
                db.session.add(admin)
                db.session.commit()
                print("Usuário admin padrão criado com sucesso.")
            else:
                print("Usuário admin padrão já existe.")
                
                
        print("Banco de dados inicializado.")
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)