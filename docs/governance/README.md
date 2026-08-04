# Research Governance

## Scope

This policy governs computational research, scientific claims, data handling,
software changes, manuscripts, and release engineering across all candidate
workspaces. It is additive: a candidate's frozen protocols and decisions
retain their own authority.

## Roles

| Role | Accountabilities |
| --- | --- |
| Principal Investigator / Scientific Owner | Defines scope, approves claim charter, accepts residual scientific risk |
| Analysis Owner | Implements methods, records runs, maintains code-to-artifact traceability |
| Data Steward | Records origin, terms, identifiers, hashes, transformations, retention |
| Independent Verifier | Recomputes material quantities without production result logic |
| Claim Reviewer | Checks that text does not exceed evidence or gate status |
| Release Manager | Freezes versions, builds packages, verifies manifests, records receipts |
| Security Steward | Reviews credentials, network behavior, dependencies, incidents |

One person may hold several roles. Final release must state which roles were
independent. Without an independent verifier or claim reviewer, record
`SELF_REVIEW_ONLY`.

## Change Classes

| Class | Examples | Approval |
| --- | --- | --- |
| C0 Editorial | Spelling, links, formatting; no semantic change | Document owner |
| C1 Implementation | Refactor preserving frozen behavior | Analysis owner |
| C2 Input/Data | New dataset, mask, catalog snapshot, transformation | Data steward + scientific owner |
| C3 Protocol | Model, prior, threshold, branch, seed, stop-rule change | Scientific owner + verifier |
| C4 Claim | New, stronger, removed, or reworded claim | Scientific owner + claim reviewer |
| C5 Release | Version, package contents, DOI, submission, archive state | Release manager + scientific owner |
| C6 Security | Credentials, network trust, dependency exception, incident | Security steward |

When uncertain, use the higher class.

## Frozen Records and Supersession

Frozen protocols, manifests, result artifacts, gate reviews, and release
receipts are append-only. A correction must:

1. Use a new versioned filename or schema revision.
2. Identify the superseded record.
3. Explain whether the cause was scientific, numerical, data, implementation,
   provenance, or security related.
4. Preserve the original file and its hash.
5. Re-run all dependent verification and claim review.

## Claim Control

Every material claim maps to evidence: claim ID, wording class (supported,
conditional, diagnostic, not claimed, prohibited), exact artifact paths and
hashes, required upstream gates, scope, reviewer, and manuscript locations.

## Version Domains

The following versions are independent and must not be conflated:

| Domain | Source of truth |
| --- | --- |
| Shared software | Root `pyproject.toml` |
| Methodology | `methods/` documents |
| Scientific evidence | Candidate release manifest and receipt |
| Manuscript | Exact source hash and submission bundle |
| Dataset snapshot | Dataset manifest or archive identifier |
| Candidate lifecycle | `candidate/<id>/candidate.json` |

## Research Integrity

Selective reporting, hidden branch deletion, post-result threshold changes,
and relabeling diagnostic calculations as measurements are prohibited.
