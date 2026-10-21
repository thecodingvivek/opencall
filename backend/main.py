"""Entry point for running `uvicorn main:app` from the backend directory."""

from app.main import app

__all__ = ["app"]
