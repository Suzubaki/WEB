// static/charts.js - Графики Chart.js
document.addEventListener('DOMContentLoaded', function() {
    initPieCharts();
    initBarCharts();
    initLineCharts();
});

function initPieCharts() {
    const pieCharts = document.querySelectorAll('.pie-chart');
    pieCharts.forEach(function(chartElement) {
        const ctx = chartElement.getContext('2d');
        const labels = JSON.parse(chartElement.dataset.labels || '[]');
        const data = JSON.parse(chartElement.dataset.data || '[]');
        const colors = JSON.parse(chartElement.dataset.colors || '[]');
        
        new Chart(ctx, {
            type: 'pie',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: colors.length > 0 ? colors : ['#FF6384', '#36A2EB', '#FFCE56'],
                    borderWidth: 1,
                    borderColor: '#fff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: { position: 'right' }
                }
            }
        });
    });
}

function initBarCharts() {
    const barCharts = document.querySelectorAll('.bar-chart');
    barCharts.forEach(function(chartElement) {
        const ctx = chartElement.getContext('2d');
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
                    y: { beginAtZero: true }
                }
            }
        });
    });
}

function initLineCharts() {
    const lineCharts = document.querySelectorAll('.line-chart');
    lineCharts.forEach(function(chartElement) {
        const ctx = chartElement.getContext('2d');
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
                    y: { beginAtZero: true }
                }
            }
        });
    });
}
