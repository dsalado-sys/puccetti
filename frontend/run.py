"""Arranque del servidor FastAPI.

Uso:
    python run.py            # http://127.0.0.1:8000
    python run.py --host 0.0.0.0 --port 8001
"""
from __future__ import annotations

import argparse

import uvicorn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--reload", action="store_true", help="Recarga en caliente")
    args = ap.parse_args()

    uvicorn.run(
        "backend.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
