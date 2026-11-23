from fastapi import FastAPI

from app.routers.admin import router as admin_router
from app.routers.application import router as applications_router
from app.routers.auth import router as auth_router
from app.routers.chat import router as chat_router
from app.routers.job_offer import router as job_offers_router
from app.routers.profile import router as profile_router
from app.routers.resume import router as resumes_router
from app.routers.saved_job import router as saved_jobs_router
from app.routers.search import router as search_router

app = FastAPI()

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(profile_router)
app.include_router(job_offers_router)
app.include_router(search_router)
app.include_router(saved_jobs_router)
app.include_router(applications_router)
app.include_router(resumes_router)
app.include_router(chat_router)


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}
