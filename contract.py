"""データ契約。

全アーティファクト = 「Markdown本文」+ 区切り `---STRUCTURED---` + JSON。
ここに (1) 各役割が末尾に吐く JSON のスキーマ指示、(2) パーサ、(3) 採点を集約する。
"""
from __future__ import annotations
import json
import re
from typing import Any

SEP = "---STRUCTURED---"

# 全エージェント共通の出力規約（system_prompt 末尾に必ず付与）
COMMON_CONTRACT = f"""

## 出力規約（厳守）
本文を Markdown で書いたあと、最後に必ず次の区切り行を置き、続けて1個の JSON だけを出力する。
JSON の前後に説明文・コードフェンス(```)を付けない。

{SEP}
{{ ...役割別スキーマ... }}

数字を出すときは必ず `basis` を `"実測"`（出典あり）か `"推定"` のどちらかで明示し、
`"実測"` のときは `source`（URL や出典名）を入れる。出典なしの数字を実測と偽らない。
"""

# 役割別の STRUCTURED スキーマ（指示文として埋め込む）
SCHEMAS: dict[str, str] = {
    "consultant": """{
  "summary": "300字以内の結論サマリ（次工程への引き継ぎ用）",
  "evaluation_axes": [
    {"axis": "市場性", "weight": 0.25, "pass_threshold": 3.5, "rubric": "5=…/1=… の採点基準"}
  ],
  "issue_tree": ["大論点1", "大論点2"]
}
※ weight の合計は 1.0。axis は3〜6個。これが後工程の自己採点とCEO最終採点の唯一の軸になる。""",
    "_cxo": """{
  "summary": "300字以内の結論サマリ",
  "self_scores": [{"axis": "市場性", "score": 4, "rationale": "根拠1行"}],
  "key_numbers": [{"label": "TAM", "value": "1,200億円", "basis": "推定", "source": ""}],
  "flags": ["未検証の前提や懸念"]
}
※ self_scores はコンサルが定義した evaluation_axes のうち自分が判断できる軸に対して 1〜5 で付ける。""",
    "critic": """{
  "summary": "300字以内の総評",
  "challenges": [
    {"target_agent": "cfo", "issue": "収益の単価仮定に出典がない", "severity": "high"}
  ]
}
※ severity は high/med/low。high は「根拠なき数字」「致命的矛盾」「未検証の事業前提」に限る。""",
    "ceo": """{
  "summary": "300字以内のエグゼクティブサマリ",
  "adopted": ["cmo", "cso"],
  "rejected": [{"agent": "cto", "reason": "…"}],
  "axis_scores": [{"axis": "市場性", "score": 4, "weight": 0.25}],
  "weighted_total": 3.8,
  "decision": "条件付Go",
  "challenge_responses": [{"challenge": "…", "response": "反論または修正内容"}],
  "priority_actions": ["最初に取り組む3〜5個"],
  "open_issues": ["残課題・未検証仮説"]
}
※ axis_scores はコンサルの evaluation_axes と同じ軸・weight を使う。decision は Go / 条件付Go / NoGo。""",
    "watcher": """{
  "summary": "このランから見えたシステム改善の総括",
  "findings": [
    {"area": "prompt", "observation": "観測した事実", "suggestion": "具体的改善", "priority": "high"}
  ],
  "metrics": {"total_cost_usd": 0.0, "unsourced_numbers": 0, "high_severity_challenges": 0}
}
※ area は prompt/process/grounding/cost のいずれか。事業の良し悪しではなく「仕組みの直し方」を書く。""",
}


def schema_for(agent_id: str) -> str:
    if agent_id in SCHEMAS:
        return SCHEMAS[agent_id]
    return SCHEMAS["_cxo"]


def split_artifact(text: str) -> tuple[str, dict[str, Any]]:
    """アーティファクト文字列を (本文Markdown, structured dict) に分解。

    STRUCTURED が無い/壊れている場合も本文は必ず返し、structured は {} を返す。
    """
    if SEP not in text:
        return text.strip(), {}
    body, _, tail = text.partition(SEP)
    structured = _loads_lenient(tail)
    return body.strip(), structured


def _loads_lenient(tail: str) -> dict[str, Any]:
    tail = tail.strip()
    # コードフェンスが混じっても拾えるように { … } を抽出
    tail = re.sub(r"^```(?:json)?|```$", "", tail.strip(), flags=re.MULTILINE).strip()
    start = tail.find("{")
    if start == -1:
        return {}
    # 末尾から閉じ括弧を探して最大の JSON を試す
    for end in range(len(tail), start, -1):
        chunk = tail[start:end]
        if chunk.rstrip().endswith("}"):
            try:
                return json.loads(chunk)
            except json.JSONDecodeError:
                continue
    return {}


def compute_weighted_total(axis_scores: list[dict], axes: list[dict]) -> float | None:
    """CEO の自己申告ではなく、軸スコア×コンサルのweightをコード側で再計算する。"""
    if not axis_scores or not axes:
        return None
    weight_by_axis = {a.get("axis"): float(a.get("weight", 0)) for a in axes}
    total = 0.0
    wsum = 0.0
    for s in axis_scores:
        w = weight_by_axis.get(s.get("axis"))
        if w is None:
            continue
        try:
            total += float(s.get("score", 0)) * w
        except (TypeError, ValueError):
            continue
        wsum += w
    if wsum == 0:
        return None
    return round(total / wsum * (sum(weight_by_axis.values()) or 1), 3)


def count_unsourced_numbers(structured_by_agent: dict[str, dict]) -> int:
    n = 0
    for st in structured_by_agent.values():
        for kn in st.get("key_numbers", []) or []:
            if kn.get("basis") == "実測" and not (kn.get("source") or "").strip():
                n += 1
    return n
