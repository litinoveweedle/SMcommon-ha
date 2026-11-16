"""Verify CI installs card drivers without replacing the shared wheel."""

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / ".github/scripts/install-card-requirements.py"
spec = importlib.util.spec_from_file_location("install_card_requirements", SCRIPT)
assert spec is not None and spec.loader is not None
install_card_requirements = importlib.util.module_from_spec(spec)
spec.loader.exec_module(install_card_requirements)


def test_excludes_shared_library_pin(tmp_path):
    manifest = tmp_path / "custom_components" / "card" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({
        "requirements": ["SomeDriver>=1.0", "Sequent_HA_Common==99.0"],
    }), encoding="utf-8")
    assert install_card_requirements.card_requirements(tmp_path) == ["SomeDriver>=1.0"]


def test_requires_single_manifest_and_shared_dependency(tmp_path):
    with pytest.raises(ValueError, match="Expected one integration manifest"):
        install_card_requirements.card_requirements(tmp_path)
    manifest = tmp_path / "custom_components" / "card" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"requirements": ["SomeDriver>=1.0"]}), encoding="utf-8")
    with pytest.raises(ValueError, match="does not require sequent-ha-common"):
        install_card_requirements.card_requirements(tmp_path)
    extra = tmp_path / "custom_components" / "other" / "manifest.json"
    extra.parent.mkdir()
    extra.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="found 2"):
        install_card_requirements.card_requirements(tmp_path)
