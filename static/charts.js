// JavaScript для работы с графиками Chart.js

// Инициализация всех графиков на странице
document.addEventListener('DOMContentLoaded', function() {
    // Инициализируем круговые диаграммы
    initPieCharts();
    
    // Инициализируем столбчатые диаграммы
    initBarCharts();
    
    // Инициализируем линейные графики
    initLineCharts();
    
    // Инициализируем события для обновления данных
    initChartEvents();
});

// Инициализация круговых диаграмм
function initPieCharts() {
    const pieCharts = document.querySelectorAll('.pie-chart');
    pieCharts.forEach(function(chartElement) {
        const ctx = chartElement.getContext('2d');
        const chartId = chartElement.id;
        
        // Получаем данные из data-атрибутов
        const labels = JSON.parse(chartElement.dataset.labels || '[]');
        const data = JSON.parse(chartElement.dataset.data || '[]');
        const colors = JSON.parse(chartElement.dataset.colors || '[]');
        
        new Chart(ctx, {
            type: 'pie',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: colors.length > 0 ? colors : generateColors(data.length),
                    borderWidth: 1,
                    borderColor: '#fff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        position: 'right',
                        labels: {
                            font: {
                                size: 12
                            }
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const label = context.label || '';
                                const value = context.raw || 0;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = total > 0 ? Math.round((value / total) * 100) : 0;
                                return `${label}: ${value} (${percentage}%)`;
                            }
                        }
                    }
                }
            }
        });
    });
}

// Инициализация столбчатых диаграмм
function initBarCharts() {
    const barCharts = document.querySelectorAll('.bar-chart');
    barCharts.forEach(function(chartElement) {
        const ctx = chartElement.getContext('2d');
        const chartId = chartElement.id;
        
        // Получаем данные из data-атрибутов
        const labels = JSON.parse(chartElement.dataset.labels || '[]');
        const data = JSON.parse(chartElement.dataset.data || '[]');
        
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: chartElement.dataset.label || 'Данные',
                    data: data,
                    backgroundColor: 'rgba(54, 162, 235, 0.6)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1,
                            precision: 0
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    }
                }
            }
        });
    });
}

// Инициализация линейных графиков
function initLineCharts() {
    const lineCharts = document.querySelectorAll('.line-chart');
    lineCharts.forEach(function(chartElement) {
        const ctx = chartElement.getContext('2d');
        const chartId = chartElement.id;
        
        // Получаем данные из data-атрибутов
        const labels = JSON.parse(chartElement.dataset.labels || '[]');
        const data = JSON.parse(chartElement.dataset.data || '[]');
        
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: chartElement.dataset.label || 'Тренд',
                    data: data,
                    backgroundColor: 'rgba(75, 192, 192, 0.2)',
                    borderColor: 'rgba(75, 192, 192, 1)',
                    borderWidth: 2,
                    tension: 0.1,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1,
                            precision: 0
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    }
                }
            }
        });
    });
}

// Инициализация событий для обновления данных
function initChartEvents() {
    // Обработчик для фильтров временного периода
    const periodSelects = document.querySelectorAll('.period-select');
    periodSelects.forEach(function(select) {
        select.addEventListener('change', function() {
            const chartId = this.dataset.chartId;
            const period = this.value;
            updateChartData(chartId, period);
        });
    });
}

// Обновление данных графика
function updateChartData(chartId, period) {
    // Здесь можно реализовать AJAX запрос для обновления данных
    console.log(`Обновление графика ${chartId} для периода ${period}`);
    // В реальной реализации здесь будет fetch запрос к endpoint с данными
}

// Генерация цветов для диаграмм
function generateColors(count) {
    const colors = [
        'rgba(255, 99, 132, 0.7)',
        'rgba(54, 162, 235, 0.7)',
        'rgba(255, 206, 86, 0.7)',
        'rgba(75, 192, 192, 0.7)',
        'rgba(153, 102, 255, 0.7)',
        'rgba(255, 159, 64, 0.7)',
        'rgba(199, 199, 199, 0.7)',
        'rgba(83, 102, 255, 0.7)',
        'rgba(255, 99, 255, 0.7)',
        'rgba(99, 255, 132, 0.7)'
    ];
    
    return colors.slice(0, count);
}

// Функция для создания графика на лету
function createChart(elementId, type, labels, data, options = {}) {
    const ctx = document.getElementById(elementId).getContext('2d');
    
    const defaultOptions = {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
            legend: {
                display: true,
                position: 'top'
            }
        }
    };
    
    const mergedOptions = { ...defaultOptions, ...options };
    
    return new Chart(ctx, {
        type: type,
        data: {
            labels: labels,
            datasets: [{
                label: options.label || 'Данные',
                data: data,
                backgroundColor: options.backgroundColor || generateColors(labels.length),
                borderColor: options.borderColor || '#fff',
                borderWidth: options.borderWidth || 1
            }]
        },
        options: mergedOptions
    });
}