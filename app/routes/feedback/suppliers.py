"""
Rotas para gerenciamento de Fornecedores/Prestadores e suas Avaliações
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import db, Supplier, SupplierEvaluation, User
from datetime import datetime
from sqlalchemy import func, desc

suppliers_bp = Blueprint('suppliers', __name__, url_prefix='/feedback/suppliers')


# ============================================
# DASHBOARD E RELATÓRIOS
# ============================================

@suppliers_bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard principal com rankings e estatísticas"""
    # Buscar todos os fornecedores ativos
    suppliers = Supplier.query.filter_by(is_active=True).all()
    
    # Calcular scores médios e ordenar
    suppliers_data = []
    for supplier in suppliers:
        avg_score = supplier.get_average_score()
        eval_count = supplier.get_evaluations_count()
        last_eval_date = supplier.get_last_evaluation_date()
        
        # Verificar se tem última avaliação
        last_eval = supplier.evaluations.order_by(
            desc(SupplierEvaluation.evaluation_date)
        ).first() if eval_count > 0 else None
        
        # Determinar se precisa de atenção
        needs_attention = False
        if eval_count > 0:
            if avg_score < 70 or (last_eval and not last_eval.had_service_last_month):
                needs_attention = True
        
        # Calcular prioridade para ordenação
        # Prioridade 1 (mais urgente): Insatisfatório não verificado (< 60%)
        # Prioridade 2: Sem serviço não verificado
        # Prioridade 3: Score baixo não verificado (60-69%)
        # Prioridade 4: Excelente (>= 80%) - Destaque positivo
        # Prioridade 5: Satisfatório (70-79%)
        # Prioridade 6: Problemas já verificados (qualquer score < 70 ou sem serviço)
        # Prioridade 7: Não avaliado
        
        if needs_attention and not supplier.issue_verified:
            # Problemas NÃO verificados (mais urgentes)
            if avg_score < 60:
                priority = 1  # Insatisfatório não verificado
            elif last_eval and not last_eval.had_service_last_month:
                priority = 2  # Sem serviço não verificado
            else:
                priority = 3  # Score baixo não verificado (60-69%)
        elif eval_count > 0 and avg_score >= 80:
            # Excelente - sempre em destaque após problemas urgentes
            priority = 4
        elif eval_count > 0 and avg_score >= 70:
            # Satisfatório (70-79%)
            priority = 5
        elif needs_attention and supplier.issue_verified:
            # Problemas JÁ verificados (após os satisfatórios)
            priority = 6
        elif eval_count == 0:
            # Não avaliado
            priority = 7
        else:
            # Casos não cobertos (fallback)
            priority = 8
        
        suppliers_data.append({
            'supplier': supplier,
            'avg_score': avg_score,
            'eval_count': eval_count,
            'last_eval_date': last_eval_date,
            'last_eval': last_eval,
            'needs_attention': needs_attention,
            'priority': priority
        })
    
    # Ordenar por prioridade (menor número = maior prioridade) e depois por score (decrescente)
    suppliers_data.sort(key=lambda x: (x['priority'], -x['avg_score']))
    
    # Estatísticas gerais
    total_suppliers = len(suppliers)
    total_evaluations = SupplierEvaluation.query.count()
    
    # Fornecedores com problemas (score < 60% OU não teve serviço no último mês)
    problematic_suppliers = []
    for s in suppliers_data:
        if s['eval_count'] > 0:
            # Verificar se teve score baixo OU se não houve serviço
            last_eval = SupplierEvaluation.query.filter_by(
                supplier_id=s['supplier'].id
            ).order_by(desc(SupplierEvaluation.evaluation_date)).first()
            
            if last_eval and (s['avg_score'] < 60 or not last_eval.had_service_last_month):
                problematic_suppliers.append(s)
    
    # Melhores fornecedores (top 5) - inclui Excelentes (>=80) e Satisfatórios (>=60)
    top_suppliers = [s for s in suppliers_data if s['eval_count'] > 0 and s['avg_score'] >= 60][:5]
    
    # Piores fornecedores (score < 70% e que foram avaliados)
    worst_suppliers = [s for s in suppliers_data if s['avg_score'] < 70 and s['eval_count'] > 0]
    
    return render_template('feedback/suppliers/dashboard.html',
                         suppliers_data=suppliers_data,
                         total_suppliers=total_suppliers,
                         total_evaluations=total_evaluations,
                         problematic_count=len(problematic_suppliers),
                         top_suppliers=top_suppliers,
                         worst_suppliers=worst_suppliers)


# ============================================
# GERENCIAMENTO DE FORNECEDORES (CRUD)
# ============================================

@suppliers_bp.route('/list')
@login_required
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
    
    return render_template('feedback/suppliers/supplier_list.html',
                         suppliers_info=suppliers_info)


@suppliers_bp.route('/register', methods=['GET', 'POST'])
@login_required
def register_supplier():
    """Cadastra um novo fornecedor"""
    if request.method == 'POST':
        company_name = request.form.get('company_name')
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
            db.session.commit()
            flash(f'Fornecedor "{company_name}" cadastrado com sucesso!', 'success')
            return redirect(url_for('suppliers.supplier_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar fornecedor: {str(e)}', 'danger')
            return redirect(url_for('suppliers.supplier_list'))
    
    # Se for GET, redireciona para a lista (modal abrirá lá)
    return redirect(url_for('suppliers.supplier_list'))


@suppliers_bp.route('/edit/<int:supplier_id>', methods=['GET', 'POST'])
@login_required
def edit_supplier(supplier_id):
    """Edita um fornecedor existente"""
    supplier = Supplier.query.get_or_404(supplier_id)
    
    if request.method == 'POST':
        supplier.company_name = request.form.get('company_name')
        supplier.cnpj = request.form.get('cnpj')
        supplier.contact_name = request.form.get('contact_name')
        supplier.phone = request.form.get('phone')
        supplier.email = request.form.get('email')
        supplier.service_type = request.form.get('service_type')
        supplier.notes = request.form.get('notes')
        
        try:
            db.session.commit()
            flash('Fornecedor atualizado com sucesso!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar fornecedor: {str(e)}', 'danger')
    
    return redirect(url_for('suppliers.supplier_list'))


@suppliers_bp.route('/delete/<int:supplier_id>', methods=['POST'])
@login_required
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
def evaluate_supplier():
    """Formulário para avaliar um fornecedor"""
    if request.method == 'POST':
        supplier_id = request.form.get('supplier_id')
        month_reference = request.form.get('month_reference')
        
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
            db.session.commit()
            flash(f'Avaliação registrada com sucesso! Score: {evaluation.total_score}%', 'success')
            return redirect(url_for('suppliers.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao registrar avaliação: {str(e)}', 'danger')
    
    # GET - Carregar fornecedores ativos
    suppliers = Supplier.query.filter_by(is_active=True).order_by(Supplier.company_name).all()
    
    # Mês de referência padrão (mês atual)
    current_month = datetime.now().strftime('%Y-%m')
    
    return render_template('feedback/suppliers/supplier_evaluation.html',
                         suppliers=suppliers,
                         current_month=current_month)


@suppliers_bp.route('/evaluations/<int:supplier_id>')
@login_required
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
    
    return render_template('feedback/suppliers/supplier_evaluations.html',
                         supplier=supplier,
                         evaluations=evaluations,
                         avg_score=avg_score,
                         avg_rating=avg_rating)


@suppliers_bp.route('/evaluation/details/<int:evaluation_id>')
@login_required
def evaluation_details(evaluation_id):
    """Detalhes de uma avaliação específica"""
    evaluation = SupplierEvaluation.query.get_or_404(evaluation_id)
    
    return render_template('feedback/suppliers/evaluation_details.html',
                         evaluation=evaluation)


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

