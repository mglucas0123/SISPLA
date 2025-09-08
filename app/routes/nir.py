from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import db, Nir, User, NirProcedure, NirSectionStatus
from app.config_procedures import search_procedures
from app.utils.rbac_permissions import require_permission, require_module_access
from datetime import datetime

nir_bp = Blueprint('nir', __name__, template_folder='../templates')

def initialize_section_statuses(nir):
    """Inicializa os status das seções baseado no tipo de entrada"""
    config = nir.get_section_control_config()
    
    for section_name, responsible_sector in config.items():
        existing = NirSectionStatus.query.filter_by(
            nir_id=nir.id,
            section_name=section_name
        ).first()
        
        if not existing:
            section_status = NirSectionStatus(
                nir_id=nir.id,
                section_name=section_name,
                responsible_sector=responsible_sector,
                status='PENDENTE'
            )
            db.session.add(section_status)

def get_user_sector(user):
    """Determina o setor do usuário baseado nos seus roles RBAC"""
    user_sectors = [role.sector for role in user.roles if role.sector]
    
    if 'CENTRO_CIRURGICO' in user_sectors:
        return 'CENTRO_CIRURGICO'
    elif 'FATURAMENTO' in user_sectors:
        return 'FATURAMENTO'
    elif any(sector in ['ENFERMAGEM', 'MEDICINA', 'RECEPCAO'] for sector in user_sectors):
        return 'NIR'
    else:
        return 'NIR'

def update_section_status(nir_id, section_name, user_id):
    """Atualiza o status de uma seção como preenchida"""
    section_status = NirSectionStatus.query.filter_by(
        nir_id=nir_id,
        section_name=section_name
    ).first()
    
    if section_status:
        section_status.status = 'PREENCHIDO'
        section_status.filled_by_user_id = user_id
        section_status.filled_at = datetime.utcnow()
        db.session.commit()

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
    sector = request.args.get('sector', '').strip()
    sector_progress = request.args.get('sector_progress', '').strip()

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

    base_records = None
    if sector or sector_progress:
        base_records = query.all()
        def matches_sector(rec):
            if not sector and not sector_progress:
                return True
            prog = rec.get_sector_progress()
            sect = sector if sector else None
            if sect and sect not in prog:
                return False
            if sect and sector_progress:
                return prog[sect]['status'] == sector_progress
            if sect and not sector_progress:
                return prog[sect]['status'] in ('PENDENTE', 'EM_ANDAMENTO')
            if not sect and sector_progress:
                return any(v['status'] == sector_progress for v in prog.values())
            return True
        filtered = [r for r in base_records if matches_sector(r)]
        total = len(filtered)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_items = filtered[start_idx:end_idx]
        from types import SimpleNamespace
        records = SimpleNamespace(
            items=page_items,
            total=total,
            pages=(total // per_page + (1 if total % per_page else 0)),
            page=page,
            has_prev=page > 1,
            has_next=end_idx < total,
            prev_num=page - 1,
            next_num=page + 1,
            iter_pages=lambda left_edge=2, right_edge=2, left_current=2, right_current=2: range(1, (total // per_page + (1 if total % per_page else 0)) + 1)
        )
    else:
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
        'end_date': end_date,
        'sector': sector,
        'sector_progress': sector_progress
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
@require_permission('new_registry_nir')
def new_record():
    user_sector = get_user_sector(current_user)
    return render_template('nir/new_record.html', user_sector=user_sector)

@nir_bp.route("/nir/criar", methods=['POST'])
@login_required
@require_permission('new_registry_nir')
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
            surgical_specialty=request.form.get('surgical_specialty'),
            auxiliary=request.form.get('auxiliary'),
            anesthetist=request.form.get('anesthetist'),
            anesthesia=request.form.get('anesthesia'),
            pediatrics=request.form.get('pediatrics'),
            surgical_type=request.form.get('surgical_type'),
            day=admission_date.day if admission_date else None,
            month=admission_date.strftime('%B') if admission_date else None,
            operator_id=current_user.id
        )

        db.session.add(new_nir)
        db.session.flush()

        initialize_section_statuses(new_nir)

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

        user_sector = get_user_sector(current_user)
        effective_entry = 'URGENCIA' if new_nir.entry_type == 'CIRURGICO' else new_nir.entry_type
        if user_sector == 'NIR':
            update_section_status(new_nir.id, 'dados_paciente', current_user.id)
            update_section_status(new_nir.id, 'dados_internacao', current_user.id)
            if effective_entry == 'ELETIVO':
                if codes or (locals().get('single_code') and locals().get('single_desc')):
                    update_section_status(new_nir.id, 'procedimentos', current_user.id)
                if new_nir.responsible_doctor:
                    update_section_status(new_nir.id, 'informacoes_medicas', current_user.id)
            if new_nir.scheduling_date or new_nir.discharge_date:
                update_section_status(new_nir.id, 'agendamento_alta', current_user.id)

        new_nir.status = new_nir.compute_overall_status()
        if effective_entry == 'URGENCIA' and new_nir.status == 'PENDENTE':
            new_nir.status = 'EM_ANDAMENTO'
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
    user_sector = get_user_sector(current_user)
    
    config = record.get_section_control_config()
    editable_sections = {}
    section_statuses = {}
    
    for section_name, responsible_sector in config.items():
        editable_sections[section_name] = (responsible_sector == user_sector)
        status_obj = record.get_section_status(section_name)
        section_statuses[section_name] = status_obj.status if status_obj else 'PENDENTE'
    
    return render_template('nir/edit_record.html', 
                         record=record, 
                         user_sector=user_sector,
                         editable_sections=editable_sections,
                         section_statuses=section_statuses,
                         config=config,
                         current_user=current_user)

@nir_bp.route("/nir/atualizar/<int:record_id>", methods=['POST'])
@login_required
@require_permission('editar_nir')
def update_record(record_id):
    record = Nir.query.get_or_404(record_id)
    user_sector = get_user_sector(current_user)
    
    try:
        config = record.get_section_control_config()
        editable_sections = {}
        for section_name, responsible_sector in config.items():
            editable_sections[section_name] = (responsible_sector == user_sector)
        
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

        if editable_sections.get('dados_paciente', True):
            record.patient_name = request.form.get('patient_name')
            record.birth_date = birth_date
            record.gender = request.form.get('gender')
            record.susfacil = request.form.get('susfacil')
            record.sus_number = request.form.get('sus_number')

        if editable_sections.get('dados_internacao', True):
            record.admission_date = admission_date
            record.entry_type = request.form.get('entry_type')
            record.admission_type = request.form.get('admission_type')
            record.admitted_from_origin = request.form.get('admitted_from_origin')
            record.aih = request.form.get('aih')
            record.day = admission_date.day if admission_date else None
            record.month = admission_date.strftime('%B') if admission_date else None

        if editable_sections.get('procedimentos', True):
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

        if editable_sections.get('informacoes_medicas', True):
            record.responsible_doctor = request.form.get('responsible_doctor')
            record.main_cid = request.form.get('main_cid')
            record.surgical_specialty = request.form.get('surgical_specialty')
            record.auxiliary = request.form.get('auxiliary')
            record.anesthetist = request.form.get('anesthetist')
            record.anesthesia = request.form.get('anesthesia')
            record.pediatrics = request.form.get('pediatrics')
            record.surgical_type = request.form.get('surgical_type')

        if editable_sections.get('agendamento_alta', True):
            record.scheduling_date = scheduling_date
            record.discharge_type = request.form.get('discharge_type')
            record.discharge_date = discharge_date
            record.total_days_admitted = total_days

        if editable_sections.get('status_controle', True):
            record.cancelled = request.form.get('cancelled')
            record.cancellation_reason = request.form.get('cancellation_reason')
            record.criticized = request.form.get('criticized')
            record.billed = request.form.get('billed')
            record.status = request.form.get('status')
            record.observation = request.form.get('observation')

        record.last_modified = datetime.utcnow()

        for section_name, can_edit in editable_sections.items():
            if can_edit:
                status = record.get_section_status(section_name)
                if not status:
                    status = NirSectionStatus(
                        nir_id=record.id,
                        section_name=section_name,
                        status='PREENCHIDO',
                        filled_by_user_id=current_user.id,
                        filled_at=datetime.utcnow()
                    )
                    db.session.add(status)
                else:
                    status.status = 'PREENCHIDO'
                    status.filled_by_user_id = current_user.id
                    status.filled_at = datetime.utcnow()

        db.session.commit()
        
        allowed_sections = [name for name, can_edit in editable_sections.items() if can_edit]
        flash(f'Seções atualizadas: {", ".join(allowed_sections)}', 'success')
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

@nir_bp.route("/nir/controle-secoes")
@login_required
@require_module_access('nir')
def section_control_demo():
    """Página de demonstração do sistema de controle de seções"""
    return render_template('nir/section_control_demo.html')