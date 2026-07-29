"""Stage-3 v3 core using the fresh protocol, seed, and namespace."""

from contextlib import contextmanager

import stage3_synthetic_calibration_core_v2 as _base


ROOT = _base.ROOT
PROTOCOL_PATH = ROOT / "data" / "stage3_synthetic_calibration_protocol_v3.json"
ARCHITECTURE_PATH = ROOT / "data" / "stage3_model_architecture_decision_v3.json"
INPUT_MANIFEST_PATH = ROOT / "data" / "stage3_input_manifest_v3.json"
SECTORS = _base.SECTORS


@contextmanager
def _configured():
    saved_protocol = _base.PROTOCOL_PATH
    saved_architecture = _base.ARCHITECTURE_PATH
    saved_manifest = _base.INPUT_MANIFEST_PATH
    _base.PROTOCOL_PATH = PROTOCOL_PATH
    _base.ARCHITECTURE_PATH = ARCHITECTURE_PATH
    _base.INPUT_MANIFEST_PATH = INPUT_MANIFEST_PATH
    try:
        yield
    finally:
        _base.PROTOCOL_PATH = saved_protocol
        _base.ARCHITECTURE_PATH = saved_architecture
        _base.INPUT_MANIFEST_PATH = saved_manifest


def load_context():
    with _configured():
        return _base.load_context()


realization_seed = _base.realization_seed
generate_latent_realization = _base.generate_latent_realization
apply_branch_baseline = _base.apply_branch_baseline
derive_mask = _base.derive_mask


def source_metadata(context):
    return {
        "calibration_protocol": {
            "path": "data/stage3_synthetic_calibration_protocol_v3.json",
            "sha256": context.protocol_sha256,
        },
        "architecture": {
            "path": "data/stage3_model_architecture_decision_v3.json",
            "sha256": context.architecture_sha256,
        },
        "input_manifest": {
            "path": "data/stage3_input_manifest_v3.json",
            "sha256": context.input_manifest_sha256,
        },
        "raw_template_rows": int(len(context.raw_template)),
        "reference_template_rows": int(len(context.reference_keys)),
        "branch_count": int(len(context.branches)),
        "complete_event_count": int(len(context.complete_events)),
        "gap_edge_event_count": int(len(context.gap_edge_events)),
        "sectors": list(SECTORS),
    }
