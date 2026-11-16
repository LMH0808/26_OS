#!/usr/bin/env python3
"""排序验证案例运行入口（李铭昊，对应项目说明 13.3）。

流程：人工先把 steps 和 expected 写进 data/policies_cases.json，
再运行本脚本比对。脚本只读用例文件，不回写 expected。

用法（仓库根目录）：
    python3 scripts/check_policies.py
    python3 scripts/check_policies.py --json-out results/policies_validation.json
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tea_break_scheduler.models import task_from_dict  # noqa: E402
from tea_break_scheduler.policies import rank_tasks  # noqa: E402

CASES_PATH = ROOT / "data" / "policies_cases.json"


def fmt(order) -> str:
    if order is None:
        return "（未登记预期顺序）"
    if not order:
        return "（空）"
    return " -> ".join(str(item) for item in order)


def run_case(case: dict) -> dict:
    policy = case["policy"]
    tasks = [task_from_dict(item) for item in case["tasks"]]
    expected = list(case["expected"]) if "expected" in case else None
    ranked = rank_tasks(tasks, policy)
    actual = [task.task_id for task, _ in ranked]

    print("=" * 66)
    print("[案例] %s %s" % (case.get("case_id", "-"), case.get("category", "")))
    print("[配置] 策略=%s，候选任务=%d 个" % (policy, len(tasks)))
    if tasks:
        print("[输入] " + "  ".join(
            "%s(p=%d,d=%d,t=%d)" % (t.task_id, t.priority, t.deadline, t.submitted_at) for t in tasks
        ))
    for line in case.get("steps", []):
        print("[手算] %s" % line)
    print("[预期（运行前登记）] %s" % fmt(expected))
    print("[实际（程序输出）]   %s" % fmt(actual))
    for index, (task, reason) in enumerate(ranked, start=1):
        print("  %d. %-6s %s" % (index, task.task_id, reason))

    passed = expected is not None and actual == expected
    print("[判定] %s" % ("通过" if passed else "不通过"))
    return {
        "case_id": case.get("case_id"),
        "policy": policy,
        "expected": expected,
        "actual": actual,
        "passed": passed,
        "reasons": [{"task_id": t.task_id, "reason": r} for t, r in ranked],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="排序验证案例")
    parser.add_argument("--json-out", type=Path, default=ROOT / "results" / "policies_validation.json")
    parser.add_argument("--no-archive", action="store_true")
    args = parser.parse_args()

    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]
    records = [run_case(case) for case in cases]
    passed = sum(1 for r in records if r["passed"])

    print("=" * 66)
    print("共 %d 个案例，通过 %d 个，失败 %d 个。" % (len(records), passed, len(records) - passed))

    if not args.no_archive:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(
                {
                    "meta": {
                        "module": "tea_break_scheduler/policies.py",
                        "generated_at": datetime.now().isoformat(timespec="seconds"),
                        "python": sys.version.split()[0],
                        "platform": platform.platform(),
                    },
                    "summary": {"total": len(records), "passed": passed, "failed": len(records) - passed},
                    "cases": records,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print("结果已归档：%s" % args.json_out)

    return 0 if passed == len(records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
