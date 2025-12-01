from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_required, current_user
from app.models import db, User
import pyotp
import qrcode
import io
import base64

user_bp = Blueprint('user', __name__, template_folder='../templates')

@user_bp.route("/profile")
@login_required
def profile():
    return render_template("user/profile.html")

@user_bp.route("/profile/2fa/setup", methods=["POST"])
@login_required
def setup_2fa():
    if current_user.totp_secret:
        flash("2FA já está configurado.", "info")
        return redirect(url_for('user.profile'))

    secret = pyotp.random_base32()
    
    session['totp_secret_setup'] = secret
    
    totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=current_user.email,
        issuer_name="SISPLA"
    )
    
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(totp_uri)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered)
    qr_code_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    
    return render_template("user/setup_2fa.html", secret=secret, qr_code=qr_code_base64)

@user_bp.route("/profile/2fa/verify", methods=["POST"])
@login_required
def verify_2fa():
    secret = session.get('totp_secret_setup')
    code = request.form.get("code")
    
    if not secret:
        flash("Sessão de configuração expirada. Tente novamente.", "danger")
        return redirect(url_for('user.profile'))
        
    totp = pyotp.TOTP(secret)
    if totp.verify(code):
        current_user.totp_secret = secret
        db.session.commit()
        session.pop('totp_secret_setup', None)
        flash("Autenticação de dois fatores ativada com sucesso!", "success")
    else:
        flash("Código incorreto. Tente novamente.", "danger")
        return redirect(url_for('user.profile'))
        
    return redirect(url_for('user.profile'))

@user_bp.route("/profile/2fa/disable", methods=["POST"])
@login_required
def disable_2fa():
    current_user.totp_secret = None
    db.session.commit()
    flash("Autenticação de dois fatores desativada.", "info")
    return redirect(url_for('user.profile'))
