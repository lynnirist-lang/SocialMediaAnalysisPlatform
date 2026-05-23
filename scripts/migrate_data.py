"""
Data refresh / migration script

Verifies integrity between CSV files and SQLite database, re-syncs all
CSV data to SQLite, invalidates Redis cache, and shows statistics before
and after the operation.

Usage:
  python scripts/migrate_data.py
"""
import sys
import os
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# Add project root to path so backend/config imports resolve correctly
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.db_sync import sync_all_from_csv, verify_data_integrity  # noqa: E402
from backend.services.data_loader import DataLoader  # noqa: E402
from backend.database import init_db  # noqa: E402


def _print_integrity(label: str, result: dict) -> None:
    csv = result["csv"]
    db = result["database"]
    print(f"\n  [{label}]")
    print(f"    CSV    -> posts={csv['posts']}, comments={csv['comments']}, user_stats={csv['user_stats']}")
    print(f"    SQLite -> posts={db['posts']}, comments={db['comments']}, user_stats={db['user_stats']}")


def _check_in_sync(result: dict) -> bool:
    csv = result["csv"]
    db = result["database"]
    return (
        csv["posts"] == db["posts"]
        and csv["comments"] == db["comments"]
        and csv["user_stats"] == db["user_stats"]
    )


def main():
    print("=" * 60)
    print(f"  Data Migration / Refresh Script")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 1. Ensure database schema exists
    # ------------------------------------------------------------------
    print("\n[1/5] Initialising database schema ...")
    try:
        init_db()
        print("  OK  Database schema ready.")
    except Exception as e:
        print(f"  WARN  init_db() failed: {e}")

    # ------------------------------------------------------------------
    # 2. Verify integrity BEFORE sync
    # ------------------------------------------------------------------
    print("\n[2/5] Verifying data integrity (before sync) ...")
    try:
        before = verify_data_integrity()
        _print_integrity("BEFORE", before)
        if _check_in_sync(before):
            print("\n  INFO  CSV and SQLite are already in sync.")
        else:
            print("\n  INFO  Mismatch detected – will re-sync.")
    except Exception as e:
        print(f"  ERROR  verify_data_integrity() failed: {e}")
        before = None

    # ------------------------------------------------------------------
    # 3. Re-sync all CSV data to SQLite
    # ------------------------------------------------------------------
    print("\n[3/5] Re-syncing CSV data to SQLite ...")
    try:
        sync_stats = sync_all_from_csv(clear_comments=True)
        print(
            f"  OK  Sync complete: "
            f"posts={sync_stats['posts']}, "
            f"comments={sync_stats['comments']}, "
            f"user_stats={sync_stats['user_stats']}"
        )
    except Exception as e:
        print(f"  ERROR  sync_all_from_csv() failed: {e}")
        import traceback
        traceback.print_exc()
        sync_stats = None

    # ------------------------------------------------------------------
    # 4. Invalidate Redis / in-process cache
    # ------------------------------------------------------------------
    print("\n[4/5] Invalidating cache ...")
    cache_invalidated = False

    # Try to invalidate via the live DataLoader used by the API
    try:
        from backend.api.main import data_loader as api_data_loader
        api_data_loader._db_available = None
        api_data_loader.invalidate_all_cache()
        print("  OK  API DataLoader cache invalidated.")
        cache_invalidated = True
    except Exception:
        pass

    # Fall back to creating a fresh DataLoader and clearing its cache
    if not cache_invalidated:
        try:
            loader = DataLoader()
            if hasattr(loader, "invalidate_all_cache"):
                loader.invalidate_all_cache()
                print("  OK  DataLoader cache invalidated (standalone).")
                cache_invalidated = True
            elif hasattr(loader, "cache"):
                loader.cache.clear()
                print("  OK  DataLoader cache cleared (standalone).")
                cache_invalidated = True
        except Exception as e:
            print(f"  WARN  Could not invalidate DataLoader cache: {e}")

    # Try Redis directly if it is configured
    try:
        import redis as _redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = _redis.from_url(redis_url, socket_connect_timeout=2)
        r.flushdb()
        print(f"  OK  Redis cache flushed ({redis_url}).")
        cache_invalidated = True
    except Exception as e:
        print(f"  INFO  Redis not available or not configured: {e}")

    if not cache_invalidated:
        print("  INFO  No cache backend was available to invalidate.")

    # ------------------------------------------------------------------
    # 5. Verify integrity AFTER sync
    # ------------------------------------------------------------------
    print("\n[5/5] Verifying data integrity (after sync) ...")
    try:
        after = verify_data_integrity()
        _print_integrity("AFTER", after)
        if _check_in_sync(after):
            print("\n  OK  CSV and SQLite are now in sync.")
        else:
            print("\n  WARN  CSV and SQLite still differ after sync – check logs above.")
    except Exception as e:
        print(f"  ERROR  verify_data_integrity() failed: {e}")
        after = None

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("  Summary")
    print("=" * 60)

    if before:
        print(
            f"  Before -> posts={before['csv']['posts']}/{before['database']['posts']}, "
            f"comments={before['csv']['comments']}/{before['database']['comments']}, "
            f"user_stats={before['csv']['user_stats']}/{before['database']['user_stats']} "
            f"(CSV/DB)"
        )
    if after:
        print(
            f"  After  -> posts={after['csv']['posts']}/{after['database']['posts']}, "
            f"comments={after['csv']['comments']}/{after['database']['comments']}, "
            f"user_stats={after['csv']['user_stats']}/{after['database']['user_stats']} "
            f"(CSV/DB)"
        )
    if sync_stats:
        print(
            f"  Synced -> posts={sync_stats['posts']}, "
            f"comments={sync_stats['comments']}, "
            f"user_stats={sync_stats['user_stats']}"
        )
    print(f"\n  Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
