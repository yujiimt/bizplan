"""集中設定。モデルやエージェント構成を変えたいときはここだけ触る。"""
from __future__ import annotations
import os
from pathlib import Path

# --- モデル割当 -------------------------------------------------------------
# 高レバレッジ(全体を規定/最終統合)は Opus、中間分析は Sonnet。
OPUS = os.environ.get("BIZPLAN_OPUS_MODEL", "claude-opus-4-8")
SONNET = os.environ.get("BIZPLAN_SONNET_MODEL", "claude-sonnet-4-6")

# --- エージェント構成 -------------------------------------------------------
# order の並び順で逐次実行（並列なし＝引き継ぎ優先）。
# deps: ハンドオフで「結論サマリ + STRUCTURED」を渡す上流。
# needs_full: 本文(Markdown)全文も渡す上流（重い引き継ぎが要る相手だけ）。
# web: WebSearch を許可するか（grounding は CMO/CSO/CTO/CFO のみ）。
AGENTS = [
    {"id": "consultant", "name": "論点整理コンサル", "model": OPUS,   "web": False,
     "deps": [], "needs_full": []},
    {"id": "cmo",        "name": "CMO",            "model": SONNET, "web": True,
     "deps": ["consultant"], "needs_full": []},
    {"id": "cpo",        "name": "CPO / PdM",      "model": SONNET, "web": False,
     "deps": ["consultant", "cmo"], "needs_full": []},
    {"id": "cso",        "name": "CSO",            "model": SONNET, "web": True,
     "deps": ["consultant", "cmo", "cpo"], "needs_full": []},
    {"id": "cto",        "name": "CTO",            "model": SONNET, "web": True,
     "deps": ["consultant", "cpo"], "needs_full": ["cpo"]},
    {"id": "cfo",        "name": "CFO",            "model": SONNET, "web": True,
     "deps": ["consultant", "cso", "cto"], "needs_full": ["cso", "cto"]},
    {"id": "critic",     "name": "クリティック",    "model": SONNET, "web": False,
     "deps": ["consultant", "cmo", "cpo", "cso", "cto", "cfo"],
     "needs_full": ["cmo", "cpo", "cso", "cto", "cfo"]},
    {"id": "ceo",        "name": "CEO",            "model": OPUS,   "web": False,
     "deps": ["consultant", "cmo", "cpo", "cso", "cto", "cfo", "critic"],
     "needs_full": ["consultant", "cmo", "cpo", "cso", "cto", "cfo", "critic"]},
]
AGENTS_BY_ID = {a["id"]: a for a in AGENTS}
PIPELINE_ORDER = [a["id"] for a in AGENTS]

# 改善ウォッチ（メタ retro）。CEO の後に1回走る。中身ではなく「システム」を観測する。
WATCHER = {"id": "watcher", "name": "改善ウォッチ", "model": OPUS, "web": False}

# クリティックの条件付きエスカレーション：severity=high の指摘を最大何件まで
# 当該CXOに1往復差し戻すか（コスト上限）。0 にすると集約型のみ＝最安。
MAX_ESCALATIONS = int(os.environ.get("BIZPLAN_MAX_ESCALATIONS", "2"))

WEB_MAX_TURNS = 12  # WebSearch を持つエージェントのagenticターン上限（コスト止め）

# --- 保存先 -----------------------------------------------------------------
ROOT = Path(os.environ.get("BIZPLAN_DATA_DIR", Path.home() / ".bizplan"))
RUNS_DIR = ROOT / "runs"          # 各ランのartifact(.md/.json)
LEDGER_PATH = ROOT / "ledger.json"  # 実行・resume台帳
IMPROVEMENTS_PATH = ROOT / "improvements.jsonl"  # 改善ウォッチ累積ログ

# --- Notion -----------------------------------------------------------------
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_RUN_DB = os.environ.get("NOTION_RUN_DB", "")        # 事業計画ラン DB
NOTION_OUTPUT_DB = os.environ.get("NOTION_OUTPUT_DB", "")  # エージェント出力 DB
NOTION_WATCH_DB = os.environ.get("NOTION_WATCH_DB", "")    # 改善ウォッチ DB
NOTION_VERSION = "2022-06-28"
