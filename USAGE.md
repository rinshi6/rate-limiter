# How and where to use this rate limiter

This service is a **separate HTTP process**, not a Python package you import into your app. Run it (default port 9000), then your API calls it **before doing the real work**.

It decides whether a given `client_key` is allowed to make another request. Your app is responsible for picking the key (API key, user id, IP, etc.) and for returning 429 to the caller.

## Where to use it

Put the check at the **edge of request handling** — as early as you can, before expensive work:


| Place                                           | Typical use                         |
| ----------------------------------------------- | ----------------------------------- |
| Middleware / interceptor                        | Cap all requests per IP or API key  |
| Login / signup / OTP routes                     | Slow down brute force               |
| Public APIs (`/search`, `/generate`, `/upload`) | Stop one client from flooding you   |
| Webhooks                                        | Limit a partner's call rate         |
| Background job enqueue                          | Stop a user from flooding the queue |


Do **not** put it inside database or business logic. It is a gate: allow or 429, then continue.

Skip health checks, static files, and this service's own admin endpoints.

## How it fits

```
Client → Your app → GET http://127.0.0.1:9000/limit/{client_key}
                      ├─ 200 allowed  → handle the request
                      └─ 429 denied   → return 429 to the client
```

`client_key` is whatever you want to limit: API key, user id, IP, or a composite like `ip:route`.

## Setup (once)

1. Start this service (`python -m app.main`). See [README.md](README.md) for install and run.
2. Register each client (or a shared key):

```http
POST /admin/clients/{client_key}
Content-Type: application/json

{
  "rate_per_second": 5,
  "burst_size": 10,
  "mode": "token_bucket"
}
```

Example:

```bash
curl -X POST http://127.0.0.1:9000/admin/clients/demo \
  -H "Content-Type: application/json" \
  -d '{"rate_per_second": 5, "burst_size": 10, "mode": "token_bucket"}'
```

- `rate_per_second` — sustained refill rate
- `burst_size` — short spike allowed (also the sliding-window cap)
- `mode` — `token_bucket` (smooth refill) or `sliding_window` (count over about 1 second)

Configure keys **before** traffic. Unknown keys return **404**.

Read a config with `GET /admin/clients/{client_key}`.

## Check (every request)

```http
GET /limit/{client_key}
```


| Status  | Meaning                                         |
| ------- | ----------------------------------------------- |
| **200** | Allowed (`allowed: true`). Process the request. |
| **429** | Over limit. Reject and copy `Retry-After`.      |
| **404** | That `client_key` was never configured.         |


Responses include `RateLimit-Limit`, `RateLimit-Remaining`, and `RateLimit-Reset`. On 429 they also include `Retry-After`. Forward those headers to your client if you want them visible.

Example FastAPI dependency:

```python
import httpx
from fastapi import HTTPException, Request

LIMITER = "http://127.0.0.1:9000"

async def rate_limit(request: Request):
    key = request.headers.get("X-API-Key") or (
        request.client.host if request.client else "anon"
    )
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{LIMITER}/limit/{key}")
    if r.status_code == 429:
        raise HTTPException(status_code=429, detail="Too many requests")
    if r.status_code != 200:
        raise HTTPException(status_code=503, detail="Rate limiter unavailable")
```

Attach it only to routes you want to protect:

```python
@app.get("/search")
async def search(..., _: None = Depends(rate_limit)):
    ...
```



## Operational notes

- The limiter must be **running** whenever your app is; state lives in SQLite (`app/rate_limiter.db`).
- In production, run it as its own process (Docker/systemd) and point your app at that URL — not `localhost` if they are on different hosts.
- If the limiter is down, choose fail-open (allow) vs fail-closed (503). The example above fails closed.
- This is for **protecting your own APIs**. It is not a browser widget and not a drop-in FastAPI middleware package — you wire `GET /limit/...` yourself.

If you change this service's code, restart it. `python -m app.main` does not auto-reload.