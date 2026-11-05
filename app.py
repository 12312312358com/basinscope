# -*- coding: utf-8 -*-
"""Compatibility entry point for the SOPRAS application in ``src/``."""
import os

from src.app import app


if __name__ == "__main__":
    app.run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5001")),
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
    )