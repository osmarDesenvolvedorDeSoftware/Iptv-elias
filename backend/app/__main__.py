"""Entry point to run the Flask API without relying on Flask CLI."""

from __future__ import annotations

import os

from . import create_app


def main() -> None:
    """Instantiate the application and start the development server."""
    app = create_app()
    host = os.environ.get("FLASK_RUN_HOST", "0.0.0.0")
    port = int(os.environ.get("FLASK_RUN_PORT", os.environ.get("PORT", "5000")))
    app.run(host=host, port=port)


if __name__ == "__main__":
    main()
