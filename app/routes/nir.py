from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import db, Nir, User, NirProcedure, NirSectionStatus
from app.config_procedures import search_procedures
from app.utils.rbac_permissions import require_permission, require_module_access
from datetime import datetime

nir_bp = Blueprint('nir', __name__, template_folder='../templates')

def get_nir_phase(record):
    config = record.get_section_control_config()
    nir_sections = [s for s, sec in config.items() if sec == 'NIR']
    alta_sections = [s for s in nir_sections if 'alta' in s]
    initial_sections = [s for s in nir_sections if s not in alta_sections]

    status_map = {s.section_name: s.status for s in record.section_statuses if s.responsible_sector == 'NIR'}
    def sections_complete(lst):
        if not lst:
            return True
        return all(status_map.get(sec) == 'PREENCHIDO' for sec in lst)

    effective_entry = record.get_effective_entry_type()
    progress = record.get_sector_progress()
    surgery_progress = progress.get('CENTRO_CIRURGICO')
    surgery_complete = (surgery_progress and surgery_progress.get('status') == 'CONCLUIDO') if surgery_progress else True
    billing_progress = progress.get('FATURAMENTO', {})
    billing_complete = billing_progress.get('status') == 'CONCLUIDO'

    if effective_entry == 'URGENCIA':
        initial_complete = sections_complete(initial_sections)
        final_complete = sections_complete(alta_sections)
        if not initial_complete:
            return dict(phase='INITIAL', locked=False, waiting_for=None, show_sections=initial_sections)
        if initial_complete and not surgery_complete:
            return dict(phase='LOCKED_WAIT_SURGERY', locked=True, waiting_for='CENTRO CIRÚRGICO', show_sections=[])
        if initial_complete and surgery_complete and not final_complete:
            return dict(phase='FINAL', locked=False, waiting_for=None, show_sections=alta_sections)
        if initial_complete and surgery_complete and final_complete and not billing_complete:
            return dict(phase='LOCKED_AFTER', locked=True, waiting_for='FATURAMENTO', show_sections=[])
        return dict(phase='LOCKED_AFTER', locked=True, waiting_for=None, show_sections=[])
    else:
        all_complete = sections_complete(nir_sections)
        if not all_complete:
            return dict(phase='FULL', locked=False, waiting_for=None, show_sections=nir_sections)
        if all_complete and not billing_complete:
            return dict(phase='LOCKED_AFTER_FULL', locked=True, waiting_for='FATURAMENTO', show_sections=[])
        return dict(phase='LOCKED_AFTER_FULL', locked=True, waiting_for=None, show_sections=[])

def initialize_section_statuses(nir):
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
    per_page = request.args.get('per_page', 10, type=int)
    if per_page <= 0:
        per_page = 10
    if per_page > 100:
        per_page = 100
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
        'sector_progress': sector_progress,
        'per_page': per_page
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

@nir_bp.route("/nir/setor/novo")
@login_required
@require_permission('new_registry_nir')
def sector_new_record():
    """Formulário específico para criação de NIR pelo setor NIR"""
    user_sector = get_user_sector(current_user)
    if user_sector != 'NIR':
        flash('Acesso negado: apenas funcionários do NIR podem criar novos registros aqui', 'danger')
        return redirect(url_for('nir.my_work'))
    return render_template('nir/sector_new_record.html', user_sector=user_sector)

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
            responsible_doctor=request.form.get('responsible_doctor') if get_user_sector(current_user) == 'NIR' else None,
            main_cid=request.form.get('main_cid') if get_user_sector(current_user) == 'NIR' else None,
            sus_number=request.form.get('sus_number'),
            aih=request.form.get('aih'),
            scheduling_date=scheduling_date if get_user_sector(current_user) == 'NIR' else None,
            discharge_type=request.form.get('discharge_type') if get_user_sector(current_user) == 'NIR' else None,
            discharge_date=discharge_date if get_user_sector(current_user) == 'NIR' else None,
            total_days_admitted=total_days if get_user_sector(current_user) == 'NIR' else None,
            cancelled='NAO',
            cancellation_reason=None,
            criticized=None,
            billed='NAO',
            status='PENDENTE',
            observation=request.form.get('observation'),
            surgical_specialty=None,
            auxiliary=None,
            anesthetist=None,
            anesthesia=None,
            pediatrics=None,
            surgical_type=None,
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

        try:
            user_sector_created = get_user_sector(current_user)
            if user_sector_created == 'NIR':
                config_sections = new_nir.get_section_control_config()
                if new_nir.patient_name and new_nir.birth_date and new_nir.gender and new_nir.sus_number:
                    update_section_status(new_nir.id, 'dados_paciente', current_user.id)
                if new_nir.admission_date and new_nir.entry_type:
                    update_section_status(new_nir.id, 'dados_internacao_iniciais', current_user.id)
                if new_nir.entry_type == 'ELETIVO':
                    if config_sections.get('procedimentos') == 'NIR' and new_nir.procedure_code:
                        update_section_status(new_nir.id, 'procedimentos', current_user.id)
                    if config_sections.get('informacoes_medicas') == 'NIR' and new_nir.responsible_doctor:
                        update_section_status(new_nir.id, 'informacoes_medicas', current_user.id)
        except Exception:
            pass

        flash('Registro NIR criado com sucesso!', 'success')
        return redirect(url_for('nir.list_records'))

    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao criar registro: {str(e)}', 'danger')
        return redirect(url_for('nir.sector_new_record'))

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
        if user_sector == 'NIR':
            phase_info = get_nir_phase(record)
            if phase_info['locked'] or not phase_info['show_sections']:
                flash('Registro bloqueado: aguardando fase de outro setor.', 'warning')
                return redirect(url_for('nir.record_details', record_id=record.id))
            for sec in list(editable_sections.keys()):
                if sec not in phase_info['show_sections']:
                    editable_sections[sec] = False
        
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
            if 'patient_name' in request.form:
                record.patient_name = request.form.get('patient_name') or record.patient_name
                record.birth_date = birth_date or record.birth_date
                record.gender = request.form.get('gender') or record.gender
                if 'susfacil' in request.form:
                    record.susfacil = request.form.get('susfacil')
                if 'sus_number' in request.form and request.form.get('sus_number'):
                    record.sus_number = request.form.get('sus_number')

        if editable_sections.get('dados_internacao_iniciais', True):
            if any(k in request.form for k in ['admission_date','entry_type','admission_type','admitted_from_origin','aih']):
                if admission_date:
                    record.admission_date = admission_date
                    record.day = admission_date.day
                    record.month = admission_date.strftime('%B')
                if 'entry_type' in request.form and request.form.get('entry_type'):
                    record.entry_type = request.form.get('entry_type')
                if 'admission_type' in request.form:
                    record.admission_type = request.form.get('admission_type')
                if 'admitted_from_origin' in request.form:
                    record.admitted_from_origin = request.form.get('admitted_from_origin')
                if 'aih' in request.form and request.form.get('aih'):
                    record.aih = request.form.get('aih')

        if editable_sections.get('procedimentos', True):
            if any(k in request.form for k in ['procedure_codes[]','procedure_code']):
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
                    if single_code:
                        record.procedure_code = single_code
                    if single_desc:
                        record.surgical_description = single_desc
                    if single_code and single_desc:
                        record.procedures.append(NirProcedure(
                            code=single_code,
                            description=single_desc,
                            sequence=0,
                            is_primary=True
                        ))

        if editable_sections.get('informacoes_medicas', True):
            if any(k in request.form for k in ['responsible_doctor','main_cid','surgical_specialty','auxiliary','anesthetist','anesthesia','pediatrics','surgical_type']):
                if 'responsible_doctor' in request.form:
                    record.responsible_doctor = request.form.get('responsible_doctor') or record.responsible_doctor
                if 'main_cid' in request.form:
                    record.main_cid = request.form.get('main_cid') or record.main_cid
                if 'surgical_specialty' in request.form:
                    record.surgical_specialty = request.form.get('surgical_specialty') or record.surgical_specialty
                if 'auxiliary' in request.form:
                    record.auxiliary = request.form.get('auxiliary') or record.auxiliary
                if 'anesthetist' in request.form:
                    record.anesthetist = request.form.get('anesthetist') or record.anesthetist
                if 'anesthesia' in request.form:
                    record.anesthesia = request.form.get('anesthesia') or record.anesthesia
                if 'pediatrics' in request.form:
                    record.pediatrics = request.form.get('pediatrics') or record.pediatrics
                if 'surgical_type' in request.form:
                    record.surgical_type = request.form.get('surgical_type') or record.surgical_type

        if editable_sections.get('dados_alta_finais', True):
            if 'scheduling_date' in request.form and scheduling_date:
                record.scheduling_date = scheduling_date
            discharge_type_form = request.form.get('discharge_type')
            record.discharge_type = discharge_type_form
            record.discharge_date = discharge_date
            if discharge_date:
                admission_for_calc = admission_date or record.admission_date
                if admission_for_calc:
                    record.total_days_admitted = (discharge_date - admission_for_calc).days
            aih_final = request.form.get('aih_final')
            if aih_final:
                record.aih = aih_final

        if editable_sections.get('status_controle', True):
            record.cancelled = request.form.get('cancelled') or 'NAO'
            record.cancellation_reason = request.form.get('cancellation_reason')
            def norm_bool(value):
                if not value:
                    return None
                value_up = value.upper()
                if value_up in ('SIM', 'NAO', 'NÃO'):
                    return 'SIM' if value_up == 'SIM' else 'NAO'
                return None
            criticized_form = norm_bool(request.form.get('criticized'))
            billed_form = norm_bool(request.form.get('billed'))
            if criticized_form is not None:
                record.criticized = criticized_form
            if billed_form is not None:
                record.billed = billed_form
            record.observation = request.form.get('observation')

        record.last_modified = datetime.utcnow()

        if editable_sections.get('dados_paciente', False):
            update_section_status(record.id, 'dados_paciente', current_user.id)
            
        if editable_sections.get('dados_internacao_iniciais', False):
            update_section_status(record.id, 'dados_internacao_iniciais', current_user.id)
            
        if editable_sections.get('procedimentos', False):
            update_section_status(record.id, 'procedimentos', current_user.id)
            
        if editable_sections.get('informacoes_medicas', False):
            update_section_status(record.id, 'informacoes_medicas', current_user.id)
            
        if editable_sections.get('dados_alta_finais', False):
            if record.discharge_date or record.discharge_type:
                update_section_status(record.id, 'dados_alta_finais', current_user.id)
            
        if editable_sections.get('status_controle', False):
            update_section_status(record.id, 'status_controle', current_user.id)

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

@nir_bp.route("/nir/meus-trabalhos")
@login_required 
@require_module_access('nir')
def my_work():
    user_sector = get_user_sector(current_user)
    
    if user_sector == 'NIR':
        return redirect(url_for('nir.sector_nir_list'))
    elif user_sector == 'CENTRO_CIRURGICO':
        return redirect(url_for('nir.sector_surgery_list'))
    elif user_sector == 'FATURAMENTO':
        return redirect(url_for('nir.sector_billing_list'))
    else:
        return redirect(url_for('nir.sector_nir_list'))

@nir_bp.route("/nir/setor/nir")
@login_required 
@require_module_access('nir')
def sector_nir_list():
    user_sector = get_user_sector(current_user)
    if user_sector != 'NIR':
        flash('Acesso negado: você não pertence ao setor NIR', 'danger')
        return redirect(url_for('nir.my_work'))
    
    filter_status = request.args.get('filter_status', '').strip().lower()
    valid_filters = {'pendente': 'PENDENTE', 'andamento': 'EM_ANDAMENTO', 'concluido': 'CONCLUIDO'}
    target_status = valid_filters.get(filter_status)
    waiting_for_param = request.args.get('waiting_for', '').strip().lower()
    valid_waiting = {'faturamento': 'FATURAMENTO', 'cirurgia': 'CENTRO CIRÚRGICO'}
    target_waiting = valid_waiting.get(waiting_for_param)
    
    query = Nir.query.order_by(Nir.creation_date.desc())
    
    patient_name = request.args.get('patient_name', '').strip()
    if patient_name:
        query = query.filter(Nir.patient_name.ilike(f'%{patient_name}%'))
    
    all_records = query.all()
    is_admin = current_user.has_permission('admin_users')
    nir_relevant_records = []
    for record in all_records:
        progress = record.get_sector_progress()
        nir_sector_progress = progress.get('NIR', {})
        entry = record.get_effective_entry_type()
        config = record.get_section_control_config()
        nir_sections = [s for s, sec in config.items() if sec == 'NIR']
        alta_sections = [s for s in nir_sections if 'alta' in s]
        initial_sections = [s for s in nir_sections if s not in alta_sections]
        status_map = {s.section_name: s.status for s in record.section_statuses if s.responsible_sector == 'NIR'}
        def sections_complete(lst):
            if not lst:
                return True
            return all(status_map.get(sec) == 'PREENCHIDO' for sec in lst)
        initial_complete = sections_complete(initial_sections)
        alta_complete = sections_complete(alta_sections)
        surgery_progress = progress.get('CENTRO_CIRURGICO')
        surgery_complete = (surgery_progress and surgery_progress.get('status') == 'CONCLUIDO') if surgery_progress else True
        include = True if is_admin else False
        if entry == 'URGENCIA':
            if not initial_complete:
                include = True
            elif initial_complete and surgery_complete and not alta_complete:
                include = True
        else:
            if nir_sector_progress.get('status') in ['PENDENTE', 'EM_ANDAMENTO']:
                include = True
        if not include and record.operator_id == current_user.id:
            include = True
        if include:
            setattr(record, '_created_by_current', record.operator_id == current_user.id)
            try:
                phase_info = get_nir_phase(record)
                setattr(record, '_nir_phase', phase_info.get('phase'))
                setattr(record, '_nir_locked', phase_info.get('locked'))
                display_status = nir_sector_progress.get('status')
                if phase_info.get('phase') == 'FINAL':
                    if not alta_complete:
                        if not record.discharge_date and not record.discharge_type:
                            display_status = 'PENDENTE'
                setattr(record, '_nir_display_status', display_status)
                setattr(record, '_nir_waiting_for', phase_info.get('waiting_for'))
            except Exception:
                setattr(record, '_nir_phase', None)
                setattr(record, '_nir_display_status', nir_sector_progress.get('status'))
                setattr(record, '_nir_waiting_for', None)
                setattr(record, '_nir_locked', False)
            nir_relevant_records.append(record)
    
    if target_status:
        filtered = []
        for r in nir_relevant_records:
            display = getattr(r, '_nir_display_status', None) or r.get_sector_progress().get('NIR', {}).get('status')
            if display == target_status:
                filtered.append(r)
        nir_relevant_records = filtered
    if target_waiting:
        filtered_wait = []
        for r in nir_relevant_records:
            waiting_val = getattr(r, '_nir_waiting_for', None)
            if waiting_val == target_waiting:
                filtered_wait.append(r)
        nir_relevant_records = filtered_wait

    total = len(nir_relevant_records)
    from types import SimpleNamespace
    records = SimpleNamespace(
        items=nir_relevant_records,
        total=total,
        pages=1,
        page=1,
        has_prev=False,
        has_next=False,
        prev_num=None,
        next_num=None
    )
    
    return render_template('nir/sector_nir_list.html', records=records, user_sector=user_sector, filter_status=filter_status, waiting_for=waiting_for_param)

@nir_bp.route("/nir/setor/centro-cirurgico")
@login_required
@require_module_access('nir') 
def sector_surgery_list():
    user_sector = get_user_sector(current_user)
    if user_sector != 'CENTRO_CIRURGICO':
        flash('Acesso negado: você não pertence ao Centro Cirúrgico', 'danger')
        return redirect(url_for('nir.my_work'))
        
    query = Nir.query.order_by(Nir.creation_date.desc())
    
    patient_name = request.args.get('patient_name', '').strip()
    if patient_name:
        query = query.filter(Nir.patient_name.ilike(f'%{patient_name}%'))
        
    all_records = query.all()
    surgery_pending_records = []
    
    for record in all_records:
        if record.is_ready_for_sector('CENTRO_CIRURGICO'):
            progress = record.get_sector_progress()
            surgery_progress = progress.get('CENTRO_CIRURGICO', {})
            
            if surgery_progress.get('status') in ['PENDENTE', 'EM_ANDAMENTO']:
                surgery_pending_records.append(record)
    
    total = len(surgery_pending_records)
    from types import SimpleNamespace
    records = SimpleNamespace(
        items=surgery_pending_records,
        total=total,
        pages=1,
        page=1,
        has_prev=False,
        has_next=False,
        prev_num=None,
        next_num=None
    )
    
    return render_template('nir/sector_surgery_list.html', records=records, user_sector=user_sector)

@nir_bp.route("/nir/setor/faturamento")
@login_required
@require_module_access('nir')
def sector_billing_list():
    user_sector = get_user_sector(current_user)
    if user_sector != 'FATURAMENTO':
        flash('Acesso negado: você não pertence ao Faturamento', 'danger')
        return redirect(url_for('nir.my_work'))
        
    query = Nir.query.order_by(Nir.creation_date.desc())
    
    patient_name = request.args.get('patient_name', '').strip()
    if patient_name:
        query = query.filter(Nir.patient_name.ilike(f'%{patient_name}%'))
        
    all_records = query.all()
    billing_pending_records = []
    
    for record in all_records:
        if record.is_ready_for_sector('FATURAMENTO'):
            progress = record.get_sector_progress()
            billing_progress = progress.get('FATURAMENTO', {})
            
            if billing_progress.get('status') in ['PENDENTE', 'EM_ANDAMENTO']:
                billing_pending_records.append(record)
    
    total = len(billing_pending_records)
    from types import SimpleNamespace
    records = SimpleNamespace(
        items=billing_pending_records,
        total=total,
        pages=1,
        page=1,
        has_prev=False,
        has_next=False,
        prev_num=None,
        next_num=None
    )
    
    return render_template('nir/sector_billing_list.html', records=records, user_sector=user_sector)

@nir_bp.route("/nir/<int:record_id>/setor/nir")
@login_required
@require_permission('editar_nir')
def sector_nir_form(record_id):
    record = Nir.query.get_or_404(record_id)
    user_sector = get_user_sector(current_user)
    
    if user_sector != 'NIR':
        flash('Acesso negado: você não pertence ao setor NIR', 'danger')
        return redirect(url_for('nir.record_details', record_id=record_id))
    section_status_map = {s.section_name: s.status for s in record.section_statuses if s.responsible_sector == 'NIR'}
    phase_info = get_nir_phase(record)
    final_phase = phase_info['phase'] == 'FINAL'
    hide_aih_initial = False
    if record.get_effective_entry_type() == 'URGENCIA' and phase_info['phase'] in ('INITIAL','LOCKED_WAIT_SURGERY'):
        hide_aih_initial = True

    config = record.get_section_control_config()
    nir_sections = [s for s, sec in config.items() if sec == 'NIR']
    alta_sections = [s for s in nir_sections if 'alta' in s]
    initial_sections = [s for s in nir_sections if s not in alta_sections]

    display_sections = []
    editable_sections = set(phase_info['show_sections']) if phase_info['show_sections'] else set()
    if phase_info['locked']:
        if phase_info['phase'] == 'LOCKED_WAIT_SURGERY':
            display_sections = initial_sections + alta_sections
        elif phase_info['phase'] in ('LOCKED_AFTER','LOCKED_AFTER_FULL'):
            display_sections = nir_sections
        else:
            display_sections = nir_sections
    else:
        display_sections = phase_info['show_sections']

    return render_template(
        'nir/forms/nir_sector_form.html',
        record=record,
        user_sector=user_sector,
        final_phase=final_phase,
        show_sections=display_sections,
        editable_sections=list(editable_sections),
        section_status_map=section_status_map,
        phase_info=phase_info,
        hide_aih_initial=hide_aih_initial
    )

@nir_bp.route("/nir/<int:record_id>/setor/centro-cirurgico")
@login_required
@require_permission('editar_nir')
def sector_surgery_form(record_id):
    record = Nir.query.get_or_404(record_id)
    user_sector = get_user_sector(current_user)
    
    if user_sector != 'CENTRO_CIRURGICO':
        flash('Acesso negado: você não pertence ao Centro Cirúrgico', 'danger')
        return redirect(url_for('nir.record_details', record_id=record_id))
    
    if not record.is_ready_for_sector('CENTRO_CIRURGICO'):
        flash('Dados iniciais do NIR ainda não finalizados. Conclua cadastro inicial no NIR antes do Centro Cirúrgico.', 'warning')
        return redirect(url_for('nir.record_details', record_id=record_id))
    
    return render_template('nir/forms/surgery_sector_form.html', record=record, user_sector=user_sector)

@nir_bp.route("/nir/<int:record_id>/setor/faturamento")
@login_required
@require_permission('editar_nir')
def sector_billing_form(record_id):
    record = Nir.query.get_or_404(record_id)
    user_sector = get_user_sector(current_user)
    
    if user_sector != 'FATURAMENTO':
        flash('Acesso negado: você não pertence ao Faturamento', 'danger')
        return redirect(url_for('nir.record_details', record_id=record_id))
    
    if not record.is_ready_for_sector('FATURAMENTO'):
        next_sector = record.get_next_available_sector()
        if next_sector == 'NIR':
            flash('Finalize também os dados de alta no NIR antes do faturamento.', 'warning')
        elif next_sector == 'CENTRO_CIRURGICO':
            flash('Aguarde a conclusão do Centro Cirúrgico antes do faturamento.', 'warning')
        else:
            flash('Este registro não está pronto para o Faturamento.', 'warning')
        return redirect(url_for('nir.record_details', record_id=record_id))
    
    return render_template('nir/forms/billing_sector_form.html', record=record, user_sector=user_sector)

@nir_bp.route('/nir/procedures/search')
@login_required
@require_module_access('nir')
def procedures_search():
    q = request.args.get('q', '').strip()
    limit = request.args.get('limit', 15, type=int)
    if limit > 50:
        limit = 50
    results = search_procedures(q, limit=limit)
    return jsonify(results)

@nir_bp.route('/nir/admin/recalibrar-alta')
@login_required
@require_permission('visualizar_relatorios')
def recalibrar_alta_sections():
    try:
        altered = 0
        nirs = Nir.query.all()
        for nir in nirs:
            section = nir.get_section_status('dados_alta_finais')
            if not section:
                continue
            if (not nir.discharge_date and not nir.discharge_type) and section.status == 'PREENCHIDO':
                section.status = 'PENDENTE'
                section.filled_by_user_id = None
                section.filled_at = None
                altered += 1
        if altered:
            db.session.commit()
            flash(f'Recalibração concluída. {altered} registros ajustados.', 'success')
        else:
            flash('Nenhum ajuste necessário.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro na recalibração: {e}', 'danger')
    return redirect(url_for('nir.list_records'))