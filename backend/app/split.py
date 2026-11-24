"""Chia tiền nhóm. Tổng các phần luôn đúng bằng tổng tiền, không làm tròn lệch.

Chỉ tính toán và soạn tin nhắn nhắc. Không gửi yêu cầu thanh toán thật.
"""

from __future__ import annotations

from .textutil import norm

MAX_PEOPLE = 20
MAX_TOTAL = 10_000_000_000


class SplitError(ValueError):
    pass


def _largest_remainder(total: int, weights: list[float]) -> list[int]:
    """Chia `total` đồng theo tỷ trọng, phần dư (từng 1đ) trao cho phần có số dư lớn nhất. Tổng luôn bằng `total`."""
    s = sum(weights)
    raw = [total * w / s for w in weights]
    base = [int(r) for r in raw]
    remainder = total - sum(base)
    order = sorted(range(len(weights)), key=lambda i: (-(raw[i] - base[i]), i))
    for i in order[:remainder]:
        base[i] += 1
    return base


def split_bill(total_vnd, people: list[str], payer: str | None = None, weights: dict[str, float] | None = None,
               label: str = "") -> dict:
    try:
        total = int(total_vnd)
    except (TypeError, ValueError) as exc:
        raise SplitError("total_vnd phải là số nguyên (VND)") from exc
    if not 1 <= total <= MAX_TOTAL:
        raise SplitError("total_vnd phải dương và không quá 10 tỷ")
    if not isinstance(people, list):
        raise SplitError("people phải là danh sách tên")
    names = [str(p).strip() for p in people if str(p).strip()]
    if not 2 <= len(names) <= MAX_PEOPLE:
        raise SplitError(f"Cần từ 2 đến {MAX_PEOPLE} người")
    if any(len(n) > 30 for n in names):
        raise SplitError("Tên mỗi người tối đa 30 ký tự")
    keys = [norm(n) for n in names]
    if len(set(keys)) != len(keys):
        raise SplitError("Có tên bị trùng, hãy phân biệt các tên")

    if weights:
        wmap = {norm(k): v for k, v in weights.items()}
        unknown = set(wmap) - set(keys)
        if unknown:
            raise SplitError("Tỷ trọng có tên không nằm trong danh sách người: " + ", ".join(sorted(unknown)))
        try:
            w = [float(wmap.get(k, 1.0)) for k in keys]
        except (TypeError, ValueError) as exc:
            raise SplitError("Tỷ trọng phải là số") from exc
        if any(x <= 0 for x in w):
            raise SplitError("Tỷ trọng phải dương")
    else:
        w = [1.0] * len(names)
    shares = _largest_remainder(total, w)

    payer_name = None
    if payer:
        pk = norm(payer)
        if pk not in keys:
            raise SplitError("Người ứng tiền phải nằm trong danh sách người")
        payer_name = names[keys.index(pk)]
    what = (label or "chi phí chung").strip()[:60]
    rows, messages = [], []
    for name, share in zip(names, shares):
        owes = share if payer_name and name != payer_name else 0
        rows.append({"name": name, "share_vnd": share, "owes_vnd": owes, **({"owes_to": payer_name} if owes else {})})
        if owes:
            amount = f"{owes:,}".replace(",", ".")
            messages.append(f"{name} gửi {payer_name} {amount}đ cho {what}.")
    return {"total_vnd": total, "payer": payer_name, "label": what, "per_person": rows, "messages": messages}


def split_block(r: dict) -> dict:
    block = {"kind": "split_result", "total_vnd": r["total_vnd"], "label": r["label"],
             "per_person": [{k: v for k, v in p.items()} for p in r["per_person"]], "messages": r["messages"]}
    if r["payer"]:
        block["payer"] = r["payer"]
    return block
