"""
WSGI entry point for JARVIS.
Supports production servers such as waitress or gunicorn.
"""

from api_server import app

application = app
