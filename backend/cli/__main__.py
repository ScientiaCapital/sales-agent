"""
CLI Entry Point

Enables running the CLI as a module:
    python -m cli.enrich
"""

from cli.enrich import app

if __name__ == "__main__":
    app()
