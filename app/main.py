from fastapi import FastAPI

from app.routes.public_verify import router as public_router
from app.routes.public_pages import router as public_pages_router

app = FastAPI()


@app.get("/health")
def health():
    return {"ok": True}


app.include_router(public_router)
app.include_router(public_pages_router)
