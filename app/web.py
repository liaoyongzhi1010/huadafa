from __future__ import annotations

from fastapi.templating import Jinja2Templates

from app.paths import APP_DIR

templates = Jinja2Templates(directory=str(APP_DIR / "templates"))
