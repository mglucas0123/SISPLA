from datetime import datetime, time
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import Date, cast, select
from sqlalchemy.sql import func
from app.models import db, Form, User

form_bp = Blueprint('form', __name__, template_folder='../templates')

@form_bp.route("/new_form", methods=["GET", "POST"])
@login_required
def new_form():
    if "CRIAR_RELATORIOS" not in current_user.profile and "ADMIN" not in current_user.profile:
        flash("Acesso negado! Você não tem permissão para criar novos formulários.", "danger")
        return redirect(url_for("main.panel"))

    if request.method == "POST":
        try:
            form = Form(
                worker_id=current_user.id,
                sector=request.form["sector"],
                date_registry=datetime.utcnow(),
                observation=request.form.get("observation")
            )
            db.session.add(form)
            db.session.commit()
            flash("Registro de Plantão enviado com sucesso!", "success")
            return redirect(url_for("main.panel"))
        
        except KeyError as e:
            flash(f"Erro no formulário: campo obrigatório '{e.name}' ausente.", "danger")
        except Exception as e:
            db.session.rollback()
            flash(f"Ocorreu um erro ao salvar o formulário: {str(e)}", "danger")

    return render_template("form/new_form.html")

@form_bp.route("/forms")
@login_required
def forms():
    if "VER_RELATORIOS" not in current_user.profile and "ADMIN" not in current_user.profile:
        flash("Acesso negado! Você não tem permissão para visualizar os relatórios.", "danger")
        return redirect(url_for("main.panel"))

    data_inicio_str = request.args.get('data_inicio', '').strip()
    data_fim_str = request.args.get('data_fim', '').strip()
    tipo_data = request.args.get('tipo_data', 'registro').strip()
    filtro_setor = request.args.get('sector_filtro', '').strip()
    filtro_nome = request.args.get('name', '').strip().lower()

    query = select(Form).order_by(Form.date_registry.desc())

    if filtro_nome:
        query = query.join(User).where(
            func.lower(User.name).like(func.lower(f"%{filtro_nome}%"))
        )
    
    if data_inicio_str or data_fim_str:
        if data_inicio_str:
            try:
                data_inicio_obj = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
                data_inicio_completo = datetime.combine(data_inicio_obj, time.min)
                query = query.where(Form.date_registry >= data_inicio_completo)
            except ValueError:
                flash(f"Formato de 'Data Início' inválido: '{data_inicio_str}'.", "warning")
        
        if data_fim_str:
            try:
                data_fim_obj = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
                data_fim_completo = datetime.combine(data_fim_obj, time.max)
                query = query.where(Form.date_registry <= data_fim_completo)
            except ValueError:
                flash(f"Formato de 'Data Fim' inválido: '{data_fim_str}'.", "warning")

    if filtro_setor:
        query = query.where(Form.sector == filtro_setor)

    if filtro_nome:
        query = query.where(
            func.lower(User.name).like(func.lower(f"%{filtro_nome}%"))
        )
    
    page_get = request.args.get('page', 1, type=int)
    pagination = db.paginate(query, page=page_get, per_page=10, error_out=False)

    return render_template(
        "form/forms.html", 
        forms=pagination.items, pagination=pagination,
        data_inicio_atual=data_inicio_str, 
        data_fim_atual=data_fim_str, 
        tipo_data_atual=tipo_data
    )

@form_bp.route("/form/<int:form_id>/details")
@login_required
def details_form(form_id):
    formulario = db.session.get(Form, form_id)
    if not formulario:
        flash("Formulário não encontrado.", "danger")
        return redirect(url_for('form.forms'))
    
    can_view_all = "ADMIN" in current_user.profile or "VER_RELATORIOS" in current_user.profile
    is_owner = "CRIAR_RELATORIOS" in current_user.profile and formulario.worker_id == current_user.id
    
    if not (can_view_all or is_owner):
        flash("Acesso negado! Você não tem permissão para visualizar os detalhes deste formulário.", "danger")
        return redirect(url_for("form.forms"))
    
    return render_template("form/details_form.html", formulario=formulario)

@form_bp.route("/form/delet/<int:form_id>", methods=["POST"])
@login_required
def delet_form(form_id):

    if "ADMIN" not in current_user.profile:
        flash("Acesso negado! Você não tem permissão para deletar formulários.", "danger")
        return redirect(url_for("form.details_form", form_id=form_id)) 

    formulario_para_deletar = db.session.get(Form, form_id)

    if not formulario_para_deletar:
        flash("Formulário não encontrado para deleção.", "danger")
        return redirect(url_for('form.forms'))

    try:
        db.session.delete(formulario_para_deletar)
        db.session.commit()
        flash(f"Formulário ID {form_id} deletado com sucesso.", "success")
        return redirect(url_for('form.forms'))
    except Exception as e:
        db.session.rollback()
        flash(f"Ocorreu um erro ao deletar o formulário: {str(e)}", "danger")
        print(f"Erro ao deletar formulário ID {form_id}: {e}")
        return redirect(url_for("form.details_form", form_id=form_id))