# Rate Limiter Service

A standalone Python network service implementing per-client token bucket and sliding-window rate limiting.

## Features

- `POST /admin/clients/{client_key}` to configure a client's rate limit
- `GET /limit/{client_key}` to evaluate allow/deny
- persistent SQLite storage for config and bucket state
- concurrent-safe request handling for same client keys
- sliding-window mode plus token bucket mode
- standard rate limit headers on every response

## Run

1. Install dependencies:

```bash
python -m pip install .
python -m pip install -e .[dev]
```

2. Start the service:

```bash
python -m app.main
```

3. Configure a client:

```bash
curl -X POST http://127.0.0.1:9000/admin/clients/demo -H "Content-Type: application/json" -d '{"rate_per_second": 5, "burst_size": 10, "mode": "token_bucket"}'
```

4. Check a request:

```bash
curl http://127.0.0.1:9000/limit/demo
```

## Load test

Run `python load_test.py` while the service is running. The script demonstrates correctness under 500+ concurrent requests.


