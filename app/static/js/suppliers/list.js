(function (window, document) {
    const bootstrap = window.bootstrap;
    const utils = window.SuppliersUtils || {};

    const state = {
        initialized: false,
        rows: [],
        detailRows: new Map(),
        totalSuppliers: 0,
        endpoints: {},
        permissions: {},
        elements: {}
    };

    function init(config = {}) {
        if (state.initialized) {
            return;
        }

        state.initialized = true;
        state.totalSuppliers = Number(config.totalSuppliers) || 0;
        state.endpoints = config.endpoints || {};
        state.permissions = config.permissions || {};

        cacheDom();
        hydrateScoreBars();
        bindFilters();
        bindTableActions();
        bindExport();
        bindEvaluatorActions();
        bindMasks();
        bindFormReset();

        applyFilters();
    }

    function cacheDom() {
        state.elements.searchInput = document.getElementById('searchInput');
        state.elements.clearSearch = document.getElementById('clearSearch');
        state.elements.statusFilter = document.getElementById('filterStatus');
        state.elements.scoreFilter = document.getElementById('filterScore');
        state.elements.sortSelect = document.getElementById('sortBy');
        state.elements.clearFilters = document.getElementById('clearFilters');
        state.elements.resultsCount = document.getElementById('resultsCount');
        state.elements.exportButton = document.getElementById('exportSuppliers');
        state.elements.table = document.getElementById('suppliersTable');
        state.elements.tableBody = state.elements.table ? state.elements.table.querySelector('tbody') : null;
        state.elements.registerModal = document.getElementById('registerModal');
        state.elements.registerForm = document.getElementById('registerSupplierForm');
        state.elements.editModal = document.getElementById('editModal');
        state.elements.editForm = document.getElementById('editSupplierForm');
        state.elements.deactivateModal = document.getElementById('deactivateModal');
        state.elements.deactivateForm = document.getElementById('deactivateForm');
        state.elements.deactivateName = document.getElementById('supplierNameModal');
        state.elements.evaluatorSearch = document.getElementById('evaluatorSearch');
        state.elements.selectAllEvaluators = document.getElementById('selectAllEvaluators');
        state.elements.clearAllEvaluators = document.getElementById('clearAllEvaluators');
        state.elements.selectedCount = document.getElementById('selectedCount');

        if (state.elements.tableBody) {
            state.rows = Array.from(state.elements.tableBody.querySelectorAll('.supplier-row'));
            state.rows.forEach((row) => {
                const supplierId = row.dataset.supplierId;
                const detailsRow = state.elements.tableBody.querySelector(
                    `.details-row[data-supplier-id="${supplierId}"]`
                );
                if (detailsRow) {
                    state.detailRows.set(supplierId, detailsRow);
                }
            });
        }
    }

    function hydrateScoreBars() {
        document.querySelectorAll('.score-fill[data-score-fill]').forEach((bar) => {
            const value = parseFloat(bar.dataset.scoreFill || '0');
            bar.style.width = `${Math.max(0, Math.min(100, value || 0))}%`;
        });
    }

    function bindFilters() {
        if (state.elements.searchInput) {
            state.elements.searchInput.addEventListener('input', debounce(applyFilters, 200));
        }
        if (state.elements.clearSearch) {
            state.elements.clearSearch.addEventListener('click', () => {
                if (state.elements.searchInput) {
                    state.elements.searchInput.value = '';
                }
                applyFilters();
            });
        }
        state.elements.statusFilter?.addEventListener('change', applyFilters);
        state.elements.scoreFilter?.addEventListener('change', applyFilters);
        state.elements.sortSelect?.addEventListener('change', applyFilters);
        state.elements.clearFilters?.addEventListener('click', () => {
            resetFilters();
            applyFilters();
        });
    }

    function bindTableActions() {
        if (!state.elements.tableBody) {
            return;
        }

        state.elements.tableBody.addEventListener('click', (event) => {
            const actionButton = event.target.closest('[data-action]');
            if (!actionButton) {
                return;
            }

            const supplierId = actionButton.dataset.supplierId;
            switch (actionButton.dataset.action) {
                case 'toggle-row':
                    toggleRow(actionButton);
                    break;
                case 'open-edit':
                    openEditModal(supplierId);
                    break;
                case 'open-deactivate':
                    openDeactivateModal(supplierId, actionButton.dataset.supplierName);
                    break;
                default:
                    break;
            }
        });
    }

    function bindExport() {
        state.elements.exportButton?.addEventListener('click', exportVisibleRows);
    }

    function bindEvaluatorActions() {
        if (!state.permissions.manageEvaluators) {
            return;
        }

        state.elements.evaluatorSearch?.addEventListener('input', (event) => {
            const term = (event.target.value || '').toLowerCase();
            document.querySelectorAll('.evaluator-item-modern').forEach((item) => {
                const name = item.dataset.name || '';
                const username = item.dataset.username || '';
                const jobTitle = item.dataset.jobtitle || '';
                const matches = name.includes(term) || username.includes(term) || jobTitle.includes(term);
                item.style.display = matches ? 'flex' : 'none';
            });
        });

        state.elements.selectAllEvaluators?.addEventListener('click', () => {
            document.querySelectorAll('.evaluator-item-modern').forEach((item) => {
                if (item.style.display !== 'none') {
                    const checkbox = item.querySelector('.evaluator-checkbox');
                    if (checkbox) {
                        checkbox.checked = true;
                    }
                }
            });
            updateEvaluatorCount();
        });

        state.elements.clearAllEvaluators?.addEventListener('click', () => {
            document.querySelectorAll('.evaluator-checkbox').forEach((checkbox) => {
                checkbox.checked = false;
            });
            updateEvaluatorCount();
        });

        document.querySelectorAll('.evaluator-checkbox').forEach((checkbox) => {
            checkbox.addEventListener('change', updateEvaluatorCount);
        });
    }

    function bindMasks() {
        attachMask('register_cnpj', utils.maskCNPJ);
        attachMask('edit_cnpj', utils.maskCNPJ);
        attachMask('register_phone', utils.maskPhone);
        attachMask('edit_phone', utils.maskPhone);
    }

    function bindFormReset() {
        if (state.elements.registerModal && state.elements.registerForm) {
            state.elements.registerModal.addEventListener('hidden.bs.modal', () => {
                state.elements.registerForm.reset();
            });
        }
    }

    function applyFilters() {
        if (!state.rows.length) {
            updateResultsCount(0);
            return;
        }

        const searchTerm = (state.elements.searchInput?.value || '').trim().toLowerCase();
        const statusFilter = state.elements.statusFilter?.value || 'all';
        const scoreFilter = state.elements.scoreFilter?.value || 'all';
        const sortBy = state.elements.sortSelect?.value || 'name';

        let visibleRows = state.rows.filter((row) => filterRow(row, { searchTerm, statusFilter, scoreFilter }));
        visibleRows = sortRows(visibleRows, sortBy);

        updateRowVisibility(visibleRows);
        updateResultsCount(visibleRows.length);
    }

    function filterRow(row, filters) {
        const name = row.dataset.name || '';
        const service = row.dataset.service || '';
        const contact = row.dataset.contact || '';
        const status = row.dataset.status;
        const score = parseFloat(row.dataset.score || '0');

        if (filters.searchTerm) {
            const haystack = `${name} ${service} ${contact}`;
            if (!haystack.includes(filters.searchTerm)) {
                return false;
            }
        }

        if (filters.statusFilter !== 'all' && filters.statusFilter !== status) {
            return false;
        }

        if (filters.scoreFilter !== 'all') {
            if (filters.scoreFilter === 'excellent' && score < 80) return false;
            if (filters.scoreFilter === 'good' && (score < 60 || score >= 80)) return false;
            if (filters.scoreFilter === 'poor' && score >= 60) return false;
            if (filters.scoreFilter === 'not_evaluated' && score > 0) return false;
        }

        return true;
    }

    function sortRows(rows, sortBy) {
        return [...rows].sort((a, b) => {
            switch (sortBy) {
                case 'name':
                    return a.dataset.name.localeCompare(b.dataset.name);
                case 'score-desc':
                    return parseFloat(b.dataset.score || '0') - parseFloat(a.dataset.score || '0');
                case 'score-asc':
                    return parseFloat(a.dataset.score || '0') - parseFloat(b.dataset.score || '0');
                case 'evaluations':
                    return parseInt(b.dataset.evaluations || '0', 10) - parseInt(a.dataset.evaluations || '0', 10);
                case 'recent':
                default:
                    return 0;
            }
        });
    }

    function updateRowVisibility(visibleRows) {
        const visibleSet = new Set(visibleRows);
        state.rows.forEach((row) => {
            const detailsRow = state.detailRows.get(row.dataset.supplierId);
            const shouldShow = visibleSet.has(row);
            row.style.display = shouldShow ? '' : 'none';
            if (detailsRow) {
                detailsRow.style.display = shouldShow ? '' : 'none';
            }
        });

        if (!state.elements.tableBody) {
            return;
        }

        visibleRows.forEach((row) => {
            state.elements.tableBody.appendChild(row);
            const detailsRow = state.detailRows.get(row.dataset.supplierId);
            if (detailsRow) {
                state.elements.tableBody.appendChild(detailsRow);
            }
        });
    }

    function updateResultsCount(visibleCount) {
        if (!state.elements.resultsCount) {
            return;
        }
        const total = state.totalSuppliers || state.rows.length;
        state.elements.resultsCount.textContent = `Mostrando ${visibleCount} de ${total} fornecedores`;
    }

    function resetFilters() {
        if (state.elements.searchInput) {
            state.elements.searchInput.value = '';
        }
        if (state.elements.statusFilter) {
            state.elements.statusFilter.value = 'all';
        }
        if (state.elements.scoreFilter) {
            state.elements.scoreFilter.value = 'all';
        }
        if (state.elements.sortSelect) {
            state.elements.sortSelect.value = 'name';
        }
    }

    function toggleRow(button) {
        const row = button.closest('tr');
        if (!row) {
            return;
        }
        const supplierId = row.dataset.supplierId;
        const detailsRow = state.detailRows.get(supplierId);
        const icon = button.querySelector('i');

        if (!detailsRow) {
            return;
        }

        detailsRow.classList.toggle('expanded');
        if (icon) {
            icon.classList.toggle('bi-chevron-right');
            icon.classList.toggle('bi-chevron-down');
        }
    }

    function exportVisibleRows() {
        if (!state.rows.length) {
            notify('Nenhum fornecedor disponível para exportação.', 'warning');
            return;
        }

        const visibleRows = state.rows.filter((row) => row.style.display !== 'none');
        if (!visibleRows.length) {
            notify('Nenhum fornecedor corresponde aos filtros atuais.', 'warning');
            return;
        }

        const header = [
            'Nome Fantasia',
            'Razão Social',
            'Contato',
            'Tipo de Serviço',
            'Performance (%)',
            'Status',
            'Avaliações',
            'Telefone',
            'Email',
            'CNPJ',
            'Responsáveis'
        ];

        const lines = visibleRows.map((row) => buildCsvLine(row));
        const csv = [header, ...lines]
            .map((cells) => cells.map(escapeCsvCell).join(','))
            .join('\n');

        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `fornecedores_${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(link);
        link.click();
        link.remove();
    }

    function buildCsvLine(row) {
        const nameElement = row.querySelector('.company-name');
        const name = nameElement?.textContent.trim() || '-';
        
        // Buscar razão social se houver nome fantasia
        const legalNameElement = row.querySelector('.company-legal-name');
        const legalName = legalNameElement?.textContent.replace(/Razão Social:/g, '').trim() || name;
        
        const contact = row.querySelector('.company-contact')?.textContent.trim() || '-';
        const service = row.querySelector('.service-badge')?.textContent.trim() || '-';
        const score = row.querySelector('.score-value')?.textContent.replace('%', '').trim() || '0';
        const status = row.querySelector('.status-badge')?.textContent.trim() || '-';
        const evalCount = row.querySelector('.eval-count strong')?.textContent.trim() || '0';

        const supplierId = row.dataset.supplierId;
        const detailsRow = state.detailRows.get(supplierId);
        let phone = '-';
        let email = '-';
        let cnpj = '-';
        let evaluators = '-';

        if (detailsRow) {
            detailsRow.querySelectorAll('.detail-item').forEach((item) => {
                const icon = item.querySelector('i');
                const text = item.querySelector('span')?.textContent.trim();
                if (!icon || !text) {
                    return;
                }
                if (icon.classList.contains('bi-phone')) phone = text;
                if (icon.classList.contains('bi-envelope')) email = text;
                if (icon.classList.contains('bi-card-text')) cnpj = text;
            });

            const evaluatorNames = Array.from(detailsRow.querySelectorAll('.evaluator-item-detail strong')).map((el) =>
                el.textContent.trim()
            );
            if (evaluatorNames.length) {
                evaluators = evaluatorNames.join('; ');
            }
        }

        return [name, legalName, contact, service, score, status, evalCount, phone, email, cnpj, evaluators];
    }

    function escapeCsvCell(value) {
        const safe = value.replace(/"/g, '""');
        return `"${safe}"`;
    }

    function openDeactivateModal(supplierId, supplierName) {
        if (!supplierId || !state.elements.deactivateModal || !state.elements.deactivateForm) {
            return;
        }

        const action = buildUrl(state.endpoints.deactivate, supplierId);
        if (!action) {
            return;
        }

        state.elements.deactivateForm.action = action;
        if (state.elements.deactivateName) {
            state.elements.deactivateName.textContent = supplierName || '';
        }

        showModal(state.elements.deactivateModal);
    }

    function openEditModal(supplierId) {
        if (!supplierId || !state.elements.editModal || !state.elements.editForm) {
            return;
        }

        const statsUrl = buildUrl(state.endpoints.stats, supplierId);
        if (!statsUrl) {
            return;
        }

        (utils.fetchJSON ? utils.fetchJSON(statsUrl) : fetch(statsUrl).then((res) => res.json()))
            .then((data) => {
                setInputValue('edit_company_name', data.company_name);
                setInputValue('edit_trade_name', data.trade_name);
                setInputValue('edit_cnpj', data.cnpj);
                setInputValue('edit_service_type', data.service_type);
                setInputValue('edit_contact_name', data.contact_name);
                setInputValue('edit_phone', data.phone);
                setInputValue('edit_email', data.email);
                setInputValue('edit_notes', data.notes);

                const formAction = buildUrl(state.endpoints.edit, supplierId);
                if (formAction) {
                    state.elements.editForm.action = formAction;
                }

                if (state.permissions.manageEvaluators) {
                    loadAssignedEvaluators(supplierId);
                }

                showModal(state.elements.editModal);
            })
            .catch(() => {
                notify('Erro ao carregar dados do fornecedor.', 'danger');
            });
    }

    function loadAssignedEvaluators(supplierId) {
        const evaluatorsUrl = buildUrl(state.endpoints.evaluators, supplierId);
        if (!evaluatorsUrl) {
            return;
        }

        (utils.fetchJSON ? utils.fetchJSON(evaluatorsUrl) : fetch(evaluatorsUrl).then((res) => res.json()))
            .then((evaluators) => {
                document.querySelectorAll('.evaluator-checkbox').forEach((checkbox) => {
                    checkbox.checked = evaluators.some((ev) => String(ev.id) === checkbox.value);
                });
                updateEvaluatorCount();
            })
            .catch(() => {
                notify('Não foi possível carregar os avaliadores atribuídos.', 'warning');
            });
    }

    function attachMask(elementId, maskFn) {
        const element = document.getElementById(elementId);
        if (!element || typeof maskFn !== 'function') {
            return;
        }
        element.addEventListener('input', (event) => {
            event.target.value = maskFn(event.target.value || '');
        });
    }

    function setInputValue(id, value) {
        const input = document.getElementById(id);
        if (input) {
            input.value = value || '';
        }
    }

    function updateEvaluatorCount() {
        if (!state.elements.selectedCount) {
            return;
        }
        const selected = document.querySelectorAll('.evaluator-checkbox:checked').length;
        state.elements.selectedCount.textContent = selected;
    }

    function buildUrl(template, supplierId) {
        if (!template || !supplierId) {
            return null;
        }
        return template.replace('{id}', supplierId);
    }

    function showModal(element) {
        if (!element) {
            return;
        }
        if (bootstrap && typeof bootstrap.Modal === 'function') {
            bootstrap.Modal.getOrCreateInstance(element).show();
        } else {
            element.classList.add('show');
        }
    }

    function notify(message, type = 'info') {
        if (utils.showToast) {
            utils.showToast(message, type);
        } else {
            window.alert(message);
        }
    }

    function debounce(fn, delay = 200) {
        let timeoutId;
        return (...args) => {
            clearTimeout(timeoutId);
            timeoutId = window.setTimeout(() => fn.apply(null, args), delay);
        };
    }

    window.SuppliersList = { init };
})(window, document);
