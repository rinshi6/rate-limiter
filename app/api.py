from fastapi import FastAPI, Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from app.database import init_db, SessionLocal
from app.schemas import ClientConfigUpdate, ClientConfigResponse, RateLimitResponse
from app.services import RateLimitService


def create_app() -> FastAPI:
    app = FastAPI(title="Rate Limiter Service")
    service = RateLimitService(session_factory=SessionLocal)

    @app.on_event("startup")
    async def startup_event() -> None:
        init_db()

    def get_service() -> RateLimitService:
        return service

    @app.post("/admin/clients/{client_key}", response_model=ClientConfigResponse)
    async def configure_client(client_key: str, config: ClientConfigUpdate, service: RateLimitService = Depends(get_service)):
        return service.upsert_client_config(client_key, config)

    @app.get("/admin/clients/{client_key}", response_model=ClientConfigResponse)
    async def get_client(client_key: str, service: RateLimitService = Depends(get_service)):
        config = service.get_client_config(client_key)
        if config is None:
            raise HTTPException(status_code=404, detail="Client not found")
        return config

    @app.get("/limit/{client_key}", response_model=RateLimitResponse)
    async def check_limit(client_key: str, response: Response, service: RateLimitService = Depends(get_service)):
        try:
            result = await service.check_limit(client_key)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        headers = {
            "RateLimit-Limit": str(result.limit),
            "RateLimit-Remaining": str(result.remaining),
            "RateLimit-Reset": str(result.reset),
        }
        if not result.allowed:
            headers["Retry-After"] = str(result.reset)
            return JSONResponse(status_code=429, content=result.model_dump(), headers=headers)
        for key, value in headers.items():
            response.headers[key] = value
        return result

    return app
