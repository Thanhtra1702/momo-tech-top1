"""Đo bộ luật kiểm tra lừa đảo (backend/app/scamcheck.py) trên các ca có nhãn. Chạy offline, không tốn chi phí API.

    cd backend
    .\\.venv\\Scripts\\python ..\\eval\\run_scam_eval.py

In precision, recall và tỷ lệ báo nhầm ở hai ngưỡng: "cảnh báo" (mức trung bình trở lên) và "nguy cơ cao" (mức cao trở lên),
cùng danh sách các ca sai để xem nguyên nhân.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "backend"))

from app.scamcheck import check  # noqa: E402

ORDER = ["low", "medium", "high", "critical"]


def load(path: Path = HERE / "scam_cases.jsonl") -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def evaluate(cases: list[dict], min_level: str) -> dict:
    tp = fp = fn = tn = 0
    wrong: list[dict] = []
    for c in cases:
        report = check(c["text"])
        flagged = ORDER.index(report["level"]) >= ORDER.index(min_level)
        if flagged and c["label"] == 1:
            tp += 1
        elif flagged and c["label"] == 0:
            fp += 1
            wrong.append({"id": c["id"], "kind": "báo nhầm", "level": report["level"], "text": c["text"][:70]})
        elif not flagged and c["label"] == 1:
            fn += 1
            wrong.append({"id": c["id"], "kind": "bỏ sót", "level": report["level"], "text": c["text"][:70]})
        else:
            tn += 1
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {"min_level": min_level, "tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": precision, "recall": recall,
            "false_positive_rate": fp / (fp + tn) if fp + tn else 0.0, "wrong": wrong}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    heldout = "--heldout" in sys.argv
    cases = load(HERE / ("scam_cases_heldout.jsonl" if heldout else "scam_cases.jsonl"))
    print("Bộ giữ riêng (chưa dùng để chỉnh luật)" if heldout else "Bộ phát triển (đã dùng để chỉnh luật, số liệu lạc quan)")
    pos = sum(c["label"] for c in cases)
    print(f"{len(cases)} ca ({pos} có dấu hiệu lừa đảo, {len(cases) - pos} bình thường)\n")
    for level, name in (("medium", "Cảnh báo (trung bình trở lên)"), ("high", "Nguy cơ cao (cao trở lên)")):
        r = evaluate(cases, level)
        print(f"{name}: precision {r['precision']:.0%}, recall {r['recall']:.0%}, báo nhầm {r['false_positive_rate']:.0%} "
              f"(TP {r['tp']}, FP {r['fp']}, FN {r['fn']}, TN {r['tn']})")
        for w in r["wrong"]:
            print(f"   - {w['id']} {w['kind']} (mức {w['level']}): {w['text']}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
