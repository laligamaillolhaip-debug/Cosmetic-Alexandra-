import json
import os
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

import app.database as database

database.DB_PATH = Path(os.environ["E2E_DB_PATH"])

from app.services import ai


def mock_structured_completion(prompt, schema, system):
    match = re.search(r"Каталог:\n(\[.*?\])\nФормат:", prompt, flags=re.DOTALL)
    if not match:
        raise RuntimeError("AI planner prompt did not contain its catalog")
    catalog = json.loads(match.group(1))

    def pick(category, time_of_day):
        eligible = [
            item for item in catalog
            if item["category"] == category and item["time"] in ("both", time_of_day)
        ]
        if not eligible:
            raise RuntimeError(f"No {category} candidate for {time_of_day}")
        return min(eligible, key=lambda item: item["price"])["id"]

    selection = {
        "morning": [
            {"id": pick(category, "morning"), "reason": "Fits the profile"}
            for category in ("cleanser", "moisturizer", "spf")
        ],
        "evening": [
            {"id": pick(category, "evening"), "reason": "Fits the profile"}
            for category in ("cleanser", "moisturizer")
        ],
        "summary": "Deterministic test proposal",
    }
    return json.dumps(selection)


ai.chat_reply = lambda *_args: "Deterministic E2E answer"
ai.complete_structured = mock_structured_completion

import uvicorn

from app.main import app


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8011, log_level="warning")
