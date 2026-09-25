from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
import os
import platform
import shutil
import socket
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

from marco_translator.knowledge import KnowledgeStore
from marco_translator.marco_adapter import MarcoResolver
from marco_translator.models import SemanticFrame, TermDecision, TranslationRequest
from marco_translator.pipeline import Translator
from marco_translator.realizer import RuleRealizer


ROOT = Path(__file__).resolve().parents[1]
WORKLOAD = ROOT / "benchmarks" / "p1-e" / "workload.v1.json"
OPTIONS = {"temperature": 0, "seed": 20260925, "top_k": 1, "num_ctx": 2048, "num_predict": 64}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def frame_from_dict(value: dict) -> SemanticFrame:
    return SemanticFrame(
        source_language=value["source_language"],
        target_language=value["target_language"],
        source_text=value["source_text"],
        domain=value.get("domain"),
        intent=value.get("intent", "statement"),
        style=value.get("style", "neutral"),
        terms=[TermDecision(**{**term, "evidence": tuple(term.get("evidence", []))}) for term in value.get("terms", [])],
        template=value.get("template"),
        slots=value.get("slots", {}),
        unresolved=value.get("unresolved", []),
        confidence=value.get("confidence", 0.0),
    )


def build_prompt(frame: dict) -> str:
    payload = {
        "target_language": "Korean",
        "domain": frame.get("domain"),
        "intent": frame.get("intent"),
        "style": frame.get("style"),
        "preferred_terms": [term["target"] for term in frame.get("terms", [])],
        "slots": frame.get("slots", {}),
    }
    return (
        "Write one concise, natural gaming-chat line in the target language. "
        "Preserve every slot, use preferred terms when applicable, add no facts, and output no explanation.\n"
        + canonical(payload)
    )


def evaluate_output(case: dict, output: str) -> dict:
    text = " ".join(output.split())
    oracle = case["oracle"]
    missing_slots = [slot for slot in oracle["required_slots"] if slot not in text]
    contradictions = [part for part in oracle["forbidden_fragments"] if part in text]
    missing_terms = [term for term in oracle["required_terminology"] if term not in text]
    return {
        "semantic": {
            "pass": not missing_slots and not contradictions,
            "missing_slots": missing_slots,
            "forbidden_fragments_found": contradictions,
        },
        "terminology": {"pass": not missing_terms, "missing_terms": missing_terms},
    }


def api_request(opener, base_url: str, path: str, payload: dict | None = None, timeout: float = 120) -> dict:
    url = base_url + path
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=data, headers={"Content-Type": "application/json"}, method="GET" if data is None else "POST")
    try:
        with opener.open(request, timeout=timeout) as response:
            return json.load(response)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"Ollama HTTP {exc.code} for {path}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"loopback Ollama request failed for {path}: {exc}") from exc


def url_parts(value: str) -> int:
    parsed = urlsplit(value)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1":
        raise ValueError("Ollama host must use IPv4 loopback")
    if parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("Ollama host must not include credentials, a path, or query")
    port = 11435 if parsed.port is None else parsed.port
    if not 1024 <= port <= 65535:
        raise ValueError("Ollama port must be between 1024 and 65535")
    return port


def sandbox_reexec(args: argparse.Namespace, argv: list[str]) -> int | None:
    if os.environ.get("MARCO_TRANSLATOR_P1E_SANDBOX_ACTIVE") == "1":
        return None
    if platform.system() != "Darwin":
        raise RuntimeError("the P1-E candidate benchmark requires macOS sandbox-exec")
    sandbox = shutil.which("sandbox-exec")
    if not sandbox:
        raise RuntimeError("sandbox-exec is unavailable; the offline benchmark cannot start")
    url_parts(args.host)
    profile = (
        '(version 1) (allow default) (deny network-outbound) (deny network-inbound) '
        '(allow network-outbound (remote ip "localhost:*")) '
        '(allow network-inbound (local ip "localhost:*"))'
    )
    child_env = os.environ.copy()
    child_env["MARCO_TRANSLATOR_P1E_SANDBOX_ACTIVE"] = "1"
    return subprocess.run(
        [sandbox, "-p", profile, sys.executable, str(Path(__file__).resolve()), *argv],
        check=False, env=child_env,
    ).returncode


def validate_isolated_cache(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    temporary_root = Path("/tmp").resolve()
    if os.path.commonpath([str(path), str(temporary_root)]) != str(temporary_root) or path == temporary_root:
        raise ValueError("model cache must be an existing child directory of /tmp")
    if not path.is_dir():
        raise ValueError("model cache directory does not exist; this script never downloads models")
    return path


def load_and_verify_workload(mco: Path, marco_root: Path) -> tuple[dict, dict]:
    workload = json.loads(WORKLOAD.read_text(encoding="utf-8"))
    identity = workload["source_identity"]
    paths = {
        "mco_sha256": mco,
        "frame_map_sha256": ROOT / "knowledge" / "marco-frame-map.zh-ko.json",
        "seed_sha256": ROOT / "knowledge" / "seed.zh-ko.json",
    }
    observed = {key: sha256(path) for key, path in paths.items()}
    if observed != {key: identity[key] for key in observed}:
        raise ValueError(f"workload provenance mismatch: {observed}")
    revision = subprocess.check_output(["git", "-C", str(marco_root), "rev-parse", "HEAD"], text=True).strip()
    if revision != identity["marco_revision"]:
        raise ValueError(f"upstream MARCO revision mismatch: {revision}")

    resolver = MarcoResolver(
        str(mco), str(ROOT / "knowledge" / "marco-frame-map.zh-ko.json"),
        knowledge=KnowledgeStore.from_json(ROOT / "knowledge" / "seed.zh-ko.json"),
        marco_root=str(marco_root),
    )
    actual_frames = {}
    for case in workload["frames"]:
        frame = resolver.resolve(TranslationRequest(
            case["frame"]["source_text"], domain=case["frame"]["domain"], style=case["frame"]["style"]
        ))
        actual = json.loads(json.dumps(frame.to_dict(), ensure_ascii=False))
        if canonical(actual) != canonical(case["frame"]):
            raise ValueError(f"frozen semantic frame changed for {case['case_id']}")
        actual_frames[case["case_id"]] = frame
        rule = RuleRealizer().realize(frame)
        if rule != case["rule_expected"]:
            raise ValueError(f"rule baseline changed for {case['case_id']}: {rule!r}")
    return workload, {"resolver": resolver, "frames": actual_frames}


def invocation_rate(workload: dict, resolver) -> dict:
    class CountingRealizer:
        calls = 0

        def realize(self, frame):
            self.calls += 1
            return "unexpected neural output"

    neural = CountingRealizer()
    translator = Translator(resolver=resolver, neural_realizer=neural)
    paths = {}
    cases = [
        {"case_id": case["case_id"], "source_text": case["frame"]["source_text"], "domain": case["frame"]["domain"]}
        for case in workload["frames"]
    ] + workload["invocation_cases"]
    for case in cases:
        result = translator.translate(TranslationRequest(case["source_text"], domain=case["domain"]))
        paths[case["case_id"]] = result.path
    grounded = len(workload["frames"])
    total = len(cases)
    return {
        "grounded_cases": grounded,
        "all_cases_including_unknown": total,
        "neural_calls": neural.calls,
        "grounded_invocation_rate": neural.calls / grounded,
        "all_case_invocation_rate": neural.calls / total,
        "result_paths": paths,
    }


def command_output(args: list[str]) -> str | None:
    try:
        completed = subprocess.run(args, check=False, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return completed.stdout.strip() if completed.returncode == 0 else None


def host_facts() -> dict:
    mem = command_output(["sysctl", "-n", "hw.memsize"])
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": command_output(["sysctl", "-n", "machdep.cpu.brand_string"]) or platform.processor(),
        "physical_memory_bytes": int(mem) if mem and mem.isdigit() else None,
        "power_state": command_output(["pmset", "-g", "batt"]),
        "thermal_state": command_output(["pmset", "-g", "therm"]),
    }


class ProcTaskInfo(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in (
        "virtual_size", "resident_size", "total_user", "total_system", "threads_user", "threads_system"
    )] + [(name, ctypes.c_int32) for name in (
        "policy", "faults", "pageins", "cow_faults", "messages_sent", "messages_received",
        "mach_calls", "unix_calls", "context_switches", "thread_count", "running_threads", "priority"
    )]


def process_tree_rss(root_pid: int) -> dict:
    libproc = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
    libproc.proc_listchildpids.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_int]
    libproc.proc_listchildpids.restype = ctypes.c_int
    libproc.proc_pidinfo.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int]
    libproc.proc_pidinfo.restype = ctypes.c_int
    tree = {root_pid}
    pending = [root_pid]
    while pending:
        parent = pending.pop()
        children = (ctypes.c_int * 4096)()
        child_count = libproc.proc_listchildpids(parent, children, ctypes.sizeof(children))
        if child_count < 0 or child_count > len(children):
            raise OSError(ctypes.get_errno(), "proc_listchildpids failed or child list was truncated")
        for child_pid in children[:child_count]:
            if child_pid > 0 and child_pid not in tree:
                tree.add(child_pid)
                pending.append(child_pid)

    total = 0
    root_rss = 0
    rss_values = []
    for pid in tree:
        task = ProcTaskInfo()
        size = libproc.proc_pidinfo(pid, 4, 0, ctypes.byref(task), ctypes.sizeof(task))
        if size == ctypes.sizeof(task):
            total += task.resident_size
            rss_values.append(task.resident_size)
            if pid == root_pid:
                root_rss = task.resident_size
    if not root_rss:
        raise RuntimeError(f"RSS unavailable for Ollama server PID {root_pid}")
    return {"process_tree_rss_bytes": total, "process_rss_bytes": sorted(rss_values)}


class RSSSampler:
    def __init__(self, root_pid: int):
        self.root_pid = root_pid
        self.samples: list[dict] = []
        self.error: str | None = None
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self._sample, daemon=True)

    def start(self):
        self.thread.start()

    def _sample(self):
        try:
            while not self.stopped.is_set():
                self.samples.append(process_tree_rss(self.root_pid))
                self.stopped.wait(0.1)
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"
            self.stopped.set()

    def finish(self) -> dict:
        self.stopped.set()
        self.thread.join(timeout=3)
        if self.error or not self.samples:
            raise RuntimeError(f"RSS sampling failed: {self.error or 'no samples'}")
        peak = max(self.samples, key=lambda sample: sample["process_tree_rss_bytes"])
        return {
            "method": "libproc resident_size samples every 100 ms for Ollama server and descendants",
            "sample_count": len(self.samples),
            "peak_process_tree_rss_bytes": peak["process_tree_rss_bytes"],
            "peak_process_count": len(peak["process_rss_bytes"]),
            "peak_process_rss_bytes": peak["process_rss_bytes"],
        }


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)]


def summarize(rows: list[dict]) -> dict:
    wall = [row["wall_time_ms"] for row in rows]
    return {
        **summarize_latencies(wall),
        "api_total_ms_median": statistics.median(row["api_total_ms"] for row in rows),
        "model_load_ms_median": statistics.median(row["model_load_ms"] for row in rows),
        "prompt_eval_ms_median": statistics.median(row["prompt_eval_ms"] for row in rows),
        "generation_ms_median": statistics.median(row["generation_ms"] for row in rows),
    }


def summarize_latencies(wall: list[float]) -> dict:
    return {
        "count": len(wall),
        "wall_time_ms": {
            "min": min(wall), "median": statistics.median(wall), "p90": percentile(wall, 0.9), "max": max(wall)
        },
    }


def generate(opener, base_url: str, model: str, case: dict) -> dict:
    started = time.perf_counter_ns()
    response = api_request(opener, base_url, "/api/generate", {
        "model": model,
        "prompt": build_prompt(case["frame"]),
        "stream": False,
        "think": False,
        "keep_alive": "10m",
        "options": OPTIONS,
    })
    wall_ms = (time.perf_counter_ns() - started) / 1_000_000
    text = response.get("response", "").strip()
    if not text:
        raise RuntimeError(f"empty candidate output for {case['case_id']}")
    return {
        "case_id": case["case_id"],
        "response": text,
        "wall_time_ms": wall_ms,
        "api_total_ms": response.get("total_duration", 0) / 1_000_000,
        "model_load_ms": response.get("load_duration", 0) / 1_000_000,
        "prompt_eval_ms": response.get("prompt_eval_duration", 0) / 1_000_000,
        "generation_ms": response.get("eval_duration", 0) / 1_000_000,
        "prompt_tokens": response.get("prompt_eval_count"),
        "generated_tokens": response.get("eval_count"),
        "done_reason": response.get("done_reason"),
        "checks": evaluate_output(case, text),
    }


def measure_rule_baseline(workload: dict, frames: dict[str, SemanticFrame], repetitions: int, warmups: int) -> dict:
    realizer = RuleRealizer()
    first_case = workload["frames"][0]
    first_started = time.perf_counter_ns()
    first_output = realizer.realize(frames[first_case["case_id"]])
    first_ms = (time.perf_counter_ns() - first_started) / 1_000_000
    if first_output != first_case["rule_expected"]:
        raise RuntimeError(f"rule baseline changed for {first_case['case_id']}")

    for _ in range(warmups):
        for case in workload["frames"]:
            if realizer.realize(frames[case["case_id"]]) != case["rule_expected"]:
                raise RuntimeError(f"rule baseline changed for {case['case_id']}")
    measurements = []
    outputs: dict[str, set[str]] = {}
    for repetition in range(repetitions):
        for case in workload["frames"]:
            started = time.perf_counter_ns()
            output = realizer.realize(frames[case["case_id"]])
            elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
            if output != case["rule_expected"]:
                raise RuntimeError(f"rule baseline changed for {case['case_id']}")
            outputs.setdefault(case["case_id"], set()).add(output)
            measurements.append({
                "case_id": case["case_id"], "response": output,
                "wall_time_ms": elapsed_ms, "repetition": repetition + 1,
                "checks": evaluate_output(case, output),
            })
    return {
        "measurement_boundary": "RuleRealizer.realize on the same in-memory verified SemanticFrames; excludes resolver and persistence",
        "first_realization_ms": first_ms,
        "measurements": measurements,
        "summary": summarize_latencies([row["wall_time_ms"] for row in measurements]),
        "repetition_stable_by_case": {case_id: len(values) == 1 for case_id, values in outputs.items()},
    }


def run(args: argparse.Namespace) -> dict:
    started_utc = datetime.now(timezone.utc).isoformat()
    port = url_parts(args.host)
    base_url = f"http://127.0.0.1:{port}"
    cache = validate_isolated_cache(args.models_dir)
    mco = Path(args.mco).resolve()
    marco_root = Path(args.marco_root).resolve()
    workload, verified = load_and_verify_workload(mco, marco_root)
    model_binary = shutil.which(args.ollama)
    if not model_binary:
        raise ValueError(f"Ollama executable not found: {args.ollama}")
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise RuntimeError(f"loopback port {port} is already in use")

    model_env = os.environ.copy()
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        model_env.pop(key, None)
    model_env.update({
        "OLLAMA_HOST": f"127.0.0.1:{port}",
        "OLLAMA_MODELS": str(cache),
        "OLLAMA_NO_CLOUD": "1",
        "OLLAMA_NUM_PARALLEL": "1",
    })
    log = tempfile.TemporaryFile(mode="w+t", encoding="utf-8")
    server = subprocess.Popen([model_binary, "serve"], env=model_env, stdout=log, stderr=log)
    sampler = None
    measurements = []
    candidate = {}
    try:
        opener = build_opener(ProxyHandler({}))
        deadline = time.monotonic() + 30
        version = None
        while time.monotonic() < deadline:
            if server.poll() is not None:
                break
            try:
                version = api_request(opener, base_url, "/api/version", timeout=1)
                break
            except (RuntimeError, URLError):
                time.sleep(0.2)
        if version is None:
            log.seek(0)
            raise RuntimeError(f"isolated Ollama server did not become ready: {log.read()[-2000:]}")

        tags = api_request(opener, base_url, "/api/tags")["models"]
        tag = next((entry for entry in tags if entry.get("name") == args.model or entry.get("model") == args.model), None)
        if tag is None:
            raise RuntimeError(f"model is not already cached at {cache}; the runner will not pull it")
        observed_digest = str(tag.get("digest", "")).removeprefix("sha256:")
        expected_digest = args.expected_digest.removeprefix("sha256:")
        if expected_digest and observed_digest != expected_digest:
            raise RuntimeError(f"model digest mismatch: {tag.get('digest')}")
        candidate = {
            "runtime": "Ollama",
            "runtime_version": version.get("version"),
            "model": args.model,
            "model_digest": f"sha256:{observed_digest}",
            "artifact_size_bytes": tag.get("size"),
            "parameter_size": tag.get("details", {}).get("parameter_size"),
            "quantization": tag.get("details", {}).get("quantization_level"),
            "cache_directory": str(cache),
        }
        ps = api_request(opener, base_url, "/api/ps").get("models", [])
        if any(item.get("name") == args.model or item.get("model") == args.model for item in ps):
            api_request(opener, base_url, "/api/generate", {"model": args.model, "keep_alive": 0})
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            ps = api_request(opener, base_url, "/api/ps").get("models", [])
            if not any(item.get("name") == args.model or item.get("model") == args.model for item in ps):
                break
            time.sleep(0.1)
        else:
            raise RuntimeError("candidate did not unload before cold measurement")

        sampler = RSSSampler(server.pid)
        sampler.start()
        cold = generate(opener, base_url, args.model, workload["frames"][0])
        cold["state"] = "cold_after_explicit_unload"
        for _ in range(args.warmups):
            for case in workload["frames"]:
                generate(opener, base_url, args.model, case)
        for repetition in range(args.repetitions):
            for case in workload["frames"]:
                row = generate(opener, base_url, args.model, case)
                row["repetition"] = repetition + 1
                measurements.append(row)
        memory = sampler.finish()
        baseline = measure_rule_baseline(workload, verified["frames"], args.repetitions, args.warmups)
        warm_by_case = {}
        for row in measurements:
            warm_by_case.setdefault(row["case_id"], set()).add(row["response"])
        return {
            "schema_version": "p1-e-tiny-realizer-benchmark-report-v1",
            "started_utc": started_utc,
            "ended_utc": datetime.now(timezone.utc).isoformat(),
            "workload": {
                "path": str(WORKLOAD.relative_to(ROOT)),
                "sha256": sha256(WORKLOAD),
                "schema_version": workload["schema_version"],
                "source_identity": workload["source_identity"],
                "frame_count": len(workload["frames"]),
                "case_ids": [case["case_id"] for case in workload["frames"]],
                "frame_identity_verified_against_actual_marco": True,
            },
            "candidate": candidate,
            "benchmark_runner": {
                "path": str(Path(__file__).resolve().relative_to(ROOT)),
                "sha256": sha256(Path(__file__).resolve()),
                "python_version": sys.version,
            },
            "host": host_facts(),
            "network": {
                "sandbox": "macOS sandbox-exec; inbound and outbound allowed only on localhost addresses",
                "ollama_cloud_disabled": True,
                "http_proxy_disabled": True,
                "model_download_attempted": False,
            },
            "prompt": {
                "policy": "target language, domain, intent, style, target terminology, and semantic slots only",
                "source_text_or_source_term_fields_included": False,
                "sha256_by_case": {case["case_id"]: hashlib.sha256(build_prompt(case["frame"]).encode("utf-8")).hexdigest() for case in workload["frames"]},
            },
            "settings": {"think": False, "keep_alive": "10m", "options": OPTIONS, "warmup_rounds": args.warmups},
            "rule_baseline": baseline,
            "cold": cold,
            "warm": {"measurements": measurements, "summary": summarize(measurements), "repetition_stable_by_case": {case_id: len(outputs) == 1 for case_id, outputs in warm_by_case.items()}},
            "memory": memory,
            "pipeline_invocation_rate": invocation_rate(workload, verified["resolver"]),
        }
    except Exception as exc:
        log.flush()
        log.seek(0)
        detail = log.read()[-2000:]
        if detail:
            raise RuntimeError(f"{exc}; Ollama server log tail: {detail}") from exc
        raise
    finally:
        if sampler is not None and sampler.thread.is_alive():
            sampler.stopped.set()
            sampler.thread.join(timeout=3)
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
        log.close()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an offline, isolated P1-E local realizer benchmark")
    parser.add_argument("--model", default="qwen3:0.6b-q4_K_M")
    parser.add_argument("--expected-digest", default="sha256:7df6b6e09427a769808717c0a93cadc4ae99ed4eb8bf5ca557c90846becea435")
    parser.add_argument("--models-dir", required=True, help="existing isolated Ollama model cache under /tmp")
    parser.add_argument("--mco", required=True, help="freshly built MARCO pack used for invocation-rate verification")
    parser.add_argument("--marco-root", required=True, help="pinned upstream MARCO checkout")
    parser.add_argument("--host", default="http://127.0.0.1:11435")
    parser.add_argument("--ollama", default="ollama")
    parser.add_argument("--repetitions", type=int, default=10)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if not 1 <= args.repetitions <= 100 or not 0 <= args.warmups <= 10:
        parser.error("repetitions must be 1..100 and warmups must be 0..10")
    return args


def main(argv: list[str] | None = None) -> int:
    original_argv = list(sys.argv[1:] if argv is None else argv)
    args = parse_args(original_argv)
    try:
        child_status = sandbox_reexec(args, original_argv)
        if child_status is not None:
            return child_status
        output = Path(args.output).expanduser().resolve()
        if output.exists():
            raise FileExistsError(f"refusing to overwrite benchmark result: {output}")
        report = run(args)
        report["repetitions"] = args.repetitions
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"report": str(output), "warm": report["warm"]["summary"], "memory": report["memory"]}, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(f"benchmark failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
