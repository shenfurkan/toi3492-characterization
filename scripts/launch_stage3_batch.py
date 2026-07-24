"""Launch parallel S3-04B screen + joint batch processes.

Each class runs as a separate Python process writing to shared checkpoint CSV.
Re-run is safe: already-completed realizations are detected and skipped.

Usage: python scripts/launch_stage3_batch.py [--screening-only]
"""

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SCREEN_CMD = [
    sys.executable, "-B", str(ROOT / "scripts" / "run_stage3_synthetic_screening.py"),
    "--workers", "1",
]
JOINT_CMD = [
    sys.executable, "-B", str(ROOT / "scripts" / "run_stage3_synthetic_joint_recovery.py"),
    "--workers", "1",
]


def launch(class_index, count, cmd, out_dir):
    args = cmd + ["--class-index", str(class_index)]
    if count is not None:
        args += ["--count", str(count)]
    log_path = out_dir / "batch_c{:02d}.log".format(class_index)
    err_path = out_dir / "batch_c{:02d}.err.log".format(class_index)
    with open(log_path, "w") as out, open(err_path, "w") as err:
        proc = subprocess.Popen(
            args, stdout=out, stderr=err,
            cwd=str(ROOT), creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    return proc


def main():
    out_dir = ROOT / "outputs"
    out_dir.mkdir(exist_ok=True)
    mode = "full"
    args = sys.argv[1:]
    if "--screening-only" in args:
        mode = "screening"

    started = time.strftime("%Y-%m-%d %H:%M:%S")
    print("Launching S3-04B batch ({}) at {}".format(mode, started), flush=True)

    procs = []
    for class_index in range(12):
        count = None
        print("  C{:02d} screening ...".format(class_index), end=" ", flush=True)
        proc = launch(class_index, count, SCREEN_CMD, out_dir)
        procs.append(("C{:02d}_screen".format(class_index), proc))
        print("PID {}".format(proc.pid), flush=True)

    if mode != "screening":
        print("\nWaiting 30s before launching joint recovery...", flush=True)
        time.sleep(30)
        for class_index in range(12):
            count = None
            print("  C{:02d} joint ...".format(class_index), end=" ", flush=True)
            proc = launch(class_index, count, JOINT_CMD, out_dir)
            procs.append(("C{:02d}_joint".format(class_index), proc))
            print("PID {}".format(proc.pid), flush=True)

    print("\nAll processes launched. Logs in {}batch_c*.log".format(out_dir))
    print("Check progress with: Get-Content outputs/batch_c00.log -Tail 5", flush=True)


if __name__ == "__main__":
    main()