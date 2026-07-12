"""Build the arXiv source package from the canonical manuscript."""

import re
import shutil
import subprocess
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DESTINATION = ROOT / "arxiv_submission"


def main():
    source = ROOT / "toi3492_characterization.tex"
    text = source.read_text()
    if DESTINATION.exists():
        shutil.rmtree(DESTINATION)
    DESTINATION.mkdir(exist_ok=True)
    (DESTINATION / source.name).write_text(text)
    if re.search(r"(?:[A-Za-z]:\\|/Users/|/home/)", text):
        raise RuntimeError("Canonical manuscript contains a local absolute path")
    shutil.copy2(ROOT / "references.bib", DESTINATION / "references.bib")

    figure_paths = re.findall(r"\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}", text)
    figure_dir = DESTINATION / "figures"
    figure_dir.mkdir(exist_ok=True)
    for relative in figure_paths:
        source_figure = ROOT / relative
        if not source_figure.is_file():
            raise FileNotFoundError(source_figure)
        shutil.copy2(source_figure, figure_dir / source_figure.name)

    commands = [
        ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", source.name],
        ["bibtex", source.stem],
        ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", source.name],
        ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", source.name],
    ]
    build_log = []
    final_output = ""
    for command in commands:
        completed = subprocess.run(
            command,
            cwd=DESTINATION,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=120,
        )
        build_log.append(f"$ {' '.join(command)}\n{completed.stdout}")
        final_output = completed.stdout
        if completed.returncode != 0:
            raise RuntimeError(
                f"Staged arXiv build failed: {' '.join(command)}\n{completed.stdout}"
            )
    if re.search(r"undefined citations|undefined references", final_output, re.I):
        raise RuntimeError("Staged arXiv build contains undefined references")

    archive = ROOT / "arxiv_submission.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        output.write(DESTINATION / source.name, source.name)
        output.write(DESTINATION / "references.bib", "references.bib")
        for relative in figure_paths:
            name = Path(relative).name
            output.write(figure_dir / name, f"figures/{name}")
    with zipfile.ZipFile(archive) as packaged:
        if packaged.testzip() is not None:
            raise RuntimeError("arXiv ZIP failed CRC verification")
    print(f"Wrote {archive}")


if __name__ == "__main__":
    main()
