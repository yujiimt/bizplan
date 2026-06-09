# bizplan — 事業計画マルチエージェント（Claude Agent SDK版）

「事業名＋概要」を入れると、論点整理コンサル→CMO→CPO→CSO→CTO→CFO→クリティック→CEO が
**逐次**で分析し、CEOがコンサル定義の評価軸で採点してGo/NoGoを出す。各エージェントの出力は
走った瞬間にNotionへ個別ページとして書き出され、最後に**改善ウォッチ**がパイプライン自体の
改善点を観測して蓄積する。

```
consultant → CMO → CPO → CSO → CTO → CFO → critic ──┐
   │(評価軸を定義)                        (高深刻度だけ当該CXOへ1往復差し戻し)
   └──────────── 同じ評価軸で採点 ───────────────→ CEO → 改善ウォッチ
```

## 設計の要点
- **閉ループ採点**: コンサルが `evaluation_axes`(軸+weight+閾値) を定義 → 各CXOが自己採点 → CEOが同じ軸で加重採点。総合点は**コード側で再計算**（モデルの自己申告を信用しない）。
- **データ契約**: 全出力 = Markdown本文 + `---STRUCTURED---` + JSON。数字は `basis:"実測"|"推定"`、実測は `source` 必須。
- **ハンドオフ**: 上流の「結論サマリ＋STRUCTURED全体」を渡す（先頭カットしない）。重い相手だけ本文も。
- **クリティック**: 集約型＋ `severity:"high"` のみ条件付きで当該CXOへ差し戻し（`MAX_ESCALATIONS` 件まで）。
- **grounding**: CMO/CSO/CTO/CFO のみ WebSearch。
- **二層保存**: ローカルJSON台帳＝実行/resume、Notion＝人が読む成果物SoT。
- **改善ウォッチ**: 中身でなく仕組み（prompt/process/grounding/cost）を観測し `improvements.jsonl`＋Notionへ蓄積。

## ファイル構成
```
bizplan/
  config.py     モデル割当・エージェント順序・依存・Notion設定（まずここを触る）
  prompts.py    各エージェントのsystem prompt本体
  contract.py   STRUCTURED契約・パーサ・採点ロジック
  ledger.py     ローカル実行台帳（resumeの真実）
  runner.py     SDKアダプタ（SDK依存はここだけ）＋StubRunner
  notion.py     Notion二層出力・md→ブロック変換＋StubNotion
  pipeline.py   オーケストレーション本体
  watcher.py    改善ウォッチ（メタretro）
  __main__.py   CLI
tests/smoke_test.py
```

## セットアップ
1. Python 3.10+。`pip install -r requirements.txt`
2. 認証（どちらか）: `claude login`（サブスク認証）または `export ANTHROPIC_API_KEY=...`
   - 注: 2026-06-15以降、サブスクでのAgent SDK利用は別枠のSDKクレジットから引かれる。7+1体×案件数で回すなら従量(APIキー)課金を推奨。
3. Notion: インテグレーションを作成し `export NOTION_TOKEN=...`。下記3つのDBを作り、各DBをそのインテグレーションに共有。DBのIDを環境変数へ。
   ```
   export NOTION_RUN_DB=...     # 事業計画ラン DB
   export NOTION_OUTPUT_DB=...  # エージェント出力 DB
   export NOTION_WATCH_DB=...   # 改善ウォッチ DB
   ```

### Notion DBのプロパティ（コードが参照する名前）
- 事業計画ラン: `事業名`(title) / `Status`(select) / `総合点`(number) / `判定`(select)
- エージェント出力: `Name`(title) / `エージェント`(select) / `Status`(select) / `ラン`(relation→事業計画ラン) / `summary`(text) / `担当軸スコア`(number)
- 改善ウォッチ: `Name`(title) / `summary`(text) / `ラン`(relation→事業計画ラン)

## 使い方
```bash
# まずドライラン（API/Notionを一切叩かず全工程を確認）
python -m bizplan run "事業名" --overview "事業概要" --dry-run

# 本番
python -m bizplan run "事業名" --overview "事業概要"

# 途中で落ちたら、台帳のrun_idから再開（done工程はスキップ）
python -m bizplan run x --overview y --resume 20260609-...

# 横断の改善レビュー（直近Nラン）／ラン結果の確認
python -m bizplan watch --last 5
python -m bizplan show <run_id>
```
データは既定で `~/.bizplan/`（`BIZPLAN_DATA_DIR` で変更可）。

## 動かしながら改善するループ
1. `run` → Notionで成果物を読む → `improvements.jsonl` と改善ウォッチDBで仕組みの弱点を見る
2. `watch --last N` で頻出の改善ポイントを特定
3. `prompts.py`（指示）や `config.py`（軸・モデル・依存・エスカレーション数）を直す
4. 再び `run` → ウォッチの指標（unsourced_numbers / high_severity_challenges / cost）が改善するか観測

## 既知の調整ポイント
- `runner.py` のWebSearchツール露出（`allowed_tools`/`tools`/`disallowed_tools`）はSDKバージョンで挙動が揺れる。期待と違えばここを調整。
- claude-agent-sdk はalpha。`query()`/`ClaudeAgentOptions` のAPI差異が出たら `runner.py` だけ直せば全体は動く。
- モデルID（`claude-opus-4-8` / `claude-sonnet-4-6`）は `config.py` または環境変数で差し替え可能。
