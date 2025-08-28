
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date
from app.models import db, NIRRecord, User
from sqlalchemy import or_, and_, desc

nir_bp = Blueprint('nir', __name__, url_prefix='/nir')

@nir_bp.route('/')
@login_required
def index():
    return redirect(url_for('nir.list_records'))

@nir_bp.route('/novo')
@login_required
def new_record():
    return render_template('nir/new_record.html')

@nir_bp.route('/criar', methods=['POST'])
@login_required
def create_record():
    try:
        birth_date = None
        if request.form.get('birth_date'):
            try:
                birth_date = datetime.strptime(request.form.get('birth_date'), '%Y-%m-%d').date()
            except ValueError:
                pass
        
        admission_date = datetime.strptime(request.form.get('admission_date'), '%Y-%m-%d').date()
        
        scheduling_date = None
        if request.form.get('scheduling_date'):
            try:
                scheduling_date = datetime.strptime(request.form.get('scheduling_date'), '%Y-%m-%d').date()
            except ValueError:
                pass
                
        discharge_date = None
        if request.form.get('discharge_date'):
            try:
                discharge_date = datetime.strptime(request.form.get('discharge_date'), '%Y-%m-%d').date()
            except ValueError:
                pass

        total_days = None
        if admission_date and discharge_date:
            total_days = (discharge_date - admission_date).days

        record = NIRRecord(
            patient_name=request.form.get('patient_name'),
            birth_date=birth_date,
            gender=request.form.get('gender'),
            susfacil=request.form.get('susfacil'),
            
            admission_date=admission_date,
            entry_type=request.form.get('entry_type'),
            admission_type=request.form.get('admission_type'),
            admitted_from_origin=request.form.get('admitted_from_origin'),
            
            procedure_code=request.form.get('procedure_code'),
            surgical_description=request.form.get('surgical_description'),
            
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
            month=admission_date.strftime('%B').upper() if admission_date else None,
            operator_id=current_user.id
        )
        
        db.session.add(record)
        db.session.commit()
        
        flash('Registro NIR criado com sucesso!', 'success')
        return redirect(url_for('nir.list_records'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao criar registro: {str(e)}', 'danger')
        return redirect(url_for('nir.new_record'))

@nir_bp.route('/registros')
@login_required
def list_records():
    page = request.args.get('page', 1, type=int)
    per_page = 15
    
    patient_name = request.args.get('patient_name', '')
    entry_type = request.args.get('entry_type', '')
    admission_type = request.args.get('admission_type', '')
    discharge_type = request.args.get('discharge_type', '')
    responsible_doctor = request.args.get('responsible_doctor', '')
    month_filter = request.args.get('month_filter', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    query = NIRRecord.query
    
    if patient_name:
        query = query.filter(NIRRecord.patient_name.ilike(f'%{patient_name}%'))
    
    if entry_type:
        query = query.filter(NIRRecord.entry_type == entry_type)
        
    if admission_type:
        query = query.filter(NIRRecord.admission_type == admission_type)
        
    if discharge_type:
        query = query.filter(NIRRecord.discharge_type == discharge_type)
        
    if responsible_doctor:
        query = query.filter(NIRRecord.responsible_doctor.ilike(f'%{responsible_doctor}%'))
        
    if month_filter:
        query = query.filter(NIRRecord.month == month_filter.upper())
        
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(NIRRecord.admission_date >= start_date_obj)
        except ValueError:
            pass
            
    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(NIRRecord.admission_date <= end_date_obj)
        except ValueError:
            pass
    
    query = query.order_by(desc(NIRRecord.creation_date))
    
    records = query.paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    entry_types = db.session.query(NIRRecord.entry_type).distinct().filter(NIRRecord.entry_type.isnot(None)).all()
    admission_types = db.session.query(NIRRecord.admission_type).distinct().filter(NIRRecord.admission_type.isnot(None)).all()
    discharge_types = db.session.query(NIRRecord.discharge_type).distinct().filter(NIRRecord.discharge_type.isnot(None)).all()
    doctors = db.session.query(NIRRecord.responsible_doctor).distinct().filter(NIRRecord.responsible_doctor.isnot(None)).all()
    months = db.session.query(NIRRecord.month).distinct().filter(NIRRecord.month.isnot(None)).all()
    
    return render_template('nir/list_records.html', 
                         records=records,
                         entry_types=[et[0] for et in entry_types],
                         admission_types=[at[0] for at in admission_types],
                         discharge_types=[dt[0] for dt in discharge_types],
                         doctors=[d[0] for d in doctors],
                         months=[m[0] for m in months],
                         filters={
                             'patient_name': patient_name,
                             'entry_type': entry_type,
                             'admission_type': admission_type,
                             'discharge_type': discharge_type,
                             'responsible_doctor': responsible_doctor,
                             'month_filter': month_filter,
                             'start_date': start_date,
                             'end_date': end_date
                         })

@nir_bp.route('/detalhes/<int:record_id>')
@login_required
def record_details(record_id):
    record = NIRRecord.query.get_or_404(record_id)
    return render_template('nir/record_details.html', record=record)

@nir_bp.route('/editar/<int:record_id>')
@login_required
def edit_record(record_id):
    record = NIRRecord.query.get_or_404(record_id)
    return render_template('nir/edit_record.html', record=record)

@nir_bp.route('/atualizar/<int:record_id>', methods=['POST'])
@login_required
def update_record(record_id):
    try:
        record = NIRRecord.query.get_or_404(record_id)
        
        birth_date = None
        if request.form.get('birth_date'):
            try:
                birth_date = datetime.strptime(request.form.get('birth_date'), '%Y-%m-%d').date()
            except ValueError:
                pass
        
        admission_date = datetime.strptime(request.form.get('admission_date'), '%Y-%m-%d').date()
        
        scheduling_date = None
        if request.form.get('scheduling_date'):
            try:
                scheduling_date = datetime.strptime(request.form.get('scheduling_date'), '%Y-%m-%d').date()
            except ValueError:
                pass
                
        discharge_date = None
        if request.form.get('discharge_date'):
            try:
                discharge_date = datetime.strptime(request.form.get('discharge_date'), '%Y-%m-%d').date()
            except ValueError:
                pass

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
        record.procedure_code = request.form.get('procedure_code')
        record.surgical_description = request.form.get('surgical_description')
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
        record.month = admission_date.strftime('%B').upper() if admission_date else None

        db.session.commit()
        
        flash('Registro NIR atualizado com sucesso!', 'success')
        return redirect(url_for('nir.record_details', record_id=record.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao atualizar registro: {str(e)}', 'danger')
        return redirect(url_for('nir.edit_record', record_id=record_id))

@nir_bp.route('/excluir/<int:record_id>', methods=['POST'])
@login_required
def delete_record(record_id):
    try:
        record = NIRRecord.query.get_or_404(record_id)
        db.session.delete(record)
        db.session.commit()
        
        flash('Registro NIR excluído com sucesso!', 'success')
        return redirect(url_for('nir.list_records'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir registro: {str(e)}', 'danger')
        return redirect(url_for('nir.list_records'))
