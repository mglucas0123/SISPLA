from datetime import datetime, time
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select
from sqlalchemy.sql import func
from app.models import db, Form, User
from app.utils.rbac_permissions import require_permission

shift_handover_bp = Blueprint('shift_handover', __name__, template_folder='../templates')

#<!--- Novo Registro de Plantão --->
@shift_handover_bp.route("/new_shift_handover_record", methods=["GET", "POST"])
@login_required
@require_permission('criar-registro-plantao')
def new_shift_handover_record():
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
            return redirect(url_for("shift_handover.shift_handover_records"))
        
        except KeyError as e:
            flash(f"Erro no formulário: campo obrigatório '{e.name}' ausente.", "danger")
        except Exception as e:
            db.session.rollback()
            flash(f"Ocorreu um erro ao salvar o formulário: {str(e)}", "danger")

    return render_template("form/new_shift_handover_record.html")

#<!--- Lista dos Registros de Plantão --->
@shift_handover_bp.route("/shift_handover_records")
@login_required
def shift_handover_records():
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

#<!--- Detalhes do Registro de Plantão --->
@shift_handover_bp.route("/shift_handover_record/<int:form_id>/details")
@login_required
def shift_handover_record_details(form_id):
    formulario = db.session.get(Form, form_id)
    if not formulario:
        flash("Formulário não encontrado.", "danger")
        return redirect(url_for('shift_handover.shift_handover_records'))
    return render_template("form/details_form.html", formulario=formulario)

#<!--- Excluir Registro de Plantão --->
@shift_handover_bp.route("/shift_handover_record/delete/<int:form_id>", methods=["POST"])
@login_required
@require_permission('excluir-registro-plantao')
def delete_shift_handover_record(form_id):
    form_to_delete = Form.query.get_or_404(form_id)
    
    db.session.delete(form_to_delete)
    db.session.commit()
    
    flash('Formulário excluído com sucesso!', 'success')
    return redirect(url_for('shift_handover.shift_handover_records'))