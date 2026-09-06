import asyncio
import time
from collections import Counter
import httpx

BASE_URL = "http://127.0.0.1:9000"
CLIENT_KEY = "loadtest"
REQUESTS = 1000
CONCURRENCY = 500


def configure_client() -> None:
    payload = {
        "rate_per_second": 50,
        "burst_size": 100,
        "mode": "token_bucket",
    }
    r = httpx.post(f"{BASE_URL}/admin/clients/{CLIENT_KEY}", json=payload, timeout=10.0)
    r.raise_for_status()
    print("Configured client", r.json())


async def make_request(client: httpx.AsyncClient, results: Counter) -> None:
    r = await client.get(f"{BASE_URL}/limit/{CLIENT_KEY}", timeout=10.0)
    results[r.status_code] += 1
    if r.status_code == 200:
        assert r.json()["allowed"] is True


async def run_test() -> None:
    async with httpx.AsyncClient() as client:
        tasks = []
        results = Counter()
        start = time.monotonic()
        for i in range(REQUESTS):
            tasks.append(make_request(client, results))
            if len(tasks) >= CONCURRENCY:
                await asyncio.gather(*tasks)
                tasks = []
        if tasks:
            await asyncio.gather(*tasks)
        elapsed = time.monotonic() - start
        print(f"Completed {REQUESTS} requests in {elapsed:.2f}s")
        print("Status codes:", dict(results))


if __name__ == "__main__":
    configure_client()
    asyncio.run(run_test())
