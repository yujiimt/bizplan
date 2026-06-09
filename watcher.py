"""改善ウォッチ（メタ retro）エージェント。

事業計画の中身ではなく「パイプライン自体」を観測する。CEOの後に1回走り、
prompt/process/grounding/cost の観点で改善 finding を出し、Notion 改善ウォッチDB と
ローカル improvements.jsonl に蓄積する。`watch --last N` で横断レビューもできる。
"""
from __future__ import annotations
import json

from . import config, contract, prompts


def _collect_metrics(run_id, ledger) -> dict:
    run = ledger.get_run(run_id)
    arts = ledger.all_artifacts(run_id)
    structured_by_agent = {aid: st for aid, (_b, st) in arts.items()}
    total_cost = round(sum(a.get("cost_usd") or 0
                           for a in run["agents"].values()), 4)
    critic_st = structured_by_agent.get("critic", {})
    highs = sum(1 for c in critic_st.get("challenges", []) or []
                if c.get("severity") == "high")
    return {
        "total_cost_usd": total_cost,
        "unsourced_numbers": contract.count_unsourced_numbers(structured_by_agent),
        "high_severity_challenges": highs,
    }


def _build_watch_prompt(run_id, ledger, metrics) -> str:
    run = ledger.get_run(run_id)
    arts = ledger.all_artifacts(run_id)
    lines = ["[AGENT:watcher]",
             f"## 対象ラン\n事業名: {run['business_name']}  判定: {run.get('decision')}  "
             f"総合点: {run.get('weighted_total')}",
             "## 計測値\n```json\n" + json.dumps(metrics, ensure_ascii=False) + "\n```",
             "## 各エージェントの結論サマリ"]
    for aid, (_b, st) in arts.items():
        if aid in ("watcher",):
            continue
        lines.append(f"- {aid}: {st.get('summary','')}")
    ceo = arts.get("ceo", ("", {}))[1]
    lines.append("## CEOの採用/不採用\n```json\n" + json.dumps(
        {"adopted": ceo.get("adopted"), "rejected": ceo.get("rejected")},
        ensure_ascii=False) + "\n```")
    critic = arts.get("critic", ("", {}))[1]
    lines.append("## クリティックの指摘\n```json\n" + json.dumps(
        critic.get("challenges", []), ensure_ascii=False) + "\n```")
    lines.append("以上から、このパイプライン（仕組み）の改善点を findings として出せ。")
    return "\n\n".join(lines)


def run_watcher(run_id, ledger, runner, notion, *, dry_run: bool) -> dict:
    metrics = _collect_metrics(run_id, ledger)
    user_prompt = _build_watch_prompt(run_id, ledger, metrics)
    sys_prompt = prompts.build_system_prompt("watcher")
    res = runner.run(system_prompt=sys_prompt, user_prompt=user_prompt,
                     model=config.WATCHER["model"], web=False)
    body, structured = contract.split_artifact(res.text)
    # 計測値はコード側の値で上書き（モデルの自己申告を信用しない）
    structured.setdefault("metrics", {}).update(metrics)
    ledger.save_artifact(run_id, "watcher", body, structured, res.cost_usd)

    run = ledger.get_run(run_id)
    notion.create_watch_page(run["run_page_id"], run["business_name"],
                             "# 改善ウォッチ\n\n" + body, structured.get("summary", ""))

    rec = {"run_id": run_id, "business_name": run["business_name"],
           "metrics": structured.get("metrics", {}),
           "findings": structured.get("findings", [])}
    with open(config.IMPROVEMENTS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"[watcher] findings={len(rec['findings'])} cost={metrics['total_cost_usd']}")
    return structured


def review_across_runs(last_n: int) -> list[dict]:
    """improvements.jsonl から直近 N ランの finding を集め、頻出順に返す。"""
    if not config.IMPROVEMENTS_PATH.exists():
        return []
    recs = [json.loads(l) for l in
            config.IMPROVEMENTS_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    recs = recs[-last_n:]
    tally: dict[tuple, dict] = {}
    for r in recs:
        for fd in r.get("findings", []):
            key = (fd.get("area"), fd.get("suggestion"))
            t = tally.setdefault(key, {"area": fd.get("area"),
                                       "suggestion": fd.get("suggestion"),
                                       "count": 0, "priority": fd.get("priority")})
            t["count"] += 1
    return sorted(tally.values(), key=lambda x: x["count"], reverse=True)
