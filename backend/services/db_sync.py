"""CSV 与 SQLite 之间的数据同步"""
import json
import re
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from backend.database import SessionLocal, init_db
from backend.models.db_models import Comment, Post, UserStats
from backend.services.data_loader import DataLoader
from config.config import CLEANED_DATA_DIR, USER_CHARACTERS_DATA_DIR


def _extract_date_from_filename(filename: str) -> str:
    match = re.search(r"(\d{8})", filename)
    return match.group(1) if match else ""


def _normalize_sentiment_columns(df: pd.DataFrame) -> pd.DataFrame:
    """合并 merged 文件中重复的 sentiment 列"""
    if "sentiment" not in df.columns:
        for col in ("sentiment_x", "sentiment_y"):
            if col in df.columns:
                df["sentiment"] = df[col]
                break
    if "置信度" not in df.columns:
        for col in ("置信度_x", "置信度_y", "置信度"):
            if col in df.columns:
                df["置信度"] = df[col]
                break
    if "Topic" in df.columns:
        df["Topic"] = pd.to_numeric(df["Topic"], errors="coerce").fillna(-1).astype(int)
    return df


def _row_to_post(row: pd.Series, source_date: str) -> Post:
    record = row.where(pd.notna(row), None).to_dict()
    for key, value in list(record.items()):
        if hasattr(value, "item"):
            try:
                record[key] = value.item()
            except Exception:
                record[key] = str(value)

    sentiment = record.get("sentiment") or record.get("sentiment_x") or record.get("sentiment_y")
    confidence = record.get("置信度") or record.get("置信度_x") or record.get("置信度_y")
    topic_val = record.get("Topic")
    try:
        topic = int(topic_val) if topic_val is not None and pd.notna(topic_val) else None
    except (TypeError, ValueError):
        topic = None

    return Post(
        note_id=str(record.get("note_id", "")),
        user_id=str(record.get("user_id", "")) if record.get("user_id") is not None else None,
        create_time=str(record.get("create_time", "")) if record.get("create_time") is not None else None,
        create_date_time=str(record.get("create_date_time", ""))
        if record.get("create_date_time") is not None
        else None,
        content=record.get("content"),
        cleaned_content=record.get("cleaned_content"),
        nickname=record.get("nickname"),
        sentiment=sentiment,
        confidence=float(confidence) if confidence is not None and pd.notna(confidence) else None,
        topic=topic,
        source_date=source_date,
        data_json=json.dumps(record, ensure_ascii=False, default=str),
    )


def _row_to_comment(row: pd.Series, source_date: str) -> Comment:
    record = row.where(pd.notna(row), None).to_dict()
    for key, value in list(record.items()):
        if hasattr(value, "item"):
            try:
                record[key] = value.item()
            except Exception:
                record[key] = str(value)

    sentiment = record.get("sentiment") or record.get("sentiment_x") or record.get("sentiment_y")
    confidence = record.get("置信度") or record.get("置信度_x") or record.get("置信度_y")

    return Comment(
        note_id=str(record.get("note_id", "")) if record.get("note_id") is not None else None,
        user_id=str(record.get("user_id", "")) if record.get("user_id") is not None else None,
        create_time=str(record.get("create_time", "")) if record.get("create_time") is not None else None,
        create_date_time=str(record.get("create_date_time", ""))
        if record.get("create_date_time") is not None
        else None,
        content=record.get("content"),
        cleaned_content=record.get("cleaned_content"),
        nickname=record.get("nickname"),
        sentiment=sentiment,
        confidence=float(confidence) if confidence is not None and pd.notna(confidence) else None,
        source_date=source_date,
        data_json=json.dumps(record, ensure_ascii=False, default=str),
    )


def _row_to_user_stats(row: pd.Series, stats_date: str) -> UserStats:
    record = row.where(pd.notna(row), None).to_dict()
    for key, value in list(record.items()):
        if hasattr(value, "item"):
            try:
                record[key] = value.item()
            except Exception:
                record[key] = str(value)

    def _float(val):
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    def _int(val):
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        try:
            return int(val)
        except (TypeError, ValueError):
            return None

    return UserStats(
        user_id=str(record.get("user_id", "")),
        stats_date=stats_date,
        nickname=record.get("nickname"),
        post_count=_int(record.get("post_count")) or 0,
        reply_count=_int(record.get("reply_count")) or 0,
        total_actions=_int(record.get("total_actions")) or 0,
        total_likes_received=_int(record.get("total_likes_received")) or 0,
        fans_count=_float(record.get("fans_count")),
        pagerank_score=_float(record.get("pagerank_score")),
        betweenness_score=_float(record.get("betweenness_score")),
        in_degree_weighted=_int(record.get("in_degree_weighted")),
        out_degree_weighted=_int(record.get("out_degree_weighted")),
        burst_power=_float(record.get("burst_power")),
        response_speed=_float(record.get("response_speed")),
        active_duration=_float(record.get("active_duration")),
        originality_score=_float(record.get("originality_score")),
        sentiment_intensity=_float(record.get("sentiment_intensity")),
        data_json=json.dumps(record, ensure_ascii=False, default=str),
    )


def _upsert_posts(session: Session, df: pd.DataFrame, source_date: str) -> int:
    valid = [
        (str(row.get("note_id", "")), row)
        for _, row in df.iterrows()
        if str(row.get("note_id", "")) not in ("", "nan")
    ]
    if not valid:
        return 0

    note_ids = [nid for nid, _ in valid]
    existing = {
        p.note_id: p
        for p in session.query(Post).filter(Post.note_id.in_(note_ids)).all()
    }

    _UPDATE_ATTRS = (
        "user_id", "create_time", "create_date_time", "content", "cleaned_content",
        "nickname", "sentiment", "confidence", "topic", "source_date", "data_json",
    )
    new_posts = []
    for note_id, row in valid:
        entity = _row_to_post(row, source_date)
        if note_id in existing:
            for attr in _UPDATE_ATTRS:
                setattr(existing[note_id], attr, getattr(entity, attr))
        else:
            new_posts.append(entity)

    if new_posts:
        session.bulk_save_objects(new_posts)

    return len(valid)


def _upsert_comments(session: Session, df: pd.DataFrame, source_date: str) -> int:
    if source_date:
        session.query(Comment).filter(Comment.source_date == source_date).delete()
    count = 0
    for _, row in df.iterrows():
        entity = _row_to_comment(row, source_date)
        session.add(entity)
        count += 1
    return count


def _upsert_user_stats(session: Session, df: pd.DataFrame, stats_date: str) -> int:
    count = 0
    for _, row in df.iterrows():
        user_id = str(row.get("user_id", ""))
        if not user_id or user_id == "nan":
            continue
        entity = _row_to_user_stats(row, stats_date)
        existing = (
            session.query(UserStats)
            .filter(UserStats.user_id == user_id, UserStats.stats_date == stats_date)
            .first()
        )
        if existing:
            for col in UserStats.__table__.columns:
                name = col.name
                if name not in ("id",):
                    setattr(existing, name, getattr(entity, name))
        else:
            session.add(entity)
        count += 1
    return count


def sync_posts_from_csv(session: Session | None = None) -> int:
    own_session = session is None
    session = session or SessionLocal()
    total = 0
    try:
        all_files = list(CLEANED_DATA_DIR.glob("posts_cleaned_merged*.csv"))
        if not all_files:
            all_files = list(CLEANED_DATA_DIR.glob("posts_cleaned_*.csv"))
        date_map = {}
        for f in all_files:
            if "merged" in f.name:
                d = _extract_date_from_filename(f.name)
                if d:
                    date_map[d] = f
        for f in all_files:
            if "merged" not in f.name:
                d = _extract_date_from_filename(f.name)
                if d and d not in date_map:
                    date_map[d] = f

        for date_str, path in sorted(date_map.items()):
            df = pd.read_csv(path, encoding="utf-8-sig")
            df = _normalize_sentiment_columns(df)
            if "note_id" in df.columns:
                if "sentiment" in df.columns:
                    df["_has_sent"] = df["sentiment"].notna()
                    df = df.sort_values(["note_id", "_has_sent"], ascending=[True, False])
                    df = df.drop(columns=["_has_sent"], errors="ignore")
                df = df.drop_duplicates(subset="note_id", keep="first")
            total += _upsert_posts(session, df, date_str)
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        if own_session:
            session.close()
    return total


def sync_comments_from_csv(session: Session | None = None, replace: bool = False) -> int:
    own_session = session is None
    session = session or SessionLocal()
    total = 0
    try:
        if replace:
            session.query(Comment).delete()
        files = sorted(CLEANED_DATA_DIR.glob("comments_cleaned_*.csv"))
        for path in files:
            date_str = _extract_date_from_filename(path.name)
            df = pd.read_csv(path, encoding="utf-8-sig")
            df = _normalize_sentiment_columns(df)
            total += _upsert_comments(session, df, date_str)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        if own_session:
            session.close()
    return total


def sync_user_stats_from_csv(session: Session | None = None) -> int:
    own_session = session is None
    session = session or SessionLocal()
    total = 0
    try:
        for path in sorted(USER_CHARACTERS_DATA_DIR.glob("user_stats_*.csv")):
            match = re.search(r"user_stats_(\d{4}-\d{2}-\d{2})", path.name)
            stats_date = match.group(1) if match else path.stem.replace("user_stats_", "")
            df = pd.read_csv(path, encoding="utf-8-sig")
            total += _upsert_user_stats(session, df, stats_date)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        if own_session:
            session.close()
    return total


def sync_all_from_csv(clear_comments: bool = True) -> dict:
    """将 CSV 全量同步到 SQLite"""
    init_db()
    session = SessionLocal()
    try:
        session.query(Post).delete()
        if clear_comments:
            session.query(Comment).delete()
        session.query(UserStats).delete()
        session.commit()
        posts = sync_posts_from_csv(session)
        comments = sync_comments_from_csv(session, replace=False)
        users = sync_user_stats_from_csv(session)
        return {"posts": posts, "comments": comments, "user_stats": users}
    finally:
        session.close()


def verify_data_integrity() -> dict:
    """对比 CSV 与数据库记录数量"""
    loader = DataLoader(use_cache=False)
    csv_posts = len(loader.load_posts())
    csv_comments = len(loader.load_comments())
    csv_users = len(loader.load_user_stats())

    init_db()
    session = SessionLocal()
    try:
        db_posts = session.query(Post).count()
        db_comments = session.query(Comment).count()
        db_users = session.query(UserStats).count()
    finally:
        session.close()

    return {
        "csv": {"posts": csv_posts, "comments": csv_comments, "user_stats": csv_users},
        "database": {"posts": db_posts, "comments": db_comments, "user_stats": db_users},
    }


def db_records_to_dataframe(records: list, model_rows) -> pd.DataFrame:
    """将 ORM 行还原为与 CSV 兼容的 DataFrame"""
    if not model_rows:
        return pd.DataFrame()

    rows = []
    for row in model_rows:
        if row.data_json:
            try:
                rows.append(json.loads(row.data_json))
                continue
            except json.JSONDecodeError:
                pass
        rows.append({c.name: getattr(row, c.name) for c in row.__table__.columns if c.name != "data_json"})
    df = pd.DataFrame(rows)
    return df
