(function (window, document) {
    const state = {
        modal: null,
        supplierId: null,
        selectors: {
            modalId: 'trackingModal',
            info: 'trackingSupplierInfo',
            form: 'trackingForm',
            history: 'trackingHistoryContainer',
            label: 'trackingModalLabel'
        },
        endpoints: {
            history: (supplierId) => `/feedback/suppliers/api/issue-history/${supplierId}`,
            addAction: (supplierId) => `/feedback/suppliers/add-issue-action/${supplierId}`
        }
    };

    function initTrackingModal(options = {}) {
        state.selectors = { ...state.selectors, ...options.selectors };
        state.endpoints = { ...state.endpoints, ...options.endpoints };

        const modalElement = document.getElementById(state.selectors.modalId);
        if (!modalElement || !window.bootstrap) {
            return;
        }

        state.modal = new window.bootstrap.Modal(modalElement);
        bindForm();
    }

    function openModal(supplier) {
        const label = document.getElementById(state.selectors.label);
        const info = document.getElementById(state.selectors.info);

        if (label) {
            label.innerHTML = `<i class="bi bi-clipboard-check-fill me-2"></i>Acompanhamento - ${supplier.name}`;
        }
        if (info) {
            info.textContent = supplier.cnpj ? `CNPJ: ${supplier.cnpj}` : '';
        }

        state.supplierId = supplier.id;
        loadHistory();
        state.modal?.show();
    }

    function bindForm() {
        const form = document.getElementById(state.selectors.form);
        if (!form) return;

        // Preview de arquivos anexados
        const fileInput = document.getElementById('attachments');
        const previewContainer = document.getElementById('attachmentPreview');
        
        if (fileInput && previewContainer) {
            fileInput.addEventListener('change', (e) => {
                const files = Array.from(e.target.files);
                if (files.length === 0) {
                    previewContainer.innerHTML = '';
                    return;
                }
                
                previewContainer.innerHTML = `
                    <div class="alert alert-info mb-0">
                        <i class="bi bi-paperclip me-2"></i>
                        <strong>${files.length} arquivo(s) selecionado(s):</strong>
                        <ul class="mb-0 mt-2">
                            ${files.map(f => `<li>${escapeHtml(f.name)} (${formatFileSize(f.size)})</li>`).join('')}
                        </ul>
                    </div>
                `;
            });
        }

        form.addEventListener('submit', (event) => {
            event.preventDefault();
            if (!state.supplierId) return;

            const submitBtn = form.querySelector('[type="submit"]');
            const original = submitBtn?.innerHTML;
            submitBtn && (submitBtn.disabled = true);
            submitBtn && (submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Salvando...');

            fetch(state.endpoints.addAction(state.supplierId), {
                method: 'POST',
                body: new FormData(form)
            })
                .then((response) => response.json())
                .then((data) => {
                    if (data.success) {
                        form.reset();
                        if (previewContainer) previewContainer.innerHTML = '';
                        SuppliersUtils?.showToast('Ação registrada com sucesso!', 'success');
                        loadHistory();
                    } else {
                        SuppliersUtils?.showToast(data.message || 'Erro ao registrar ação', 'danger');
                    }
                })
                .catch((error) => SuppliersUtils?.showToast(error.message, 'danger'))
                .finally(() => {
                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.innerHTML = original;
                    }
                });
        });
    }

    function loadHistory() {
        const historyContainer = document.getElementById(state.selectors.history);
        if (!historyContainer || !state.supplierId) return;

        historyContainer.innerHTML = '<div class="loading-state"><div class="spinner-border text-primary" role="status"></div></div>';

        SuppliersUtils?.fetchJSON(state.endpoints.history(state.supplierId))
            .then((data) => {
                if (data.success && data.history?.length) {
                    historyContainer.innerHTML = renderTimeline(data.history);
                    
                    // Adicionar event listeners para os lightbox triggers
                    historyContainer.querySelectorAll('.lightbox-trigger').forEach(trigger => {
                        trigger.addEventListener('click', (e) => {
                            e.preventDefault();
                            const imageUrl = trigger.getAttribute('data-image-url');
                            const filename = trigger.getAttribute('data-filename');
                            openImageLightbox(imageUrl, filename);
                        });
                    });
                } else {
                    historyContainer.innerHTML = `
                        <div class="empty-state">
                            <i class="bi bi-inbox"></i>
                            <p class="mt-3 mb-2"><strong>Nenhum registro de acompanhamento ainda</strong></p>
                            <p class="small">Adicione a primeira ação usando o formulário acima.</p>
                        </div>`;
                }
            })
            .catch((error) => {
                historyContainer.innerHTML = `
                    <div class="alert alert-danger">
                        <i class="bi bi-exclamation-triangle me-2"></i>
                        Erro ao carregar histórico: ${error.message}
                    </div>`;
            });
    }

    function renderTimeline(history = []) {
        return `
            <div class="timeline mt-4">
                ${history.map(renderTimelineItem).join('')}
            </div>
        `;
    }

    function isImageFile(filename) {
        const imageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'];
        return imageExtensions.some(ext => filename.toLowerCase().endsWith(ext));
    }

    function openImageLightbox(imageUrl, filename) {
        const modal = new bootstrap.Modal(document.getElementById('imageLightboxModal'));
        document.getElementById('lightboxImage').src = imageUrl;
        document.getElementById('lightboxImageTitle').textContent = filename;
        document.getElementById('lightboxDownload').href = imageUrl;
        document.getElementById('lightboxDownload').download = filename;
        modal.show();
    }

    function renderTimelineItem(item) {
        const attachmentsHtml = item.attachments && item.attachments.length > 0 
            ? `
                <div class="attachments-list mt-3">
                    <div class="small text-muted mb-2">
                        <i class="bi bi-paperclip me-1"></i>
                        <strong>Anexos (${item.attachments.length}):</strong>
                    </div>
                    <div class="d-flex flex-wrap gap-3">
                        ${item.attachments.map(att => {
                            if (isImageFile(att.filename)) {
                                return `
                                    <div class="attachment-image-preview">
                                        <a href="#" class="lightbox-trigger" data-image-url="${att.url}" data-filename="${escapeHtml(att.filename)}">
                                            <img src="${att.url}" alt="${escapeHtml(att.filename)}" class="img-thumbnail">
                                            <div class="image-filename">
                                                <i class="bi bi-image me-1"></i>
                                                ${escapeHtml(att.filename)}
                                            </div>
                                        </a>
                                    </div>
                                `;
                            } else {
                                return `
                                    <a href="${att.url}" class="btn btn-sm btn-outline-primary" download>
                                        <i class="bi bi-download me-1"></i>
                                        ${escapeHtml(att.filename)}
                                    </a>
                                `;
                            }
                        }).join('')}
                    </div>
                </div>
            `
            : '';

        return `
            <div class="timeline-item">
                <div class="timeline-marker ${item.action_color}"></div>
                <div class="timeline-line"></div>
                <div class="timeline-content">
                    <div class="d-flex justify-content-between align-items-start mb-3">
                        <div>
                            <span class="badge bg-${item.action_color} me-2">
                                <i class="${item.action_icon} me-1"></i>
                                ${item.action_label}
                            </span>
                        </div>
                        <small class="text-muted">
                            <i class="bi bi-clock me-1"></i>${SuppliersUtils?.formatDateTime(item.created_at)}
                        </small>
                    </div>

                    <p class="mb-3">${escapeHtml(item.description)}</p>

                    ${attachmentsHtml}

                    <div class="d-flex justify-content-end align-items-center mt-3">
                        <div class="small text-muted">
                            <i class="bi bi-person-circle me-1"></i>${item.user_name || ''}
                            ${item.user_job ? `<span class="text-muted">• ${item.user_job}</span>` : ''}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
    }

    function escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, (m) => map[m]);
    }

    window.SuppliersTracking = {
        initTrackingModal,
        openModal
    };
})(window, document);
