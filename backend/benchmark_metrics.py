import time
import uuid
import statistics
import httpx
import json

BASE_URL = "http://localhost:8000"

def run_benchmarks():
    results = {}
    client = httpx.Client(base_url=BASE_URL, timeout=15.0)

    # 1. Health Endpoint Latency
    health_times = []
    for _ in range(50):
        t0 = time.perf_counter()
        r = client.get("/health")
        t1 = time.perf_counter()
        assert r.status_code == 200
        health_times.append((t1 - t0) * 1000)
    
    results["health_check"] = {
        "samples": len(health_times),
        "avg_ms": round(statistics.mean(health_times), 2),
        "median_ms": round(statistics.median(health_times), 2),
        "p95_ms": round(statistics.quantiles(health_times, n=20)[18], 2),
        "min_ms": round(min(health_times), 2),
        "max_ms": round(max(health_times), 2),
    }

    # 2. Order Creation Latency
    order_times = []
    created_orders = []
    for i in range(25):
        t0 = time.perf_counter()
        r = client.post("/api/v1/orders/", json={
            "merchant_id": "merchant_001",
            "customer_id": f"cust_{i}_{uuid.uuid4().hex[:6]}",
            "customer_email": f"cust{i}@example.com",
            "amount": 1499.00,
            "currency": "INR",
            "description": f"Benchmark Order {i}"
        })
        t1 = time.perf_counter()
        assert r.status_code == 201, f"Failed with {r.status_code}: {r.text}"
        order_times.append((t1 - t0) * 1000)
        created_orders.append(r.json())
    
    results["order_creation"] = {
        "samples": len(order_times),
        "avg_ms": round(statistics.mean(order_times), 2),
        "median_ms": round(statistics.median(order_times), 2),
        "p95_ms": round(statistics.quantiles(order_times, n=20)[18], 2),
        "min_ms": round(min(order_times), 2),
        "max_ms": round(max(order_times), 2),
    }

    # 3. Idempotency Key Enforced Order Creation vs Replay
    idempotency_key = f"bench-idem-{uuid.uuid4()}"
    payload = {
        "merchant_id": "merchant_001",
        "customer_id": "cust_idem_99",
        "customer_email": "idem@example.com",
        "amount": 2999.00,
        "currency": "INR",
        "description": "Idempotent Order"
    }
    t0 = time.perf_counter()
    r1 = client.post("/api/v1/orders/", json=payload, headers={"Idempotency-Key": idempotency_key})
    t1 = time.perf_counter()
    assert r1.status_code == 201
    first_ms = (t1 - t0) * 1000

    replay_times = []
    for _ in range(25):
        t0 = time.perf_counter()
        r2 = client.post("/api/v1/orders/", json=payload, headers={"Idempotency-Key": idempotency_key})
        t1 = time.perf_counter()
        assert r2.status_code in (200, 201)
        assert r2.json()["order_ref"] == r1.json()["order_ref"]
        replay_times.append((t1 - t0) * 1000)
    
    results["idempotency_performance"] = {
        "initial_execution_ms": round(first_ms, 2),
        "replay_avg_ms": round(statistics.mean(replay_times), 2),
        "replay_median_ms": round(statistics.median(replay_times), 2),
        "replay_p95_ms": round(statistics.quantiles(replay_times, n=20)[18], 2),
        "replay_speedup_factor": round(first_ms / max(statistics.mean(replay_times), 0.001), 2),
    }

    # 4. Payment Processing Latency (Real Gateway State Engine + Webhook Trigger)
    payment_times = []
    for order in created_orders[:15]:
        t0 = time.perf_counter()
        r = client.post("/api/v1/payments/process", json={
            "order_id": order["order_ref"],
            "method": "card",
            "card_number": "4111111111111111",
            "card_expiry": "12/26",
            "card_cvv": "123"
        })
        t1 = time.perf_counter()
        assert r.status_code in (200, 201), f"Failed payment: {r.status_code}: {r.text}"
        payment_times.append((t1 - t0) * 1000)
    
    results["payment_processing"] = {
        "samples": len(payment_times),
        "avg_ms": round(statistics.mean(payment_times), 2),
        "median_ms": round(statistics.median(payment_times), 2),
        "p95_ms": round(statistics.quantiles(payment_times, n=20)[18], 2),
        "min_ms": round(min(payment_times), 2),
        "max_ms": round(max(payment_times), 2),
    }

    # 5. Webhook Verification Endpoint Latency
    wh_times = []
    test_payload = json.dumps({"event": "payment.captured", "timestamp": time.time()})
    import hmac
    import hashlib
    sig = hmac.new(b"whsec_payment_simulator_secret_key_2024", test_payload.encode(), hashlib.sha256).hexdigest()
    
    for _ in range(30):
        t0 = time.perf_counter()
        r = client.post("/api/v1/webhooks/verify", json={
            "payload": test_payload,
            "signature": sig,
            "secret": "whsec_payment_simulator_secret_key_2024"
        })
        t1 = time.perf_counter()
        assert r.status_code == 200
        wh_times.append((t1 - t0) * 1000)

    results["webhook_signature_verification"] = {
        "samples": len(wh_times),
        "avg_ms": round(statistics.mean(wh_times), 2),
        "median_ms": round(statistics.median(wh_times), 2),
        "p95_ms": round(statistics.quantiles(wh_times, n=20)[18], 2),
        "min_ms": round(min(wh_times), 2),
        "max_ms": round(max(wh_times), 2),
    }

    # 6. Admin Telemetry / Stats Query Latency
    stats_times = []
    for _ in range(25):
        t0 = time.perf_counter()
        r = client.get("/api/v1/webhooks/stats")
        t1 = time.perf_counter()
        assert r.status_code == 200
        stats_times.append((t1 - t0) * 1000)

    results["telemetry_stats_query"] = {
        "samples": len(stats_times),
        "avg_ms": round(statistics.mean(stats_times), 2),
        "median_ms": round(statistics.median(stats_times), 2),
        "p95_ms": round(statistics.quantiles(stats_times, n=20)[18], 2),
        "min_ms": round(min(stats_times), 2),
        "max_ms": round(max(stats_times), 2),
    }

    # 7. High-concurrency throughput
    import concurrent.futures
    def ping_health():
        t0 = time.perf_counter()
        with httpx.Client(base_url=BASE_URL, timeout=10.0) as c:
            r = c.get("/health")
        t1 = time.perf_counter()
        return (t1 - t0) * 1000, r.status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        t_start = time.perf_counter()
        futures = [executor.submit(ping_health) for _ in range(100)]
        concurrent_results = [f.result() for f in futures]
        t_total = time.perf_counter() - t_start

    durations = [dur for dur, code in concurrent_results]
    success_cnt = sum(1 for dur, code in concurrent_results if code == 200)

    results["concurrency_stress"] = {
        "total_requests": 100,
        "concurrent_workers": 10,
        "successful_requests": success_cnt,
        "total_duration_sec": round(t_total, 3),
        "throughput_rps": round(100 / t_total, 1),
        "avg_latency_ms": round(statistics.mean(durations), 2),
        "median_latency_ms": round(statistics.median(durations), 2),
        "p95_latency_ms": round(statistics.quantiles(durations, n=20)[18], 2),
        "min_latency_ms": round(min(durations), 2),
        "max_latency_ms": round(max(durations), 2)
    }

    output_str = json.dumps(results, indent=2)
    print(output_str)
    with open("benchmark_results.json", "w") as f:
        f.write(output_str)

if __name__ == "__main__":
    run_benchmarks()
