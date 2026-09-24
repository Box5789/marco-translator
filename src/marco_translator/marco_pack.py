from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit
import zlib
from importlib import metadata


GRAPH_PATH = "graphs/graph_zh_ko_gaming_semantics.kg"
PACK_NAME = "marco-translator-zh-ko-gaming"


class MarcoPackBuildError(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(marco_root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(marco_root), *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise MarcoPackBuildError("MARCO build provenance requires a readable Git checkout") from exc
    return result.stdout.strip()


def _safe_remote_url(value: str) -> str:
    if value.startswith("git@") and ":" in value:
        host, path = value[4:].split(":", 1)
        return f"https://{host}/{path.removesuffix('.git')}"
    parsed = urlsplit(value)
    if parsed.scheme and parsed.hostname:
        path = parsed.path.removesuffix(".git")
        return f"{parsed.scheme}://{parsed.hostname}{path}"
    return value.removesuffix(".git")


def _distribution_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def _input_files(source: Path) -> list[str]:
    if not source.is_dir():
        raise MarcoPackBuildError("MARCO translator source must be a directory")
    graph = source / GRAPH_PATH
    if not graph.is_file() or graph.is_symlink():
        raise MarcoPackBuildError(f"MARCO source is missing a regular graph: {GRAPH_PATH}")
    paths = [GRAPH_PATH]
    style_count = 0
    for folder in ("styles", "axioms"):
        directory = source / folder
        if directory.exists() and (directory.is_symlink() or not directory.is_dir()):
            raise MarcoPackBuildError(f"MARCO model input directory is not regular: {folder}")
        for path in sorted((source / folder).glob("*.json")):
            if path.is_symlink() or not path.is_file():
                raise MarcoPackBuildError(f"MARCO model input is not a regular file: {path}")
            paths.append(path.relative_to(source).as_posix())
            if folder == "styles":
                style_count += 1
    if style_count == 0:
        raise MarcoPackBuildError("MARCO translator style/config JSON is required")
    return paths


def compile_marco_pack(source: str | Path, output: str | Path, *,
                       marco_root: str | Path | None = None) -> dict:
    source, output = Path(source).resolve(), Path(output).resolve()
    try:
        import mco
    except ImportError as exc:
        raise MarcoPackBuildError("mco is not installed") from exc

    if marco_root is None:
        module_path = Path(mco.__file__).resolve()
        candidates = (module_path.parent.parent, *module_path.parents)
        marco_root = next((path for path in candidates if (path / "kgpack.py").is_file()), None)
    if marco_root is None:
        raise MarcoPackBuildError("MARCO source checkout is required for build provenance")
    marco_root = Path(marco_root).resolve()
    module_path = Path(mco.__file__).resolve()
    if not module_path.is_relative_to(marco_root / "mco"):
        raise MarcoPackBuildError("the imported mco package does not belong to the recorded MARCO checkout")
    if _git(marco_root, "status", "--porcelain", "--untracked-files=all"):
        raise MarcoPackBuildError("MARCO build checkout must be clean")
    revision = _git(marco_root, "rev-parse", "HEAD")
    remote = _safe_remote_url(_git(marco_root, "remote", "get-url", "origin"))
    if not revision or not remote:
        raise MarcoPackBuildError("MARCO repository identity is incomplete")

    inputs = _input_files(source)
    if output.is_symlink():
        raise MarcoPackBuildError("MARCO pack output must not be a symlink")
    if output in {(source / name).resolve() for name in inputs}:
        raise MarcoPackBuildError("MARCO pack output must not replace a compiler input")
    script = Path(__file__).resolve().parents[2] / "scripts" / "build_marco_pack.py"
    if not script.is_file():
        raise MarcoPackBuildError("the canonical MARCO build script is unavailable")
    source_digests = {
        name: _sha256((source / name).read_bytes())
        for name in inputs
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        report = mco.compile(
            source,
            output,
            name=PACK_NAME,
            graphs=[GRAPH_PATH],
            marco_root=str(marco_root),
        )
    except Exception as exc:
        raise MarcoPackBuildError(f"MARCO pack compilation failed: {type(exc).__name__}: {exc}") from exc
    payload = output.read_bytes()
    output_digest = _sha256(payload)
    if report.sha256 != output_digest:
        raise MarcoPackBuildError("mco inspection digest does not match the compiled output")

    return {
        "schema_version": "marco-build-provenance-v1",
        "marco": {"repository": remote, "revision": revision},
        "compiler": {"package": "mco", "version": str(mco.__version__), "api": "mco.compile"},
        "python": {
            "implementation": sys.implementation.name,
            "version": platform.python_version(),
            "platform": platform.system(),
            "architecture": platform.machine(),
            "platform_version": platform.platform(),
            "zlib_version": zlib.ZLIB_VERSION,
            "zlib_runtime_version": getattr(zlib, "ZLIB_RUNTIME_VERSION", zlib.ZLIB_VERSION),
        },
        "dependencies": {
            "numpy": _distribution_version("numpy"),
        },
        "recipe": {
            "script": "scripts/build_marco_pack.py",
            "script_sha256": _sha256(script.read_bytes()),
            "module": "src/marco_translator/marco_pack.py",
            "module_sha256": _sha256(Path(__file__).read_bytes()),
            "name": PACK_NAME,
            "graphs": [GRAPH_PATH],
            "model_inputs": source_digests,
        },
        "output": {"sha256": output_digest, "size_bytes": len(payload)},
    }
