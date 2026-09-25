import json
import os
import platform
from pathlib import Path

import pytest

from scripts.benchmark_tiny_realizer import (
    build_prompt, evaluate_output, frame_from_dict, measure_rule_baseline, process_tree_rss, url_parts,
)


ROOT = Path(__file__).resolve().parents[1]


def workload():
    return json.loads((ROOT / "benchmarks" / "p1-e" / "workload.v1.json").read_text(encoding="utf-8"))


def test_prompt_uses_target_semantics_without_source_fields():
    frame = {
        "source_text": "SOURCE_SECRET_中文",
        "domain": "gaming",
        "intent": "warning",
        "style": "gaming",
        "terms": [{"source": "SOURCE_TERM", "concept": "PRIVATE_CONCEPT", "target": "저격수"}],
        "slots": {"entity": "저격수"},
    }

    prompt = build_prompt(frame)

    assert "SOURCE_SECRET" not in prompt
    assert "SOURCE_TERM" not in prompt
    assert "PRIVATE_CONCEPT" not in prompt
    assert "저격수" in prompt


def test_semantic_and_terminology_oracles_are_separate():
    case = next(case for case in workload()["frames"] if case["case_id"] == "stop_feeding_complaint")

    checks = evaluate_output(case, "한 명씩 가서 죽어주면 답이 없어")

    assert checks["semantic"]["pass"]
    assert not checks["terminology"]["pass"]
    assert checks["terminology"]["missing_terms"] == ["킬 헌납"]


@pytest.mark.parametrize(("case_id", "output"), [
    ("west_sniper_warning", "저격수 서쪽에 위치하며, 게임을 진행할 수 있는 공간입니다."),
    ("base_enemy_warning", "본진에 적이 있고 본진이 적을 방어하고 있다."),
    ("church_materials_request", "교회에 건축 자재가 필요해. 건축 작업을 진행 중."),
    ("group_push_request", "뭉쳐서 망치던 게임을 한 번에 밀자."),
])
def test_semantic_oracle_rejects_unsupported_claims_even_when_slots_are_present(case_id, output):
    case = next(case for case in workload()["frames"] if case["case_id"] == case_id)

    checks = evaluate_output(case, output)

    assert not checks["semantic"]["pass"]
    assert checks["semantic"]["forbidden_fragments_found"]


def test_rule_baseline_matches_every_frozen_case():
    frozen = workload()
    frames = {case["case_id"]: frame_from_dict(case["frame"]) for case in frozen["frames"]}

    report = measure_rule_baseline(frozen, frames, repetitions=1, warmups=0)

    assert report["summary"]["count"] == len(frozen["frames"])
    assert all(report["repetition_stable_by_case"].values())
    assert all(row["checks"]["semantic"]["pass"] for row in report["measurements"])


@pytest.mark.skipif(platform.system() != "Darwin", reason="libproc RSS sampler is macOS-specific")
def test_process_tree_rss_reads_the_current_process():
    assert process_tree_rss(os.getpid())["process_tree_rss_bytes"] > 0


@pytest.mark.parametrize("host", ["https://127.0.0.1:11435", "http://example.com:11435", "http://localhost:11435/path"])
def test_benchmark_host_must_be_plain_loopback_http(host):
    with pytest.raises(ValueError):
        url_parts(host)
