from fastapi import FastAPI

from app.routes.public_verify import router as public_router

app = FastAPI()


@app.get("/health")
def health():
    return {"ok": True}


app.include_router(public_router)
