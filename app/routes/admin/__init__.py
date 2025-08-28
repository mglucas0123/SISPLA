from flask import Blueprint, redirect, url_for
from flask_login import login_required
from .utils import admin_required

from .users import users_bp
from .notices import notices_bp
from .repositories import repositories_bp
from .courses import courses_bp
from .quiz import quiz_bp
from .duty import duty_bp

def create_admin_blueprint():    
    admin_bp = Blueprint('admin', __name__, url_prefix='/admin')
    
    admin_bp.register_blueprint(users_bp)
    admin_bp.register_blueprint(notices_bp)
    admin_bp.register_blueprint(repositories_bp)
    admin_bp.register_blueprint(courses_bp)
    admin_bp.register_blueprint(quiz_bp)
    admin_bp.register_blueprint(duty_bp)
    
    @admin_bp.route("/")
    @login_required
    @admin_required
    def admin_dashboard():
        """Dashboard principal do admin"""
        return redirect(url_for('admin.users.list_users'))
    
    return admin_bp
