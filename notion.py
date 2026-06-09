"""Notion 出力（オーケストレーターが書く役）。

二層構成:
  事業計画ラン DB     … 1行=1ラン（Status/総合点/判定）
  エージェント出力 DB … 1行=1エージェント実行=個別ページ（本文=ページ本体）
  改善ウォッチ DB     … 1行=1ランの改善観測

クライアント種別:
  NotionClient    … NOTION_TOKEN 環境変数でREST直叩き
  McpNotionClient … BIZPLAN_NOTION_MCP=1 のとき。操作をnotion_ops.jsonlに記録し、
                    パイプライン完了後にClaudeがMCPツールで同期する。
  StubNotion      … ドライランのみ。APIを一切叩かない。
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any

from . import config

API = "https://api.notion.com/v1"
MAX_BLOCKS_PER_CALL = 100
MAX_RICH_TEXT = 2000


# --- Markdown → Notion ブロック --------------------------------------------
def _rich(text: str) -> list[dict]:
    """2000字制限に合わせて rich_text を分割。"""
    out = []
    for i in range(0, max(len(text), 1), MAX_RICH_TEXT):
        out.append({"type": "text", "text": {"content": text[i:i + MAX_RICH_TEXT]}})
    return out


def md_to_blocks(md: str) -> list[dict]:
    blocks: list[dict] = []
    in_code = False
    code_buf: list[str] = []
    for raw in md.splitlines():
        line = raw.rstrip("\n")
        if line.strip().startswith("```"):
            if in_code:
                blocks.append({"object": "block", "type": "code", "code": {
                    "language": "plain text", "rich_text": _rich("\n".join(code_buf))}})
                code_buf, in_code = [], False
            else:
                in_code = True
            continue
        if in_code:
            code_buf.append(line)
            continue
        if not line.strip():
            continue
        if line.startswith("### "):
            blocks.append(_heading(3, line[4:]))
        elif line.startswith("## "):
            blocks.append(_heading(2, line[3:]))
        elif line.startswith("# "):
            blocks.append(_heading(1, line[2:]))
        elif line.strip() in ("---", "***", "___"):
            blocks.append({"object": "block", "type": "divider", "divider": {}})
        elif line.lstrip().startswith(("- ", "* ")):
            blocks.append({"object": "block", "type": "bulleted_list_item",
                           "bulleted_list_item": {"rich_text": _rich(line.lstrip()[2:])}})
        else:
            blocks.append({"object": "block", "type": "paragraph",
                           "paragraph": {"rich_text": _rich(line)}})
    if code_buf:
        blocks.append({"object": "block", "type": "code", "code": {
            "language": "plain text", "rich_text": _rich("\n".join(code_buf))}})
    return blocks


def _heading(level: int, text: str) -> dict:
    key = f"heading_{level}"
    return {"object": "block", "type": key, key: {"rich_text": _rich(text)}}


# --- 本番クライアント -------------------------------------------------------
class NotionClient:
    def __init__(self) -> None:
        import requests  # 遅延 import
        self._requests = requests
        if not config.NOTION_TOKEN:
            raise RuntimeError("NOTION_TOKEN 未設定。環境変数を設定してください。")
        self.headers = {
            "Authorization": f"Bearer {config.NOTION_TOKEN}",
            "Notion-Version": config.NOTION_VERSION,
            "Content-Type": "application/json",
        }

    def _post(self, path: str, payload: dict) -> dict:
        r = self._requests.post(f"{API}{path}", headers=self.headers,
                                data=json.dumps(payload))
        r.raise_for_status()
        return r.json()

    def _patch(self, path: str, payload: dict) -> dict:
        r = self._requests.patch(f"{API}{path}", headers=self.headers,
                                 data=json.dumps(payload))
        r.raise_for_status()
        return r.json()

    def create_run_page(self, business_name: str) -> str:
        page = self._post("/pages", {
            "parent": {"database_id": config.NOTION_RUN_DB},
            "properties": {
                "事業名": {"title": [{"text": {"content": business_name}}]},
                "Status": {"select": {"name": "running"}},
            },
        })
        return page["id"]

    def update_run_page(self, page_id: str, *, status: str,
                        weighted_total: float | None, decision: str | None) -> None:
        props: dict[str, Any] = {"Status": {"select": {"name": status}}}
        if weighted_total is not None:
            props["総合点"] = {"number": weighted_total}
        if decision:
            props["判定"] = {"select": {"name": decision}}
        self._patch(f"/pages/{page_id}", {"properties": props})

    def create_agent_page(self, run_page_id: str, agent_name: str) -> str:
        page = self._post("/pages", {
            "parent": {"database_id": config.NOTION_OUTPUT_DB},
            "properties": {
                "Name": {"title": [{"text": {"content": agent_name}}]},
                "エージェント": {"select": {"name": agent_name}},
                "Status": {"select": {"name": "running"}},
                "ラン": {"relation": [{"id": run_page_id}]},
            },
        })
        return page["id"]

    def finalize_agent_page(self, page_id: str, body_md: str,
                            summary: str, score: float | None) -> None:
        blocks = md_to_blocks(body_md)
        for i in range(0, len(blocks), MAX_BLOCKS_PER_CALL):
            self._patch(f"/blocks/{page_id}/children",
                        {"children": blocks[i:i + MAX_BLOCKS_PER_CALL]})
        props: dict[str, Any] = {
            "Status": {"select": {"name": "done"}},
            "summary": {"rich_text": _rich(summary or "")},
        }
        if score is not None:
            props["担当軸スコア"] = {"number": score}
        self._patch(f"/pages/{page_id}", {"properties": props})

    def create_watch_page(self, run_page_id: str, business_name: str,
                          body_md: str, summary: str) -> str:
        page = self._post("/pages", {
            "parent": {"database_id": config.NOTION_WATCH_DB},
            "properties": {
                "Name": {"title": [{"text": {"content": f"改善ウォッチ: {business_name}"}}]},
                "summary": {"rich_text": _rich(summary or "")},
                "ラン": {"relation": [{"id": run_page_id}]},
            },
        })
        blocks = md_to_blocks(body_md)
        for i in range(0, len(blocks), MAX_BLOCKS_PER_CALL):
            self._patch(f"/blocks/{page['id']}/children",
                        {"children": blocks[i:i + MAX_BLOCKS_PER_CALL]})
        return page["id"]


# --- MCP 遅延実行クライアント ------------------------------------------------
class McpNotionClient:
    """パイプライン中は操作をJSONLに記録し、完了後にClaudeがMCPで同期する。

    各操作には $ref（シンボリックID）を付与。sync時にClaudeが実際のpage_idに解決する。
    run後に `python -m bizplan sync-notion <run_id>` を呼ぶと操作一覧を出力するので、
    ClaudeがNotion MCPツールを使って順番に実行する。
    """

    def __init__(self, ops_path: Path) -> None:
        self._ops_path = ops_path
        ops_path.parent.mkdir(parents=True, exist_ok=True)
        ops_path.write_text("")

    def _write(self, op: dict) -> None:
        with open(self._ops_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(op, ensure_ascii=False) + "\n")

    def create_run_page(self, business_name: str) -> str:
        self._write({"op": "create_run_page", "ref": "$run",
                     "business_name": business_name})
        return "$run"

    def update_run_page(self, page_id: str, *, status: str,
                        weighted_total: float | None, decision: str | None) -> None:
        self._write({"op": "update_run_page", "ref": page_id, "status": status,
                     "weighted_total": weighted_total, "decision": decision})

    def create_agent_page(self, run_page_id: str, agent_name: str) -> str:
        ref = f"$agent_{agent_name}"
        self._write({"op": "create_agent_page", "ref": ref,
                     "run_ref": run_page_id, "agent_name": agent_name})
        return ref

    def finalize_agent_page(self, page_id: str, body_md: str,
                            summary: str, score: float | None) -> None:
        self._write({"op": "finalize_agent_page", "ref": page_id,
                     "body_md": body_md, "summary": summary or "", "score": score})

    def create_watch_page(self, run_page_id: str, business_name: str,
                          body_md: str, summary: str) -> str:
        self._write({"op": "create_watch_page", "ref": "$watch",
                     "run_ref": run_page_id, "business_name": business_name,
                     "body_md": body_md, "summary": summary or ""})
        return "$watch"


# --- スタブ -----------------------------------------------------------------
class StubNotion:
    def __init__(self) -> None:
        self.log: list[str] = []
        self._n = 0

    def _id(self, kind: str) -> str:
        self._n += 1
        pid = f"stub-{kind}-{self._n}"
        self.log.append(f"[notion] +page {pid}")
        return pid

    def create_run_page(self, business_name): return self._id("run")
    def update_run_page(self, page_id, *, status, weighted_total, decision):
        self.log.append(f"[notion] update {page_id} status={status} total={weighted_total} decision={decision}")
    def create_agent_page(self, run_page_id, agent_name): return self._id("agent")
    def finalize_agent_page(self, page_id, body_md, summary, score):
        self.log.append(f"[notion] finalize {page_id} score={score} blocks={len(md_to_blocks(body_md))}")
    def create_watch_page(self, run_page_id, business_name, body_md, summary):
        return self._id("watch")


def get_notion(dry_run: bool, run_id: str | None = None):
    if dry_run:
        return StubNotion()
    if os.environ.get("BIZPLAN_NOTION_MCP"):
        ops_path = config.RUNS_DIR / (run_id or "unknown") / "notion_ops.jsonl"
        return McpNotionClient(ops_path)
    return NotionClient()
