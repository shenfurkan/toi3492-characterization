# TOI-3492.01 Legacy Project

Migrated on 2026-08-04 while the repository was converted into a multi-candidate
pipeline workspace.

This subtree preserves the original TOI-3492.01 project layout, source code,
tests, local evidence directories, protocols, and release materials. Relative
paths inside the legacy project remain unchanged so its scripts can still be
inspected or rerun from this directory.

## Status

The contents are frozen historical evidence. Do not edit a protocol, result,
manifest, or scientific claim here to support a new target. Adapt a method only
through a new candidate-specific protocol in `../../../protocols/`.

The authoritative TOI-3492.01 candidate record lives in `../candidate.json`.

TOI-3495.01 is not part of this project. Its intake workspace is
`../../toi-3495.01/`.

## Legacy Verification

From this directory, the historical suite can be invoked with:

```powershell
python -m pytest -q
```

Its original dependency declaration and lock file are retained locally. The
archive's package metadata now declares its license inline because the shared
repository license remains at the top level.
