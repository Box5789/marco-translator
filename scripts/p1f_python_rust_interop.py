from __future__ import annotations

import ctypes
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile

from marco_translator.portable_contract import CONTRACT_VERSION
from marco_translator.tm import SQLiteTranslationMemory
from marco_translator.user_state import SQLiteUserOverlay


def load_runtime(path: Path):
    library = ctypes.CDLL(str(path))
    byte_pointer = ctypes.POINTER(ctypes.c_uint8)
    library.marco_runtime_open.argtypes = [byte_pointer, ctypes.c_size_t, ctypes.POINTER(ctypes.c_void_p)]
    library.marco_runtime_open.restype = ctypes.c_int32
    library.marco_runtime_process_json.argtypes = [
        ctypes.c_void_p,
        byte_pointer,
        ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    library.marco_runtime_process_json.restype = ctypes.c_int32
    library.marco_runtime_close.argtypes = [ctypes.c_void_p]
    library.marco_runtime_string_free.argtypes = [ctypes.c_void_p]
    return library


def call(library, handle: ctypes.c_void_p, document: dict) -> dict:
    payload = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    data = (ctypes.c_uint8 * len(payload)).from_buffer_copy(payload)
    output = ctypes.c_void_p()
    status = library.marco_runtime_process_json(handle, data, len(payload), ctypes.byref(output))
    if status != 0 or not output.value:
        raise RuntimeError(f"Rust runtime status {status}")
    try:
        return json.loads(ctypes.string_at(output.value))
    finally:
        library.marco_runtime_string_free(output)


def operation(name: str, **fields) -> dict:
    return {"contract_version": CONTRACT_VERSION, "operation": name, **fields}


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: p1f_python_rust_interop.py RUST_LIBRARY")
    library_path = Path(sys.argv[1]).resolve()
    library = load_runtime(library_path)
    fixture_path = Path(__file__).resolve().parents[1] / "runtime" / "fixtures" / "conformance-v1.json"
    fixture_hash = hashlib.sha256(fixture_path.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="marco-p1f-interop-") as folder:
        database = Path(folder) / "runtime.sqlite"
        tm = SQLiteTranslationMemory(database)
        overlay = SQLiteUserOverlay(database)
        tm.put("zh", "ko", None, "python-tm-source", "Python TM 값", origin="user_correction")
        overlay.add_terminology("python-term", "Python overlay 값", domain=None, concept="INTEROP_TERM")
        tm._db.close()
        overlay.close()

        handle = ctypes.c_void_p()
        encoded_path = str(database).encode("utf-8")
        path_bytes = (ctypes.c_uint8 * len(encoded_path)).from_buffer_copy(encoded_path)
        status = library.marco_runtime_open(path_bytes, len(encoded_path), ctypes.byref(handle))
        if status != 0 or not handle.value:
            raise RuntimeError(f"Rust open status {status}")
        try:
            tm_result = call(library, handle, operation(
                "translate",
                request={"text": "python-tm-source", "source_language": "zh", "target_language": "ko", "domain": None, "style": "neutral", "session_id": None},
            ))["result"]
            overlay_result = call(library, handle, operation(
                "translate",
                request={"text": "python-term", "source_language": "zh", "target_language": "ko", "domain": None, "style": "neutral", "session_id": None},
            ))["result"]
            if (tm_result["path"], tm_result["translated_text"]) != ("tm", "Python TM 값"):
                raise AssertionError(f"Python TM read mismatch: {tm_result}")
            if (overlay_result["path"], overlay_result["translated_text"]) != ("rule", "Python overlay 값"):
                raise AssertionError(f"Python overlay read mismatch: {overlay_result}")
            receipt = call(library, handle, operation(
                "correct",
                request={"text": "rust-tm-source", "source_language": "zh", "target_language": "ko", "domain": None, "style": "neutral", "session_id": None},
                corrected_text="Rust TM 값",
                generated_text=None,
            ))["result"]
            if receipt["tm_written"] is not True:
                raise AssertionError(f"Rust TM write missing: {receipt}")
        finally:
            library.marco_runtime_close(handle)

        reopened_tm = SQLiteTranslationMemory(database)
        reopened_overlay = SQLiteUserOverlay(database)
        try:
            if reopened_tm.lookup("zh", "ko", None, "rust-tm-source") != "Rust TM 값":
                raise AssertionError("Python could not read the Rust-written TM row")
            terms = reopened_overlay.resolve_terms("python-term", "zh", "ko", None)
            if len(terms) != 1 or terms[0].target != "Python overlay 값":
                raise AssertionError("Python could not reopen its overlay row after Rust access")
            version = reopened_tm._db.execute("PRAGMA user_version").fetchone()[0]
            if version != 1:
                raise AssertionError(f"unexpected SQLite user_version: {version}")
        finally:
            reopened_tm._db.close()
            reopened_overlay.close()

    print(
        f"P1F_PYTHON_RUST_INTEROP contract={CONTRACT_VERSION} fixture_sha256={fixture_hash} "
        f"python={sys.version.split()[0]} sqlite={sqlite3.sqlite_version} "
        "python_to_rust=tm+overlay rust_to_python=tm status=passed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
