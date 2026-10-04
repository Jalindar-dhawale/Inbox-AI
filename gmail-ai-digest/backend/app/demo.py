import json
from pathlib import Path

def demo_messages() -> list[dict]:
    path = Path(__file__).resolve().parents[2] / "data" / "demo_emails.json"
    messages = json.loads(path.read_text(encoding="utf-8"))
    return [{"id": f"demo-{index}", "snippet": item["summary"], **item} for index, item in enumerate(messages, 1)]
