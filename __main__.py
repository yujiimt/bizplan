"""CLI エントリ。

  python -m bizplan run "事業名" --overview "事業概要" [--dry-run] [--resume RUN_ID]
  python -m bizplan watch --last 5            # 横断の改善レビュー
  python -m bizplan show RUN_ID               # ランの結果サマリ
  python -m bizplan sync-notion RUN_ID        # MCP用: 操作ログをJSONLで出力
"""
from __future__ import annotations
import argparse
import json
import sys

from . import config
from .ledger import Ledger
from .pipeline import run_pipeline
from . import watcher as watcher_mod


def _cmd_run(args) -> None:
    run_id = run_pipeline(args.business_name, args.overview or "",
                          dry_run=args.dry_run, resume_run_id=args.resume)
    print(f"\nrun_id = {run_id}")
    if args.dry_run:
        print("（--dry-run: APIもNotionも叩いていません。本番は外して実行）")


def _cmd_watch(args) -> None:
    rows = watcher_mod.review_across_runs(args.last)
    if not rows:
        print("改善ログがまだありません。")
        return
    print(f"直近{args.last}ランの頻出改善ポイント:")
    for r in rows:
        print(f"  [{r['count']}回][{r['area']}/{r.get('priority')}] {r['suggestion']}")


def _cmd_sync_notion(args) -> None:
    """notion_ops.jsonl の内容を標準出力に出力する（ClaudeがMCPで同期するための情報源）。"""
    ops_path = config.RUNS_DIR / args.run_id / "notion_ops.jsonl"
    if not ops_path.exists():
        print(f"[sync-notion] {ops_path} が見つかりません。BIZPLAN_NOTION_MCP=1 で実行しましたか？",
              file=sys.stderr)
        sys.exit(1)
    ops = [json.loads(line) for line in ops_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    print(json.dumps(ops, ensure_ascii=False, indent=2))


def _cmd_show(args) -> None:
    ledger = Ledger()
    run = ledger.get_run(args.run_id)
    print(json.dumps({
        "business_name": run["business_name"],
        "status": run["status"],
        "decision": run.get("decision"),
        "weighted_total": run.get("weighted_total"),
        "agents": {k: v.get("status") for k, v in run["agents"].items()},
    }, ensure_ascii=False, indent=2))


def main() -> None:
    p = argparse.ArgumentParser(prog="bizplan")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("run", help="事業計画パイプラインを実行")
    pr.add_argument("business_name")
    pr.add_argument("--overview", default="")
    pr.add_argument("--dry-run", action="store_true")
    pr.add_argument("--resume", default=None, help="途中で落ちたランのrun_id")
    pr.set_defaults(func=_cmd_run)

    pw = sub.add_parser("watch", help="横断の改善レビュー")
    pw.add_argument("--last", type=int, default=5)
    pw.set_defaults(func=_cmd_watch)

    ps = sub.add_parser("show", help="ランの結果を表示")
    ps.add_argument("run_id")
    ps.set_defaults(func=_cmd_show)

    psn = sub.add_parser("sync-notion", help="MCP用: notion_ops.jsonlを出力してClaudeに渡す")
    psn.add_argument("run_id")
    psn.set_defaults(func=_cmd_sync_notion)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
