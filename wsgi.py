"""
Legacy WSGI entry point for the old Flask/static dashboard.

Active web development uses:
- React frontend on port 3000
- FastAPI backend (`backend.server:app`) on port 8001
"""

from api_server import app

application = app
