"""教材讀取與測驗批改。

教材是 repo 裡的靜態檔案（course/catalog.json、course/units/*.md、
course/quizzes/*.json），部署後不會變，所以第一次讀取後就快取在記憶體。

題庫的正確答案只留在後端：送給前端的題目一律先剝掉 `answer` / `explain`，
批改在伺服器端做，避免開 DevTools 就能看到答案。
"""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

_UNIT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")


def course_dir() -> Path:
    """教材根目錄：COURSE_DIR 環境變數優先，否則是 repo 根目錄的 course/。

    backend/app/course/content.py → parents[3] 就是 repo 根目錄（Docker 內是 /app）。
    """
    override = os.environ.get("COURSE_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[3] / "course"


class CourseContentError(RuntimeError):
    """教材檔案缺漏或格式錯誤。"""


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CourseContentError(f"找不到教材檔案：{path.name}") from exc
    except json.JSONDecodeError as exc:
        raise CourseContentError(f"教材 JSON 格式錯誤：{path.name}（{exc}）") from exc


@lru_cache(maxsize=1)
def load_catalog() -> dict:
    catalog = _read_json(course_dir() / "catalog.json")
    units = catalog.get("units") or []
    for unit in units:
        if not _UNIT_ID_RE.match(str(unit.get("id", ""))):
            raise CourseContentError(f"單元 id 不合法：{unit.get('id')!r}")
    units.sort(key=lambda u: u.get("order", 0))
    return catalog


def unit_ids() -> list[str]:
    return [u["id"] for u in load_catalog()["units"]]


def get_unit_meta(unit_id: str) -> dict | None:
    if not _UNIT_ID_RE.match(unit_id or ""):
        return None
    for unit in load_catalog()["units"]:
        if unit["id"] == unit_id:
            return unit
    return None


def required_unit_ids() -> list[str]:
    """結業所需通過測驗的單元（catalog 裡 required: true）。"""
    return [u["id"] for u in load_catalog()["units"] if u.get("required")]


@lru_cache(maxsize=64)
def load_unit_markdown(unit_id: str) -> str:
    meta = get_unit_meta(unit_id)
    if meta is None:
        raise CourseContentError(f"沒有這個單元：{unit_id}")
    path = course_dir() / "units" / f"{unit_id}.md"
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise CourseContentError(f"找不到單元內容：{unit_id}.md") from exc


@lru_cache(maxsize=64)
def load_quiz(quiz_id: str) -> dict | None:
    """回傳完整題庫（含答案），只給後端批改用。沒有題庫的單元回 None。"""
    if not _UNIT_ID_RE.match(quiz_id or ""):
        return None
    path = course_dir() / "quizzes" / f"{quiz_id}.json"
    if not path.exists():
        return None
    quiz = _read_json(path)
    for q in quiz.get("questions", []):
        options = q.get("options") or []
        if not isinstance(q.get("answer"), int) or not (0 <= q["answer"] < len(options)):
            raise CourseContentError(f"題目 {quiz_id}/{q.get('id')} 的 answer 超出選項範圍")
    return quiz


def public_quiz(quiz: dict | None) -> dict | None:
    """剝掉答案與解析，給前端顯示用。"""
    if quiz is None:
        return None
    return {
        "pass_ratio": quiz.get("pass_ratio", 0.8),
        "questions": [
            {"id": q["id"], "question": q["question"], "options": q["options"]}
            for q in quiz.get("questions", [])
        ],
    }


def grade_quiz(quiz: dict, answers: dict[str, int]) -> dict:
    """批改測驗。answers 是 {題目 id: 選項索引}；沒作答的題目算錯。

    回傳分數、是否通過，以及每題結果。答錯的題目附上解析與對應段落標題
    （section），讓前端把學習者帶回該段補強——對應流程圖「測 → 補強」那條回饋迴圈。
    """
    questions = quiz.get("questions", [])
    results = []
    correct = 0
    for q in questions:
        chosen = answers.get(q["id"])
        ok = chosen == q["answer"]
        correct += ok
        item = {"id": q["id"], "correct": ok, "chosen": chosen}
        if not ok:
            item.update({
                "answer": q["answer"],
                "explain": q.get("explain", ""),
                "section": q.get("section", ""),
            })
        results.append(item)
    total = len(questions)
    ratio = correct / total if total else 0.0
    pass_ratio = quiz.get("pass_ratio", 0.8)
    return {
        "correct": correct,
        "total": total,
        "ratio": round(ratio, 4),
        "passed": total > 0 and ratio + 1e-9 >= pass_ratio,
        "pass_ratio": pass_ratio,
        "results": results,
    }


def grade_placement(quiz: dict, answers: dict[str, int]) -> dict:
    """程度檢測：每題帶 tag（對應單元 id）。

    一個單元底下的題目全對，才視為「已具備」；建議起點是依課程順序第一個
    尚未具備的必修單元。只做規則判斷、不呼叫 LLM——檢測要即時、可重現。
    """
    by_unit: dict[str, list[bool]] = {}
    for q in quiz.get("questions", []):
        by_unit.setdefault(q.get("tag", ""), []).append(answers.get(q["id"]) == q["answer"])

    known = [uid for uid, oks in by_unit.items() if uid and oks and all(oks)]
    start = None
    for uid in unit_ids():
        meta = get_unit_meta(uid) or {}
        if meta.get("required") and uid not in known:
            start = uid
            break
    scores = {uid: {"correct": sum(oks), "total": len(oks)} for uid, oks in by_unit.items() if uid}
    return {"known_units": known, "recommended_start": start or unit_ids()[0], "scores": scores}


def lab_dir(unit_id: str) -> Path | None:
    """單元的 lab 資料夾（catalog 的 lab 欄位，例如 labs/u2）；必須在教材目錄底下。"""
    meta = get_unit_meta(unit_id)
    if not meta or not meta.get("lab"):
        return None
    root = course_dir().resolve()
    path = (root / meta["lab"]).resolve()
    if not path.is_relative_to(root) or not path.is_dir():
        return None
    return path


def load_lab_readme(unit_id: str) -> str | None:
    path = lab_dir(unit_id)
    readme = path / "README.md" if path else None
    return readme.read_text(encoding="utf-8") if readme and readme.is_file() else None


def lab_zip_bytes(unit_id: str) -> bytes | None:
    """把 lab 資料夾打包成 zip，讓沒有 repo 權限的學習者也能下載起始檔。"""
    import io
    import zipfile

    path = lab_dir(unit_id)
    if path is None:
        return None
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in sorted(path.rglob("*")):
            if file.is_file() and "__pycache__" not in file.parts:
                zf.write(file, f"{unit_id}-lab/{file.relative_to(path).as_posix()}")
    return buf.getvalue()


def unit_excerpt(unit_id: str, limit: int = 8000) -> str:
    """AI 助教用的教材摘錄：截斷避免 prompt 過長。"""
    text = load_unit_markdown(unit_id)
    return text if len(text) <= limit else text[:limit] + "\n…（以下略）"
