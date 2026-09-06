import asyncio
import time
from contextlib import contextmanager
from sqlalchemy.orm import Session
from app.models import ClientConfig, ClientState
from app.schemas import ClientConfigUpdate, ClientConfigResponse, RateLimitResponse

TOKEN_BUCKET_MODE = "token_bucket"
SLIDING_WINDOW_MODE = "sliding_window"


class RateLimitService:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock_for_client(self, client_key: str) -> asyncio.Lock:
        if client_key not in self._locks:
            self._locks[client_key] = asyncio.Lock()
        return self._locks[client_key]

    @contextmanager
    def session_scope(self) -> Session:
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except:
            session.rollback()
            raise
        finally:
            session.close()

    def upsert_client_config(self, client_key: str, config: ClientConfigUpdate) -> ClientConfigResponse:
        with self.session_scope() as session:
            db_obj = session.get(ClientConfig, client_key)
            if db_obj is None:
                db_obj = ClientConfig(client_key=client_key, **config.model_dump())
                session.add(db_obj)
            else:
                for field, value in config.model_dump().items():
                    setattr(db_obj, field, value)
            session.flush()
            return ClientConfigResponse.model_validate(db_obj)

    def get_client_config(self, client_key: str) -> ClientConfigResponse | None:
        with self.session_scope() as session:
            db_obj = session.get(ClientConfig, client_key)
            if db_obj is None:
                return None
            return ClientConfigResponse.model_validate(db_obj)

    async def check_limit(self, client_key: str) -> RateLimitResponse:
        lock = self._lock_for_client(client_key)
        async with lock:
            with self.session_scope() as session:
                config = session.get(ClientConfig, client_key)
                if config is None:
                    raise ValueError("Client not configured")

                state = session.get(ClientState, client_key)
                now = time.time()
                if state is None:
                    state = ClientState(
                        client_key=client_key,
                        tokens=float(config.burst_size),
                        last_refill=now,
                        window_start=now,
                        request_count=0,
                    )
                    session.add(state)
                    session.flush()

                if config.mode == TOKEN_BUCKET_MODE:
                    result = self._check_token_bucket(config, state, now)
                else:
                    result = self._check_sliding_window(config, state, now)

                session.add(state)
                session.flush()
                return result

    def _check_token_bucket(self, config: ClientConfig, state: ClientState, now: float) -> RateLimitResponse:
        elapsed = max(0.0, now - state.last_refill)
        refill_amount = elapsed * config.rate_per_second
        tokens = min(config.burst_size, state.tokens + refill_amount)
        allowed = tokens >= 1.0
        if allowed:
            tokens -= 1.0
            remaining = int(tokens)
        else:
            remaining = int(tokens)

        reset = now + (1.0 - tokens) / config.rate_per_second if tokens < 1.0 else 0.0
        state.tokens = tokens
        state.last_refill = now
        return RateLimitResponse(
            client_key=config.client_key,
            allowed=allowed,
            limit=config.burst_size,
            remaining=max(0, remaining),
            reset=reset,
            mode=config.mode,
            timestamp=now,
        )

    def _check_sliding_window(self, config: ClientConfig, state: ClientState, now: float) -> RateLimitResponse:
        window_length = 1.0
        elapsed = now - state.window_start
        if elapsed >= window_length:
            shift = int(elapsed // window_length)
            state.previous_request_count = state.request_count if shift == 1 else 0
            state.request_count = 0
            state.window_start += shift * window_length
            elapsed = now - state.window_start

        weight = 1.0 - min(1.0, elapsed / window_length)
        sliding_count = int(state.request_count + state.previous_request_count * weight)
        allowed = sliding_count < config.burst_size
        if allowed:
            state.request_count += 1

        reset = max(0.0, (state.window_start + window_length) - now)
        remaining = max(0, config.burst_size - sliding_count - (1 if allowed else 0))
        return RateLimitResponse(
            client_key=config.client_key,
            allowed=allowed,
            limit=config.burst_size,
            remaining=remaining,
            reset=reset,
            mode=config.mode,
            timestamp=now,
        )
