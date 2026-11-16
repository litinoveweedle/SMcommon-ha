"""Install card dependencies without replacing the wheel under test."""

import json
import subprocess
import sys
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


def card_requirements(repo: Path) -> list[str]:
    """Read the hardware requirements from one card manifest."""
    manifests = list((repo / "custom_components").glob("*/manifest.json"))
    if len(manifests) != 1:
        raise ValueError(f"Expected one integration manifest in {repo}, found {len(manifests)}")
    with manifests[0].open(encoding="utf-8") as manifest:
        requirements = json.load(manifest)["requirements"]
    drivers = []
    has_common = False
    for requirement in requirements:
        if canonicalize_name(Requirement(requirement).name) == "SMcommonHA":
            has_common = True
        else:
            drivers.append(requirement)
    if not has_common:
        raise ValueError(f"{manifests[0]} does not require SMcommonHA")
    return drivers


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Pass at least one card repository path")
    requirements = [requirement for repo in sys.argv[1:] for requirement in card_requirements(Path(repo))]
    if requirements:
        subprocess.run(
            [sys.executable, "-m", "pip", "--isolated", "install",
             "--index-url", "https://pypi.org/simple", *requirements],
            check=True,
        )


if __name__ == "__main__":
    main()
