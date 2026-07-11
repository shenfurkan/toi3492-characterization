"""Build the arXiv source package from the canonical manuscript."""

import re
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DESTINATION = ROOT / "arxiv_submission"


def main():
    source = ROOT / "toi3492_characterization.tex"
    text = source.read_text()
    DESTINATION.mkdir(exist_ok=True)
    (DESTINATION / source.name).write_text(text)
    shutil.copy2(ROOT / "references.bib", DESTINATION / "references.bib")

    figure_paths = re.findall(r"\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}", text)
    figure_dir = DESTINATION / "figures"
    figure_dir.mkdir(exist_ok=True)
    for relative in figure_paths:
        source_figure = ROOT / relative
        if not source_figure.is_file():
            raise FileNotFoundError(source_figure)
        shutil.copy2(source_figure, figure_dir / source_figure.name)

    archive = ROOT / "arxiv_submission.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        output.write(DESTINATION / source.name, source.name)
        output.write(DESTINATION / "references.bib", "references.bib")
        for relative in figure_paths:
            name = Path(relative).name
            output.write(figure_dir / name, f"figures/{name}")
    print(f"Wrote {archive}")


if __name__ == "__main__":
    main()
