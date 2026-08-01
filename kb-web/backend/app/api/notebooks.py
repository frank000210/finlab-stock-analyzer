from fastapi import APIRouter, Depends
from pymongo.database import Database

from ..deps import get_db, require_auth

router = APIRouter(prefix="/api", tags=["notebooks"])


@router.get("/notebooks")
def list_notebooks(db: Database = Depends(get_db), _: str = Depends(require_auth)):
    pipeline = [
        {
            "$group": {
                "_id": "$doc_type",
                "doc_count": {"$sum": 1},
                "last_updated": {"$max": "$updated_at"},
                "quality_failed": {
                    "$sum": {"$cond": [{"$eq": ["$quality.pass", False]}, 1, 0]}
                },
                "needs_review": {
                    "$sum": {
                        "$cond": [{"$eq": ["$ui_knowledge.needs_ui_review", True]}, 1, 0]
                    }
                },
            }
        },
        {"$sort": {"_id": 1}},
    ]
    rows = list(db.spec_docs.aggregate(pipeline))
    return [
        {
            "domain": row["_id"] or "(未分類)",
            "doc_count": row["doc_count"],
            "last_updated": row["last_updated"],
            "quality_failed": row["quality_failed"],
            "needs_review": row["needs_review"],
        }
        for row in rows
    ]
