# !/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试运行脚本
用法:
    python run_tests.py                  # 运行所有测试
    python run_tests.py --quick          # 快速测试（跳过性能测试）
    python run_tests.py --coverage       # 生成覆盖率报告
    python run_tests.py --html           # 生成HTML报告
"""
import sys
import subprocess
import argparse


def run_tests(args):
    """运行pytest测试"""
    cmd = ["pytest", "tests/", "-v"]

    if args.quick:
        cmd.extend(["-m", "not performance"])

    if args.coverage:
        cmd.extend([
            "--cov=backend",
            "--cov-report=html",
            "--cov-report=term-missing"
        ])

    if args.html:
        cmd.extend([
            "--html=reports/test_report.html",
            "--self-contained-html"
        ])

    if args.marker:
        cmd.extend(["-m", args.marker])

    print(f"执行命令: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    return result.returncode


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="运行API自动化测试")
    parser.add_argument("--quick", action="store_true", help="快速测试模式")
    parser.add_argument("--coverage", action="store_true", help="生成覆盖率报告")
    parser.add_argument("--html", action="store_true", help="生成HTML报告")
    parser.add_argument("--marker", type=str, help="运行特定标记的测试")

    args = parser.parse_args()
    exit_code = run_tests(args)
    sys.exit(exit_code)
