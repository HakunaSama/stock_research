"""Strategy hall — public discovery, likes, favorites, comments, tags.

Mounted under ``/api/hall``. Personal library CRUD stays in ``app.py``;
publishing a private strategy into the hall (and social engagement) lives here.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from . import auth, db

router = APIRouter(prefix="/api/hall", tags=["hall"])


def _hall_card(row, tags: Optional[List[str]] = None) -> dict:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "author_name": row["author_name"] if "author_name" in row.keys() else "",
        "name": row["name"],
        "summary": row["summary"] or "",
        "raw_text": row["raw_text"],
        "tags": tags if tags is not None else db.get_strategy_tags(row["id"]),
        "like_count": int(row["like_count"] or 0),
        "favorite_count": int(row["favorite_count"] or 0),
        "comment_count": int(row["comment_count"] or 0),
        "liked": bool(row["liked"]) if "liked" in row.keys() else False,
        "favorited": bool(row["favorited"]) if "favorited" in row.keys() else False,
        "published_at": row["published_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "is_owner": False,  # filled by caller when known
    }


@router.get("/strategies")
def hall_list(
    tag: str = Query(default="", max_length=24),
    q: str = Query(default="", max_length=64),
    sort: str = Query(default="hot", pattern="^(hot|new|likes|comments)$"),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user=Depends(auth.current_user),
):
    rows = db.list_hall_strategies(
        viewer_id=user["id"],
        tag=tag.strip().lstrip("#"),
        q=q.strip(),
        sort=sort,
        limit=limit,
        offset=offset,
    )
    tag_map = db.get_strategies_tags_map([r["id"] for r in rows])
    items = []
    for r in rows:
        card = _hall_card(r, tag_map.get(r["id"], []))
        card["is_owner"] = r["user_id"] == user["id"]
        items.append(card)
    return {"items": items, "sort": sort, "tag": tag, "q": q}


@router.get("/strategies/{sid}")
def hall_detail(sid: int, user=Depends(auth.current_user)):
    row = db.get_hall_strategy(sid, user["id"])
    if row is None:
        raise HTTPException(status_code=404, detail="策略不存在或未公开")
    card = _hall_card(row)
    card["is_owner"] = row["user_id"] == user["id"]
    return card


@router.get("/tags")
def hall_tags(user=Depends(auth.current_user)):
    return {"tags": db.list_popular_tags()}


@router.get("/favorites")
def my_favorites(user=Depends(auth.current_user)):
    rows = db.list_favorite_strategies(user["id"])
    tag_map = db.get_strategies_tags_map([r["id"] for r in rows])
    items = []
    for r in rows:
        card = _hall_card(r, tag_map.get(r["id"], []))
        card["is_owner"] = r["user_id"] == user["id"]
        items.append(card)
    return {"items": items}


@router.post("/strategies/{sid}/like")
def like_strategy(sid: int, user=Depends(auth.current_user)):
    res = db.toggle_like(user["id"], sid)
    if res is None:
        raise HTTPException(status_code=404, detail="策略不存在或未公开")
    return res


@router.post("/strategies/{sid}/favorite")
def favorite_strategy(sid: int, user=Depends(auth.current_user)):
    res = db.toggle_favorite(user["id"], sid)
    if res is None:
        raise HTTPException(status_code=404, detail="策略不存在或未公开")
    return res


class CommentBody(BaseModel):
    body: str = Field(..., min_length=1, max_length=500)


@router.get("/strategies/{sid}/comments")
def get_comments(sid: int, user=Depends(auth.current_user)):
    row = db.get_hall_strategy(sid, user["id"])
    if row is None:
        raise HTTPException(status_code=404, detail="策略不存在或未公开")
    return {
        "comments": [
            {
                "id": c["id"],
                "user_id": c["user_id"],
                "username": c["username"],
                "body": c["body"],
                "created_at": c["created_at"],
                "is_mine": c["user_id"] == user["id"],
            }
            for c in db.list_comments(sid)
        ]
    }


@router.post("/strategies/{sid}/comments")
def post_comment(sid: int, body: CommentBody, user=Depends(auth.current_user)):
    text = body.body.strip()
    if not text:
        raise HTTPException(status_code=400, detail="评论不能为空")
    cid = db.add_comment(sid, user["id"], text)
    if cid is None:
        raise HTTPException(status_code=404, detail="策略不存在或未公开")
    return {"id": cid, "ok": True}


@router.delete("/comments/{cid}")
def remove_comment(cid: int, user=Depends(auth.current_user)):
    if not db.delete_comment(cid, user["id"], is_admin=bool(user["is_admin"])):
        raise HTTPException(status_code=404, detail="评论不存在或无权删除")
    return {"ok": True}


class AdoptBody(BaseModel):
    activate: bool = False


@router.post("/strategies/{sid}/adopt")
def adopt(sid: int, body: AdoptBody, user=Depends(auth.current_user)):
    """Copy a public strategy into the current user's personal library."""
    if db.count_strategies(user["id"]) >= 20:
        raise HTTPException(status_code=400, detail="策略数量已达上限（20 条）。")
    new_id = db.adopt_strategy(sid, user["id"], activate=body.activate)
    if new_id is None:
        raise HTTPException(status_code=404, detail="策略不存在或未公开")
    return {"ok": True, "strategy_id": new_id}
