"""StubRunner 用の擬似アーティファクト。API を叩かずパイプライン全体を通すため。"""

ARTIFACTS = {
    "consultant": """### 入力解釈
中小製造業向けのAI在庫最適化SaaS。前提: 国内、初期はニッチ特化。

### 論点ツリー
- 市場/ 顧客の在庫課題は支払意欲があるか
- 実現/ 需要予測精度は実務に足るか
- 収益/ 単価×継続率で回収できるか

### 評価軸定義
市場性・実現性・収益性・競合優位・リスクの5軸。

### 自己レビューと修正
リスク軸の閾値を明確化した。

---STRUCTURED---
{
  "summary": "中小製造業向けAI在庫最適化SaaS。5軸(市場性0.25/実現性0.20/収益性0.20/競合優位0.20/リスク0.15)で評価する。",
  "evaluation_axes": [
    {"axis": "市場性", "weight": 0.25, "pass_threshold": 3.5, "rubric": "5=明確な需要/1=需要不明"},
    {"axis": "実現性", "weight": 0.20, "pass_threshold": 3.5, "rubric": "5=既存技術で可/1=研究段階"},
    {"axis": "収益性", "weight": 0.20, "pass_threshold": 3.5, "rubric": "5=高粗利/1=赤字構造"},
    {"axis": "競合優位", "weight": 0.20, "pass_threshold": 3.0, "rubric": "5=持続的堀/1=容易に模倣"},
    {"axis": "リスク", "weight": 0.15, "pass_threshold": 3.0, "rubric": "5=低リスク/1=致命的リスク"}
  ],
  "issue_tree": ["支払意欲", "予測精度", "回収可能性"]
}""",
    "cmo": """### 市場分析
国内中小製造業は約38万社。SAMは在庫管理に課題を持つ層。

### 競合分析
汎用在庫SaaSが既存。AI特化は手薄。

### 自己修正
TAM根拠が弱いので推定と明示。

---STRUCTURED---
{
  "summary": "国内中小製造業38万社が母集団。AI在庫特化は競合手薄でポジションあり。",
  "self_scores": [
    {"axis": "市場性", "score": 4, "rationale": "母集団大・課題明確"},
    {"axis": "競合優位", "score": 3, "rationale": "特化で一時的優位"}
  ],
  "key_numbers": [
    {"label": "国内中小製造業数", "value": "約38万社", "basis": "実測", "source": "中小企業白書"},
    {"label": "TAM", "value": "約900億円", "basis": "推定", "source": ""}
  ],
  "flags": ["TAM推定の刻みが粗い"]
}""",
    "cpo": """### プロダクトビジョン
発注点を自動提案するAI在庫アシスタント。

### MVP
需要予測+発注点提案の最小機能。

### 自己修正
オンボーディング摩擦を成功指標に追加。

---STRUCTURED---
{
  "summary": "需要予測と発注点提案に絞ったMVPで検証。既存ERP連携が鍵。",
  "self_scores": [{"axis": "実現性", "score": 4, "rationale": "既存ML手法で可"}],
  "key_numbers": [],
  "flags": ["ERP連携の多様性"]
}""",
    "cso": """### ビジネスモデル
月額SaaS+導入支援。足場は食品加工のニッチ。

### 勝ち筋
ニッチ特化→横展開。

### 自己修正
模倣容易性を競合優位の弱点として明記。

---STRUCTURED---
{
  "summary": "食品加工ニッチを足場にSaaS展開。短期はニッチ深耕、中期に横展開。",
  "self_scores": [
    {"axis": "競合優位", "score": 3, "rationale": "データ蓄積が堀になりうる"},
    {"axis": "収益性", "score": 4, "rationale": "SaaS継続課金"}
  ],
  "key_numbers": [],
  "flags": ["横展開時の汎化リスク"]
}""",
    "cto": """### 技術実現性
需要予測=中難易度。既存時系列モデルで可。

### システム構成
クラウドML+API連携。

### 自己修正
ERP連携の標準化が技術リスク。

---STRUCTURED---
{
  "summary": "需要予測は既存技術で実現可能。最大リスクはERP連携の多様性。",
  "self_scores": [{"axis": "実現性", "score": 4, "rationale": "枯れた手法で足りる"}],
  "key_numbers": [],
  "flags": ["連携工数が読みにくい"]
}""",
    "cfo": """### 収益モデル
月額3万円×継続。

### 収支シミュレーション
3年で黒字化想定。

### 自己修正
単価の根拠が弱い。

---STRUCTURED---
{
  "summary": "月額3万円・解約率2%前提で3年黒字化。単価前提が最大の不確実性。",
  "self_scores": [
    {"axis": "収益性", "score": 3, "rationale": "単価×継続で回収可だが薄い"},
    {"axis": "リスク", "score": 3, "rationale": "単価前提の感度が高い"}
  ],
  "key_numbers": [
    {"label": "想定月額単価", "value": "30,000円", "basis": "実測", "source": ""},
    {"label": "想定解約率", "value": "月2%", "basis": "推定", "source": ""}
  ],
  "flags": ["単価の市場検証が未"]
}""",
    "critic": """### 総評
骨子は妥当だが数字の足腰が弱い。

### 根拠の弱い数字
CFOの想定月額単価に出典がない。

### 最重要の指摘
単価前提の検証なしにGo判断は危険。

---STRUCTURED---
{
  "summary": "全体の論理は通るが、CFOの単価前提が出典なしで、収益性の根拠が脆い。",
  "challenges": [
    {"target_agent": "cfo", "issue": "想定月額単価30,000円に出典がなく実測と矛盾", "severity": "high"},
    {"target_agent": "cmo", "issue": "TAM推定の刻みが粗い", "severity": "med"}
  ]
}""",
    "ceo": """### 採用/不採用
CMO・CSOを採用、CTOの楽観は割引。

### クリティック応答
単価前提は実証実験で検証する条件を付す。

### 軸採点
5軸で加重採点。

### Go判断
条件付Go。

---STRUCTURED---
{
  "summary": "ニッチ足場のAI在庫SaaSは条件付Go。単価の実証を最優先条件とする。",
  "adopted": ["cmo", "cso", "cpo"],
  "rejected": [{"agent": "cto", "reason": "ERP連携工数を楽観視"}],
  "axis_scores": [
    {"axis": "市場性", "score": 4, "weight": 0.25},
    {"axis": "実現性", "score": 4, "weight": 0.20},
    {"axis": "収益性", "score": 3, "weight": 0.20},
    {"axis": "競合優位", "score": 3, "weight": 0.20},
    {"axis": "リスク", "score": 3, "weight": 0.15}
  ],
  "weighted_total": 3.45,
  "decision": "条件付Go",
  "challenge_responses": [
    {"challenge": "単価前提に出典なし", "response": "PoCで3社の支払意欲を実測してから本格投資"}
  ],
  "priority_actions": ["単価の実証(3社PoC)", "ERP連携の標準化検証", "食品加工ニッチでの初期獲得"],
  "open_issues": ["単価の市場検証", "横展開時の汎化"]
}""",
    "watcher": """### 総括
評価軸は機能したが、grounding が一部空回り。

### grounding改善
CFOの実測ラベルに source 空欄が混在。

### 次に効く一手
key_numbers の basis=実測 で source 空欄なら自動で推定に格下げする検証を入れる。

---STRUCTURED---
{
  "summary": "評価軸ループは機能。ただし実測ラベルの出典欠落が残り、CFO段が弱点。",
  "findings": [
    {"area": "grounding", "observation": "CFOが単価を実測扱いだが source 空欄", "suggestion": "source空の実測は自動で推定に降格＋警告", "priority": "high"},
    {"area": "process", "observation": "CTOがCEOに不採用された", "suggestion": "CTOへ連携工数の根拠提示を必須化", "priority": "med"}
  ],
  "metrics": {"total_cost_usd": 0.0, "unsourced_numbers": 0, "high_severity_challenges": 0}
}""",
}
