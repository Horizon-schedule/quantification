"""WSGI entry for Gunicorn."""

from config.settings import reload_settings
from quant_platform.ui.app import create_app

reload_settings()
app = create_app()
