// app.js - Main dashboard application controller
window.App = {
  selectedTab: 'dashboard',
  pollingInterval: null,
  activeOrderRef: null,
  activePaymentRef: null,

  init() {
    // 1. Setup Tab Navigation
    document.querySelectorAll('.nav-item').forEach(item => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        const tab = item.getAttribute('data-tab');
        this.switchTab(tab);
      });
    });

    // 2. Setup Form Submissions
    document.getElementById('form-order').addEventListener('submit', (e) => {
      e.preventDefault();
      this.handleCreateOrder();
    });

    document.getElementById('form-payment').addEventListener('submit', (e) => {
      e.preventDefault();
      this.handleProcessPayment();
    });

    document.getElementById('form-refund').addEventListener('submit', (e) => {
      e.preventDefault();
      this.handleIssueRefund();
    });

    // 3. Initialize Charts
    if (window.Charts) {
      window.Charts.init();
    }

    // 4. Start Polling & Setup Initial State
    this.checkHealth();
    this.refresh();
    this.startPolling();
    this.generateIdempotencyKey();

    // Attach click listener for webhook table inspection
    document.getElementById('tbody-webhooks').addEventListener('click', (e) => {
      const row = e.target.closest('tr');
      if (row && row.dataset.eventId) {
        this.inspectWebhook(row.dataset.eventId);
      }
    });

    // Attach click listeners for transactions modal view
    document.getElementById('tbody-transactions').addEventListener('click', (e) => {
      const row = e.target.closest('tr');
      if (row && row.dataset.txnDetails) {
        this.showModal('Transaction JSON Details', row.dataset.txnDetails);
      }
    });

    // Attach click listeners for refunds modal view
    document.getElementById('tbody-refunds').addEventListener('click', (e) => {
      const row = e.target.closest('tr');
      if (row && row.dataset.refundDetails) {
        this.showModal('Refund JSON Details', row.dataset.refundDetails);
      }
    });
  },

  switchTab(tabId) {
    if (!tabId) return;
    this.selectedTab = tabId;

    // Toggle active link
    document.querySelectorAll('.nav-item').forEach(item => {
      if (item.getAttribute('data-tab') === tabId) {
        item.classList.add('active');
      } else {
        item.classList.remove('active');
      }
    });

    // Toggle active tab content
    document.querySelectorAll('.tab-content').forEach(content => {
      if (content.id === `tab-${tabId}`) {
        content.classList.add('active');
      } else {
        content.classList.remove('active');
      }
    });

    // Update Header Title
    const titleMap = {
      dashboard: 'Dashboard',
      simulator: 'Simulator Lab',
      transactions: 'Transactions Registry',
      webhooks: 'Webhook Deliveries',
      refunds: 'Refunds Console',
      retry: 'Retry Queue Monitor',
      pitfalls: 'Pitfalls Playground'
    };
    const subtitleMap = {
      dashboard: 'Real-time payment gateway monitoring',
      simulator: 'Step-by-step transaction walkthrough & failure injection',
      transactions: 'Audit log of all order lifecycles',
      webhooks: 'HMAC signature logs and delivery attempts',
      refunds: 'Processing full and partial payment reversals',
      retry: 'Exponential backoff visualizer and retry queue',
      pitfalls: 'Common merchant integration vulnerabilities and how to solve them'
    };

    document.getElementById('page-title').textContent = titleMap[tabId] || 'Dashboard';
    document.getElementById('page-subtitle').textContent = subtitleMap[tabId] || '';

    // Specific tab loads
    if (tabId === 'transactions') this.loadTransactions();
    if (tabId === 'webhooks') this.loadWebhooks();
    if (tabId === 'refunds') this.loadRefunds();
    if (tabId === 'retry') this.loadRetryQueue();
  },

  startPolling() {
    if (this.pollingInterval) clearInterval(this.pollingInterval);
    this.pollingInterval = setInterval(() => {
      this.checkHealth();
      this.refreshStatsAndFeed();
      if (this.selectedTab === 'webhooks') this.loadWebhooks();
      if (this.selectedTab === 'transactions') this.loadTransactions();
      if (this.selectedTab === 'refunds') this.loadRefunds();
      if (this.selectedTab === 'retry') this.loadRetryQueue();
    }, 3000);
  },

  async checkHealth() {
    try {
      const res = await fetch('/health');
      const dot = document.getElementById('status-dot');
      const txt = document.getElementById('status-text');
      if (res.ok) {
        dot.className = 'status-dot online';
        txt.textContent = 'Engine Connected';
      } else {
        dot.className = 'status-dot offline';
        txt.textContent = 'Server Error';
      }
    } catch {
      const dot = document.getElementById('status-dot');
      const txt = document.getElementById('status-text');
      dot.className = 'status-dot offline';
      txt.textContent = 'Engine Offline';
    }
  },

  refresh() {
    this.refreshStatsAndFeed();
    if (this.selectedTab === 'transactions') this.loadTransactions();
    if (this.selectedTab === 'webhooks') this.loadWebhooks();
    if (this.selectedTab === 'refunds') this.loadRefunds();
    if (this.selectedTab === 'retry') this.loadRetryQueue();
  },

  async refreshStatsAndFeed() {
    try {
      const stats = await window.API.getStats();
      this.updateStatsUI(stats);
      if (window.Charts) {
        window.Charts.update(stats);
      }
      this.loadLiveFeed();
    } catch (err) {
      console.error('Error refreshing telemetry:', err);
    }
  },

  updateStatsUI(stats) {
    if (!stats || !stats.summary) return;
    const s = stats.summary;
    document.getElementById('val-revenue').textContent = `₹${s.total_revenue.toLocaleString('en-IN')}`;
    document.getElementById('val-orders').textContent = s.total_orders;
    document.getElementById('val-success').textContent = `${s.success_rate}%`;
    document.getElementById('val-webhooks').textContent = stats.webhooks?.total || 0;
    document.getElementById('val-refunds').textContent = `₹${s.total_refunded_amount.toLocaleString('en-IN')}`;
    document.getElementById('val-duplicates').textContent = stats.webhooks?.duplicates_detected || 0;

    // Sidebar webhooks warning badge if duplicates detected
    const whBadge = document.getElementById('badge-webhooks');
    const dupCount = stats.webhooks?.duplicates_detected || 0;
    whBadge.textContent = stats.webhooks?.total || 0;
    if (dupCount > 0) {
      whBadge.className = 'nav-badge webhook-badge warning-badge';
      whBadge.title = `${dupCount} duplicate webhooks detected!`;
    } else {
      whBadge.className = 'nav-badge';
      whBadge.title = '';
    }

    const txBadge = document.getElementById('badge-transactions');
    txBadge.textContent = s.total_orders;
  },

  async loadLiveFeed() {
    try {
      const txns = await window.API.getTransactions();
      const feed = document.getElementById('live-feed');
      if (!txns.orders || txns.orders.length === 0) {
        feed.innerHTML = '<div class="feed-empty">No transactions yet. Use the Simulator to create some.</div>';
        return;
      }

      feed.innerHTML = '';
      // Show only top 5 recent orders
      txns.orders.slice(0, 5).forEach(order => {
        const item = document.createElement('div');
        item.className = 'feed-item';
        
        let iconClass = 'pending';
        let iconText = '⏳';
        if (order.status === 'completed') { iconClass = 'captured'; iconText = '✓'; }
        else if (order.status === 'failed') { iconClass = 'failed'; iconText = '✗'; }
        else if (order.status === 'refunded' || order.status === 'partially_refunded') { iconClass = 'refunded'; iconText = '♻️'; }

        const timeString = new Date(order.created_at).toLocaleTimeString();

        item.innerHTML = `
          <div class="feed-left">
            <div class="feed-status-icon ${iconClass}">${iconText}</div>
            <div class="feed-details">
              <span class="feed-title">${order.description || 'Payment Order'}</span>
              <span class="feed-subtitle-text">Ref: ${order.order_ref} · Merchant: ${order.merchant_id}</span>
            </div>
          </div>
          <div class="feed-right">
            <span class="feed-amount">₹${order.amount}</span>
            <span class="feed-time">${timeString}</span>
          </div>
        `;
        feed.appendChild(item);
      });
    } catch (err) {
      console.error('Error loading feed:', err);
    }
  },

  async loadTransactions() {
    try {
      const filterStatus = document.getElementById('txn-status-filter').value;
      const filterMerchant = document.getElementById('txn-merchant-filter').value;
      const data = await window.API.getTransactions(filterStatus, filterMerchant);
      
      const tbody = document.getElementById('tbody-transactions');
      if (!data.orders || data.orders.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="empty-row">No matching transactions found.</td></tr>';
        return;
      }

      tbody.innerHTML = '';
      data.orders.forEach(order => {
        const tr = document.createElement('tr');
        tr.dataset.txnDetails = JSON.stringify(order, null, 2);
        
        let badgeClass = 'pending';
        if (order.status === 'completed') badgeClass = 'success';
        else if (order.status === 'failed') badgeClass = 'failed';
        else if (order.status === 'refunded' || order.status === 'partially_refunded') badgeClass = 'refunded';
        else if (order.status === 'processing') badgeClass = 'processing';

        const createdDate = new Date(order.created_at).toLocaleString();

        tr.innerHTML = `
          <td><code class="font-mono">${order.order_ref}</code></td>
          <td>${order.merchant_id}</td>
          <td>${order.customer_id}</td>
          <td>₹${order.amount}</td>
          <td><span class="badge ${badgeClass}">${order.status}</span></td>
          <td>${createdDate}</td>
        `;
        tbody.appendChild(tr);
      });
    } catch (err) {
      console.error('Error loading transactions tab:', err);
    }
  },

  async loadWebhooks() {
    try {
      const statusFilter = document.getElementById('wh-status-filter').value;
      const dupOnly = document.getElementById('wh-duplicates-only').checked;
      
      const data = await window.API.getWebhooks(statusFilter, dupOnly);
      const tbody = document.getElementById('tbody-webhooks');
      
      // Load Webhook Stats Bar
      const stats = await window.API.getWebhookStats();
      document.getElementById('ws-total').textContent = stats.total || 0;
      document.getElementById('ws-delivered').textContent = stats.delivered || 0;
      document.getElementById('ws-retrying').textContent = stats.retrying || 0;
      document.getElementById('ws-exhausted').textContent = stats.exhausted || 0;
      document.getElementById('ws-duplicates').textContent = stats.duplicates_detected || 0;
      document.getElementById('ws-rate').textContent = `${stats.delivery_success_rate || 0}%`;

      if (!data.events || data.events.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="empty-row">No webhook logs found.</td></tr>';
        return;
      }

      tbody.innerHTML = '';
      data.events.forEach(evt => {
        const tr = document.createElement('tr');
        tr.dataset.eventId = evt.event_id;
        
        let badgeClass = 'pending';
        if (evt.delivery_status === 'delivered') badgeClass = 'success';
        else if (evt.delivery_status === 'retrying') badgeClass = 'retrying';
        else if (evt.delivery_status === 'exhausted') badgeClass = 'exhausted';
        else if (evt.delivery_status === 'failed') badgeClass = 'failed';

        const hmacDisplay = evt.signature ? '✓ Verified' : '✗ Unsigned';
        const hmacClass = evt.signature_valid ? 'text-success' : 'text-danger';
        const dupDisplay = evt.is_duplicate ? '⚠️ Yes' : 'No';

        tr.innerHTML = `
          <td><code class="font-mono">${evt.event_id}</code></td>
          <td><span class="font-mono">${evt.event_type}</span></td>
          <td><span class="badge ${badgeClass}">${evt.delivery_status}</span></td>
          <td>${evt.attempts_count} / 5</td>
          <td class="${hmacClass}">${hmacDisplay}</td>
          <td>${dupDisplay}</td>
          <td>${new Date(evt.created_at).toLocaleTimeString()}</td>
        `;
        tbody.appendChild(tr);
      });
    } catch (err) {
      console.error('Error loading webhooks tab:', err);
    }
  },

  async inspectWebhook(eventId) {
    try {
      const evt = await window.API.getWebhookEvent(eventId);
      document.getElementById('inspector-hint').classList.add('hidden');
      const content = document.getElementById('inspector-content');
      content.classList.remove('hidden');

      // Populate details
      const details = document.getElementById('inspector-details');
      details.innerHTML = `
        <div class="detail-pair"><span class="detail-label">Event ID</span><span class="detail-value font-mono">${evt.event_id}</span></div>
        <div class="detail-pair"><span class="detail-label">Type</span><span class="detail-value font-mono">${evt.event_type}</span></div>
        <div class="detail-pair"><span class="detail-label">Delivery Status</span><span class="detail-value"><span class="badge ${evt.delivery_status === 'delivered' ? 'success' : 'failed'}">${evt.delivery_status}</span></span></div>
        <div class="detail-pair"><span class="detail-label">Attempts</span><span class="detail-value">${evt.attempts_count}</span></div>
        <div class="detail-pair"><span class="detail-label">Last Error</span><span class="detail-value">${evt.last_error || 'None'}</span></div>
      `;

      // Payload
      document.getElementById('inspector-payload').textContent = JSON.stringify(JSON.parse(evt.payload), null, 2);

      // Signature
      document.getElementById('inspector-sig').textContent = evt.signature || 'None';
      const verifyDiv = document.getElementById('hmac-verify-result');
      if (evt.signature_valid) {
        verifyDiv.className = 'hmac-verify-result success';
        verifyDiv.textContent = 'HMAC signature matches webhook secret ✓';
      } else {
        verifyDiv.className = 'hmac-verify-result danger';
        verifyDiv.textContent = 'HMAC signature validation failed ✗';
      }
    } catch (err) {
      console.error('Error inspecting webhook:', err);
    }
  },

  async loadRefunds() {
    try {
      const data = await window.API.getRefunds();
      const tbody = document.getElementById('tbody-refunds');
      if (!data.refunds || data.refunds.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="empty-row">No refunds processed.</td></tr>';
        return;
      }

      tbody.innerHTML = '';
      data.refunds.forEach(ref => {
        const tr = document.createElement('tr');
        tr.dataset.refundDetails = JSON.stringify(ref, null, 2);

        tr.innerHTML = `
          <td><code class="font-mono">${ref.refund_ref}</code></td>
          <td><code class="font-mono">${ref.payment_ref || ref.payment_id}</code></td>
          <td>₹${ref.amount}</td>
          <td><span class="font-mono">${ref.refund_type}</span></td>
          <td><span class="badge success">${ref.status}</span></td>
          <td>${ref.reason}</td>
          <td>${new Date(ref.processed_at).toLocaleString()}</td>
        `;
        tbody.appendChild(tr);
      });
    } catch (err) {
      console.error('Error loading refunds tab:', err);
    }
  },

  async loadRetryQueue() {
    try {
      const tbody = document.getElementById('retry-queue');
      const data = await window.API.getWebhooks('retrying');
      
      // Update retry timeline highlights
      document.querySelectorAll('.retry-attempt').forEach(el => el.classList.remove('active-attempt'));
      
      if (!data.events || data.events.length === 0) {
        tbody.innerHTML = '<div class="queue-empty">No events in retry queue.</div>';
        return;
      }

      tbody.innerHTML = '';
      data.events.forEach(evt => {
        const item = document.createElement('div');
        item.className = 'queue-item';

        const nextRetry = evt.next_retry_at ? new Date(evt.next_retry_at).toLocaleTimeString() : 'N/A';
        const delayLeft = evt.next_retry_at ? Math.max(0, Math.round((new Date(evt.next_retry_at) - new Date()) / 1000)) : 0;

        item.innerHTML = `
          <div class="qi-top">
            <span class="qi-event font-mono">${evt.event_type}</span>
            <span class="qi-badge">Attempt ${evt.attempts_count}</span>
          </div>
          <div class="qi-mid">Event: <code class="font-mono">${evt.event_id}</code></div>
          <div class="qi-bottom">
            <span>Next retry at: ${nextRetry} (${delayLeft}s left)</span>
            <span>Error: ${evt.last_error || 'Network error'}</span>
          </div>
        `;
        tbody.appendChild(item);

        // Highlight active attempt in UI timeline
        const nextAttempt = Math.min(5, evt.attempts_count + 1);
        const attemptEl = document.querySelector(`.retry-attempt[data-attempt="${nextAttempt}"]`);
        if (attemptEl) {
          attemptEl.classList.add('active-attempt');
        }
      });
    } catch (err) {
      console.error('Error loading retry queue:', err);
    }
  },

  async triggerRetry() {
    try {
      this.showToast('Triggering webhook retry engine...', 'info');
      await window.API.triggerRetry();
      this.showToast('Retry engine completed execution.', 'success');
      this.refresh();
    } catch (err) {
      this.showToast('Failed to trigger retry engine.', 'danger');
    }
  },

  generateIdempotencyKey() {
    const key = 'idem_' + Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
    document.getElementById('order-idem-key').value = key;
  },

  togglePaymentFields() {
    const method = document.getElementById('pay-method').value;
    const cardFields = document.getElementById('card-fields');
    const upiFields = document.getElementById('upi-fields');
    
    if (method === 'card') {
      cardFields.classList.remove('hidden');
      upiFields.classList.add('hidden');
    } else if (method === 'upi') {
      cardFields.classList.add('hidden');
      upiFields.classList.remove('hidden');
    } else {
      cardFields.classList.add('hidden');
      upiFields.classList.add('hidden');
    }
  },

  // ── Form Actions ────────────────────────────────────────────────────────
  async handleCreateOrder() {
    const amount = document.getElementById('order-amount').value;
    const currency = document.getElementById('order-currency').value;
    const merchantId = document.getElementById('order-merchant').value;
    const customerId = document.getElementById('order-customer').value;
    const email = document.getElementById('order-email').value;
    const description = document.getElementById('order-desc').value;
    const idempotencyKey = document.getElementById('order-idem-key').value;

    const resultBox = document.getElementById('result-order');
    resultBox.classList.remove('hidden');
    resultBox.className = 'step-result';
    resultBox.textContent = 'Creating order...';

    const res = await window.API.createOrder({
      amount, currency, merchantId, customerId, email, description, idempotencyKey
    });

    if (res.ok) {
      this.activeOrderRef = res.data.order_ref;
      resultBox.className = 'step-result success';
      resultBox.textContent = JSON.stringify(res.data, null, 2);
      this.showToast('Order created successfully!', 'success');
      
      // Auto-fill Step 2
      document.getElementById('pay-order-ref').value = this.activeOrderRef;
      document.getElementById('btn-process-payment').removeAttribute('disabled');
      
      // Highlight Step 2
      document.getElementById('step-order').classList.remove('active-step');
      document.getElementById('step-payment').classList.add('active-step');
    } else {
      resultBox.className = 'step-result danger';
      resultBox.textContent = JSON.stringify(res.data || res.error, null, 2);
      this.showToast(`Order creation failed: ${res.status || 'Error'}`, 'danger');
    }
    this.refreshStatsAndFeed();
  },

  async handleProcessPayment() {
    const orderId = document.getElementById('pay-order-ref').value;
    const method = document.getElementById('pay-method').value;
    const cardNumber = document.getElementById('pay-card').value;
    const cardExpiry = document.getElementById('pay-expiry').value;
    const cardCvv = document.getElementById('pay-cvv').value;
    const upiId = document.getElementById('pay-upi').value;
    const simulateFailure = document.getElementById('pay-failure').value;
    const forceHmacMismatch = document.getElementById('pay-hmac-mismatch').checked;

    const resultBox = document.getElementById('result-payment');
    resultBox.classList.remove('hidden');
    resultBox.className = 'step-result';
    resultBox.textContent = 'Processing payment...';

    const res = await window.API.processPayment({
      orderId, method, cardNumber, cardExpiry, cardCvv, upiId, simulateFailure, forceHmacMismatch
    });

    if (res.ok) {
      this.activePaymentRef = res.data.payment_ref;
      
      if (res.data.status === 'captured') {
        resultBox.className = 'step-result success';
        this.showToast('Payment CAPTURED successfully!', 'success');
        
        // Auto fill Step 3
        document.getElementById('refund-payment-ref').value = this.activePaymentRef;
        document.getElementById('btn-refund').removeAttribute('disabled');
        
        // Highlight Step 3
        document.getElementById('step-payment').classList.remove('active-step');
        document.getElementById('step-refund').classList.add('active-step');
      } else {
        resultBox.className = 'step-result danger';
        this.showToast(`Payment FAILED: ${res.data.failure_reason}`, 'warning');
      }
      resultBox.textContent = JSON.stringify(res.data, null, 2);
    } else {
      resultBox.className = 'step-result danger';
      resultBox.textContent = JSON.stringify(res.data || res.error, null, 2);
      this.showToast(`Payment processing request failed!`, 'danger');
    }
    this.refreshStatsAndFeed();
  },

  async handleIssueRefund() {
    const paymentId = document.getElementById('refund-payment-ref').value;
    const amount = document.getElementById('refund-amount').value;
    const reason = document.getElementById('refund-reason').value;

    const resultBox = document.getElementById('result-refund');
    resultBox.classList.remove('hidden');
    resultBox.className = 'step-result';
    resultBox.textContent = 'Initiating refund...';

    const res = await window.API.issueRefund({ paymentId, amount, reason });

    if (res.ok) {
      resultBox.className = 'step-result success';
      resultBox.textContent = JSON.stringify(res.data, null, 2);
      this.showToast('Refund issued successfully!', 'success');
      
      // De-highlight Step 3
      document.getElementById('step-refund').classList.remove('active-step');
      document.getElementById('step-order').classList.add('active-step');
      this.generateIdempotencyKey();
    } else {
      resultBox.className = 'step-result danger';
      resultBox.textContent = JSON.stringify(res.data || res.error, null, 2);
      this.showToast(`Refund initiation failed: ${res.status}`, 'danger');
    }
    this.refreshStatsAndFeed();
  },

  async resetData() {
    if (confirm('Are you sure you want to delete all simulation records from the database?')) {
      try {
        await window.API.resetData();
        this.showToast('All data has been reset.', 'warning');
        
        // Reset local variables
        this.activeOrderRef = null;
        this.activePaymentRef = null;
        
        // Reset inputs
        document.getElementById('pay-order-ref').value = '';
        document.getElementById('refund-payment-ref').value = '';
        document.getElementById('btn-process-payment').setAttribute('disabled', 'true');
        document.getElementById('btn-refund').setAttribute('disabled', 'true');
        
        document.getElementById('result-order').classList.add('hidden');
        document.getElementById('result-payment').classList.add('hidden');
        document.getElementById('result-refund').classList.add('hidden');

        document.getElementById('step-payment').classList.remove('active-step');
        document.getElementById('step-refund').classList.remove('active-step');
        document.getElementById('step-order').classList.add('active-step');
        
        this.generateIdempotencyKey();
        this.refresh();
      } catch {
        this.showToast('Reset failed.', 'danger');
      }
    }
  },

  // ── Demo Scenarios ──────────────────────────────────────────────────────
  async runScenario(type) {
    this.switchTab('simulator');
    this.showToast(`Running scenario: ${type.replace(/_/g, ' ')}...`, 'info');
    
    // Highlight step 1
    document.getElementById('step-order').classList.add('active-step');
    document.getElementById('step-payment').classList.remove('active-step');
    document.getElementById('step-refund').classList.remove('active-step');

    if (type === 'success') {
      // 1. Fill Order Form
      document.getElementById('order-amount').value = Math.floor(Math.random() * 4000) + 500;
      document.getElementById('order-desc').value = 'Scenario: Success Path Payment';
      this.generateIdempotencyKey();
      
      await this.sleep(400);
      await this.handleCreateOrder();
      
      await this.sleep(600);
      // 2. Process Payment successfully
      document.getElementById('pay-method').value = 'card';
      document.getElementById('pay-card').value = '4111111111111111';
      document.getElementById('pay-failure').value = '';
      document.getElementById('pay-hmac-mismatch').checked = false;
      this.togglePaymentFields();
      
      await this.sleep(400);
      await this.handleProcessPayment();

    } else if (type === 'card_declined') {
      document.getElementById('order-amount').value = 750;
      document.getElementById('order-desc').value = 'Scenario: Decline Fail Path';
      this.generateIdempotencyKey();
      
      await this.sleep(400);
      await this.handleCreateOrder();
      
      await this.sleep(600);
      document.getElementById('pay-method').value = 'card';
      document.getElementById('pay-card').value = '5111111111111111';
      document.getElementById('pay-failure').value = 'card_declined';
      document.getElementById('pay-hmac-mismatch').checked = false;
      this.togglePaymentFields();
      
      await this.sleep(400);
      await this.handleProcessPayment();

    } else if (type === 'hmac_mismatch') {
      document.getElementById('order-amount').value = 1200;
      document.getElementById('order-desc').value = 'Scenario: HMAC Verification Mismatch';
      this.generateIdempotencyKey();
      
      await this.sleep(400);
      await this.handleCreateOrder();
      
      await this.sleep(600);
      document.getElementById('pay-method').value = 'upi';
      document.getElementById('pay-upi').value = 'attacker@fraud';
      document.getElementById('pay-failure').value = '';
      document.getElementById('pay-hmac-mismatch').checked = true; // Force mismatch
      this.togglePaymentFields();
      
      await this.sleep(400);
      await this.handleProcessPayment();
      
      // Auto switch to webhooks tab to show the result
      await this.sleep(800);
      this.switchTab('webhooks');

    } else if (type === 'idempotency') {
      this.generateIdempotencyKey();
      const sameKey = document.getElementById('order-idem-key').value;
      
      document.getElementById('order-amount').value = 999;
      document.getElementById('order-desc').value = 'Scenario: Idempotent Payment Attempt 1';
      
      await this.sleep(400);
      await this.handleCreateOrder();
      
      // Try again with exact same key
      await this.sleep(1000);
      this.showToast('Retrying order creation with SAME key to simulate duplicate network request...', 'info');
      document.getElementById('order-idem-key').value = sameKey;
      document.getElementById('order-desc').value = 'Scenario: Idempotent Payment Attempt 2 (Duplicate)';
      
      await this.sleep(600);
      await this.handleCreateOrder();

    } else if (type === 'refund') {
      document.getElementById('order-amount').value = 3500;
      document.getElementById('order-desc').value = 'Scenario: Capture & Reversal Path';
      this.generateIdempotencyKey();
      
      await this.sleep(400);
      await this.handleCreateOrder();
      
      await this.sleep(600);
      document.getElementById('pay-method').value = 'card';
      document.getElementById('pay-card').value = '4111111111111111';
      document.getElementById('pay-failure').value = '';
      document.getElementById('pay-hmac-mismatch').checked = false;
      this.togglePaymentFields();
      
      await this.sleep(400);
      await this.handleProcessPayment();
      
      await this.sleep(800);
      document.getElementById('refund-amount').value = ''; // Full refund
      document.getElementById('refund-reason').value = 'Customer request';
      await this.handleIssueRefund();

    } else if (type === 'retry') {
      await this.triggerRetry();
      await this.sleep(500);
      this.switchTab('retry');
    }
  },

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  },

  // ── UI Helpers ──────────────────────────────────────────────────────────
  showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    let icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    else if (type === 'danger') icon = '🚨';
    else if (type === 'warning') icon = '⚠️';

    toast.innerHTML = `
      <span class="toast-icon">${icon}</span>
      <span class="toast-message">${message}</span>
      <span class="toast-close" onclick="this.parentElement.remove()">✕</span>
    `;

    container.appendChild(toast);
    
    // Auto-remove after 4s
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(100%)';
      setTimeout(() => {
        toast.remove();
      }, 300);
    }, 4000);
  },

  showModal(title, bodyText) {
    const overlay = document.getElementById('modal-overlay');
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-body').textContent = bodyText;
    overlay.classList.remove('hidden');
  },

  closeModal() {
    document.getElementById('modal-overlay').classList.add('hidden');
  },

  debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  }
};

// Start application when page loaded
window.addEventListener('DOMContentLoaded', () => {
  window.App.init();
});
