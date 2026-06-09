"""パイプライン・オーケストレーション。

逐次実行（並列なし＝引き継ぎ優先）。各エージェント完了直後に
Notion へ個別ページを作成→本文を流し込む。クリティックは集約型＋
severity=high のみ条件付きで当該CXOへ1往復差し戻す（コスト上限あり）。
最後に改善ウォッチ（メタ retro）を1回走らせる。
"""
from __future__ import annotations
import json
from typing import Any

from . import config, contract, prompts
from .ledger import Ledger
from .runner import get_runner
from .notion import get_notion
from . import watcher as watcher_mod


def _fmt_business(run: dict) -> str:
    return (f"## 事業情報\n事業名: {run['business_name']}\n"
            f"事業概要: {run['overview']}\n"
            "（不足する前提は各エージェントが妥当な範囲で補い、補った前提は明示すること）")


def build_user_prompt(agent_id: str, run: dict, ledger: Ledger,
                      extra: str = "") -> str:
    spec = config.AGENTS_BY_ID[agent_id]
    parts = [f"[AGENT:{agent_id}]", _fmt_business(run)]

    # コンサル以外には評価軸を必ず渡す（自己採点/最終採点の基準）
    if agent_id != "consultant":
        cons = ledger.get_run(run_id_of(run, ledger))["agents"].get("consultant")
        if cons and cons.get("status") == "done":
            _, cs = ledger.load_artifact(run_id_of(run, ledger), "consultant")
            axes = cs.get("evaluation_axes", [])
            parts.append("## 評価軸（この軸で自己採点せよ）\n```json\n"
                         + json.dumps(axes, ensure_ascii=False) + "\n```")

    # 上流ハンドオフ：結論サマリ + STRUCTURED（先頭カットはしない）
    rid = run_id_of(run, ledger)
    for dep in spec["deps"]:
        if dep == "consultant":
            continue
        if ledger.agent_status(rid, dep) != "done":
            continue
        body, st = ledger.load_artifact(rid, dep)
        name = config.AGENTS_BY_ID[dep]["name"]
        block = [f"## {name} の結論", st.get("summary", "(なし)"),
                 "```json\n" + json.dumps(st, ensure_ascii=False) + "\n```"]
        if dep in spec["needs_full"]:
            block.append("### " + name + " 本文\n" + body)
        parts.append("\n".join(block))

    if extra:
        parts.append(extra)
    return "\n\n".join(parts)


def run_id_of(run: dict, ledger: Ledger) -> str:
    for rid, r in ledger.data["runs"].items():
        if r is run:
            return rid
    raise KeyError("run not found in ledger")


def _run_one(agent_id: str, run_id: str, ledger: Ledger, runner, notion,
             extra: str = "", version: int = 1) -> dict[str, Any]:
    run = ledger.get_run(run_id)
    spec = config.AGENTS_BY_ID[agent_id]
    # Notion 個別ページを先に作る（走った瞬間に running ページが見える）
    if version == 1:
        page_id = notion.create_agent_page(run["run_page_id"], spec["name"])
    else:
        page_id = ledger.page_id(run_id, agent_id)
    ledger.mark_running(run_id, agent_id, page_id)

    user_prompt = build_user_prompt(agent_id, run, ledger, extra=extra)
    sys_prompt = prompts.build_system_prompt(agent_id)
    res = runner.run(system_prompt=sys_prompt, user_prompt=user_prompt,
                     model=spec["model"], web=spec["web"])
    body, structured = contract.split_artifact(res.text)
    ledger.save_artifact(run_id, agent_id, body, structured, res.cost_usd, version)

    score = _own_axis_score(structured)
    label = spec["name"] + ("（改訂）" if version > 1 else "")
    md = (f"# {label}\n\n" + body) if version == 1 else \
         (f"\n\n## クリティック対応改訂版\n\n" + body)
    notion.finalize_agent_page(page_id, md, structured.get("summary", ""), score)
    return structured


def _own_axis_score(structured: dict) -> float | None:
    scores = [s.get("score") for s in structured.get("self_scores", []) or []
              if isinstance(s.get("score"), (int, float))]
    return round(sum(scores) / len(scores), 2) if scores else None


def run_pipeline(business_name: str, overview: str, *, dry_run: bool,
                 resume_run_id: str | None = None) -> str:
    ledger = Ledger()
    runner = get_runner(dry_run)

    if resume_run_id:
        run_id = resume_run_id
        run = ledger.get_run(run_id)
        notion = get_notion(dry_run, run_id=run_id)
        print(f"[resume] {run_id} ({run['business_name']})")
    else:
        run_id = ledger.create_run(business_name, overview)
        run = ledger.get_run(run_id)
        notion = get_notion(dry_run, run_id=run_id)
        run["run_page_id"] = notion.create_run_page(business_name)
        ledger.set_run_field(run_id, run_page_id=run["run_page_id"], status="running")
        print(f"[start] {run_id} ({business_name})")

    try:
        # 1) 逐次パイプライン（done はスキップ＝resume）
        for agent_id in config.PIPELINE_ORDER:
            if ledger.agent_status(run_id, agent_id) == "done":
                print(f"  - {agent_id}: skip (done)")
                continue
            print(f"  - {agent_id}: running")
            _run_one(agent_id, run_id, ledger, runner, notion)

        # 2) クリティック条件付きエスカレーション
        _, critic_st = ledger.load_artifact(run_id, "critic")
        highs = [c for c in critic_st.get("challenges", []) or []
                 if c.get("severity") == "high"
                 and c.get("target_agent") in config.AGENTS_BY_ID][:config.MAX_ESCALATIONS]
        for ch in highs:
            tgt = ch["target_agent"]
            print(f"  ! escalate -> {tgt}: {ch.get('issue','')[:40]}")
            extra = ("## クリティックからの指摘（高深刻度）\n"
                     f"{ch.get('issue','')}\n上記に応答し、必要なら分析・数字・出典を修正せよ。")
            _run_one(tgt, run_id, ledger, runner, notion, extra=extra, version=2)
            # CEO は最新版を読むので再実行（CEOがまだ古い前提で出していたら）
        if highs and ledger.agent_status(run_id, "ceo") == "done":
            print("  - ceo: re-run after escalation")
            # CEO を作り直す（ページは追記改訂）
            _run_one("ceo", run_id, ledger, runner, notion, version=2)

        # 3) 採点の確定（CEOの自己申告ではなくコード側で再計算）
        _, cons_st = ledger.load_artifact(run_id, "consultant")
        _, ceo_st = ledger.load_artifact(run_id, "ceo")
        axes = cons_st.get("evaluation_axes", [])
        recomputed = contract.compute_weighted_total(ceo_st.get("axis_scores", []), axes)
        total = recomputed if recomputed is not None else ceo_st.get("weighted_total")
        decision = ceo_st.get("decision")
        ledger.set_run_field(run_id, status="done", weighted_total=total,
                             decision=decision)
        notion.update_run_page(run["run_page_id"], status="done",
                               weighted_total=total, decision=decision)
        print(f"[done] total={total} decision={decision}")

        # 4) 改善ウォッチ（メタ retro）
        watcher_mod.run_watcher(run_id, ledger, runner, notion, dry_run=dry_run)

    except Exception as e:  # noqa: BLE001
        # どのエージェントで落ちても、最後に running だったものを failed に
        for aid in config.PIPELINE_ORDER:
            if ledger.agent_status(run_id, aid) == "running":
                ledger.mark_failed(run_id, aid, repr(e))
        print(f"[error] {e!r} — resume_run_id='{run_id}' で再開できます")
        raise

    return run_id
