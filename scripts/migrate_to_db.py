"""
CSV → SQLite 数据迁移脚本

用法:
  python scripts/migrate_to_db.py
  python scripts/migrate_to_db.py --verify-only
"""
import argparse
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.db_sync import sync_all_from_csv, verify_data_integrity  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="将 CSV 数据迁移到 SQLite")
    parser.add_argument("--verify-only", action="store_true", help="仅校验，不写入")
    args = parser.parse_args()

    if args.verify_only:
        result = verify_data_integrity()
        print("数据完整性校验:")
        print(f"  CSV    -> posts={result['csv']['posts']}, comments={result['csv']['comments']}, user_stats={result['csv']['user_stats']}")
        print(f"  SQLite -> posts={result['database']['posts']}, comments={result['database']['comments']}, user_stats={result['database']['user_stats']}")
        return

    print("开始迁移 CSV → SQLite ...")
    stats = sync_all_from_csv()
    print(f"迁移完成: posts={stats['posts']}, comments={stats['comments']}, user_stats={stats['user_stats']}")

    result = verify_data_integrity()
    print("\n校验结果:")
    print(f"  CSV posts: {result['csv']['posts']} | DB posts: {result['database']['posts']}")
    print(f"  CSV comments: {result['csv']['comments']} | DB comments: {result['database']['comments']}")
    print(f"  CSV user_stats: {result['csv']['user_stats']} | DB user_stats: {result['database']['user_stats']}")


if __name__ == "__main__":
    main()
