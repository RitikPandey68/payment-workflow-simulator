// api.js - API Client Wrapper for Payment Workflow Simulator
const API_BASE = '/api/v1';

window.API = {
  async getStats() {
    try {
      const res = await fetch(`${API_BASE}/admin/stats`);
      return await res.json();
    } catch (err) {
      console.error('Error fetching admin stats:', err);
      throw err;
    }
  },

  async resetData() {
    try {
      const res = await fetch(`${API_BASE}/admin/reset`, { method: 'DELETE' });
      return await res.json();
    } catch (err) {
      console.error('Error resetting data:', err);
      throw err;
    }
  },

  async getTransactions(status = '', merchantId = '') {
    try {
      const params = new URLSearchParams();
      if (status) params.append('status', status);
      if (merchantId) params.append('merchant_id', merchantId);
      const res = await fetch(`${API_BASE}/orders?${params.toString()}`);
      return await res.json();
    } catch (err) {
      console.error('Error fetching transactions:', err);
      throw err;
    }
  },

  async getWebhooks(status = '', duplicatesOnly = false) {
    try {
      const params = new URLSearchParams();
      if (status) params.append('delivery_status', status);
      if (duplicatesOnly) params.append('duplicates_only', 'true');
      const res = await fetch(`${API_BASE}/webhooks?${params.toString()}`);
      return await res.json();
    } catch (err) {
      console.error('Error fetching webhooks:', err);
      throw err;
    }
  },

  async getWebhookStats() {
    try {
      const res = await fetch(`${API_BASE}/webhooks/stats`);
      return await res.json();
    } catch (err) {
      console.error('Error fetching webhook stats:', err);
      throw err;
    }
  },

  async getRefunds(paymentRef = '', status = '') {
    try {
      const params = new URLSearchParams();
      if (paymentRef) params.append('payment_ref', paymentRef);
      if (status) params.append('status', status);
      const res = await fetch(`${API_BASE}/refunds?${params.toString()}`);
      return await res.json();
    } catch (err) {
      console.error('Error fetching refunds:', err);
      throw err;
    }
  },

  async createOrder(data) {
    try {
      const headers = { 'Content-Type': 'application/json' };
      if (data.idempotencyKey) {
        headers['Idempotency-Key'] = data.idempotencyKey;
      }
      
      const payload = {
        amount: parseFloat(data.amount),
        currency: data.currency || 'INR',
        merchant_id: data.merchantId || 'merchant_001',
        customer_id: data.customerId || 'cust_123',
        email: data.email || 'customer@example.com',
        description: data.description || ''
      };

      const res = await fetch(`${API_BASE}/orders`, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(payload)
      });
      return { ok: res.ok, status: res.status, data: await res.json() };
    } catch (err) {
      console.error('Error creating order:', err);
      return { ok: false, error: err.message };
    }
  },

  async processPayment(data) {
    try {
      const headers = { 'Content-Type': 'application/json' };
      const params = new URLSearchParams();
      if (data.forceHmacMismatch) {
        params.append('force_hmac_mismatch', 'true');
      }
      
      const payload = {
        order_id: data.orderId,
        method: data.method || 'card',
        card_number: data.cardNumber || null,
        card_expiry: data.cardExpiry || null,
        card_cvv: data.cardCvv || null,
        upi_id: data.upiId || null,
        simulate_failure: data.simulateFailure || null
      };

      const res = await fetch(`${API_BASE}/payments/process?${params.toString()}`, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(payload)
      });
      return { ok: res.ok, status: res.status, data: await res.json() };
    } catch (err) {
      console.error('Error processing payment:', err);
      return { ok: false, error: err.message };
    }
  },

  async issueRefund(data) {
    try {
      const headers = { 'Content-Type': 'application/json' };
      const payload = {
        payment_id: data.paymentId,
        amount: data.amount ? parseFloat(data.amount) : null,
        reason: data.reason || 'Customer request',
        notes: data.notes || ''
      };

      const res = await fetch(`${API_BASE}/refunds`, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(payload)
      });
      return { ok: res.ok, status: res.status, data: await res.json() };
    } catch (err) {
      console.error('Error issuing refund:', err);
      return { ok: false, error: err.message };
    }
  },

  async triggerRetry() {
    try {
      const res = await fetch(`${API_BASE}/admin/retry-webhooks`, { method: 'POST' });
      return await res.json();
    } catch (err) {
      console.error('Error triggering webhook retry:', err);
      throw err;
    }
  },

  async getWebhookEvent(eventId) {
    try {
      const res = await fetch(`${API_BASE}/webhooks/${eventId}`);
      return await res.json();
    } catch (err) {
      console.error(`Error fetching webhook event ${eventId}:`, err);
      throw err;
    }
  }
};
