"""Запуск интерфейса и API Ядра через один HTTP-сервер."""
import argparse
import importlib.util
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    if importlib.util.find_spec("uvicorn") is None:
        parser.exit(1, "Установите зависимости: python -m pip install -r backend/requirements.txt\n")
    import uvicorn
    print(f"Ядро: http://{args.host}:{args.port}/login.html", flush=True)
    uvicorn.run("app.main:app", app_dir=str(Path(__file__).resolve().parent / "backend"),
                host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
