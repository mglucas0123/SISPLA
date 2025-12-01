// app/static/js/employees/dashboard.js

document.addEventListener('DOMContentLoaded', function () {
    const ctx = document.getElementById('evaluationsChart').getContext('2d');

    if (evaluationsData.labels.length > 0) {
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: evaluationsData.labels.reverse(),
                datasets: [{
                    label: 'Minha Pontuação',
                    data: evaluationsData.scores.reverse(),
                    fill: true,
                    borderColor: 'rgb(75, 192, 192)',
                    tension: 0.1,
                    backgroundColor: 'rgba(75, 192, 192, 0.2)',
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 10
                    }
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) {
                                    label += ': ';
                                }
                                if (context.parsed.y !== null) {
                                    label += context.parsed.y.toFixed(1) + ' / 10';
                                }
                                return label;
                            }
                        }
                    }
                }
            }
        });
    } else {
        const canvas = document.getElementById('evaluationsChart');
        const p = document.createElement('p');
        p.textContent = 'Não há dados de avaliação suficientes para exibir o gráfico.';
        p.classList.add('text-center', 'text-muted', 'mt-3');
        canvas.parentElement.replaceChild(p, canvas);
    }

    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    })
});
