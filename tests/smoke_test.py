"""依存(SDK/Notion)なしで動くユニットスモーク: `python tests/smoke_test.py`"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bizplan import contract
from bizplan.notion import md_to_blocks


def test_split_clean():
    body, st = contract.split_artifact('本文\n\n---STRUCTURED---\n{"summary":"ok"}')
    assert body == "本文" and st["summary"] == "ok"


def test_split_fenced_json():
    # モデルが誤ってコードフェンスを付けても拾える
    txt = '本文\n---STRUCTURED---\n```json\n{"summary":"x","findings":[]}\n```'
    _, st = contract.split_artifact(txt)
    assert st["summary"] == "x"


def test_split_missing():
    body, st = contract.split_artifact("構造化ブロックなしの本文だけ")
    assert "本文だけ" in body and st == {}


def test_weighted():
    axes = [{"axis": "A", "weight": 0.5}, {"axis": "B", "weight": 0.5}]
    scores = [{"axis": "A", "score": 4}, {"axis": "B", "score": 2}]
    assert contract.compute_weighted_total(scores, axes) == 3.0


def test_unsourced():
    sba = {"cfo": {"key_numbers": [
        {"label": "x", "value": "1", "basis": "実測", "source": ""},
        {"label": "y", "value": "2", "basis": "推定", "source": ""},
        {"label": "z", "value": "3", "basis": "実測", "source": "url"},
    ]}}
    assert contract.count_unsourced_numbers(sba) == 1


def test_blocks_chunk():
    # 2000字超の段落は rich_text が分割される
    blocks = md_to_blocks("# 見出し\n" + "あ" * 2500 + "\n- 箇条書き")
    para = [b for b in blocks if b["type"] == "paragraph"][0]
    assert len(para["paragraph"]["rich_text"]) == 2
    assert any(b["type"] == "heading_1" for b in blocks)
    assert any(b["type"] == "bulleted_list_item" for b in blocks)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
