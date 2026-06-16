// charts.js - Chart visualizations for Payment Simulator Dashboard
window.Charts = {
  paymentChart: null,
  webhookChart: null,
  failureChart: null,

  init() {
    const fontConfig = {
      family: "'Inter', sans-serif",
      size: 11
    };

    // 1. Payment Status Donut Chart
    const ctxPayment = document.getElementById('chart-payment-status').getContext('2d');
    this.paymentChart = new Chart(ctxPayment, {
      type: 'doughnut',
      data: {
        labels: ['Captured', 'Failed', 'Refunded', 'Pending'],
        datasets: [{
          data: [0, 0, 0, 0],
          backgroundColor: ['#10b981', '#ef4444', '#f59e0b', '#6b7280'],
          borderColor: '#111827',
          borderWidth: 2,
          hoverOffset: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#1e293b',
            titleColor: '#f3f4f6',
            bodyColor: '#f3f4f6',
            borderColor: 'rgba(255, 255, 255, 0.08)',
            borderWidth: 1,
            padding: 10,
            displayColors: true
          }
        },
        cutout: '70%'
      }
    });

    // 2. Webhook Status Donut Chart
    const ctxWebhook = document.getElementById('chart-webhook-status').getContext('2d');
    this.webhookChart = new Chart(ctxWebhook, {
      type: 'doughnut',
      data: {
        labels: ['Delivered', 'Retrying', 'Exhausted', 'Failed'],
        datasets: [{
          data: [0, 0, 0, 0],
          backgroundColor: ['#10b981', '#f59e0b', '#ef4444', '#6b7280'],
          borderColor: '#111827',
          borderWidth: 2,
          hoverOffset: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#1e293b',
            titleColor: '#f3f4f6',
            bodyColor: '#f3f4f6',
            borderColor: 'rgba(255, 255, 255, 0.08)',
            borderWidth: 1,
            padding: 10,
            displayColors: true
          }
        },
        cutout: '70%'
      }
    });

    // 3. Failure Breakdown Horizontal Bar Chart
    const ctxFailure = document.getElementById('chart-failures').getContext('2d');
    this.failureChart = new Chart(ctxFailure, {
      type: 'bar',
      data: {
        labels: [],
        datasets: [{
          label: 'Failures',
          data: [],
          backgroundColor: 'rgba(239, 68, 68, 0.75)',
          borderColor: '#ef4444',
          borderWidth: 1,
          borderRadius: 4,
          barThickness: 16
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#1e293b',
            titleColor: '#f3f4f6',
            bodyColor: '#f3f4f6',
            borderColor: 'rgba(255, 255, 255, 0.08)',
            borderWidth: 1,
            padding: 10
          }
        },
        scales: {
          x: {
            grid: { color: 'rgba(255, 255, 255, 0.05)' },
            ticks: {
              color: '#9ca3af',
              font: fontConfig,
              stepSize: 1
            }
          },
          y: {
            grid: { display: false },
            ticks: {
              color: '#9ca3af',
              font: fontConfig
            }
          }
        }
      }
    });
  },

  update(stats) {
    if (!stats) return;

    // Update Payments Chart
    const pCaptured = stats.payments?.by_status?.captured || 0;
    const pFailed = stats.payments?.by_status?.failed || 0;
    const pRefunded = stats.payments?.by_status?.refunded || 0;
    const pPending = stats.payments?.by_status?.pending || 0;
    
    this.paymentChart.data.datasets[0].data = [pCaptured, pFailed, pRefunded, pPending];
    this.paymentChart.update();
    this.renderLegend('legend-payment-status', this.paymentChart);

    // Update Webhooks Chart
    const wDelivered = stats.webhooks?.by_status?.delivered || 0;
    const wRetrying = stats.webhooks?.by_status?.retrying || 0;
    const wExhausted = stats.webhooks?.by_status?.exhausted || 0;
    const wFailed = stats.webhooks?.by_status?.failed || 0;

    this.webhookChart.data.datasets[0].data = [wDelivered, wRetrying, wExhausted, wFailed];
    this.webhookChart.update();
    this.renderLegend('legend-webhook-status', this.webhookChart);

    // Update Failures Chart
    const failures = stats.payments?.failure_breakdown || {};
    const labels = Object.keys(failures).map(f => f.replace(/_/g, ' ').toUpperCase());
    const data = Object.values(failures);

    this.failureChart.data.labels = labels;
    this.failureChart.data.datasets[0].data = data;
    this.failureChart.update();
  },

  renderLegend(containerId, chart) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const data = chart.data;
    const dataset = data.datasets[0];
    
    container.innerHTML = '';
    data.labels.forEach((label, i) => {
      const val = dataset.data[i];
      if (val === undefined) return;

      const item = document.createElement('div');
      item.className = 'legend-item';
      
      const color = document.createElement('span');
      color.className = 'legend-color';
      color.style.backgroundColor = dataset.backgroundColor[i];
      
      const text = document.createElement('span');
      text.innerHTML = `<strong>${val}</strong> ${label}`;
      text.style.color = '#9ca3af';

      item.appendChild(color);
      item.appendChild(text);
      container.appendChild(item);
    });
  }
};
