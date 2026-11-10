from fastapi import FastAPI

from app.routers.admin import router as admin_router
from app.routers.auth import router as auth_router

app = FastAPI()

app.include_router(auth_router)
app.include_router(admin_router)


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}
