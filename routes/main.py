from flask import Blueprint, render_template, redirect, session, url_for, flash
from flask_login import login_required, current_user
from db import db, Notice

main_bp = Blueprint('main', __name__, template_folder='../templates')

#<-- REDIRECIONAMENTO PARA LINK VAZIO -->
@main_bp.route("/")
def index():
    return redirect(url_for("main.panel"))

#<-- PAINEL PRINCIPAL -->
@main_bp.route("/panel")
@login_required
def panel():
    popup_aviso = None
    if session.get('show_notice_popup'):
        aviso_query = db.select(Notice).order_by(Notice.date_registry.desc()).limit(1)
        popup_aviso = db.session.execute(aviso_query).scalar_one_or_none()
        session.pop('show_notice_popup', None)
        
    avisos_fixos_query = db.select(Notice).order_by(Notice.date_registry.desc())
    todos_os_avisos = db.session.execute(avisos_fixos_query).scalars().all()

    return render_template(
        "panel.html",
        notice=todos_os_avisos,
        popup_aviso=popup_aviso
    )

@main_bp.route("/mark_notice_seen/<int:notice_id>")
@login_required
def mark_notice_seen(notice_id):
    session['notice_seen_' + str(notice_id)] = True
    return redirect(url_for('main.panel'))