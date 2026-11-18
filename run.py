"""Запуск интерфейса и API Ядра через один HTTP-сервер."""
import argparse
import importlib.util
from pathlib import Path
import json
import threading
import time
from urllib.request import urlopen
import webbrowser


def open_when_ready(host, port):
    browser_host = "127.0.0.1" if host == "0.0.0.0" else host
    base = f"http://{browser_host}:{port}"
    for _ in range(60):
        try:
            with urlopen(base + "/openapi.json", timeout=1) as response:
                schema = json.load(response)
            if schema.get("info", {}).get("title") == "Ядро API":
                webbrowser.open(base + "/login.html")
                return
        except (OSError, ValueError):
            pass
        time.sleep(0.5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--open-browser", action="store_true")
    args = parser.parse_args()
    if importlib.util.find_spec("uvicorn") is None:
        parser.exit(1, "Установите зависимости: python -m pip install -r backend/requirements.txt\n")
    import uvicorn
    print(f"Ядро: http://{args.host}:{args.port}/login.html", flush=True)
    if args.open_browser:
        threading.Thread(target=open_when_ready, args=(args.host, args.port), daemon=True).start()
    uvicorn.run("app.main:app", app_dir=str(Path(__file__).resolve().parent / "backend"),
                host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
