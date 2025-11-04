function getCsrfToken() {
    const csrfInput = document.querySelector('input[name="csrf_token"]');
    if (csrfInput) {
        return csrfInput.value;
    }
    const csrfMeta = document.querySelector('meta[name="csrf_token"]');
    if (csrfMeta) {
        return csrfMeta.getAttribute('content');
    }
    return '';
}

document.addEventListener('DOMContentLoaded', function () {
    function formatElapsedTime(faDatetime) {
        const now = new Date();
        const fa = new Date(faDatetime);
        const diffMs = now - fa;
        
        if (diffMs < 0) {
            return '0h 0m 0s';
        }
        
        const totalSeconds = Math.floor(diffMs / 1000);
        const hours = Math.floor(totalSeconds / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const seconds = totalSeconds % 60;
        
        return `${hours}h ${minutes}m ${seconds}s`;
    }
    
    function updateObservationTimers() {
        document.querySelectorAll('.observation-timer').forEach(timer => {
            const faDatetime = timer.getAttribute('data-fa-datetime');
            if (faDatetime) {
                const display = timer.querySelector('.timer-display');
                if (display) {
                    display.textContent = formatElapsedTime(faDatetime);
                }
            }
        });
    }
    
    updateObservationTimers();
    
    setInterval(updateObservationTimers, 1000);
    
    document.addEventListener('click', function (e) {
        const btn = e.target.closest('.toggle-detail-alta, .toggle-detail-observation');
        if (!btn) return;

        const id = btn.getAttribute('data-detail-id');
        if (!id) return;

        const row = document.getElementById(id);
        if (!row) return;

        const visible = row.style.display !== 'none';

        if (visible) {
            if (id.startsWith('detail-alta-')) {
                const recordId = id.replace('detail-alta-', '');
                resetAltaForm(recordId);
            }
        }

        document.querySelectorAll('tr.detail-row').forEach(r => {
            if (r !== row && r.style.display !== 'none') {
                r.style.display = 'none';

                const otherId = r.id;
                
                document.querySelectorAll(`button.toggle-detail-alta[data-detail-id="${otherId}"] .btn-text`).forEach(span => {
                    if (span) span.textContent = 'Ver e gerenciar';
                });
                
                document.querySelectorAll(`button.toggle-detail-observation[data-detail-id="${otherId}"] .btn-text`).forEach(span => {
                    if (span) span.textContent = 'Gerenciar Observação';
                });
            }
        });

        row.style.display = visible ? 'none' : '';

        const card = row.querySelector('.inline-detail-card');
        if (!visible && card) {
            card.classList.remove('animate-in');
            void card.offsetWidth;
            card.classList.add('animate-in');
        }

        const btnTextElement = btn.querySelector('.btn-text');
        if (btnTextElement) {
            if (id.startsWith('detail-alta-')) {
                btnTextElement.textContent = row.style.display === 'none' ? 'Ver e gerenciar' : 'Ocultar painel';
            } else if (id.startsWith('detail-observation-')) {
                btnTextElement.textContent = row.style.display === 'none' ? 'Gerenciar Observação' : 'Ocultar painel';
            }
        }

        if (row.style.display !== 'none') {
            setTimeout(() => row.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50);
        }
    });

    document.addEventListener('click', function (e) {
        const cancelBtn = e.target.closest('.cancel-alta-form');
        if (!cancelBtn) return;

        const recordId = cancelBtn.getAttribute('data-record-id');
        const detailRow = document.getElementById(`detail-alta-${recordId}`);
        
        if (detailRow) {
            detailRow.style.display = 'none';
            document.querySelectorAll(`button.toggle-detail-alta[data-detail-id="detail-alta-${recordId}"] .btn-text`).forEach(span => {
                if (span) span.textContent = 'Ver e gerenciar';
            });
            resetAltaForm(recordId);
        }
    });

    document.addEventListener('click', function (e) {
        const cancelBtn = e.target.closest('.cancel-observation-panel');
        if (!cancelBtn) return;

        const recordId = cancelBtn.getAttribute('data-record-id');
        const detailRow = document.getElementById(`detail-observation-${recordId}`);
        
        if (detailRow) {
            detailRow.style.display = 'none';
            document.querySelectorAll(`button.toggle-detail-observation[data-detail-id="detail-observation-${recordId}"] .btn-text`).forEach(span => {
                if (span) span.textContent = 'Gerenciar Observação';
            });
        }
    });

    function resetAltaForm(recordId) {
        const form = document.getElementById(`alta-form-${recordId}`);
        if (!form) return;

        form.querySelectorAll('input[type="text"], input[type="date"], select').forEach(input => {
            if (input.name !== 'csrf_token') {
                const originalValue = input.getAttribute('value');
                if (originalValue !== null) {
                    input.value = originalValue;
                } else {
                    input.value = '';
                }
            }
        });

        form.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
    }

    document.querySelectorAll('form[id^="alta-form-"]').forEach(form => {
        form.addEventListener('submit', function (e) {
            const requiredInputs = this.querySelectorAll('input[required], select[required]');
            let firstInvalidField = null;

            requiredInputs.forEach(input => {
                if (!input.value.trim()) {
                    input.classList.add('is-invalid');
                    if (!firstInvalidField) {
                        firstInvalidField = input;
                    }
                } else {
                    input.classList.remove('is-invalid');
                }
            });

            if (firstInvalidField) {
                e.preventDefault();
                e.stopPropagation();
                firstInvalidField.focus();
                firstInvalidField.scrollIntoView({ behavior: 'smooth', block: 'center' });
                return false;
            }

            const submitBtn = this.querySelector('button[type="submit"]');
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Salvando...';

            return true;
        });
    });
});

function evolveObservation(recordId, patientName) {
    const detailRow = document.getElementById(`detail-observation-${recordId}`);
    if (!detailRow) return;
    
    const detailBody = detailRow.querySelector('.inline-detail-body');
    if (!detailBody) return;
    
    detailBody.innerHTML = `
        <div class="alert alert-success mb-3 py-2">
            <i class="bi bi-check-circle me-2"></i>
            <strong>Evoluindo para Internação:</strong> ${patientName}
        </div>
        
        <form method="POST" action="/nir/observacao/${recordId}/evoluir" id="inline-evolve-form-${recordId}">
            <input type="hidden" name="csrf_token" value="${getCsrfToken()}">
            
            <ul class="nav nav-tabs mb-3" id="evolve-tabs-${recordId}" role="tablist">
                <li class="nav-item" role="presentation">
                    <button class="nav-link active" id="tab-basic-${recordId}" data-bs-toggle="tab" 
                            data-bs-target="#content-basic-${recordId}" type="button" role="tab">
                        <i class="bi bi-file-earmark-text me-1"></i>
                        Dados Básicos
                        <i class="bi bi-check-circle-fill ms-1 text-success" id="check-basic-${recordId}" style="display:none;"></i>
                    </button>
                </li>
                <li class="nav-item" role="presentation" id="li-tab-susfacil-${recordId}" style="display:none;">
                    <button class="nav-link" id="tab-susfacil-${recordId}" data-bs-toggle="tab" 
                            data-bs-target="#content-susfacil-${recordId}" type="button" role="tab">
                        <i class="bi bi-shield-check me-1"></i>
                        Aceite SUSFACIL
                        <i class="bi bi-check-circle-fill ms-1 text-success" id="check-susfacil-${recordId}" style="display:none;"></i>
                    </button>
                </li>
                <li class="nav-item" role="presentation" id="li-tab-procedures-${recordId}" style="display:none;">
                    <button class="nav-link" id="tab-procedures-${recordId}" data-bs-toggle="tab" 
                            data-bs-target="#content-procedures-${recordId}" type="button" role="tab">
                        <i class="bi bi-activity me-1"></i>
                        Procedimentos
                        <i class="bi bi-check-circle-fill ms-1 text-success" id="check-procedures-${recordId}" style="display:none;"></i>
                    </button>
                </li>
                <li class="nav-item" role="presentation" id="li-tab-clinical-${recordId}" style="display:none;">
                    <button class="nav-link" id="tab-clinical-${recordId}" data-bs-toggle="tab" 
                            data-bs-target="#content-clinical-${recordId}" type="button" role="tab">
                        <i class="bi bi-heart-pulse me-1"></i>
                        Dados Clínicos
                        <i class="bi bi-check-circle-fill ms-1 text-success" id="check-clinical-${recordId}" style="display:none;"></i>
                    </button>
                </li>
            </ul>
            
            <div class="tab-content" id="evolve-tab-content-${recordId}">
                
                <div class="tab-pane fade show active" id="content-basic-${recordId}" role="tabpanel">
                    <div class="row g-3 mb-3">
                        <div class="col-md-4">
                            <label class="form-label fw-bold">Data de Internação <span class="text-danger">*</span></label>
                            <input type="date" class="form-control" name="admission_date" id="admission_date_${recordId}" required>
                        </div>
                        <div class="col-md-4">
                            <label class="form-label fw-bold">Tipo de Entrada <span class="text-danger">*</span></label>
                            <select class="form-select" name="entry_type" id="entry_type_${recordId}" required>
                                <option value="">Selecione</option>
                                <option value="ELETIVO">Eletivo</option>
                                <option value="URGENCIA">Urgência</option>
                            </select>
                        </div>
                        <div class="col-md-4">
                            <label class="form-label fw-bold">Tipo de Internação <span class="text-danger">*</span></label>
                            <select class="form-select" name="admission_type" id="admission_type_${recordId}" required>
                                <option value="">Selecione</option>
                                <option value="CLINICO">Clínico</option>
                                <option value="CIRURGICO">Cirúrgico</option>
                            </select>
                        </div>
                    </div>
                    
                    <div class="row g-3 mb-3">
                        <div class="col-md-6">
                            <label class="form-label fw-bold">Local de Origem <span class="text-danger">*</span></label>
                            <select class="form-select" name="admitted_from_origin" id="admitted_from_${recordId}" required>
                                <option value="Iturama">Iturama</option>
                                <option value="São Francisco">São Francisco</option>
                                <option value="União de Minas">União de Minas</option>
                                <option value="Carneirinho">Carneirinho</option>
                                <option value="Limeira do Oeste">Limeira do Oeste</option>
                                <option value="Outro">Outro...</option>
                            </select>
                        </div>
                        <div class="col-md-6">
                            <label class="form-label fw-bold">Data de Agendamento <span class="text-danger">*</span></label>
                            <input type="date" class="form-control" name="scheduling_date" id="scheduling_date_${recordId}" required>
                        </div>
                    </div>
                    
                    <div class="d-flex justify-content-end gap-2 mt-3">
                        <button type="button" class="btn btn-secondary" onclick="cancelEvolveInline(${recordId})">
                            <i class="bi bi-x-circle me-1"></i>Cancelar
                        </button>
                        <button type="button" class="btn btn-primary" id="btn-next-basic-${recordId}">
                            Próximo <i class="bi bi-arrow-right ms-1"></i>
                        </button>
                        <button type="button" class="btn btn-success" id="btn-finish-basic-${recordId}" style="display:none;">
                            <i class="bi bi-check-circle me-1"></i>Confirmar Internação
                        </button>
                    </div>
                </div>
                
                <div class="tab-pane fade" id="content-susfacil-${recordId}" role="tabpanel">
                    <div class="alert alert-info mb-3">
                        <i class="bi bi-info-circle me-2"></i>
                        <strong>Atenção:</strong> Para internações eletivas, é obrigatório confirmar o aceite no sistema SUSFACIL.
                    </div>
                    <div class="row g-3 mb-3">
                        <div class="col-md-12">
                            <div class="form-check form-switch mb-3">
                                <input class="form-check-input" type="checkbox" id="susfacil_accepted_${recordId}" name="susfacil_accepted">
                                <label class="form-check-label fw-bold text-success" for="susfacil_accepted_${recordId}">
                                    <i class="bi bi-check-circle me-1"></i>
                                    Confirmo que realizei o aceite do paciente no sistema SUSFACIL
                                </label>
                            </div>
                        </div>
                        <div class="col-md-12" id="aceite-datetime-field-${recordId}" style="display: none;">
                            <label class="form-label fw-bold">Data e Hora do Aceite no SUSFACIL <span class="text-danger">*</span></label>
                            <input type="datetime-local" class="form-control" name="susfacil_accept_datetime" id="susfacil_accept_datetime_${recordId}">
                            <small class="form-text text-muted">
                                <i class="bi bi-clock-history me-1"></i>
                                Informe exatamente a data e hora que aparece no SUSFACIL após o aceite
                            </small>
                        </div>
                    </div>
                    
                    <div class="d-flex justify-content-between gap-2 mt-3">
                        <button type="button" class="btn btn-secondary" id="btn-prev-susfacil-${recordId}">
                            <i class="bi bi-arrow-left me-1"></i>Voltar
                        </button>
                        <button type="button" class="btn btn-primary" id="btn-next-susfacil-${recordId}" style="display:none;">
                            Próximo <i class="bi bi-arrow-right ms-1"></i>
                        </button>
                        <button type="button" class="btn btn-success" id="btn-finish-susfacil-${recordId}">
                            <i class="bi bi-check-circle me-1"></i>Confirmar Internação
                        </button>
                    </div>
                </div>
                
                <div class="tab-pane fade" id="content-procedures-${recordId}" role="tabpanel">
                    <div class="alert alert-info mb-3">
                        <i class="bi bi-activity me-2"></i>
                        <strong>Procedimentos:</strong> Adicione os procedimentos que serão realizados.
                    </div>
                    
                    <div class="row g-3 align-items-end mb-3">
                        <div class="col-md-5">
                            <label class="form-label fw-bold">Código do Procedimento</label>
                            <div style="position: relative;">
                                <input type="text" class="form-control" 
                                    id="procedure_code_input_${recordId}" 
                                    placeholder="Digite código ou descrição"
                                    autocomplete="off">
                                <div id="procedure_search_results_${recordId}" class="procedure-search-results" style="display:none; position:absolute; top:100%; left:0; right:0; background:white; border:1px solid #ddd; border-radius:4px; max-height:200px; overflow-y:auto; z-index:1000;"></div>
                            </div>
                        </div>
                        <div class="col-md-5">
                            <label class="form-label fw-bold">Descrição</label>
                            <input type="text" class="form-control bg-light" 
                                id="procedure_description_input_${recordId}" 
                                readonly>
                        </div>
                        <div class="col-md-2">
                            <button type="button" class="btn btn-primary w-100" id="add_procedure_btn_${recordId}">
                                <i class="bi bi-plus-circle"></i> Adicionar
                            </button>
                        </div>
                    </div>
                    
                    <div class="border rounded p-3 bg-body-tertiary mb-3" id="procedures_list_${recordId}">
                        <p class="text-muted text-center mb-0">
                            <i class="bi bi-info-circle me-2"></i>Nenhum procedimento adicionado
                        </p>
                    </div>
                    <small class="text-muted d-block mb-3">
                        <i class="bi bi-lightbulb me-1"></i>O primeiro procedimento será considerado principal.
                    </small>
                    
                    <div class="d-flex justify-content-between gap-2 mt-3">
                        <button type="button" class="btn btn-secondary" id="btn-prev-procedures-${recordId}">
                            <i class="bi bi-arrow-left me-1"></i>Voltar
                        </button>
                        <button type="button" class="btn btn-primary" id="btn-next-procedures-${recordId}">
                            Próximo <i class="bi bi-arrow-right ms-1"></i>
                        </button>
                    </div>
                </div>
                
                <div class="tab-pane fade" id="content-clinical-${recordId}" role="tabpanel">
                    <div class="alert alert-warning mb-3">
                        <i class="bi bi-heart-pulse me-2"></i>
                        <strong>Internação Clínica:</strong> Preencha os dados médicos adicionais necessários.
                    </div>
                    
                    <div class="form-check form-switch mb-4">
                        <input class="form-check-input" type="checkbox" id="is_palliative_${recordId}" name="is_palliative">
                        <label class="form-check-label fw-bold text-danger" for="is_palliative_${recordId}">
                            <i class="bi bi-exclamation-triangle-fill me-1"></i>
                            Paciente Paliativo
                        </label>
                    </div>
                    
                    <div class="row g-3 mb-3">
                        <div class="col-md-6">
                            <label class="form-label fw-bold">Médico Responsável <span class="text-danger">*</span></label>
                            <input type="text" class="form-control" name="responsible_doctor" id="responsible_doctor_${recordId}" placeholder="Nome do médico">
                        </div>
                        <div class="col-md-6">
                            <label class="form-label fw-bold">Especialidade <span class="text-danger">*</span></label>
                            <select class="form-select" name="surgical_specialty" id="surgical_specialty_${recordId}">
                                <option value="">Selecione</option>
                                <option value="CIRURGIA GERAL">Cirurgia Geral</option>
                                <option value="CLINICO GERAL">Clínico Geral</option>
                                <option value="DENTISTA">Dentista</option>
                                <option value="DERMATO">Dermatologia</option>
                                <option value="OBSTETRICIA">Obstetrícia</option>
                                <option value="OFTALMOLOGISTA">Oftalmologia</option>
                                <option value="ORTOPEDISTA">Ortopedia</option>
                                <option value="UROLOGISTA">Urologia</option>
                                <option value="VASCULAR">Vascular</option>
                                <option value="PEDIATRIA">Pediatria</option>
                            </select>
                        </div>
                        <div class="col-md-12">
                            <label class="form-label fw-bold">CID Principal <span class="text-danger">*</span></label>
                            <select class="form-select" name="main_cid" id="main_cid_${recordId}">
                                <option value="">Adicione um procedimento primeiro</option>
                            </select>
                            <small class="form-text text-muted">
                                <i class="bi bi-lightbulb me-1"></i>
                                Apenas CIDs relacionados ao procedimento principal.
                            </small>
                        </div>
                    </div>
                    
                    <div class="d-flex justify-content-between gap-2 mt-3">
                        <button type="button" class="btn btn-secondary" id="btn-prev-clinical-${recordId}">
                            <i class="bi bi-arrow-left me-1"></i>Voltar
                        </button>
                        <button type="button" class="btn btn-success" id="btn-finish-clinical-${recordId}">
                            <i class="bi bi-check-circle me-1"></i>Confirmar Internação
                        </button>
                    </div>
                </div>
            </div>
        </form>
    `;
    
    const form = document.getElementById(`inline-evolve-form-${recordId}`);
    const entryTypeSelect = document.getElementById(`entry_type_${recordId}`);
    const admissionTypeSelect = document.getElementById(`admission_type_${recordId}`);
    const susfacilCheckbox = document.getElementById(`susfacil_accepted_${recordId}`);
    const aceiteDatetimeField = document.getElementById(`aceite-datetime-field-${recordId}`);
    const aceiteDatetimeInput = document.getElementById(`susfacil_accept_datetime_${recordId}`);
    const responsibleDoctorInput = document.getElementById(`responsible_doctor_${recordId}`);
    const surgicalSpecialtySelect = document.getElementById(`surgical_specialty_${recordId}`);
    const mainCidSelect = document.getElementById(`main_cid_${recordId}`);
    const admissionDateInput = document.getElementById(`admission_date_${recordId}`);
    
    if (admissionDateInput) {
        const today = new Date();
        const year = today.getFullYear();
        const month = String(today.getMonth() + 1).padStart(2, '0');
        const day = String(today.getDate()).padStart(2, '0');
        const todayFormatted = `${year}-${month}-${day}`;
        admissionDateInput.value = todayFormatted;
    }
    
    const procedureCodeInput = document.getElementById(`procedure_code_input_${recordId}`);
    const procedureDescInput = document.getElementById(`procedure_description_input_${recordId}`);
    const procedureSearchResults = document.getElementById(`procedure_search_results_${recordId}`);
    const addProcedureBtn = document.getElementById(`add_procedure_btn_${recordId}`);
    const proceduresList = document.getElementById(`procedures_list_${recordId}`);
    let addedProcedures = [];
    let selectedProcedure = null;
    let searchTimeout;
    
    const tabSusfacil = document.getElementById(`tab-susfacil-${recordId}`);
    const tabProcedures = document.getElementById(`tab-procedures-${recordId}`);
    const tabClinical = document.getElementById(`tab-clinical-${recordId}`);
    const liTabSusfacil = document.getElementById(`li-tab-susfacil-${recordId}`);
    const liTabProcedures = document.getElementById(`li-tab-procedures-${recordId}`);
    const liTabClinical = document.getElementById(`li-tab-clinical-${recordId}`);
    const checkBasic = document.getElementById(`check-basic-${recordId}`);
    const checkSusfacil = document.getElementById(`check-susfacil-${recordId}`);
    const checkProcedures = document.getElementById(`check-procedures-${recordId}`);
    const checkClinical = document.getElementById(`check-clinical-${recordId}`);
    
    const btnNextBasic = document.getElementById(`btn-next-basic-${recordId}`);
    const btnFinishBasic = document.getElementById(`btn-finish-basic-${recordId}`);
    const btnPrevSusfacil = document.getElementById(`btn-prev-susfacil-${recordId}`);
    const btnNextSusfacil = document.getElementById(`btn-next-susfacil-${recordId}`);
    const btnFinishSusfacil = document.getElementById(`btn-finish-susfacil-${recordId}`);
    const btnPrevProcedures = document.getElementById(`btn-prev-procedures-${recordId}`);
    const btnNextProcedures = document.getElementById(`btn-next-procedures-${recordId}`);
    const btnPrevClinical = document.getElementById(`btn-prev-clinical-${recordId}`);
    const btnFinishClinical = document.getElementById(`btn-finish-clinical-${recordId}`);
    
    function showTabValidationError(tabElement, message) {
        const navTabs = tabElement.closest('.nav-tabs');
        if (!navTabs) return;
        
        navTabs.querySelectorAll('.nav-link').forEach(t => {
            if (t !== tabElement) t.classList.remove('tab-error');
        });
        
        tabElement.classList.add('tab-error');
        
        const tooltip = document.createElement('div');
        tooltip.className = 'tab-validation-tooltip alert alert-danger mb-2 py-2 px-3';
        tooltip.innerHTML = `<i class="bi bi-exclamation-triangle me-2"></i>${message}`;
        
        const tabsContainer = navTabs.parentElement;
        const existingTooltips = tabsContainer.querySelectorAll('.tab-validation-tooltip');
        existingTooltips.forEach(t => t.remove());
        tabsContainer.insertBefore(tooltip, navTabs);
        
        setTimeout(() => {
            tabElement.classList.remove('tab-error');
            tooltip.remove();
        }, 4000);
    }
    
    function validateBasicTab() {
        const admissionDate = document.getElementById(`admission_date_${recordId}`);
        const entryTypeElem = entryTypeSelect;
        const admissionTypeElem = admissionTypeSelect;
        const origin = document.getElementById(`admitted_from_${recordId}`);
        const schedulingDate = document.getElementById(`scheduling_date_${recordId}`);
        
        const fields = [admissionDate, entryTypeElem, admissionTypeElem, origin, schedulingDate];
        let isValid = true;
        
        fields.forEach(field => {
            if (!field.value.trim()) {
                field.classList.add('is-invalid');
                isValid = false;
            } else {
                field.classList.remove('is-invalid');
            }
        });
        
        if (!isValid) {
            showTabValidationError(
                document.getElementById(`tab-basic-${recordId}`),
                'Preencha todos os campos obrigatórios da aba Dados Básicos!'
            );
        }
        return isValid;
    }
    
    function validateSusfacilTab() {
        const checkboxElem = susfacilCheckbox;
        const datetimeElem = aceiteDatetimeInput;
        let isValid = true;
        
        if (!checkboxElem.checked) {
            checkboxElem.closest('.col-md-12').classList.add('is-invalid');
            isValid = false;
        } else {
            checkboxElem.closest('.col-md-12').classList.remove('is-invalid');
        }
        
        if (!datetimeElem.value.trim()) {
            datetimeElem.classList.add('is-invalid');
            isValid = false;
        } else {
            datetimeElem.classList.remove('is-invalid');
        }
        
        if (!isValid) {
            showTabValidationError(
                document.getElementById(`tab-susfacil-${recordId}`),
                'Confirme o aceite SUSFACIL e informe a data/hora!'
            );
        }
        return isValid;
    }
    
    function validateProceduresTab() {
        if (addedProcedures.length === 0) {
            const proceduresListElem = document.getElementById(`procedures_list_${recordId}`);
            if (proceduresListElem) {
                proceduresListElem.classList.add('is-invalid');
                setTimeout(() => proceduresListElem.classList.remove('is-invalid'), 3000);
            }
            
            showTabValidationError(
                document.getElementById(`tab-procedures-${recordId}`),
                'Adicione pelo menos um procedimento!'
            );
            return false;
        }
        return true;
    }
    
    function validateClinicalTab() {
        const doctorElem = responsibleDoctorInput;
        const specialtyElem = surgicalSpecialtySelect;
        const cidElem = mainCidSelect;
        
        const fields = [doctorElem, specialtyElem, cidElem];
        let isValid = true;
        
        fields.forEach(field => {
            if (!field.value.trim()) {
                field.classList.add('is-invalid');
                isValid = false;
            } else {
                field.classList.remove('is-invalid');
            }
        });
        
        if (!isValid) {
            showTabValidationError(
                document.getElementById(`tab-clinical-${recordId}`),
                'Preencha todos os campos obrigatórios da aba Dados Clínicos!'
            );
        }
        return isValid;
    }
    
    function updateVisibleTabs() {
        const isEletivo = entryTypeSelect.value === 'ELETIVO';
        const isClinico = admissionTypeSelect.value === 'CLINICO';
        
        if (liTabSusfacil) {
            if (isEletivo) {
                liTabSusfacil.style.display = 'block';
            } else {
                liTabSusfacil.style.display = 'none';
            }
        }
        
        if (liTabProcedures) {
            if (isClinico) {
                liTabProcedures.style.display = 'block';
            } else {
                liTabProcedures.style.display = 'none';
            }
        }
        
        if (liTabClinical) {
            if (isClinico) {
                liTabClinical.style.display = 'block';
                responsibleDoctorInput.required = true;
                surgicalSpecialtySelect.required = true;
                mainCidSelect.required = true;
            } else {
                liTabClinical.style.display = 'none';
                responsibleDoctorInput.required = false;
                surgicalSpecialtySelect.required = false;
                mainCidSelect.required = false;
            }
        }
        
        const hasAdditionalTabs = isEletivo || isClinico;
        if (hasAdditionalTabs) {
            btnNextBasic.style.display = 'inline-block';
            btnFinishBasic.style.display = 'none';
        } else {
            btnNextBasic.style.display = 'none';
            btnFinishBasic.style.display = 'inline-block';
        }
        
        if (isEletivo && isClinico) {
            btnNextSusfacil.style.display = 'inline-block';
            btnFinishSusfacil.style.display = 'none';
        } else if (isEletivo) {
            btnNextSusfacil.style.display = 'none';
            btnFinishSusfacil.style.display = 'inline-block';
        }
    }
    
    entryTypeSelect.addEventListener('change', updateVisibleTabs);
    admissionTypeSelect.addEventListener('change', updateVisibleTabs);
    
    btnNextBasic.addEventListener('click', function() {
        if (!validateBasicTab()) return;
        
        checkBasic.style.display = 'inline';
        
        const isEletivo = entryTypeSelect.value === 'ELETIVO';
        const isClinico = admissionTypeSelect.value === 'CLINICO';
        
        if (isEletivo) {
            document.getElementById(`tab-susfacil-${recordId}`).click();
        } else if (isClinico) {
            document.getElementById(`tab-procedures-${recordId}`).click();
        } else {
            form.submit();
        }
    });
    
    btnFinishBasic.addEventListener('click', function() {
        if (!validateBasicTab()) return;
        
        checkBasic.style.display = 'inline';
        form.submit();
    });
    
    btnPrevSusfacil.addEventListener('click', function() {
        document.getElementById(`tab-basic-${recordId}`).click();
    });
    
    btnNextSusfacil.addEventListener('click', function() {
        if (!validateSusfacilTab()) return;
        
        checkSusfacil.style.display = 'inline';
        document.getElementById(`tab-procedures-${recordId}`).click();
    });
    
    btnFinishSusfacil.addEventListener('click', function() {
        if (!validateSusfacilTab()) return;
        
        checkSusfacil.style.display = 'inline';
        form.submit();
    });
    
    btnPrevProcedures.addEventListener('click', function() {
        const isEletivo = entryTypeSelect.value === 'ELETIVO';
        if (isEletivo) {
            document.getElementById(`tab-susfacil-${recordId}`).click();
        } else {
            document.getElementById(`tab-basic-${recordId}`).click();
        }
    });
    
    btnNextProcedures.addEventListener('click', function() {
        if (!validateProceduresTab()) return;
        
        checkProcedures.style.display = 'inline';
        document.getElementById(`tab-clinical-${recordId}`).click();
    });
    
    btnPrevClinical.addEventListener('click', function() {
        document.getElementById(`tab-procedures-${recordId}`).click();
    });
    
    btnFinishClinical.addEventListener('click', function() {
        if (!validateClinicalTab()) return;
        
        checkClinical.style.display = 'inline';
        form.submit();
    });
    
    function updateCidOptions() {
        if (addedProcedures.length === 0) {
            mainCidSelect.innerHTML = '<option value="">Adicione um procedimento primeiro</option>';
            return;
        }
        
        const mainProcedure = addedProcedures[0];
        const cids = mainProcedure.cids || [];
        
        if (cids.length === 0) {
            mainCidSelect.innerHTML = '<option value="">Nenhum CID disponível para o procedimento principal</option>';
            return;
        }
        
        mainCidSelect.innerHTML = '<option value="">Selecione o CID principal</option>' +
            cids.map(cid => `<option value="${cid.code}">${cid.code} - ${cid.description}</option>`).join('');
    }
    
    function updateProceduresList() {
        if (addedProcedures.length === 0) {
            proceduresList.innerHTML = '<p class="text-muted text-center mb-0"><i class="bi bi-info-circle me-2"></i>Nenhum procedimento adicionado</p>';
        } else {
            proceduresList.innerHTML = addedProcedures.map((proc, index) => `
                <div class="d-flex justify-content-between align-items-center p-2 mb-2 bg-white rounded border">
                    <div>
                        <strong>${proc.code}</strong> - ${proc.description}
                        ${index === 0 ? '<span class="badge bg-primary ms-2">Principal</span>' : ''}
                        <input type="hidden" name="procedure_codes[]" value="${proc.code}">
                        <input type="hidden" name="procedure_descriptions[]" value="${proc.description}">
                    </div>
                    <button type="button" class="btn btn-sm btn-outline-danger" onclick="removeProcedure${recordId}(${index})">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            `).join('');
        }
        updateCidOptions();
    }
    
    window[`removeProcedure${recordId}`] = function(index) {
        addedProcedures.splice(index, 1);
        updateProceduresList();
    };
    
    if (procedureCodeInput) {
        procedureCodeInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            const query = this.value.trim();
            
            if (selectedProcedure && query !== selectedProcedure.code) {
                procedureDescInput.value = '';
                selectedProcedure = null;
            }
            
            if (query.length < 2) {
                procedureSearchResults.innerHTML = '';
                procedureSearchResults.style.display = 'none';
                return;
            }
            
            searchTimeout = setTimeout(() => {
                fetch(`/nir/search_procedures?q=${encodeURIComponent(query)}`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.results && data.results.length > 0) {
                            procedureSearchResults.innerHTML = data.results.map((proc, index) => 
                                `<div class="procedure-result-item p-2" style="cursor:pointer; border-bottom:1px solid #eee;" data-index="${index}">
                                    <strong>${proc.code}</strong> - ${proc.description}
                                </div>`
                            ).join('');
                            procedureSearchResults.style.display = 'block';
                            procedureSearchResults.dataset.results = JSON.stringify(data.results);
                        } else {
                            procedureSearchResults.innerHTML = '<div class="p-2 text-muted"><i class="bi bi-info-circle me-2"></i>Nenhum procedimento encontrado</div>';
                            procedureSearchResults.style.display = 'block';
                        }
                    })
                    .catch(error => {
                        console.error('Erro ao buscar procedimento:', error);
                        procedureSearchResults.innerHTML = '<div class="p-2 text-danger"><i class="bi bi-exclamation-triangle me-2"></i>Erro ao buscar</div>';
                        procedureSearchResults.style.display = 'block';
                    });
            }, 300);
        });
        
        procedureSearchResults.addEventListener('click', function(e) {
            const item = e.target.closest('.procedure-result-item');
            if (item) {
                const results = JSON.parse(this.dataset.results || '[]');
                const index = parseInt(item.dataset.index);
                
                if (results[index]) {
                    selectedProcedure = results[index];
                    procedureCodeInput.value = selectedProcedure.code;
                    procedureDescInput.value = selectedProcedure.description;
                    procedureSearchResults.style.display = 'none';
                }
            }
        });
        
        document.addEventListener('click', function(e) {
            if (!procedureCodeInput.contains(e.target) && !procedureSearchResults.contains(e.target)) {
                procedureSearchResults.style.display = 'none';
            }
        });
    }
    
    if (addProcedureBtn) {
        addProcedureBtn.addEventListener('click', function() {
            if (!selectedProcedure) {
                alert('Por favor, selecione um procedimento da lista de busca antes de adicionar.');
                procedureCodeInput.focus();
                return;
            }
            
            if (addedProcedures.some(p => p.code === selectedProcedure.code)) {
                alert('Este procedimento já foi adicionado.');
                return;
            }
            
            addedProcedures.push(selectedProcedure);
            updateProceduresList();
            
            procedureCodeInput.value = '';
            procedureDescInput.value = '';
            selectedProcedure = null;
            procedureSearchResults.style.display = 'none';
        });
    }
    
    susfacilCheckbox.addEventListener('change', function() {
        if (this.checked) {
            aceiteDatetimeField.style.display = 'block';
            aceiteDatetimeInput.required = true;
        } else {
            aceiteDatetimeField.style.display = 'none';
            aceiteDatetimeInput.value = '';
            aceiteDatetimeInput.required = false;
        }
    });
    
    form.addEventListener('submit', function(e) {
        const finishButtons = form.querySelectorAll('[id^="btn-finish-"]');
        finishButtons.forEach(btn => {
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Processando...';
        });
    });
    
    updateVisibleTabs();
}

function cancelEvolveInline(recordId) {
    const detailRow = document.getElementById(`detail-observation-${recordId}`);
    if (detailRow) {
        detailRow.style.display = 'none';
        document.querySelectorAll(`button.toggle-detail-observation[data-detail-id="detail-observation-${recordId}"] .btn-text`).forEach(span => {
            if (span) span.textContent = 'Gerenciar Observação';
        });
    }
}

function cancelObservation(recordId, patientName) {
    document.getElementById('cancelPatientName').textContent = patientName;
    document.getElementById('cancelReason').value = '';
    const form = document.getElementById('cancelObservationForm');
    form.action = `/nir/observacao/${recordId}/cancelar`;
    
    const modal = new bootstrap.Modal(document.getElementById('cancelObservationModal'));
    modal.show();
}

document.getElementById('cancelObservationForm').addEventListener('submit', function(e) {
    const reason = document.getElementById('cancelReason').value.trim();
    
    if (!reason) {
        e.preventDefault();
        alert('Por favor, informe o motivo do cancelamento.');
        return false;
    }
    
    const submitBtn = this.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Processando...';
});
