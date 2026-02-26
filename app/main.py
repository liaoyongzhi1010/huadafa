from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.settings import get_settings
from app.routes.admin_auth import router as admin_auth_router
from app.routes.admin_pages import router as admin_pages_router
from app.routes.admin_products import router as admin_products_router
from app.routes.admin_batches import router as admin_batches_router
from app.routes.admin_config import router as admin_config_router
from app.routes.admin_content import router as admin_content_router
from app.routes.admin_recommendations import router as admin_recommendations_router
from app.routes.admin_exports import router as admin_exports_router
from app.routes.public_verify import router as public_router
from app.routes.public_pages import router as public_pages_router

app = FastAPI()

settings = get_settings()
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    same_site="lax",
)

@app.get("/health")
def health():
    return {"ok": True}


app.include_router(public_router)
app.include_router(public_pages_router)
app.include_router(admin_auth_router)
app.include_router(admin_pages_router)
app.include_router(admin_products_router)
app.include_router(admin_batches_router)
app.include_router(admin_config_router)
app.include_router(admin_content_router)
app.include_router(admin_recommendations_router)
app.include_router(admin_exports_router)
