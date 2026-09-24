from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import tempfile
from typing import Mapping

from .knowledge import KnowledgeStore
from .maintenance import PatchValidationError, _canonical_json, _strict_json_loads, load_analysis_package
from .marco_adapter import MarcoResolver
from .marco_pack import compile_marco_pack
from .models import TranslationRequest
from .patches import _seed_entry, apply_patch_operations
from .pipeline import Translator


SEED = "knowledge/seed.zh-ko.json"
FRAME_MAP = "knowledge/marco-frame-map.zh-ko.json"
GRAPH = "marco/graphs/graph_zh_ko_gaming_semantics.kg"
VERSION_SCHEMA = "knowledge-version-v2"
SNAPSHOT_SCHEMA = "knowledge-snapshot-v2"
_REQUIRED_ASSETS = {SEED, FRAME_MAP, GRAPH}
_CORPUS = (
    ("marco:west_sniper", TranslationRequest("西边有狙", domain="gaming"), "서쪽에 저격수 있음", "marco"),
    ("marco:base_enemy", TranslationRequest("家里有人", domain="gaming"), "본진에 적 있음", "marco"),
    ("marco:church_materials", TranslationRequest("教堂需要建材", domain="gaming"), "교회에 건축 자재가 필요함", "marco"),
    ("marco:group_push", TranslationRequest("集合一波去啊", domain="gaming"), "뭉쳐서 한 번에 밀자", "marco"),
    ("marco:stop_feeding", TranslationRequest("一个一个送没辙", domain="gaming"), "한 명씩 가서 죽어주면 답이 없어", "marco"),
    ("marco:unknown", TranslationRequest("完全未知的新句子", domain="gaming"), "", "marco"),
    ("lexical:home_literal", TranslationRequest("家里"), "집", "lexical"),
    ("lexical:home_gaming", TranslationRequest("家里", domain="gaming"), "본진", "lexical"),
)


class KnowledgeVersionError(RuntimeError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _version_id(asset_digests: Mapping[str, str], provenance: dict) -> str:
    identity = {"assets": dict(sorted(asset_digests.items())), "build_provenance": provenance}
    return "kg2_" + sha256(_canonical_json(identity))


def validate_snapshot(snapshot: object) -> dict:
    if not isinstance(snapshot, dict) or set(snapshot) != {"schema_version", "manifest", "assets", "mco"}:
        raise KnowledgeVersionError("knowledge snapshot has an invalid shape")
    if snapshot.get("schema_version") != SNAPSHOT_SCHEMA:
        raise KnowledgeVersionError("unsupported knowledge snapshot schema")
    manifest, assets, mco = snapshot.get("manifest"), snapshot.get("assets"), snapshot.get("mco")
    if (not isinstance(manifest, dict) or manifest.get("schema_version") != VERSION_SCHEMA
            or set(manifest) != {"schema_version", "version_id", "parent_version_id", "patch_sha256",
                                 "evidence_ids", "assets", "build_provenance"}):
        raise KnowledgeVersionError("knowledge-version manifest is missing or unsupported")
    if not isinstance(assets, dict) or not all(isinstance(name, str) and isinstance(data, bytes)
                                               for name, data in assets.items()):
        raise KnowledgeVersionError("knowledge snapshot assets must map paths to bytes")
    if not _REQUIRED_ASSETS.issubset(assets) or not any(name.startswith("marco/styles/") for name in assets):
        raise KnowledgeVersionError("knowledge snapshot is missing a canonical asset")
    for name in assets:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name:
            raise KnowledgeVersionError("knowledge snapshot contains an unsafe asset path")
        if name not in _REQUIRED_ASSETS and not (
            name.startswith("marco/styles/") or name.startswith("marco/axioms/")
        ):
            raise KnowledgeVersionError("knowledge snapshot contains an unsupported canonical asset")
        if path.suffix != ".json" and name != GRAPH and name not in {SEED, FRAME_MAP}:
            raise KnowledgeVersionError("knowledge snapshot contains an unsupported asset type")
    try:
        seed = _strict_json_loads(assets[SEED])
        frame_map = _strict_json_loads(assets[FRAME_MAP])
        if not isinstance(seed, dict) or seed.get("schema_version") != "knowledge-seed-v1" or not isinstance(seed.get("entries"), list):
            raise ValueError("invalid seed schema")
        seed_sources = set()
        for index, entry in enumerate(seed["entries"]):
            normalized = dict(entry) if isinstance(entry, dict) else entry
            if isinstance(normalized, dict):
                normalized.setdefault("source_language", "zh")
                normalized.setdefault("target_language", "ko")
                normalized.setdefault("domain", None)
            normalized = _seed_entry(normalized, f"seed.entries[{index}]")
            source_key = (normalized["source_language"], normalized["target_language"],
                          normalized["domain"], normalized["source"])
            if source_key in seed_sources:
                raise ValueError("duplicate seed source in one scope")
            seed_sources.add(source_key)
        if (not isinstance(frame_map, dict) or frame_map.get("schema_version") != "marco-frame-map-v1"
                or not isinstance(frame_map.get("frames"), dict)):
            raise ValueError("invalid frame map")
        for node_id, spec in frame_map["frames"].items():
            if not isinstance(node_id, str) or not isinstance(spec, dict):
                raise ValueError("invalid frame entry")
            for key, minimum, maximum in (("confidence", 0.0, 1.0), ("routing_weight", -0.10, 0.10)):
                value = spec.get(key, 1.0 if key == "confidence" else 0.0)
                if (isinstance(value, bool) or not isinstance(value, (int, float))
                        or not math.isfinite(value) or not minimum <= value <= maximum):
                    raise ValueError(f"invalid frame {key}")
        for resource in assets:
            if resource.startswith(("marco/styles/", "marco/axioms/")):
                if not isinstance(_strict_json_loads(assets[resource]), dict):
                    raise ValueError(f"invalid MARCO compiler asset: {resource}")
        assets[GRAPH].decode("utf-8")
    except (ValueError, UnicodeDecodeError, TypeError) as exc:
        raise KnowledgeVersionError("canonical source assets are malformed") from exc
    digests = {name: sha256(data) for name, data in sorted(assets.items())}
    if manifest.get("assets") != digests:
        raise KnowledgeVersionError("canonical asset digest mismatch")
    provenance = manifest.get("build_provenance")
    if not isinstance(provenance, dict):
        raise KnowledgeVersionError("build provenance is missing")
    required_provenance = {"schema_version", "marco", "compiler", "python", "dependencies", "recipe", "output"}
    recipe = provenance.get("recipe")
    if (provenance.get("schema_version") != "marco-build-provenance-v1"
            or set(provenance) != required_provenance or not isinstance(recipe, dict)
            or set(recipe) != {"script", "script_sha256", "module", "module_sha256", "name", "graphs", "model_inputs"}):
        raise KnowledgeVersionError("build provenance schema is invalid")
    marco = provenance.get("marco")
    compiler = provenance.get("compiler")
    python = provenance.get("python")
    dependencies = provenance.get("dependencies")
    if (not isinstance(marco, dict) or set(marco) != {"repository", "revision"}
            or not isinstance(marco.get("repository"), str) or not marco["repository"].startswith("https://")
            or not isinstance(marco.get("revision"), str) or len(marco["revision"]) != 40
            or any(char not in "0123456789abcdef" for char in marco["revision"])):
        raise KnowledgeVersionError("MARCO build identity is invalid")
    if (not isinstance(compiler, dict) or compiler.get("package") != "mco"
            or compiler.get("api") != "mco.compile" or not isinstance(compiler.get("version"), str)):
        raise KnowledgeVersionError("MARCO compiler identity is invalid")
    if (not isinstance(python, dict) or set(python) != {"implementation", "version", "platform", "architecture",
                                                           "platform_version", "zlib_version", "zlib_runtime_version"}
            or any(not isinstance(value, str) or not value for value in python.values())):
        raise KnowledgeVersionError("build runtime provenance is invalid")
    if (not isinstance(dependencies, dict) or set(dependencies) != {"numpy"}
            or dependencies.get("numpy") is not None and not isinstance(dependencies.get("numpy"), str)):
        raise KnowledgeVersionError("build dependency provenance is invalid")
    for field in ("script_sha256", "module_sha256"):
        digest = recipe.get(field)
        if not isinstance(digest, str) or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise KnowledgeVersionError("build recipe digest is invalid")
    if recipe.get("script") != "scripts/build_marco_pack.py" or recipe.get("module") != "src/marco_translator/marco_pack.py":
        raise KnowledgeVersionError("build recipe identity is invalid")
    if recipe.get("graphs") != [GRAPH.removeprefix("marco/")]:
        raise KnowledgeVersionError("build recipe graph selection is invalid")
    compiler_inputs = recipe.get("model_inputs")
    expected_inputs = {name.removeprefix("marco/"): digest for name, digest in digests.items()
                       if name == GRAPH or name.startswith(("marco/styles/", "marco/axioms/"))}
    if compiler_inputs != expected_inputs:
        raise KnowledgeVersionError("build provenance does not identify the canonical compiler inputs")
    if not isinstance(mco, bytes):
        raise KnowledgeVersionError("derived MARCO model must be bytes")
    output = provenance.get("output")
    if (not isinstance(output, dict) or set(output) != {"sha256", "size_bytes"}
            or output.get("sha256") != sha256(mco) or isinstance(output.get("size_bytes"), bool)
            or output.get("size_bytes") != len(mco) or len(mco) == 0):
        raise KnowledgeVersionError("derived .mco output does not match build provenance")
    version_id = manifest.get("version_id")
    if not isinstance(version_id, str) or version_id != _version_id(digests, provenance):
        raise KnowledgeVersionError("canonical Knowledge Version identity mismatch")
    parent = manifest.get("parent_version_id")
    if (parent is not None and (not isinstance(parent, str) or len(parent) != 68
                                or not parent.startswith("kg2_")
                                or any(char not in "0123456789abcdef" for char in parent[4:]))):
        raise KnowledgeVersionError("parent Knowledge Version identity is invalid")
    patch_sha = manifest.get("patch_sha256")
    if patch_sha is not None and (not isinstance(patch_sha, str) or len(patch_sha) != 64
                                  or any(char not in "0123456789abcdef" for char in patch_sha)):
        raise KnowledgeVersionError("patch lineage digest is invalid")
    evidence_ids = manifest.get("evidence_ids")
    if (not isinstance(evidence_ids, list)
            or any(not isinstance(item, str) or len(item) != 68 or not item.startswith("ev1_")
                   or any(char not in "0123456789abcdef" for char in item[4:]) for item in evidence_ids)
            or len(evidence_ids) != len(set(evidence_ids))):
        raise KnowledgeVersionError("version evidence lineage is invalid")
    return snapshot


def snapshot_document(snapshot: dict) -> dict:
    validate_snapshot(snapshot)
    return {
        "schema_version": SNAPSHOT_SCHEMA,
        "manifest": snapshot["manifest"],
        "asset_digests": snapshot["manifest"]["assets"],
        "derived_mco": snapshot["manifest"]["build_provenance"]["output"],
    }


class KnowledgeVersionStore:
    """Immutable canonical snapshots and one atomically activated version pointer."""

    def __init__(self, database: str | Path, *, marco_root: str | Path,
                 cache_dir: str | Path | None = None) -> None:
        self.database = Path(database).resolve()
        self.marco_root = Path(marco_root).resolve()
        self.cache_dir = Path(cache_dir).resolve() if cache_dir else self.database.with_suffix(".cache")
        if not self.marco_root.is_dir():
            raise KnowledgeVersionError("a MARCO source checkout is required")
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=30, isolation_level=None)
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _ensure_schema(self) -> None:
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 2):
                raise KnowledgeVersionError(f"unsupported Knowledge Version database schema: {version}")
            if version == 2:
                return
            connection.execute("BEGIN IMMEDIATE")
            try:
                for statement in (
                    """
                    CREATE TABLE versions (
                        version_id TEXT PRIMARY KEY,
                        manifest_json TEXT NOT NULL,
                        mco BLOB NOT NULL
                    )
                    """,
                    """
                    CREATE TABLE assets (
                        version_id TEXT NOT NULL REFERENCES versions(version_id),
                        resource TEXT NOT NULL,
                        content BLOB NOT NULL,
                        PRIMARY KEY(version_id, resource)
                    )
                    """,
                    """
                    CREATE TABLE active_version (
                        singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                        version_id TEXT NOT NULL REFERENCES versions(version_id)
                    )
                    """,
                    """
                    CREATE TABLE activation_events (
                        event_id INTEGER PRIMARY KEY,
                        action TEXT NOT NULL,
                        prior_version_id TEXT,
                        version_id TEXT NOT NULL REFERENCES versions(version_id),
                        created_at TEXT NOT NULL,
                        proposal_sha256 TEXT,
                        evidence_ids_json TEXT NOT NULL
                    )
                    """,
                ):
                    connection.execute(statement)
                connection.execute("PRAGMA user_version=2")
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def _source_assets(source_root: str | Path) -> dict[str, bytes]:
        root = Path(source_root).resolve()
        names = set(_REQUIRED_ASSETS)
        for folder in ("marco/styles", "marco/axioms"):
            directory = root / folder
            if directory.exists():
                if directory.is_symlink() or not directory.is_dir():
                    raise KnowledgeVersionError(f"canonical asset directory is not regular: {folder}")
                names.update(path.relative_to(root).as_posix() for path in directory.glob("*.json"))
        assets = {}
        for name in sorted(names):
            path = root / name
            if path.is_symlink() or not path.is_file():
                raise KnowledgeVersionError(f"canonical asset is missing or not a regular file: {name}")
            assets[name] = path.read_bytes()
        if not any(name.startswith("marco/styles/") for name in assets):
            raise KnowledgeVersionError("MARCO compiler style/config assets are required")
        return assets

    def _build_snapshot(self, assets: dict[str, bytes], *, parent_version_id: str | None,
                        patch_sha256: str | None, evidence_ids: list[str]) -> dict:
        with tempfile.TemporaryDirectory(prefix="marco-translator-kg-build-") as temporary:
            root = Path(temporary)
            marco_source = root / "marco-source"
            for name, content in assets.items():
                if name.startswith("marco/"):
                    target = marco_source / name.removeprefix("marco/")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(content)
            output = root / "derived.mco"
            try:
                provenance = compile_marco_pack(marco_source, output, marco_root=self.marco_root)
            except Exception as exc:
                raise KnowledgeVersionError(f"MARCO model build failed: {exc}") from exc
            mco = output.read_bytes()
        digests = {name: sha256(data) for name, data in sorted(assets.items())}
        manifest = {
            "schema_version": VERSION_SCHEMA,
            "version_id": _version_id(digests, provenance),
            "parent_version_id": parent_version_id,
            "patch_sha256": patch_sha256,
            "evidence_ids": list(evidence_ids),
            "assets": digests,
            "build_provenance": provenance,
        }
        return validate_snapshot({"schema_version": SNAPSHOT_SCHEMA, "manifest": manifest,
                                 "assets": assets, "mco": mco})

    def initialize(self, source_root: str | Path) -> str:
        if self.active_version_id() is not None:
            raise KnowledgeVersionError("Knowledge Version store is already initialized")
        snapshot = self._build_snapshot(self._source_assets(source_root), parent_version_id=None,
                                        patch_sha256=None, evidence_ids=[])
        baseline = self._replay(snapshot)
        if not all(self._matches_oracle(expected, mode, result)
                   for (_, _, expected, mode), result in zip(_CORPUS, baseline)):
            raise KnowledgeVersionError("initial Knowledge Version fails the registered replay corpus")
        self._materialize(snapshot)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT 1 FROM active_version").fetchone():
                raise KnowledgeVersionError("another process initialized the version store")
            self._insert_snapshot(connection, snapshot)
            version_id = snapshot["manifest"]["version_id"]
            connection.execute("INSERT INTO active_version(singleton, version_id) VALUES(1, ?)", (version_id,))
            self._activation_event(connection, "initialize", None, version_id, None, [])
            connection.commit()
            return version_id
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _insert_snapshot(self, connection: sqlite3.Connection, snapshot: dict) -> None:
        validate_snapshot(snapshot)
        manifest = snapshot["manifest"]
        connection.execute(
            "INSERT INTO versions(version_id, manifest_json, mco) VALUES(?, ?, ?)",
            (manifest["version_id"], json.dumps(manifest, ensure_ascii=False, sort_keys=True), snapshot["mco"]),
        )
        connection.executemany(
            "INSERT INTO assets(version_id, resource, content) VALUES(?, ?, ?)",
            [(manifest["version_id"], name, data) for name, data in sorted(snapshot["assets"].items())],
        )

    @staticmethod
    def _activation_event(connection: sqlite3.Connection, action: str, prior: str | None,
                          version_id: str, proposal_sha256: str | None, evidence_ids: list[str]) -> None:
        connection.execute(
            "INSERT INTO activation_events(action, prior_version_id, version_id, created_at, proposal_sha256, evidence_ids_json) "
            "VALUES(?, ?, ?, ?, ?, ?)",
            (action, prior, version_id, datetime.now(timezone.utc).isoformat(), proposal_sha256,
             json.dumps(evidence_ids, ensure_ascii=False)),
        )

    def active_version_id(self) -> str | None:
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT version_id FROM active_version WHERE singleton=1").fetchone()
        return row[0] if row else None

    def snapshot(self, version_id: str | None = None) -> dict:
        if version_id is None:
            version_id = self.active_version_id()
        if not version_id:
            raise KnowledgeVersionError("Knowledge Version store is not initialized")
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT manifest_json, mco FROM versions WHERE version_id=?", (version_id,)).fetchone()
            if row is None:
                raise KnowledgeVersionError("Knowledge Version does not exist")
            asset_rows = connection.execute(
                "SELECT resource, content FROM assets WHERE version_id=? ORDER BY resource", (version_id,)
            ).fetchall()
        try:
            manifest = _strict_json_loads(row[0])
        except ValueError as exc:
            raise KnowledgeVersionError("stored version manifest is corrupt") from exc
        return validate_snapshot({"schema_version": SNAPSHOT_SCHEMA, "manifest": manifest,
                                  "assets": {name: bytes(data) for name, data in asset_rows}, "mco": bytes(row[1])})

    def preview_patch(self, proposal: dict | str | Path, *, analysis_package: str | Path) -> dict:
        active = self.active_version_id()
        if active is None:
            raise KnowledgeVersionError("Knowledge Version store is not initialized")
        package = load_analysis_package(analysis_package)
        if package["version_id"] != active:
            raise PatchValidationError("analysis package does not identify the active Knowledge Version")
        if isinstance(proposal, (str, Path)):
            from .maintenance import load_patch_proposal

            proposal = load_patch_proposal(proposal, analysis_package=analysis_package,
                                           current_base_kg_version=active)
        else:
            try:
                proposal = _strict_json_loads(_canonical_json(proposal))
            except ValueError as exc:
                raise PatchValidationError("patch proposal must contain finite JSON values") from exc
        from .maintenance import validate_patch_document

        validate_patch_document(proposal, known_evidence_ids=package["evidence_ids"],
                                current_base_kg_version=active)
        base = self.snapshot(active)
        candidate_assets = apply_patch_operations(base["assets"], proposal)
        patch_sha = sha256(_canonical_json(proposal))
        evidence_ids = sorted({item for patch in proposal["patches"] for item in patch["evidence_ids"]})
        candidate = self._build_snapshot(candidate_assets, parent_version_id=active,
                                         patch_sha256=patch_sha, evidence_ids=evidence_ids)
        before = self._replay(base)
        after_first = self._replay(candidate)
        after_second = self._replay(candidate)
        if any(len(results) != len(_CORPUS) for results in (before, after_first, after_second)):
            raise KnowledgeVersionError("corpus replay returned an incomplete result set")
        if after_first != after_second:
            raise KnowledgeVersionError("candidate corpus replay is not deterministic")
        cases = []
        for (case_id, _, expected, mode), old, new in zip(_CORPUS, before, after_first):
            old_pass = self._matches_oracle(expected, mode, old)
            new_pass = self._matches_oracle(expected, mode, new)
            if old_pass and not new_pass:
                category = "regressed"
            elif not old_pass and new_pass:
                category = "improved"
            elif old["output"] == new["output"]:
                category = "unchanged"
            else:
                category = "changed"
            cases.append({"id": case_id, "expected": expected, "before": old,
                          "after": new, "category": category})
        counts = {name: sum(case["category"] == name for case in cases)
                  for name in ("unchanged", "improved", "regressed", "changed")}
        changed_resources = sorted(name for name in base["assets"]
                                   if base["assets"][name] != candidate_assets[name])
        operations_by_resource = {
            name: [patch["id"] for patch in proposal["patches"] if patch["resource"] == name]
            for name in changed_resources
        }
        return {
            "base_version_id": active,
            "candidate_version_id": candidate["manifest"]["version_id"],
            "patch_sha256": patch_sha,
            "operations": [{key: patch[key] for key in (
                "id", "type", "resource", "target", "expected_old_state",
                "proposed_new_state", "evidence_ids",
            )} for patch in proposal["patches"]],
            "asset_diff": [{"resource": name, "patch_ids": operations_by_resource[name],
                            "before_sha256": base["manifest"]["assets"][name],
                            "after_sha256": candidate["manifest"]["assets"][name]}
                           for name in changed_resources],
            "derived_mco": {
                "before_sha256": base["manifest"]["build_provenance"]["output"]["sha256"],
                "after_sha256": candidate["manifest"]["build_provenance"]["output"]["sha256"],
            },
            "cases": cases,
            "counts": counts,
            "deterministic": True,
            "eligible": counts["regressed"] == 0 and all(
                self._matches_oracle(case["expected"], _CORPUS[index][3], case["after"])
                for index, case in enumerate(cases)
            ),
        }

    @staticmethod
    def _matches_oracle(expected: str, mode: str, result: dict) -> bool:
        if expected == "":
            return result.get("output") == "" and result.get("path") == "unresolved"
        return result.get("output") == expected and result.get("path") == ("lexical" if mode == "lexical" else "rule")

    def _replay(self, snapshot: dict) -> list[dict]:
        with tempfile.TemporaryDirectory(prefix="marco-translator-replay-") as temporary:
            root = Path(temporary)
            model = root / "model.mco"
            model.write_bytes(snapshot["mco"])
            seed = root / "seed.json"
            frame_map = root / "frame-map.json"
            seed.write_bytes(snapshot["assets"][SEED])
            frame_map.write_bytes(snapshot["assets"][FRAME_MAP])
            knowledge = KnowledgeStore.from_json(seed)
            resolver = MarcoResolver(str(model), str(frame_map), knowledge=knowledge,
                                     marco_root=str(self.marco_root))
            translator = Translator(resolver=resolver)
            output = []
            for _, request, _, mode in _CORPUS:
                if mode == "marco":
                    result = translator.translate(request)
                    output.append({"output": result.translated_text, "path": result.path,
                                   "confidence": result.confidence})
                else:
                    terms = knowledge.resolve_terms(request.text, request.source_language,
                                                    request.target_language, request.domain)
                    target = terms[0].target if len(terms) == 1 and terms[0].source == request.text else ""
                    output.append({"output": target, "path": "lexical" if target else "unresolved",
                                   "confidence": terms[0].confidence if target else 0.0})
            return output

    def approve_patch(self, proposal: dict | str | Path, *, analysis_package: str | Path,
                      approved_candidate_version_id: str) -> str:
        if not isinstance(proposal, (str, Path)):
            try:
                proposal = _strict_json_loads(_canonical_json(proposal))
            except ValueError as exc:
                raise PatchValidationError("patch proposal must contain finite JSON values") from exc
        preview = self.preview_patch(proposal, analysis_package=analysis_package)
        if not preview["eligible"]:
            raise KnowledgeVersionError("candidate replay contains a regression or oracle failure")
        if approved_candidate_version_id != preview["candidate_version_id"]:
            raise KnowledgeVersionError("explicit approval does not match the freshly replayed candidate")
        snapshot = self._build_snapshot_from_preview(proposal, analysis_package, preview)
        self._materialize(snapshot)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT version_id FROM active_version WHERE singleton=1").fetchone()
            if row is None or row[0] != preview["base_version_id"]:
                raise KnowledgeVersionError("active Knowledge Version changed during approval")
            candidate_id = preview["candidate_version_id"]
            existing = connection.execute("SELECT 1 FROM versions WHERE version_id=?", (candidate_id,)).fetchone()
            if existing is None:
                self._insert_snapshot(connection, snapshot)
            else:
                retained = self.snapshot(candidate_id)
                if retained["assets"] != snapshot["assets"] or retained["mco"] != snapshot["mco"]:
                    raise KnowledgeVersionError("retained candidate Knowledge Version is corrupt")
            connection.execute("UPDATE active_version SET version_id=? WHERE singleton=1", (candidate_id,))
            evidence_ids = snapshot["manifest"]["evidence_ids"]
            self._activation_event(connection, "approve_patch", row[0], candidate_id,
                                   preview["patch_sha256"], evidence_ids)
            connection.commit()
            return candidate_id
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _build_snapshot_from_preview(self, proposal: dict | str | Path, analysis_package: str | Path,
                                     preview: dict) -> dict:
        active = self.snapshot(preview["base_version_id"])
        if isinstance(proposal, (str, Path)):
            from .maintenance import load_patch_proposal

            proposal = load_patch_proposal(proposal, analysis_package=analysis_package,
                                           current_base_kg_version=preview["base_version_id"])
        assets = apply_patch_operations(active["assets"], proposal)
        evidence_ids = sorted({item for patch in proposal["patches"] for item in patch["evidence_ids"]})
        snapshot = self._build_snapshot(assets, parent_version_id=preview["base_version_id"],
                                        patch_sha256=sha256(_canonical_json(proposal)), evidence_ids=evidence_ids)
        if snapshot["manifest"]["version_id"] != preview["candidate_version_id"]:
            raise KnowledgeVersionError("candidate changed between replay and approval")
        return snapshot

    def rollback(self, version_id: str) -> str:
        target = self.snapshot(version_id)
        self._materialize(target)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT version_id FROM active_version WHERE singleton=1").fetchone()
            if row is None:
                raise KnowledgeVersionError("Knowledge Version store is not initialized")
            if connection.execute("SELECT 1 FROM versions WHERE version_id=?", (version_id,)).fetchone() is None:
                raise KnowledgeVersionError("rollback target disappeared")
            connection.execute("UPDATE active_version SET version_id=? WHERE singleton=1", (version_id,))
            self._activation_event(connection, "rollback", row[0], version_id, None, [])
            connection.commit()
            return version_id
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def activation_history(self) -> list[dict]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT action, prior_version_id, version_id, created_at, proposal_sha256, evidence_ids_json "
                "FROM activation_events ORDER BY event_id"
            ).fetchall()
        return [{"action": row[0], "prior_version_id": row[1], "version_id": row[2],
                 "created_at": row[3], "proposal_sha256": row[4], "evidence_ids": json.loads(row[5])}
                for row in rows]

    def active_runtime_directory(self) -> Path:
        version_id = self.active_version_id()
        if version_id is None:
            raise KnowledgeVersionError("Knowledge Version store is not initialized")
        return self._materialize(self.snapshot(version_id))

    def load_active_resolver(self) -> MarcoResolver:
        directory = self.active_runtime_directory()
        return MarcoResolver(
            str(directory / "derived/zh-ko-gaming.mco"),
            str(directory / FRAME_MAP),
            knowledge=KnowledgeStore.from_json(directory / SEED),
            marco_root=str(self.marco_root),
        )

    def _materialize(self, snapshot: dict) -> Path:
        validate_snapshot(snapshot)
        version_id = snapshot["manifest"]["version_id"]
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        destination = self.cache_dir / version_id
        if destination.is_symlink():
            raise KnowledgeVersionError("materialized version cache is a symlink")
        if destination.exists():
            self._verify_materialized(destination, snapshot)
            return destination
        staging = Path(tempfile.mkdtemp(prefix=f".{version_id}.", dir=self.cache_dir))
        try:
            for name, content in snapshot["assets"].items():
                target = staging / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
            derived = staging / "derived/zh-ko-gaming.mco"
            derived.parent.mkdir(parents=True, exist_ok=True)
            derived.write_bytes(snapshot["mco"])
            (staging / "knowledge-version.json").write_text(
                json.dumps(snapshot["manifest"], ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            os.replace(staging, destination)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        self._verify_materialized(destination, snapshot)
        return destination

    @staticmethod
    def _verify_materialized(directory: Path, snapshot: dict) -> None:
        if directory.is_symlink() or not directory.is_dir():
            raise KnowledgeVersionError("materialized version cache is not a regular directory")
        for name, content in snapshot["assets"].items():
            path = directory / name
            if path.is_symlink() or not path.is_file() or path.read_bytes() != content:
                raise KnowledgeVersionError("materialized canonical asset is corrupt")
        model = directory / "derived/zh-ko-gaming.mco"
        if model.is_symlink() or not model.is_file() or model.read_bytes() != snapshot["mco"]:
            raise KnowledgeVersionError("materialized .mco cache is corrupt")
        manifest = directory / "knowledge-version.json"
        if manifest.is_symlink() or not manifest.is_file() or _strict_json_loads(manifest.read_bytes()) != snapshot["manifest"]:
            raise KnowledgeVersionError("materialized version manifest is corrupt")
