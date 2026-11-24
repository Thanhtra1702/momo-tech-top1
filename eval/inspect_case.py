"""In chi tiết các ca đánh giá (lệnh gọi công cụ, thẻ, phản hồi, kiểm tra) để tìm nguyên nhân khi ca không đạt.

    cd backend
    .\\.venv\\Scripts\\python ..\\eval\\inspect_case.py e06 t02 --mode fast
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "backend"))

import run_eval  # noqa: E402
from scoring import score  # noqa: E402

from app.config import Settings  # noqa: E402
from app.db import Database  # noqa: E402
from app.llm import LLMClient  # noqa: E402
from app.seed import ensure_seeded  # noqa: E402


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="+")
    ap.add_argument("--mode", default="fast")
    ap.add_argument("--cases", default="cases", choices=list(run_eval.CASE_FILES))
    args = ap.parse_args()
    settings = Settings.from_env()
    llm = LLMClient(settings)
    with tempfile.TemporaryDirectory() as tmp:
        db = Database(str(Path(tmp) / "inspect.db"))
        ensure_seeded(db)
        for case in [c for c in run_eval.load_cases(args.cases) if c["id"] in args.ids]:
            trace = run_eval.run_case(case, args.mode, db, llm, settings.max_agent_steps)
            print("==", case["id"], [t if isinstance(t, str) else t["text"] + " [ảnh " + t["image"] + "]" for t in case["turns"]])
            print("calls:", json.dumps(trace.calls, ensure_ascii=False))
            print("cards:", [(i["title"], i["price_vnd"]) for b in trace.blocks if b["kind"] == "ticket_cards" for i in b["items"]])
            print("text:", trace.final.text[:400].replace("\n", " "))
            print("checks:", score(case["expect"], trace))
    return 0


if __name__ == "__main__":
    sys.exit(main())
