"""
Rotas para gerenciamento de Fornecedores/Prestadores e suas Avaliações
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from app.models import db, Supplier, SupplierEvaluation, User, SupplierIssueTracking
from datetime import datetime, date
from calendar import monthrange
from sqlalchemy import func, desc
from app.utils.rbac_permissions import require_permission
import mimetypes

suppliers_bp = Blueprint('suppliers', __name__, url_prefix='/feedback/suppliers')


FOLLOW_UP_ACTION_MAP = {
    'opened': 'open',
    'reopened': 'open',
    'escalated': 'open',
    'contact': 'in_progress',
    'follow_up': 'in_progress',
    'note': 'in_progress',
    'resolved': 'resolved'
}


def _collect_non_conformities(evaluation: SupplierEvaluation) -> list:
    issues = []
    if not evaluation.had_service_last_month:
        issues.append('Sem registro de fornecimento ou prestação no mês avaliado.')

    criteria = [
        ('contract_compliance', 'Conformidade com contrato'),
        ('equipment_adequacy', 'Adequação de equipamentos'),
        ('invoice_validation', 'Validação de faturamento'),
        ('service_timeliness', 'Prazo de atendimento'),
        ('quantity_description_compliance', 'Quantitativo/descrição do contrato'),
        ('support_quality', 'Qualidade do suporte/documentação')
    ]

    for field, label in criteria:
        value = getattr(evaluation, field)
        if value == 'nao_conforme':
            issues.append(f'{label} marcada como NÃO CONFORME.')

    if evaluation.overall_rating < 7:
        issues.append(f'Nota final {evaluation.overall_rating}/10 abaixo do mínimo aceitável (7).')

    if not issues:
        issues.append('Avaliação marcada como não conforme mesmo sem detalhes adicionais. Revisar justificativas.')

    return issues


def _register_initial_follow_up(evaluation: SupplierEvaluation, user_id: int):
    if evaluation.is_compliant:
        evaluation.follow_up_status = 'not_required'
        evaluation.follow_up_closed_at = None
        return

    evaluation.follow_up_status = 'open'
    evaluation.follow_up_closed_at = None

    summary_lines = [
        f'Avaliação {evaluation.month_reference or "sem referência"} registrada como NÃO CONFORME.',
        'Principais apontamentos:'
    ]
    for item in _collect_non_conformities(evaluation):
        summary_lines.append(f'- {item}')

    tracking = SupplierIssueTracking(
        supplier_id=evaluation.supplier_id,
        evaluation_id=evaluation.id,
        user_id=user_id,
        action_type='opened',
        description='\n'.join(summary_lines)
    )
    db.session.add(tracking)


def _update_follow_up_status(evaluation: SupplierEvaluation, action_type: str):
    if not evaluation:
        return

    new_status = FOLLOW_UP_ACTION_MAP.get(action_type)
    if not new_status:
        return

    if new_status == 'resolved':
        evaluation.follow_up_status = 'resolved'
        evaluation.follow_up_closed_at = datetime.utcnow()
    else:
        evaluation.follow_up_status = new_status
        evaluation.follow_up_closed_at = None


# ============================================
# DASHBOARD E RELATÓRIOS
# ============================================

@suppliers_bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard principal com rankings e estatísticas"""
    # Filtro por mês (opcional)
    month = request.args.get('month')
    
    # Se não foi especificado um mês, usar o último mês com avaliações
    if not month:
        latest = db.session.query(func.max(SupplierEvaluation.month_reference)).scalar()
        month = latest
    
    # Buscar todos os fornecedores ativos
    suppliers = Supplier.query.filter_by(is_active=True).all()
    
    # Calcular scores médios e ordenar
    suppliers_data = []
    for supplier in suppliers:
        # Se há filtro de mês, calcular score apenas para esse mês
        if month:
            month_evals = [e for e in supplier.evaluations.all() 
                         if e.month_reference == month and e.had_service_last_month]
            if month_evals:
                avg_score = round(sum(e.total_score for e in month_evals) / len(month_evals), 2)
                eval_count = len(month_evals)
                last_eval = max(month_evals, key=lambda e: e.evaluation_date)
                last_eval_date = last_eval.evaluation_date
            else:
                # Verificar se há avaliação sem serviço nesse mês
                no_service_evals = [e for e in supplier.evaluations.all() 
                                   if e.month_reference == month and not e.had_service_last_month]
                if no_service_evals:
                    avg_score = 0
                    eval_count = 0  # Não conta como avaliação com score
                    last_eval = no_service_evals[0]
                    last_eval_date = last_eval.evaluation_date
                else:
                    avg_score = 0
                    eval_count = 0
                    last_eval = None
                    last_eval_date = None
        else:
            avg_score = supplier.get_average_score()
            eval_count = supplier.get_evaluations_count()
            last_eval_date = supplier.get_last_evaluation_date()
            last_eval = supplier.evaluations.order_by(
                desc(SupplierEvaluation.evaluation_date)
            ).first() if eval_count > 0 else None
        
        # Determinar se precisa de atenção (apenas para score baixo, não para "sem serviço")
        needs_attention = False
        has_low_score = avg_score < 60 and eval_count > 0
        no_service_last_month = last_eval and not last_eval.had_service_last_month
        
        if has_low_score:
            needs_attention = True

        failing_eval = None
        if needs_attention and eval_count > 0:
            if month:
                failing_evals = [e for e in supplier.evaluations.all() 
                                if e.month_reference == month and e.total_score < 60]
                failing_eval = failing_evals[0] if failing_evals else last_eval
            else:
                failing_eval = supplier.evaluations.filter(
                    SupplierEvaluation.total_score < 60
                ).order_by(desc(SupplierEvaluation.evaluation_date)).first()
                if not failing_eval:
                    failing_eval = last_eval
        
        # Calcular prioridade para ordenação
        if has_low_score and not supplier.issue_verified:
            priority = 1  # Insatisfatório não verificado
        elif eval_count > 0 and avg_score >= 80:
            priority = 2  # Excelente
        elif eval_count > 0 and avg_score >= 60:
            priority = 3  # Satisfatório (60-79%)
        elif no_service_last_month:
            priority = 4  # Sem serviço no último mês
        elif has_low_score and supplier.issue_verified:
            priority = 5  # Problemas JÁ verificados
        elif eval_count == 0:
            priority = 6  # Não avaliado
        else:
            priority = 7  # Casos não cobertos (fallback)
        
        suppliers_data.append({
            'supplier': supplier,
            'avg_score': avg_score,
            'eval_count': eval_count,
            'last_eval_date': last_eval_date,
            'last_eval': last_eval,
            'needs_attention': needs_attention,
            'has_low_score': has_low_score,
            'no_service_last_month': no_service_last_month,
            'priority': priority,
            'failing_eval': failing_eval
        })
    
    # Ordenar por prioridade (menor número = maior prioridade) e depois por score (decrescente)
    suppliers_data.sort(key=lambda x: (x['priority'], -x['avg_score']))
    
    # Estatísticas gerais
    total_suppliers = len(suppliers)
    if month:
        total_evaluations = SupplierEvaluation.query.filter_by(month_reference=month).count()
    else:
        total_evaluations = SupplierEvaluation.query.count()
    
    # Fornecedores com problemas (apenas score < 60%)
    problematic_suppliers = [s for s in suppliers_data if s['has_low_score']]
    
    # Melhores fornecedores (top 5)
    top_suppliers_filtered = [
        s for s in suppliers_data 
        if s['eval_count'] > 0 
        and s['avg_score'] >= 60
    ]
    top_suppliers = sorted(top_suppliers_filtered, key=lambda x: x['avg_score'], reverse=True)[:5]
    
    # Piores fornecedores (score < 60% e que foram avaliados)
    worst_suppliers = [s for s in suppliers_data if s['avg_score'] < 60 and s['eval_count'] > 0]
    
    return render_template('feedback/suppliers/dashboard.html',
                         suppliers_data=suppliers_data,
                         total_suppliers=total_suppliers,
                         total_evaluations=total_evaluations,
                         problematic_count=len(problematic_suppliers),
                         top_suppliers=top_suppliers,
                         worst_suppliers=worst_suppliers,
                         month=month)


# ============================================
# GERENCIAMENTO DE FORNECEDORES (CRUD)
# ============================================

@suppliers_bp.route('/list')
@login_required
@require_permission('visualizar-fornecedores')
def supplier_list():
    """Lista todos os fornecedores cadastrados"""
    suppliers = Supplier.query.order_by(Supplier.company_name).all()
    
    suppliers_info = []
    for supplier in suppliers:
        suppliers_info.append({
            'supplier': supplier,
            'avg_score': supplier.get_average_score(),
            'eval_count': supplier.get_evaluations_count(),
            'last_eval': supplier.get_last_evaluation_date()
        })
    
    # Buscar todos os usuários ativos para atribuição
    all_users = User.query.filter_by(is_active=True).order_by(User.name).all()
    
    return render_template('feedback/suppliers/supplier_list.html',
                         suppliers_info=suppliers_info,
                         all_users=all_users)


@suppliers_bp.route('/register', methods=['GET', 'POST'])
@login_required
@require_permission('criar-fornecedor')
def register_supplier():
    """Cadastra um novo fornecedor"""
    if request.method == 'POST':
        company_name = request.form.get('company_name')
        trade_name = request.form.get('trade_name')  # Nome fantasia
        cnpj = request.form.get('cnpj')
        contact_name = request.form.get('contact_name')
        phone = request.form.get('phone')
        email = request.form.get('email')
        service_type = request.form.get('service_type')
        notes = request.form.get('notes')
        
        # Validação
        if not company_name:
            flash('O nome da empresa é obrigatório!', 'danger')
            return redirect(url_for('suppliers.supplier_list'))
        
        # Verificar se já existe
        existing = Supplier.query.filter_by(company_name=company_name).first()
        if existing:
            flash('Já existe um fornecedor com este nome!', 'warning')
            return redirect(url_for('suppliers.supplier_list'))
        
        # Criar novo fornecedor
        new_supplier = Supplier(
            company_name=company_name,
            trade_name=trade_name if trade_name else None,
            cnpj=cnpj,
            contact_name=contact_name,
            phone=phone,
            email=email,
            service_type=service_type,
            notes=notes,
            created_by_id=current_user.id
        )
        
        try:
            db.session.add(new_supplier)
            db.session.flush()  # get id before commit to save files

            # Processar uploads de documentos (campo 'documents')
            uploaded_files = request.files.getlist('documents')
            attachments = []
            if uploaded_files:
                import os
                from werkzeug.utils import secure_filename
                from flask import current_app

                # Diretório: uploads/fornecedores/{supplier_id}
                upload_folder = os.path.join('/app/uploads/fornecedores', str(new_supplier.id))
                os.makedirs(upload_folder, exist_ok=True)

                for file in uploaded_files:
                    if file and file.filename:
                        # Validar tipo e tamanho (<= 500MB)
                        file.seek(0, os.SEEK_END)
                        file_size = file.tell()
                        file.seek(0)

                        # Aceitar apenas PDF
                        allowed = (file.mimetype == 'application/pdf') or file.filename.lower().endswith('.pdf')
                        if not allowed:
                            # Ignorar arquivo não-PDF
                            continue

                        if file_size > 500 * 1024 * 1024:
                            # Ignorar arquivos muito grandes
                            continue

                        filename = secure_filename(file.filename)
                        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                        unique_filename = f"{timestamp}_{filename}"
                        file_path = os.path.join(upload_folder, unique_filename)
                        file.save(file_path)

                        attachments.append({
                            'filename': filename,
                            'stored_filename': unique_filename,
                            'path': file_path,
                            'size': file_size,
                            'uploaded_at': datetime.utcnow().isoformat()
                        })

                # Salvar metadados em arquivo JSON no diretório do fornecedor
                if attachments:
                    import json
                    meta_path = os.path.join(upload_folder, 'attachments.json')
                    try:
                        with open(meta_path, 'w', encoding='utf-8') as mf:
                            json.dump(attachments, mf, ensure_ascii=False, indent=2)
                    except Exception:
                        # Não impedir cadastro se não conseguir gravar metadados
                        pass

            db.session.commit()
            display_name = trade_name if trade_name else company_name
            flash(f'Fornecedor "{display_name}" cadastrado com sucesso!', 'success')
            return redirect(url_for('suppliers.supplier_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar fornecedor: {str(e)}', 'danger')
            return redirect(url_for('suppliers.supplier_list'))
    
    # Se for GET, redireciona para a lista (modal abrirá lá)
    return redirect(url_for('suppliers.supplier_list'))


@suppliers_bp.route('/edit/<int:supplier_id>', methods=['GET', 'POST'])
@login_required
@require_permission('editar-fornecedor')
def edit_supplier(supplier_id):
    """Edita um fornecedor existente"""
    supplier = Supplier.query.get_or_404(supplier_id)
    
    if request.method == 'POST':
        supplier.company_name = request.form.get('company_name')
        supplier.trade_name = request.form.get('trade_name')
        supplier.cnpj = request.form.get('cnpj')
        supplier.contact_name = request.form.get('contact_name')
        supplier.phone = request.form.get('phone')
        supplier.email = request.form.get('email')
        supplier.service_type = request.form.get('service_type')
        supplier.notes = request.form.get('notes')
        
        # Atualizar avaliadores se o usuário tiver permissão
        if current_user.has_permission('assign-supplier-evaluators') or current_user.has_permission('admin-total'):
            evaluator_ids = request.form.getlist('evaluator_ids')
            
            # Limpar avaliadores atuais
            supplier.assigned_evaluators.clear()
            
            # Adicionar novos avaliadores
            for user_id in evaluator_ids:
                user = User.query.get(int(user_id))
                if user:
                    supplier.assigned_evaluators.append(user)
        
        try:
            db.session.commit()
            flash('Fornecedor atualizado com sucesso!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar fornecedor: {str(e)}', 'danger')
    
    return redirect(url_for('suppliers.supplier_list'))


@suppliers_bp.route('/delete/<int:supplier_id>', methods=['POST'])
@login_required
@require_permission('excluir-fornecedor')
def delete_supplier(supplier_id):
    """Desativa um fornecedor (soft delete)"""
    supplier = Supplier.query.get_or_404(supplier_id)
    supplier.is_active = False
    
    try:
        db.session.commit()
        flash(f'Fornecedor "{supplier.company_name}" desativado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao desativar fornecedor: {str(e)}', 'danger')
    
    return redirect(url_for('suppliers.supplier_list'))


# ============================================
# AVALIAÇÕES DE FORNECEDORES
# ============================================

@suppliers_bp.route('/evaluate', methods=['GET', 'POST'])
@login_required
@require_permission('avaliar-fornecedor')
def evaluate_supplier():
    """Formulário para avaliar um fornecedor"""
    if request.method == 'POST':
        supplier_id = request.form.get('supplier_id')
        month_reference = request.form.get('month_reference')
        
        # Verificar se o usuário tem permissão para avaliar este fornecedor
        supplier = Supplier.query.get_or_404(supplier_id)
        
        # Se o usuário tem fornecedores atribuídos, verificar se este está na lista
        if current_user.assigned_suppliers.count() > 0:
            if supplier not in current_user.assigned_suppliers.all():
                flash('Você não tem permissão para avaliar este fornecedor!', 'danger')
                return redirect(url_for('suppliers.evaluate_supplier'))
        
        # Verificar se já existe avaliação para este mês
        existing = SupplierEvaluation.query.filter_by(
            supplier_id=supplier_id,
            evaluator_id=current_user.id,
            month_reference=month_reference
        ).first()
        
        if existing:
            flash('Você já avaliou este fornecedor neste mês!', 'warning')
            return redirect(url_for('suppliers.evaluate_supplier'))
        
        # Coletar respostas do formulário
        had_service = request.form.get('had_service_last_month') == 'true'
        
        # Validar campos obrigatórios da seção "Critérios de Avaliação"
        required_fields = [
            ('contract_compliance', 'Conformidade com Contrato'),
            ('contract_compliance_justification', 'Justificativa - Conformidade com Contrato'),
            ('equipment_adequacy', 'Equipamento'),
            ('equipment_adequacy_justification', 'Justificativa - Equipamento'),
            ('invoice_validation', 'Validação de Faturamento'),
            ('invoice_validation_justification', 'Justificativa - Validação de Faturamento'),
            ('service_timeliness', 'Prazo de Atendimento'),
            ('service_timeliness_justification', 'Justificativa - Prazo de Atendimento'),
            ('quantity_description_compliance', 'Quantitativo'),
            ('quantity_description_justification', 'Justificativa - Quantitativo'),
            ('support_quality', 'Suporte'),
            ('support_quality_justification', 'Justificativa - Suporte'),
            ('rating_justification', 'Justificativa da Nota Final')
        ]
        
        # Verificar se todos os campos obrigatórios foram preenchidos
        for field_name, field_label in required_fields:
            field_value = request.form.get(field_name)
            if not field_value or (isinstance(field_value, str) and not field_value.strip()):
                flash(f'Campo obrigatório não preenchido: {field_label}', 'danger')
                return redirect(url_for('suppliers.evaluate_supplier'))
        
        evaluation = SupplierEvaluation(
            supplier_id=supplier_id,
            evaluator_id=current_user.id,
            month_reference=month_reference,
            had_service_last_month=had_service,
            service_justification=request.form.get('service_justification'),
            contract_compliance=request.form.get('contract_compliance'),
            contract_compliance_justification=request.form.get('contract_compliance_justification'),
            equipment_adequacy=request.form.get('equipment_adequacy'),
            equipment_adequacy_justification=request.form.get('equipment_adequacy_justification'),
            invoice_validation=request.form.get('invoice_validation'),
            invoice_validation_justification=request.form.get('invoice_validation_justification'),
            service_timeliness=request.form.get('service_timeliness'),
            service_timeliness_justification=request.form.get('service_timeliness_justification'),
            quantity_description_compliance=request.form.get('quantity_description_compliance'),
            quantity_description_justification=request.form.get('quantity_description_justification'),
            support_quality=request.form.get('support_quality'),
            support_quality_justification=request.form.get('support_quality_justification'),
            overall_rating=int(request.form.get('overall_rating', 0)),
            rating_justification=request.form.get('rating_justification'),
            general_observations=request.form.get('general_observations')
        )
        
        # Calcular score
        evaluation.total_score = evaluation.calculate_score()
        # O método calculate_score() já define is_compliant internamente
        
        try:
            db.session.add(evaluation)
            db.session.flush()
            _register_initial_follow_up(evaluation, current_user.id)
            db.session.commit()
            flash(f'Avaliação registrada com sucesso! Score: {evaluation.total_score}%', 'success')
            return redirect(url_for('suppliers.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao registrar avaliação: {str(e)}', 'danger')
    
    # GET - Carregar fornecedores ativos
    # Se o usuário tem fornecedores atribuídos, mostrar apenas esses
    # Se não tem nenhum atribuído, mostrar todos (para compatibilidade com usuários antigos)
    if current_user.assigned_suppliers.count() > 0:
        suppliers = current_user.assigned_suppliers.filter_by(is_active=True).order_by(Supplier.company_name).all()
    else:
        suppliers = Supplier.query.filter_by(is_active=True).order_by(Supplier.company_name).all()

    # Calcular o mês de referência (mês anterior)
    current_date = datetime.now()
    if current_date.month == 1:
        previous_month = current_date.replace(year=current_date.year - 1, month=12)
    else:
        previous_month = current_date.replace(month=current_date.month - 1)
    current_month = previous_month.strftime('%Y-%m')

    # Filtrar fornecedores que já foram avaliados pelo usuário atual no mês de referência
    evaluated_supplier_ids = set()
    existing_evaluations = SupplierEvaluation.query.filter_by(
        evaluator_id=current_user.id,
        month_reference=current_month
    ).all()
    
    for evaluation in existing_evaluations:
        evaluated_supplier_ids.add(evaluation.supplier_id)
    
    # Remover fornecedores já avaliados da lista
    suppliers = [s for s in suppliers if s.id not in evaluated_supplier_ids]

    # Convert Supplier objects to dicts for JSON serialization
    suppliers_json = [
        {
            "id": s.id,
            "name": s.company_name,
            "type": s.service_type or ""
        }
        for s in suppliers
    ]

    return render_template('feedback/suppliers/supplier_evaluation.html',
                         suppliers=suppliers_json,
                         current_month=current_month)


@suppliers_bp.route('/evaluations/<int:supplier_id>')
@login_required
@require_permission('visualizar-fornecedores')
def supplier_evaluations(supplier_id):
    """Lista todas as avaliações de um fornecedor"""
    supplier = Supplier.query.get_or_404(supplier_id)
    evaluations = supplier.evaluations.order_by(desc(SupplierEvaluation.evaluation_date)).all()
    
    avg_score = supplier.get_average_score()
    
    # Calcular média de notas (overall_rating)
    if evaluations:
        avg_rating = sum(e.overall_rating for e in evaluations) / len(evaluations)
    else:
        avg_rating = 0
    
    # Carregar anexos salvos em disco (uploads/fornecedores/{supplier_id}/attachments.json)
    attachments = []
    try:
        import os, json
        from flask import current_app, url_for

        upload_folder = os.path.join('/app/uploads/fornecedores', str(supplier.id))
        meta_path = os.path.join(upload_folder, 'attachments.json')
        if os.path.exists(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as mf:
                attachments = json.load(mf)
            # Gerar URL de visualização para cada anexo
            for att in attachments:
                att['url'] = url_for('suppliers.download_supplier_document', supplier_id=supplier.id, filename=att.get('stored_filename'))
    except Exception:
        attachments = []

    return render_template('feedback/suppliers/supplier_evaluations.html',
                         supplier=supplier,
                         evaluations=evaluations,
                         avg_score=avg_score,
                         avg_rating=avg_rating,
                         attachments=attachments)


@suppliers_bp.route('/evaluation/details/<int:evaluation_id>')
@login_required
def evaluation_details(evaluation_id):
    """Detalhes de uma avaliação específica"""
    evaluation = SupplierEvaluation.query.get_or_404(evaluation_id)
    
    return render_template('feedback/suppliers/evaluation_details.html',
                         evaluation=evaluation)


@suppliers_bp.route('/download-supplier-doc/<int:supplier_id>/<filename>')
@login_required
@require_permission('visualizar-fornecedores')
def download_supplier_document(supplier_id, filename):
    """Serve um documento (PDF/contrato) cadastrado para um fornecedor."""
    import os, json
    from flask import current_app, flash, redirect, url_for

    supplier = Supplier.query.get_or_404(supplier_id)

    upload_folder = os.path.join('/app/uploads/fornecedores', str(supplier.id))
    meta_path = os.path.join(upload_folder, 'attachments.json')

    attachment = None
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as mf:
                attachments = json.load(mf)
                attachment = next((att for att in attachments if att.get('stored_filename') == filename), None)
        except Exception:
            attachment = None

    if not attachment:
        flash('Anexo não encontrado', 'danger')
        return redirect(url_for('suppliers.supplier_evaluations', supplier_id=supplier_id))

    file_path = os.path.join(upload_folder, attachment.get('stored_filename'))
    if not os.path.exists(file_path):
        flash('Arquivo não encontrado no servidor', 'danger')
        return redirect(url_for('suppliers.supplier_evaluations', supplier_id=supplier_id))

    mimetype = mimetypes.guess_type(attachment.get('filename'))[0] or 'application/octet-stream'

    # Enviar para visualização no navegador (não forçar download)
    return send_file(
        file_path,
        mimetype=mimetype,
        as_attachment=False,
        download_name=attachment.get('filename')
    )


@suppliers_bp.route('/upload-supplier-doc/<int:supplier_id>', methods=['POST'])
@login_required
@require_permission('editar-fornecedor')
def upload_supplier_document(supplier_id):
    """Carrega novos documentos (PDF) para um fornecedor existente.
    Form expects `documents` file input (multiple allowed).
    """
    supplier = Supplier.query.get_or_404(supplier_id)
    uploaded_files = request.files.getlist('documents')
    if not uploaded_files:
        flash('Nenhum arquivo selecionado para upload.', 'warning')
        return redirect(url_for('suppliers.supplier_evaluations', supplier_id=supplier_id))

    import os, json
    from werkzeug.utils import secure_filename
    from flask import current_app

    upload_folder = os.path.join('/app/uploads/fornecedores', str(supplier.id))
    os.makedirs(upload_folder, exist_ok=True)

    attachments = []
    meta_path = os.path.join(upload_folder, 'attachments.json')
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as mf:
                attachments = json.load(mf)
        except Exception:
            attachments = []

    saved = 0
    for file in uploaded_files:
        if file and file.filename:
            # Validate PDF and size
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)

            allowed = (file.mimetype == 'application/pdf') or file.filename.lower().endswith('.pdf')
            if not allowed:
                continue
            if file_size > 500 * 1024 * 1024:
                continue

            filename = secure_filename(file.filename)
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            unique_filename = f"{timestamp}_{filename}"
            file_path = os.path.join(upload_folder, unique_filename)
            try:
                file.save(file_path)
            except Exception:
                continue

            attachments.append({
                'filename': filename,
                'stored_filename': unique_filename,
                'path': file_path,
                'size': file_size,
                'uploaded_at': datetime.utcnow().isoformat()
            })
            saved += 1

    # Save metadata
    try:
        with open(meta_path, 'w', encoding='utf-8') as mf:
            json.dump(attachments, mf, ensure_ascii=False, indent=2)
    except Exception:
        pass

    if saved > 0:
        flash(f'{saved} arquivo(s) enviados com sucesso.', 'success')
    else:
        flash('Nenhum arquivo válido enviado (apenas PDF até 500MB).', 'warning')

    return redirect(url_for('suppliers.supplier_evaluations', supplier_id=supplier_id))


@suppliers_bp.route('/delete-supplier-doc/<int:supplier_id>', methods=['POST'])
@login_required
@require_permission('editar-fornecedor')
def delete_supplier_document(supplier_id):
    """Remove um documento do fornecedor (apaga arquivo e atualiza attachments.json).
    Espera um campo form `stored_filename` com o nome armazenado.
    """
    supplier = Supplier.query.get_or_404(supplier_id)
    stored = request.form.get('stored_filename')
    if not stored:
        flash('Arquivo inválido para remoção.', 'danger')
        return redirect(url_for('suppliers.supplier_evaluations', supplier_id=supplier_id))

    import os, json
    from flask import current_app

    upload_folder = os.path.join('/app/uploads/fornecedores', str(supplier.id))
    meta_path = os.path.join(upload_folder, 'attachments.json')

    attachments = []
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as mf:
                attachments = json.load(mf)
        except Exception:
            attachments = []

    removed = False
    new_attachments = []
    for att in attachments:
        if att.get('stored_filename') == stored:
            # remove file from disk
            try:
                fp = os.path.join(upload_folder, att.get('stored_filename'))
                if os.path.exists(fp):
                    os.remove(fp)
                removed = True
            except Exception:
                # ignore file deletion errors
                pass
        else:
            new_attachments.append(att)

    # write updated metadata
    try:
        with open(meta_path, 'w', encoding='utf-8') as mf:
            json.dump(new_attachments, mf, ensure_ascii=False, indent=2)
    except Exception:
        pass

    if removed:
        flash('Arquivo removido com sucesso.', 'success')
    else:
        flash('Arquivo não encontrado.', 'warning')

    return redirect(url_for('suppliers.supplier_evaluations', supplier_id=supplier_id))


# ============================================
# API ENDPOINTS (JSON)
# ============================================

@suppliers_bp.route('/api/suppliers')
@login_required
def api_suppliers_list():
    """Retorna lista de fornecedores em JSON"""
    suppliers = Supplier.query.filter_by(is_active=True).all()
    
    return jsonify([{
        'id': s.id,
        'company_name': s.company_name,
        'service_type': s.service_type,
        'avg_score': s.get_average_score()
    } for s in suppliers])


@suppliers_bp.route('/api/supplier/<int:supplier_id>/stats')
@login_required
def api_supplier_stats(supplier_id):
    """Retorna estatísticas de um fornecedor em JSON"""
    supplier = Supplier.query.get_or_404(supplier_id)
    
    evaluations = supplier.evaluations.all()
    
    # Calcular médias
    scores = [e.total_score for e in evaluations]
    ratings = [e.overall_rating for e in evaluations]
    
    return jsonify({
        'id': supplier.id,
        'company_name': supplier.company_name,
        'trade_name': supplier.trade_name,
        'cnpj': supplier.cnpj,
        'contact_name': supplier.contact_name,
        'phone': supplier.phone,
        'email': supplier.email,
        'service_type': supplier.service_type,
        'notes': supplier.notes,
        'is_active': supplier.is_active,
        'total_evaluations': len(evaluations),
        'avg_score': supplier.get_average_score(),
        'avg_rating': round(sum(ratings) / len(ratings), 2) if ratings else 0,
        'last_evaluation': supplier.get_last_evaluation_date().strftime('%d/%m/%Y') if supplier.get_last_evaluation_date() else None,
        'monthly_scores': [{'month': e.month_reference, 'score': e.total_score} for e in evaluations]
    })


@suppliers_bp.route('/verify-issue/<int:supplier_id>', methods=['POST'])
@login_required
@require_permission('verificar-problemas-fornecedor')
def verify_issue(supplier_id):
    """Marca um fornecedor com problema como verificado"""
    supplier = Supplier.query.get_or_404(supplier_id)
    
    supplier.issue_verified = True
    supplier.verified_at = datetime.now()
    supplier.verified_by_id = current_user.id
    
    try:
        db.session.commit()
        flash(f'Problema do fornecedor "{supplier.company_name}" marcado como verificado!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao verificar fornecedor: {str(e)}', 'danger')
    
    return redirect(url_for('suppliers.dashboard'))


@suppliers_bp.route('/unverify-issue/<int:supplier_id>', methods=['POST'])
@login_required
def unverify_issue(supplier_id):
    """Desmarca um fornecedor como verificado"""
    supplier = Supplier.query.get_or_404(supplier_id)
    
    supplier.issue_verified = False
    supplier.verified_at = None
    supplier.verified_by_id = None
    
    try:
        db.session.commit()
        flash(f'Verificação do fornecedor "{supplier.company_name}" removida!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao desmarcar verificação: {str(e)}', 'danger')
    
    return redirect(url_for('suppliers.dashboard'))


# ============================================
# ATRIBUIÇÃO DE AVALIADORES (GESTORES)
# ============================================

@suppliers_bp.route('/assign-evaluators/<int:supplier_id>', methods=['POST'])
@login_required
@require_permission('assign-supplier-evaluators')
def assign_evaluators(supplier_id):
    """Atribui gestores responsáveis por avaliar um fornecedor"""
    supplier = Supplier.query.get_or_404(supplier_id)
    
    # Pegar IDs dos usuários selecionados
    user_ids = request.form.getlist('evaluator_ids')
    
    # Limpar avaliadores atuais
    supplier.assigned_evaluators.clear()
    
    # Adicionar novos avaliadores
    for user_id in user_ids:
        user = User.query.get(int(user_id))
        if user:
            supplier.assigned_evaluators.append(user)
    
    try:
        db.session.commit()
        flash(f'Avaliadores atribuídos ao fornecedor "{supplier.company_name}" com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao atribuir avaliadores: {str(e)}', 'danger')
    
    return redirect(url_for('suppliers.supplier_list'))


@suppliers_bp.route('/api/supplier/<int:supplier_id>/evaluators')
@login_required
def get_supplier_evaluators(supplier_id):
    """Retorna os avaliadores atribuídos a um fornecedor"""
    supplier = Supplier.query.get_or_404(supplier_id)
    
    evaluators = [{
        'id': user.id,
        'name': user.name,
        'username': user.username,
        'job_title': user.job_title
    } for user in supplier.assigned_evaluators]
    
    return jsonify(evaluators)


# ============================================
# GERENCIAMENTO DE HISTÓRICO DE PROBLEMAS
# ============================================

# Rota desabilitada - funcionalidade agora está inline no dashboard via modal
# @suppliers_bp.route('/issue-tracking/<int:supplier_id>')
# @login_required
# def issue_tracking(supplier_id):
#     """Visualiza todo o histórico de acompanhamento de um fornecedor"""
#     supplier = Supplier.query.get_or_404(supplier_id)
#     
#     # Buscar todo o histórico ordenado por data decrescente
#     history = supplier.issue_history.all()
#     
#     # Estatísticas
#     total_actions = len(history)
#     open_issues = any(h.action_type in ['opened', 'reopened', 'escalated'] for h in history if h == history[0]) if history else False
#     
#     return render_template('feedback/suppliers/issue_tracking.html',
#                          supplier=supplier,
#                          history=history,
#                          total_actions=total_actions,
#                          has_open_issue=open_issues,
#                          current_date=date.today())


@suppliers_bp.route('/add-issue-action/<int:supplier_id>', methods=['POST'])
@login_required
@require_permission('gerenciar-rastreamento-fornecedor')
def add_issue_action(supplier_id):
    """Adiciona uma nova ação/registro no histórico de problemas"""
    supplier = Supplier.query.get_or_404(supplier_id)
    
    action_type = request.form.get('action_type')
    description = request.form.get('description')
    evaluation_id = request.form.get('evaluation_id')
    evaluation = None
    if evaluation_id:
        evaluation = SupplierEvaluation.query.get(int(evaluation_id))
        if not evaluation or evaluation.supplier_id != supplier.id:
            return jsonify({
                'success': False,
                'message': 'Avaliação inválida para este fornecedor.'
            }), 400
    
    if not action_type or not description:
        return jsonify({
            'success': False,
            'message': 'Tipo de ação e descrição são obrigatórios!'
        }), 400
    
    # Processar anexos
    attachments_data = []
    uploaded_files = request.files.getlist('attachments')
    
    if uploaded_files:
        import os
        from werkzeug.utils import secure_filename
        from flask import current_app
        
        # Criar diretório para anexos de fornecedores (caminho absoluto)
        upload_folder = os.path.join('/app/uploads', 'supplier_tracking')
        os.makedirs(upload_folder, exist_ok=True)
        
        for file in uploaded_files:
            if file and file.filename:
                # Validar tamanho (10MB max)
                file.seek(0, os.SEEK_END)
                file_size = file.tell()
                file.seek(0)
                
                if file_size > 10 * 1024 * 1024:  # 10MB
                    return jsonify({
                        'success': False,
                        'message': f'Arquivo {file.filename} excede o tamanho máximo de 10MB!'
                    }), 400
                
                # Salvar arquivo
                filename = secure_filename(file.filename)
                timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                unique_filename = f"{timestamp}_{filename}"
                file_path = os.path.join(upload_folder, unique_filename)
                file.save(file_path)
                
                # Guardar informações do anexo
                attachments_data.append({
                    'filename': filename,
                    'stored_filename': unique_filename,
                    'path': file_path,
                    'size': file_size,
                    'uploaded_at': datetime.utcnow().isoformat()
                })
    
    # Criar novo registro
    tracking = SupplierIssueTracking(
        supplier_id=supplier_id,
        evaluation_id=evaluation.id if evaluation else None,
        user_id=current_user.id,
        action_type=action_type,
        description=description,
        attachments=attachments_data if attachments_data else None
    )
    
    # Se a ação for "resolved", marcar o fornecedor como verificado
    if action_type == 'resolved':
        supplier.issue_verified = True
        supplier.verified_at = datetime.utcnow()
        supplier.verified_by_id = current_user.id
    elif action_type in ['reopened', 'opened', 'escalated']:
        supplier.issue_verified = False
        supplier.verified_at = None
        supplier.verified_by_id = None
    _update_follow_up_status(evaluation, action_type)
    
    try:
        db.session.add(tracking)
        db.session.commit()
        return jsonify({
            'success': True,
            'message': f'Ação "{tracking.get_action_label()}" registrada com sucesso!',
            'follow_up_status': evaluation.follow_up_status if evaluation else None
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Erro ao registrar ação: {str(e)}'
        }), 400


@suppliers_bp.route('/api/issue-history/<int:supplier_id>')
@login_required
def api_issue_history(supplier_id):
    """Retorna o histórico de problemas em JSON"""
    supplier = Supplier.query.get_or_404(supplier_id)
    
    history = [{
        'id': h.id,
        'action_type': h.action_type,
        'action_label': h.get_action_label(),
        'action_icon': h.get_action_icon(),
        'action_color': h.get_action_color(),
        'description': h.description,
        'attachments': [
            {
                'filename': att['filename'],
                'url': url_for('suppliers.download_attachment', 
                              supplier_id=supplier_id, 
                              tracking_id=h.id, 
                              filename=att['stored_filename'])
            }
            for att in (h.attachments or [])
        ] if h.attachments else [],
        'created_at': h.created_at.isoformat(),
        'user_name': h.user.name,
        'user_job': h.user.job_title if hasattr(h.user, 'job_title') else ''
    } for h in supplier.issue_history.order_by(SupplierIssueTracking.created_at.desc()).all()]
    
    return jsonify({'success': True, 'history': history})


@suppliers_bp.route('/download-attachment/<int:supplier_id>/<int:tracking_id>/<filename>')
@login_required
def download_attachment(supplier_id, tracking_id, filename):
    """Faz download de um anexo do histórico de tracking"""
    import os
    
    # Verificar se o tracking existe e pertence ao supplier
    tracking = SupplierIssueTracking.query.get_or_404(tracking_id)
    if tracking.supplier_id != supplier_id:
        flash('Anexo não encontrado', 'danger')
        return redirect(url_for('suppliers.dashboard'))
    
    # Buscar o anexo
    if not tracking.attachments:
        flash('Nenhum anexo encontrado', 'danger')
        return redirect(url_for('suppliers.dashboard'))
    
    attachment = next((att for att in tracking.attachments if att['stored_filename'] == filename), None)
    if not attachment:
        flash('Anexo não encontrado', 'danger')
        return redirect(url_for('suppliers.dashboard'))
    
    file_path = attachment['path']
    if not os.path.exists(file_path):
        flash('Arquivo não encontrado no servidor', 'danger')
        return redirect(url_for('suppliers.dashboard'))
    
    # Determinar o mimetype baseado na extensão
    mimetype = mimetypes.guess_type(attachment['filename'])[0] or 'application/octet-stream'
    
    return send_file(
        file_path, 
        mimetype=mimetype,
        as_attachment=True, 
        download_name=attachment['filename']
    )
