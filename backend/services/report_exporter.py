"""PDF 报告数据组装与导出辅助逻辑"""
from __future__ import annotations

from typing import Any

import pandas as pd

from backend.services.data_loader import DataLoader


def extract_date_series(df: pd.DataFrame, col: str = "create_time") -> pd.Series:
    """从时间戳或日期字符串列提取 YYYY-MM-DD"""
    if df.empty:
        return pd.Series(dtype=str)

    if col in df.columns:
        numeric = pd.to_numeric(df[col], errors="coerce")
        if numeric.notna().sum() > len(df) * 0.3:
            seconds = numeric.copy()
            mask_ms = numeric > 1e12
            seconds[mask_ms] = seconds[mask_ms] / 1000.0
            dt = pd.to_datetime(seconds, unit="s", errors="coerce")
            formatted = dt.dt.strftime("%Y-%m-%d")
            if formatted.notna().sum() > 0:
                return formatted.fillna("未知日期")

    if "create_date_time" in df.columns:
        dt = pd.to_datetime(df["create_date_time"], errors="coerce")
        return dt.dt.strftime("%Y-%m-%d").fillna("未知日期")

    return pd.Series(["未知日期"] * len(df), index=df.index)


def filter_by_keyword_and_date(
    df: pd.DataFrame,
    date_range: list | None,
    keyword: str,
) -> pd.DataFrame:
    """按日期区间与关键词筛选"""
    if df.empty:
        return df

    result = df.copy()

    if date_range and len(date_range) >= 2:
        dates = extract_date_series(result)
        start_d = pd.to_datetime(date_range[0]).date()
        end_d = pd.to_datetime(date_range[1]).date()
        day_dates = pd.to_datetime(dates, errors="coerce").dt.date
        result = result[(day_dates >= start_d) & (day_dates <= end_d)]

    kw = (keyword or "").strip()
    if kw:
        text_cols = [c for c in ("content", "cleaned_content", "source_keyword") if c in result.columns]
        if not text_cols:
            return result.iloc[0:0]
        mask = pd.Series(False, index=result.index)
        for col in text_cols:
            mask |= result[col].astype(str).str.contains(kw, case=False, na=False)
        result = result[mask]

    return result


def _load_topic_name_map(data_loader: DataLoader) -> dict:
    topic_name_map: dict[Any, str] = {}
    bertopic_df = data_loader.load_bertopic_results()
    if bertopic_df.empty or "Topic" not in bertopic_df.columns:
        return topic_name_map

    name_col = "topic_name" if "topic_name" in bertopic_df.columns else "Name"
    if name_col not in bertopic_df.columns:
        return topic_name_map

    for _, row in bertopic_df.drop_duplicates(subset=["Topic"]).iterrows():
        topic_id = row["Topic"]
        name = row.get(name_col)
        if pd.notna(name) and str(name).strip():
            topic_name_map[topic_id] = str(name).strip()
            try:
                topic_name_map[int(topic_id)] = str(name).strip()
            except (TypeError, ValueError):
                pass
    return topic_name_map


def _resolve_topic_name(topic_id, topic_name_map: dict) -> str:
    if topic_id in topic_name_map:
        return topic_name_map[topic_id]
    try:
        tid = int(topic_id)
        if tid in topic_name_map:
            return topic_name_map[tid]
    except (TypeError, ValueError):
        pass
    return f"话题 {topic_id}"


def _extract_day_topics(group: pd.DataFrame, topic_name_map: dict) -> list[dict]:
    if "Topic" not in group.columns:
        return []

    valid = group.copy()
    valid["Topic"] = pd.to_numeric(valid["Topic"], errors="coerce")
    valid = valid[valid["Topic"].notna() & (valid["Topic"] >= 0)]

    if valid.empty:
        return []

    counts = valid["Topic"].value_counts().head(5)
    topics = []
    for topic_id, count in counts.items():
        topics.append({
            "name": _resolve_topic_name(topic_id, topic_name_map),
            "post_count": int(count),
        })
    return topics


def _extract_day_users(data_loader: DataLoader, date: str) -> list[dict]:
    user_df = data_loader.load_user_stats(start_date=date, end_date=date)
    if user_df.empty:
        return []

    fan_col = "fans_count" if "fans_count" in user_df.columns else "followers"
    top_users = user_df.nlargest(5, "post_count") if "post_count" in user_df.columns else user_df.head(5)

    users = []
    for _, row in top_users.iterrows():
        fan_val = row.get(fan_col, 0)
        users.append({
            "nickname": row.get("nickname", "未知"),
            "post_count": int(row.get("post_count", 0) or 0),
            "followers": int(fan_val) if pd.notna(fan_val) else 0,
        })
    return users


def normalize_sentiment_block(group: pd.DataFrame) -> tuple[dict, dict]:
    """返回 (sent_dist 百分比, sent_counts 中文计数)"""
    sent_counts: dict[str, int] = {}
    if "sentiment" in group.columns:
        raw = group["sentiment"].value_counts().to_dict()
        mapping = {
            "积极": "积极", "positive": "积极", "Positive": "积极",
            "消极": "消极", "negative": "消极", "Negative": "消极",
            "中性": "中性", "neutral": "中性", "Neutral": "中性",
        }
        for key, val in raw.items():
            cn = mapping.get(str(key), str(key))
            sent_counts[cn] = sent_counts.get(cn, 0) + int(val)

    total = len(group) or 1
    sent_dist = {
        "positive": sent_counts.get("积极", 0) / total * 100,
        "negative": sent_counts.get("消极", 0) / total * 100,
        "neutral": sent_counts.get("中性", 0) / total * 100,
    }
    return sent_dist, sent_counts


def build_report_summary(posts_df: pd.DataFrame, comments_df: pd.DataFrame) -> dict:
    """报告头部汇总指标"""
    sent_dist, sent_counts = normalize_sentiment_block(posts_df)
    dates = extract_date_series(posts_df)
    valid_dates = sorted(d for d in dates.unique() if d and d != "未知日期")

    return {
        "total_posts": len(posts_df),
        "total_comments": len(comments_df),
        "total_users": int(posts_df["user_id"].nunique()) if "user_id" in posts_df.columns and not posts_df.empty else 0,
        "date_from": valid_dates[0] if valid_dates else "-",
        "date_to": valid_dates[-1] if valid_dates else "-",
        "day_count": len(valid_dates),
        "sent_dist": sent_dist,
        "sent_counts": sent_counts,
    }


def build_report_data(
    data_loader: DataLoader,
    date_range: list | None = None,
    keyword: str = "",
) -> tuple[bool, dict, list[dict]]:
    """
    组装报告数据。

    Returns:
        is_full_report: 是否按日分段的全量报告
        summary: 汇总信息
        report_data: 各时间段明细列表
    """
    date_range = date_range or []
    keyword = (keyword or "").strip()

    posts_df = data_loader.load_posts()
    comments_df = data_loader.load_comments()

    posts_df = filter_by_keyword_and_date(posts_df, date_range, keyword)
    comments_df = filter_by_keyword_and_date(comments_df, date_range, keyword)

    topic_name_map = _load_topic_name_map(data_loader)
    summary = build_report_summary(posts_df, comments_df)

    is_full_report = not date_range and not keyword

    if posts_df.empty:
        label = "筛选结果（无匹配数据）"
        if date_range and len(date_range) >= 2:
            label = f"{date_range[0]} 至 {date_range[1]}"
        if keyword:
            label = f"{label} | 关键词: {keyword}"
        return is_full_report, summary, [{
            "date": label,
            "total_posts": 0,
            "total_comments": len(comments_df),
            "sent_dist": {"positive": 0, "negative": 0, "neutral": 0},
            "sent_counts": {},
            "topics": [],
            "users": [],
        }]

    posts_df = posts_df.copy()
    posts_df["date"] = extract_date_series(posts_df)
    comments_df = comments_df.copy()
    comments_df["date"] = extract_date_series(comments_df)

    if is_full_report:
        report_data = []
        for date, group in posts_df.groupby("date"):
            report_data.append(
                _build_day_record(str(date), group, comments_df, data_loader, topic_name_map)
            )
        report_data.sort(key=lambda x: x["date"])
        return True, summary, report_data

    # 筛选模式：单日范围仍可按天展示，否则合并为一段
    unique_days = sorted(posts_df["date"].unique())
    if date_range and len(unique_days) > 1:
        report_data = []
        for date in unique_days:
            group = posts_df[posts_df["date"] == date]
            report_data.append(
                _build_day_record(str(date), group, comments_df, data_loader, topic_name_map)
            )
        return False, summary, report_data

    if date_range and len(date_range) >= 2:
        date_label = f"{date_range[0]} 至 {date_range[1]}"
    elif keyword:
        date_label = f"关键词「{keyword}」匹配结果"
    else:
        date_label = str(unique_days[0]) if len(unique_days) == 1 else "筛选结果"

    report_data = [
        _build_day_record(date_label, posts_df, comments_df, data_loader, topic_name_map, merged_section=True)
    ]
    return False, summary, report_data


def _build_day_record(
    date_label: str,
    posts_group: pd.DataFrame,
    comments_df: pd.DataFrame,
    data_loader: DataLoader,
    topic_name_map: dict,
    merged_section: bool = False,
) -> dict:
    sent_dist, sent_counts = normalize_sentiment_block(posts_group)

    if merged_section:
        day_comment_count = len(comments_df)
        users = []
        if not posts_group.empty and "user_id" in posts_group.columns:
            uid_counts = posts_group["user_id"].value_counts().head(5)
            nick_map = {}
            if "nickname" in posts_group.columns:
                nick_map = posts_group.drop_duplicates("user_id").set_index("user_id")["nickname"].to_dict()
            for uid, cnt in uid_counts.items():
                users.append({
                    "nickname": nick_map.get(uid, str(uid)),
                    "post_count": int(cnt),
                    "followers": 0,
                })
    else:
        day_comment_count = (
            len(comments_df[comments_df["date"] == date_label])
            if "date" in comments_df.columns
            else 0
        )
        users = _extract_day_users(data_loader, str(date_label))

    return {
        "date": str(date_label),
        "total_posts": len(posts_group),
        "total_comments": day_comment_count,
        "sent_dist": sent_dist,
        "sent_counts": sent_counts,
        "topics": _extract_day_topics(posts_group, topic_name_map),
        "users": users,
    }
