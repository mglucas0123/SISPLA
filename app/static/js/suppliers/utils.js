(function (window, document) {
    const TOAST_DURATION = 3200;

    function showToast(message, type = 'info', duration = TOAST_DURATION) {
        const toast = document.createElement('div');
        toast.className = `toast-notification alert alert-${type}`;
        toast.innerHTML = `
            <i class="bi bi-${type === 'success' ? 'check-circle' : type === 'danger' ? 'exclamation-octagon' : 'info-circle'} me-2"></i>
            ${message}
        `;
        document.body.appendChild(toast);

        requestAnimationFrame(() => {
            toast.style.animation = 'slideInRight 0.3s ease-out forwards';
        });

        setTimeout(() => {
            toast.style.animation = 'slideInRight 0.3s ease-out reverse forwards';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }

    function formatDate(dateStr, locale = 'pt-BR') {
        if (!dateStr) return '';
        try {
            const date = new Date(dateStr);
            return date.toLocaleDateString(locale, { timeZone: 'America/Sao_Paulo' });
        } catch (err) {
            return dateStr;
        }
    }

    function formatDateTime(dateStr, locale = 'pt-BR') {
        if (!dateStr) return '';
        try {
            const date = new Date(dateStr.endsWith('Z') ? dateStr : `${dateStr}Z`);
            return date.toLocaleString(locale, {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
                timeZone: 'America/Sao_Paulo'
            });
        } catch (err) {
            return dateStr;
        }
    }

    function maskCNPJ(value = '') {
        return value
            .replace(/\D/g, '')
            .replace(/(\d{2})(\d)/, '$1.$2')
            .replace(/(\d{3})(\d)/, '$1.$2')
            .replace(/(\d{3})(\d)/, '$1/$2')
            .replace(/(\d{4})(\d)/, '$1-$2')
            .slice(0, 18);
    }

    function maskPhone(value = '') {
        const digits = value.replace(/\D/g, '').slice(0, 11);
        if (!digits) {
            return '';
        }

        let formatted = digits.replace(/(\d{2})(\d)/, '($1) $2');
        if (formatted.length > 10) {
            formatted = formatted.replace(/(\d{5})(\d)/, '$1-$2');
        } else {
            formatted = formatted.replace(/(\d{4})(\d)/, '$1-$2');
        }
        return formatted;
    }

    function fetchJSON(url, options = {}) {
        return fetch(url, options)
            .then((response) => {
                if (!response.ok) {
                    throw new Error(`Erro ${response.status}`);
                }
                return response.json();
            });
    }

    window.SuppliersUtils = {
        showToast,
        formatDate,
        formatDateTime,
        maskCNPJ,
        maskPhone,
        fetchJSON
    };
})(window, document);
