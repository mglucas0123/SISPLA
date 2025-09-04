from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import db, Nir, User, NirProcedure
from app.config_procedures import search_procedures
from app.utils.rbac_permissions import require_permission, require_module_access
from datetime import datetime

nir_bp = Blueprint('nir', __name__, template_folder='../templates')

@nir_bp.route("/nir")
@login_required
@require_module_access('nir')
def list_records():
    page = request.args.get('page', 1, type=int)
    per_page = 15
    is_ajax = request.args.get('ajax') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    patient_name = request.args.get('patient_name', '').strip()
    entry_type = request.args.get('entry_type', '').strip()
    admission_type = request.args.get('admission_type', '').strip()
    responsible_doctor = request.args.get('responsible_doctor', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()

    query = Nir.query.order_by(Nir.creation_date.desc())

    if patient_name:
        query = query.filter(Nir.patient_name.ilike(f'%{patient_name}%'))

    if entry_type:
        query = query.filter(Nir.entry_type.ilike(entry_type))

    if admission_type:
        query = query.filter(Nir.admission_type.ilike(admission_type))

    if responsible_doctor:
        query = query.filter(Nir.responsible_doctor.ilike(f'%{responsible_doctor}%'))

    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(Nir.admission_date >= start_date_obj)
        except ValueError:
            flash('Data inicial inválida', 'warning')

    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(Nir.admission_date <= end_date_obj)
        except ValueError:
            flash('Data final inválida', 'warning')

    records = query.paginate(page=page, per_page=per_page, error_out=False)

    entry_types = db.session.query(Nir.entry_type).distinct().filter(Nir.entry_type.isnot(None)).all()
    entry_types = [et[0] for et in entry_types if et[0]]

    admission_types = db.session.query(Nir.admission_type).distinct().filter(Nir.admission_type.isnot(None)).all()
    admission_types = [at[0] for at in admission_types if at[0]]

    filters = {
        'patient_name': patient_name,
        'entry_type': entry_type,
        'admission_type': admission_type,
        'responsible_doctor': responsible_doctor,
        'start_date': start_date,
        'end_date': end_date
    }

    if is_ajax:
        return render_template('nir/list_records.html', 
                             records=records, 
                             entry_types=entry_types,
                             admission_types=admission_types,
                             filters=filters,
                             ajax_request=True)

    return render_template('nir/list_records.html', 
                         records=records, 
                         entry_types=entry_types,
                         admission_types=admission_types,
                         filters=filters)

@nir_bp.route("/nir/filter", methods=['POST'])
@login_required
@require_module_access('nir')
def filter_records_ajax():
    page = request.form.get('page', 1, type=int)
    per_page = 15

    patient_name = request.form.get('patient_name', '').strip()
    entry_type = request.form.get('entry_type', '').strip()
    admission_type = request.form.get('admission_type', '').strip()
    responsible_doctor = request.form.get('responsible_doctor', '').strip()
    start_date = request.form.get('start_date', '').strip()
    end_date = request.form.get('end_date', '').strip()

    query = Nir.query.order_by(Nir.creation_date.desc())

    if patient_name:
        query = query.filter(Nir.patient_name.ilike(f'%{patient_name}%'))

    if entry_type:
        query = query.filter(Nir.entry_type.ilike(entry_type))

    if admission_type:
        query = query.filter(Nir.admission_type.ilike(admission_type))

    if responsible_doctor:
        query = query.filter(Nir.responsible_doctor.ilike(f'%{responsible_doctor}%'))

    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(Nir.admission_date >= start_date_obj)
        except ValueError:
            pass

    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(Nir.admission_date <= end_date_obj)
        except ValueError:
            pass

    records = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template('nir/list_records_ajax.html', records=records)

@nir_bp.route("/nir/novo")
@login_required
@require_permission('criar_nir')
def new_record():
    return render_template('nir/new_record.html')

@nir_bp.route("/nir/criar", methods=['POST'])
@login_required
@require_permission('criar_nir')
def create_record():
    try:
        birth_date_str = request.form.get('birth_date')
        birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date() if birth_date_str else None

        admission_date_str = request.form.get('admission_date')
        admission_date = datetime.strptime(admission_date_str, '%Y-%m-%d').date() if admission_date_str else None

        scheduling_date_str = request.form.get('scheduling_date')
        scheduling_date = datetime.strptime(scheduling_date_str, '%Y-%m-%d').date() if scheduling_date_str else None

        discharge_date_str = request.form.get('discharge_date')
        discharge_date = datetime.strptime(discharge_date_str, '%Y-%m-%d').date() if discharge_date_str else None

        total_days = None
        if admission_date and discharge_date:
            total_days = (discharge_date - admission_date).days

        new_nir = Nir(
            patient_name=request.form.get('patient_name'),
            birth_date=birth_date,
            gender=request.form.get('gender'),
            susfacil=request.form.get('susfacil'),
            admission_date=admission_date,
            entry_type=request.form.get('entry_type'),
            admission_type=request.form.get('admission_type'),
            admitted_from_origin=request.form.get('admitted_from_origin'),
            procedure_code=None,
            surgical_description=None,
            responsible_doctor=request.form.get('responsible_doctor'),
            main_cid=request.form.get('main_cid'),
            sus_number=request.form.get('sus_number'),
            aih=request.form.get('aih'),
            scheduling_date=scheduling_date,
            discharge_type=request.form.get('discharge_type'),
            discharge_date=discharge_date,
            total_days_admitted=total_days,
            cancelled=request.form.get('cancelled'),
            cancellation_reason=request.form.get('cancellation_reason'),
            criticized=request.form.get('criticized'),
            billed=request.form.get('billed'),
            status=request.form.get('status'),
            observation=request.form.get('observation'),
            day=admission_date.day if admission_date else None,
            month=admission_date.strftime('%B') if admission_date else None,
            operator_id=current_user.id
        )

        db.session.add(new_nir)
        db.session.flush()

        codes = request.form.getlist('procedure_codes[]')
        descs = request.form.getlist('procedure_descriptions[]')
        seen = set()
        for idx, (c, d) in enumerate(zip(codes, descs)):
            c_norm = (c or '').strip()
            d_norm = (d or '').strip()
            if not c_norm or not d_norm:
                continue
            if c_norm in seen:
                continue
            seen.add(c_norm)
            proc = NirProcedure(
                nir_id=new_nir.id,
                code=c_norm,
                description=d_norm,
                sequence=idx,
                is_primary=(idx == 0)
            )
            db.session.add(proc)
            if idx == 0:
                new_nir.procedure_code = c_norm
                new_nir.surgical_description = d_norm

        if not seen:
            single_code = request.form.get('procedure_code')
            single_desc = request.form.get('surgical_description')
            if single_code and single_desc:
                new_nir.procedure_code = single_code
                new_nir.surgical_description = single_desc
                db.session.add(NirProcedure(
                    nir_id=new_nir.id,
                    code=single_code,
                    description=single_desc,
                    sequence=0,
                    is_primary=True
                ))

        db.session.commit()

        flash('Registro NIR criado com sucesso!', 'success')
        return redirect(url_for('nir.list_records'))

    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao criar registro: {str(e)}', 'danger')
        return redirect(url_for('nir.new_record'))

@nir_bp.route("/nir/<int:record_id>")
@login_required
@require_permission('visualizar_nir')
def record_details(record_id):
    record = Nir.query.get_or_404(record_id)
    return render_template('nir/record_details.html', record=record)

@nir_bp.route("/nir/editar/<int:record_id>")
@login_required
@require_permission('editar_nir')
def edit_record(record_id):
    record = Nir.query.get_or_404(record_id)
    return render_template('nir/edit_record.html', record=record)

@nir_bp.route("/nir/atualizar/<int:record_id>", methods=['POST'])
@login_required
@require_permission('editar_nir')
def update_record(record_id):
    record = Nir.query.get_or_404(record_id)

    try:
        birth_date_str = request.form.get('birth_date')
        birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date() if birth_date_str else None

        admission_date_str = request.form.get('admission_date')
        admission_date = datetime.strptime(admission_date_str, '%Y-%m-%d').date() if admission_date_str else None

        scheduling_date_str = request.form.get('scheduling_date')
        scheduling_date = datetime.strptime(scheduling_date_str, '%Y-%m-%d').date() if scheduling_date_str else None

        discharge_date_str = request.form.get('discharge_date')
        discharge_date = datetime.strptime(discharge_date_str, '%Y-%m-%d').date() if discharge_date_str else None

        total_days = None
        if admission_date and discharge_date:
            total_days = (discharge_date - admission_date).days

        record.patient_name = request.form.get('patient_name')
        record.birth_date = birth_date
        record.gender = request.form.get('gender')
        record.susfacil = request.form.get('susfacil')
        record.admission_date = admission_date
        record.entry_type = request.form.get('entry_type')
        record.admission_type = request.form.get('admission_type')
        record.admitted_from_origin = request.form.get('admitted_from_origin')
        record.procedures.clear()
        db.session.flush()

        codes = request.form.getlist('procedure_codes[]')
        descs = request.form.getlist('procedure_descriptions[]')
        seen = set()
        for idx, (c, d) in enumerate(zip(codes, descs)):
            c_norm = (c or '').strip()
            d_norm = (d or '').strip()
            if not c_norm or not d_norm:
                continue
            if c_norm in seen:
                continue
            seen.add(c_norm)
            record.procedures.append(NirProcedure(
                code=c_norm,
                description=d_norm,
                sequence=idx,
                is_primary=(idx == 0)
            ))
            if idx == 0:
                record.procedure_code = c_norm
                record.surgical_description = d_norm

        if not seen:
            single_code = request.form.get('procedure_code')
            single_desc = request.form.get('surgical_description')
            record.procedure_code = single_code
            record.surgical_description = single_desc
            if single_code and single_desc:
                record.procedures.append(NirProcedure(
                    code=single_code,
                    description=single_desc,
                    sequence=0,
                    is_primary=True
                ))
        record.responsible_doctor = request.form.get('responsible_doctor')
        record.main_cid = request.form.get('main_cid')
        record.sus_number = request.form.get('sus_number')
        record.aih = request.form.get('aih')
        record.scheduling_date = scheduling_date
        record.discharge_type = request.form.get('discharge_type')
        record.discharge_date = discharge_date
        record.total_days_admitted = total_days
        record.cancelled = request.form.get('cancelled')
        record.cancellation_reason = request.form.get('cancellation_reason')
        record.criticized = request.form.get('criticized')
        record.billed = request.form.get('billed')
        record.status = request.form.get('status')
        record.observation = request.form.get('observation')
        record.day = admission_date.day if admission_date else None
        record.month = admission_date.strftime('%B') if admission_date else None
        record.last_modified = datetime.utcnow()

        db.session.commit()

        flash('Registro NIR atualizado com sucesso!', 'success')
        return redirect(url_for('nir.record_details', record_id=record.id))

    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao atualizar registro: {str(e)}', 'danger')
        return redirect(url_for('nir.edit_record', record_id=record_id))

@nir_bp.route("/nir/excluir/<int:record_id>", methods=['POST'])
@login_required
@require_permission('excluir_nir')
def delete_record(record_id):
    record = Nir.query.get_or_404(record_id)

    try:
        db.session.delete(record)
        db.session.commit()
        flash('Registro NIR excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir registro: {str(e)}', 'danger')

    return redirect(url_for('nir.list_records'))

@nir_bp.route('/nir/procedures/search')
@login_required
@require_module_access('nir')
def procedures_search():
    """Endpoint para auto-complete de procedimentos.

    Parâmetros:
        q: termo de busca (código ou parte da descrição)
        limit: máximo de resultados (default 15)
    """
    q = request.args.get('q', '').strip()
    limit = request.args.get('limit', 15, type=int)
    if limit > 50:
        limit = 50
    results = search_procedures(q, limit=limit)
    return jsonify(results)