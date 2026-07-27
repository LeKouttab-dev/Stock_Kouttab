"""Passenger WSGI entry-point for O2Switch (cPanel Python apps)."""

from __future__ import annotations

import os
import sys


INTERP = os.path.expanduser("~/virtualenv/stock.lekouttab.fr/3.11/bin/python")
if sys.executable != INTERP and os.path.exists(INTERP):
    os.execl(INTERP, INTERP, *sys.argv)

sys.path.insert(0, os.path.dirname(__file__))

from a2wsgi import ASGIMiddleware  # noqa: E402

from app.main import app  # noqa: E402


application = ASGIMiddleware(app)
