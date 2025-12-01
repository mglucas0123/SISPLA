(function (window, document) {
    const state = {
        data: {},
        tooltip: null,
        selectors: {
            sortSelect: '#sortOrder',
            tableBody: '#rankingTable tbody',
            detailButton: '.toggle-detail-supplier',
            detailRow: '.detail-row',
            closeDetail: '.cancel-supplier-panel',
            trackingButton: '.open-tracking-modal',
            donutSegments: '.donut-segment',
            dataElement: '#suppliers-dashboard-data'
        }
    };

    function init(options = {}) {
        state.selectors = { ...state.selectors, ...options.selectors };
        SuppliersTracking?.initTrackingModal();
        initTooltip();
        loadDistributionData();
        bindSort();
        bindDetailToggles();
        bindTrackingButtons();
        bindDonutSegments();
    }

    function initTooltip() {
        state.tooltip = document.createElement('div');
        state.tooltip.className = 'donut-tooltip';
        document.body.appendChild(state.tooltip);
    }

    function loadDistributionData() {
        const element = document.querySelector(state.selectors.dataElement);
        if (!element) {
            state.data = {};
            return;
        }

        try {
            state.data = JSON.parse(element.textContent.trim());
        } catch (error) {
            console.error('Erro ao ler dados do dashboard', error);
            state.data = {};
        }
    }

    function bindSort() {
        const select = document.querySelector(state.selectors.sortSelect);
        if (!select) return;

        select.addEventListener('change', () => {
            const tbody = document.querySelector(state.selectors.tableBody);
            if (!tbody) return;

            const rows = Array.from(tbody.querySelectorAll('tr.supplier-row'));
            const sortType = select.value;

            rows.sort((a, b) => {
                if (sortType === 'desc') {
                    const priorityA = parseInt(a.dataset.priority) || 999;
                    const priorityB = parseInt(b.dataset.priority) || 999;
                    if (priorityA === priorityB) {
                        return parseFloat(b.dataset.score) - parseFloat(a.dataset.score);
                    }
                    return priorityA - priorityB;
                }
                if (sortType === 'asc') {
                    return parseFloat(a.dataset.score) - parseFloat(b.dataset.score);
                }
                return a.dataset.name.localeCompare(b.dataset.name);
            });

            rows.forEach((row, index) => {
                row.querySelector('.cell-id .badge').textContent = `#${index + 1}`;
                const supplierId = row.dataset.supplierId;
                const detailRow = document.getElementById(`detail-supplier-${supplierId}`);
                tbody.appendChild(row);
                if (detailRow) {
                    tbody.appendChild(detailRow);
                }
            });
        });
    }

    function bindDetailToggles() {
        const buttons = document.querySelectorAll(state.selectors.detailButton);
        buttons.forEach((button) => {
            button.addEventListener('click', (event) => {
                event.preventDefault();
                const detailId = button.dataset.detailId;
                const detailRow = document.getElementById(detailId);
                if (!detailRow) return;

                const isVisible = detailRow.style.display !== 'none';
                document.querySelectorAll(state.selectors.detailRow).forEach((row) => {
                    row.style.display = 'none';
                });
                detailRow.style.display = isVisible ? 'none' : 'table-row';
                if (!isVisible) {
                    detailRow.querySelector('.inline-detail-card')?.classList.add('animate-in');
                }
            });
        });

        document.querySelectorAll(state.selectors.closeDetail).forEach((button) => {
            button.addEventListener('click', () => {
                const supplierId = button.dataset.supplierId;
                const detailRow = document.getElementById(`detail-supplier-${supplierId}`);
                if (detailRow) {
                    detailRow.style.display = 'none';
                }
            });
        });
    }

    function bindTrackingButtons() {
        const buttons = document.querySelectorAll(state.selectors.trackingButton);
        if (!buttons.length) return;

        buttons.forEach((button) => {
            button.addEventListener('click', () => {
                SuppliersTracking?.openModal({
                    id: button.dataset.supplierId,
                    name: button.dataset.supplierName,
                    cnpj: button.dataset.supplierCnpj
                });
            });
        });
    }

    function bindDonutSegments() {
        const segments = document.querySelectorAll(state.selectors.donutSegments);
        if (!segments.length || !state.tooltip) return;

        segments.forEach((segment) => {
            segment.style.cursor = 'pointer';
            segment.addEventListener('mouseenter', () => handleSegmentEnter(segment));
            segment.addEventListener('mousemove', handleSegmentMove);
            segment.addEventListener('mouseleave', handleSegmentLeave);
        });
    }

    function handleSegmentEnter(segment) {
        const category = segment.dataset.category;
        const color = segment.dataset.color || '#333';
        const suppliers = state.data[category] || [];
        if (!suppliers.length) {
            state.tooltip.style.opacity = '0';
            return;
        }

        const title = segment.dataset.label || '';
        let html = `<div style="font-weight:600;margin-bottom:8px;color:${color};">${title}</div>`;
        html += '<div style="max-height:200px;overflow-y:auto;">';

        suppliers.forEach((supplier, index) => {
            if (index < 10) {
                html += `
                    <div style="padding:4px 0;font-size:13px;border-bottom:1px solid #f0f0f0;">
                        <strong>${supplier.name}</strong>
                        ${supplier.score > 0 ? `<span style="color:#7f8c8d;float:right;">${supplier.score}%</span>` : ''}
                    </div>
                `;
            }
        });

        if (suppliers.length > 10) {
            html += `<div style="padding:8px 0;color:#7f8c8d;font-size:12px;text-align:center;">+${suppliers.length - 10} fornecedor(es)...</div>`;
        }

        html += '</div>';

        state.tooltip.innerHTML = html;
        state.tooltip.style.borderLeftColor = color;
        state.tooltip.style.opacity = '1';
    }

    function handleSegmentMove(event) {
        if (!state.tooltip) return;
        state.tooltip.style.left = `${event.clientX + 15}px`;
        state.tooltip.style.top = `${event.clientY + 15}px`;
    }

    function handleSegmentLeave() {
        if (!state.tooltip) return;
        state.tooltip.style.opacity = '0';
    }

    window.SuppliersDashboard = {
        init
    };

    document.addEventListener('DOMContentLoaded', init);
})(window, document);
