# EXONYM Global Templates

Target-neutral protocol templates cloned into every candidate workspace by
`exonym init`. Placeholders (`{{CANDIDATE_ID}}`, `{{TOI}}`, `{{TIC}}`,
`{{TIMESTAMP}}`) are bound to the candidate identity record on instantiation.

| Path | Phase | Purpose |
| --- | --- | --- |
| `docs/01_intake_manifest.md` | intake | Catalog identity, astrometry, collision checks |
| `docs/02_feasibility_report.md` | feasibility | Contamination, SNR, sector coverage, go/no-go |
| `docs/03_spoc_dv_vetting.md` | vetting | SPOC DV diagnostics and centroid tests |
| `docs/04_tfop_sg_followup.md` | followup | TFOP SG1-SG5 coordination status |
| `protocols/transit_fitting.md` | analysis | Transit model prior specification |
| `protocols/radial_velocity.md` | analysis | Keplerian orbit fitting protocol |
| `decisions/review_gate.md` | review | Peer-review and scientific disposition gate |
| `tracking/pipeline_status.md` | all | Local checkpoint telemetry summary |

Mandatory gate items are marked `[MANDATORY]`; `exonym advance` refuses to
promote a phase until every mandatory item is checked (`- [x]`).
