# Запуск JS-тестов
import shutil
import subprocess
from pathlib import Path


def test_javascript_frontend_unit_suite():
    root = Path(__file__).resolve().parents[3]
    node = shutil.which("node")
    assert node, "Node.js is required for the frontend unit tests"

    result = subprocess.run(
        [node, "--test", "tests/frontend/js"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
