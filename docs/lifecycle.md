# Candidate Lifecycle

A candidate workspace is a permanent directory. Lifecycle changes are records,
never directory moves.

## States

| State | Meaning |
| --- | --- |
| `active` | Scientific or publication work may change the candidate contents |
| `paused` | Temporary hold; preserve handover and next-action information |
| `stopped` | Work intentionally discontinued; record the decision and supported negative results |
| `published` | At least one immutable, citable release exists; does not imply validation |
| `archived` | Scientific payload frozen; no further in-place maintenance |

Every transition appends an event with the from-state, to-state, timestamp,
actor, reason, and relevant freeze/release identifiers.

## Workflow Phases

`intake`, `feasibility`, `acquisition`, `vetting`, `followup`, `analysis`,
`review`. The phase describes where work is, not the state of the candidate.
Phases are gate-protected: `exonym advance` promotes a phase only after every
`[MANDATORY]` checkbox in the phase document is checked. Legacy records that
predate this ordering used `writing`, `submission`, or `post-publication`;
those map to `review`.

## Freeze and Archive Semantics

An archived candidate stays at `candidate/<candidate-id>/`. A freeze should:

1. Assign a freeze ID and set lifecycle to `archived`.
2. Append the final transition event.
3. Inventory claim-bearing sources, protocols, inputs, results, manuscripts,
   environment records, and release objects with paths, sizes, and hashes.
4. Verify the manifest from a clean location.
5. Protect the corresponding commit/tag and external release packages.

While archived: manifest-listed files cannot be edited, deleted, renamed, or
regenerated in place. Corrections use new versioned files with explicit
supersession links. Reopening preserves the old snapshot before new work.

## Verification Layers

| Layer | Purpose |
| ---: | --- |
| Q0 | Syntax and schema |
| Q1 | Unit behavior |
| Q2 | Artifact integrity (existence, size, hash, lineage) |
| Q3 | Numerical reproduction from frozen inputs |
| Q4 | Independent calculation |
| Q5 | Scientific gate (thresholds, stop rules, applicability) |
| Q6 | Claim audit |
| Q7 | Release verification (manifest, extraction, offline run) |
| Q8 | External verification |

A release claim must state the highest completed layer.
