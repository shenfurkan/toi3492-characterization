"""Strict, create-only JSON I/O for Stage-3 records."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Mapping

from .errors import ContractError


def _reject_constant(value: str):
    raise ContractError("non-standard JSON constant: {}".format(value))


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("duplicate JSON key: {}".format(key))
        result[key] = value
    return result


def _strict_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ContractError("non-finite JSON number: {}".format(value))
    return result


def load_strict_json(path: Path):
    return json.loads(
        Path(path).read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_constant,
        parse_float=_strict_float,
    )


def _validate_finite(value, location="$", seen=None):
    if seen is None:
        seen = set()
    if isinstance(value, float) and not math.isfinite(value):
        raise ContractError("non-finite value at {}".format(location))
    if isinstance(value, Mapping):
        marker = id(value)
        if marker in seen:
            raise ContractError("cyclic mapping at {}".format(location))
        seen.add(marker)
        for key, item in value.items():
            if not isinstance(key, str):
                raise ContractError("non-string JSON key at {}".format(location))
            _validate_finite(item, "{}.{}".format(location, key), seen)
        seen.remove(marker)
    elif isinstance(value, (list, tuple)):
        marker = id(value)
        if marker in seen:
            raise ContractError("cyclic sequence at {}".format(location))
        seen.add(marker)
        for index, item in enumerate(value):
            _validate_finite(item, "{}[{}]".format(location, index), seen)
        seen.remove(marker)


def canonical_json_bytes(payload) -> bytes:
    _validate_finite(payload)
    try:
        text = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ContractError("payload is not strict JSON: {}".format(exc)) from exc
    return (text + "\n").encode("utf-8")


def create_immutable_json(path: Path, payload) -> bool:
    """Create a record exactly once; identical retries are accepted."""
    path = Path(path)
    encoded = canonical_json_bytes(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        if path.read_bytes() != encoded:
            raise FileExistsError("immutable record differs: {}".format(path))
        return False
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return True
