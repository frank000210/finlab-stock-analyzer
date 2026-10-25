"""學習中心：教材完整性、批改邏輯、密碼雜湊、公開端點。

教材是手寫的 Markdown／JSON，最容易壞的是「題目的 section 對不到單元標題」
（補強連結會失效）與「answer 超出選項範圍」，所以這裡把整份題庫掃過一遍。
不需要 MongoDB：只測不碰資料庫的部分。
"""

import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.course import accounts, content


def _headings(unit_id: str) -> set[str]:
    md = content.load_unit_markdown(unit_id)
    return {m.group(1).strip() for m in re.finditer(r"^#{2,3}\s+(.+)$", md, re.M)}


def test_catalog_units_all_have_markdown():
    for uid in content.unit_ids():
        assert content.load_unit_markdown(uid).startswith("# ")


def test_quiz_flags_match_files():
    for unit in content.load_catalog()["units"]:
        has_file = content.load_quiz(unit["id"]) is not None
        assert has_file == bool(unit.get("quiz")), unit["id"]


def test_required_units_have_quizzes():
    for uid in content.required_unit_ids():
        assert content.load_quiz(uid) is not None, uid


@pytest.mark.parametrize("uid", [u["id"] for u in content.load_catalog()["units"] if u.get("quiz")])
def test_quiz_sections_point_to_real_headings(uid):
    headings = _headings(uid)
    quiz = content.load_quiz(uid)
    ids = [q["id"] for q in quiz["questions"]]
    assert len(ids) == len(set(ids))
    for q in quiz["questions"]:
        assert q["section"] in headings, f"{uid}/{q['id']} section {q['section']!r} 找不到"
        assert q["explain"]


def test_placement_tags_are_units():
    quiz = content.load_quiz("placement")
    ids = set(content.unit_ids())
    assert all(q["tag"] in ids for q in quiz["questions"])


def test_public_quiz_strips_answers():
    pub = content.public_quiz(content.load_quiz("u1"))
    for q in pub["questions"]:
        assert set(q) == {"id", "question", "options"}


def test_grade_quiz_pass_and_fail():
    quiz = content.load_quiz("u1")
    all_right = {q["id"]: q["answer"] for q in quiz["questions"]}
    result = content.grade_quiz(quiz, all_right)
    assert result["passed"] and result["correct"] == result["total"]

    one_wrong = dict(all_right)
    first = quiz["questions"][0]
    one_wrong[first["id"]] = (first["answer"] + 1) % len(first["options"])
    result = content.grade_quiz(quiz, one_wrong)
    wrong = [r for r in result["results"] if not r["correct"]]
    assert len(wrong) == 1 and wrong[0]["section"] == first["section"]

    assert content.grade_quiz(quiz, {})["passed"] is False


def test_grade_placement_recommends_first_unknown_required_unit():
    quiz = content.load_quiz("placement")
    answers = {q["id"]: q["answer"] for q in quiz["questions"] if q["tag"] in ("u1", "u2")}
    result = content.grade_placement(quiz, answers)
    assert result["recommended_start"] == "u3"
    assert set(result["known_units"]) == {"u1", "u2"}

    assert content.grade_placement(quiz, {})["recommended_start"] == "u1"


def test_unit_meta_rejects_bad_ids():
    assert content.get_unit_meta("../catalog") is None
    assert content.load_quiz("../../etc") is None


def test_password_hash_roundtrip():
    stored = accounts.hash_password("correct horse")
    assert stored.startswith("pbkdf2_sha256$")
    assert accounts.verify_password("correct horse", stored)
    assert not accounts.verify_password("wrong", stored)
    assert not accounts.verify_password("x", "garbage")


def test_email_validation():
    assert accounts.is_valid_email("a.b@example.com")
    assert not accounts.is_valid_email("no-at-sign")
    assert accounts.normalize_email("  A@B.COM ") == "a@b.com"


@pytest.fixture()
def client():
    from app.api.course import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_public_endpoints(client):
    cat = client.get("/api/v1/course/catalog").json()
    assert cat["units"][0]["id"] == "l0"

    unit = client.get("/api/v1/course/units/u1").json()
    assert unit["prev"] == "l0" and unit["next"] == "u2"
    assert "answer" not in unit["quiz"]["questions"][0]

    assert client.get("/api/v1/course/units/nope").status_code == 404


def test_anonymous_quiz_grading_is_not_saved(client):
    quiz = content.load_quiz("u2")
    answers = {q["id"]: q["answer"] for q in quiz["questions"]}
    res = client.post("/api/v1/course/units/u2/quiz", json={"answers": answers}).json()
    assert res["passed"] is True and res["saved"] is False


def test_protected_endpoints_require_login(client):
    assert client.get("/api/v1/course/me").status_code == 401
    assert client.post("/api/v1/course/tutor", json={"unit_id": "u1", "question": "hi"}).status_code == 401
    bad = {"X-Admin-Token": "not-a-jwt"}
    assert client.get("/api/v1/course/me", headers=bad).status_code == 401
    assert client.get("/api/v1/course/admin/projects", headers=bad).status_code == 401
