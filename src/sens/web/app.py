"""Web interface for SENS - Natural Language SQL."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sens.api.app import app as api_app

# Create web app
web_app = FastAPI(title="SENS Web Interface")

# Mount the API app
web_app.mount("/api", api_app)

# Setup templates
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# Serve static files if needed
# static_dir = Path(__file__).parent / "static"
# if static_dir.exists():
#     web_app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@web_app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the main web interface."""
    # For now, we'll serve the HTML directly
    # In production, you'd use proper template rendering
    html_file = templates_dir / "index.html"
    if html_file.exists():
        return HTMLResponse(content=html_file.read_text())
    else:
        return HTMLResponse(
            content="<h1>SENS Web Interface</h1><p>Template not found.</p>"
        )


@web_app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "sens-web"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(web_app, host="0.0.0.0", port=8000)
