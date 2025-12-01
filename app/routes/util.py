from flask import Blueprint, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_required, current_user
from app.models import db
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

util_bp = Blueprint('util', __name__, template_folder='../templates')

#<!--- TROCA DE SENHA NAVBAR --->
@util_bp.route("/change-password", methods=["POST"])
@login_required
def user_change_password():
    senha_atual = request.form.get("senha_atual")
    nova_senha = request.form.get("nova_senha")
    if not senha_atual or not nova_senha:
        flash("Todos os campos são obrigatórios.", "danger")
        return redirect(request.referrer or url_for("main.painel"))
    if len(nova_senha) < 8:
        flash("A nova senha deve ter pelo menos 8 caracteres.", "warning")
        return redirect(request.referrer or url_for("main.painel"))
    user = current_user
    if check_password_hash(user.password, senha_atual):
        user.password = generate_password_hash(nova_senha)
        db.session.commit()
        flash("Senha alterada com sucesso!", "success")
    else:
        flash("Senha atual incorreta.", "danger")
    return redirect(request.referrer or url_for("main.painel"))

#<!--- FILTRO DATA E HORA --->
def format_date_filter(value, target_tz_str='America/Sao_Paulo', format_str='%d/%m/%Y'):
    if value is None:
        return "N/A" 

    if isinstance(value, date) and not isinstance(value, datetime):
        return value.strftime(format_str)

    dt_object = None
    if isinstance(value, datetime):
        dt_object = value
    elif isinstance(value, str):
        parsed_successfully = False
        if 'T' in value and (value.endswith('Z') or '+' in value[19:] or (value.count('-') >= 2 and '-' in value[19:] and len(value) > 19)):
            try:
                dt_object = datetime.fromisoformat(value.replace('Z', '+00:00'))
                parsed_successfully = True
            except ValueError: pass
        if not parsed_successfully:
            formats_to_try = [
                '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', 
                '%Y-%m-%d',
            ]
            for fmt in formats_to_try:
                try:
                    dt_object = datetime.strptime(value, fmt)
                    parsed_successfully = True; break 
                except ValueError: continue
        if not parsed_successfully: return value
    
    if not isinstance(dt_object, datetime):
        return value 

    try:
        target_tz = ZoneInfo(target_tz_str)
        if dt_object.tzinfo is None:
            # Heuristic: if the naive datetime is very close to now() in UTC, it's likely stored as UTC (e.g. default datetime.utcnow())
            now_utc_naive = datetime.utcnow()
            if abs((dt_object - now_utc_naive).total_seconds()) < 3600:
                # Interpret as UTC and convert to target timezone
                local_dt = dt_object.replace(tzinfo=timezone.utc).astimezone(target_tz)
            else:
                # Assume the naive timestamp represents local time
                local_dt = dt_object.replace(tzinfo=target_tz)
        else:
            local_dt = dt_object.astimezone(target_tz)
        return local_dt.strftime(format_str)
    except Exception as e:
        print(f"AVISO: Erro na conversão de fuso ou formatação: {e}. Retornando string formata do datetime original.")
        try:
            return dt_object.strftime(format_str)
        except Exception:
            return str(dt_object)