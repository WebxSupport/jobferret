import importlib.util
from pathlib import Path
from unittest.mock import patch
import zipfile

import pytest


SPEC = importlib.util.spec_from_file_location("jobferret_install", Path(__file__).resolve().parents[1] / "install.py")
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


@pytest.mark.parametrize("host,folder", [("codex", ".agents"), ("claude", ".claude")])
def test_project_install_offline_without_home_access(tmp_path, host, folder):
    project = tmp_path / "Project with spaces"
    with patch.object(installer.Path, "home", side_effect=AssertionError("must not access home")):
        assert installer.main(["--host", host, "--project", str(project)]) == 0
    skill = project / folder / "skills" / "jobferret"
    assert (skill / "SKILL.md").read_bytes() == (installer.SOURCE / "SKILL.md").read_bytes()
    assert (skill / "scripts" / "sources" / "nhs.py").is_file()
    assert not (skill / "scripts" / "tests").exists()
    assert not (skill / "evals").exists()
    assert not list(skill.rglob("*.pyc"))


def test_existing_install_is_preserved(tmp_path):
    destination = tmp_path / "jobferret"
    destination.mkdir()
    marker = destination / "keep.txt"
    marker.write_text("existing version")
    with pytest.raises(FileExistsError):
        installer.install(installer.SOURCE, destination)
    assert marker.read_text() == "existing version"
    assert list(destination.iterdir()) == [marker]


def test_copy_failure_leaves_no_partial_skill(tmp_path):
    destination = tmp_path / "jobferret"
    with patch.object(installer.shutil, "copy2", side_effect=PermissionError("denied")):
        with pytest.raises(PermissionError):
            installer.install(installer.SOURCE, destination)
    assert not destination.exists()
    assert not list(tmp_path.iterdir())


def test_bundle_layout_and_no_overwrite(tmp_path):
    output = tmp_path / "jobferret.zip"
    installer.bundle(installer.SOURCE, output)
    before = output.read_bytes()
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        assert "jobferret/SKILL.md" in archive.namelist()
        assert "jobferret/scripts/setup_check.py" in archive.namelist()
        assert all(name.startswith("jobferret/") for name in archive.namelist())
        assert not any("/__pycache__/" in name or "/tests/" in name or "/evals/" in name for name in archive.namelist())
    with pytest.raises(FileExistsError):
        installer.bundle(installer.SOURCE, output)
    assert output.read_bytes() == before


def test_incomplete_source_does_not_create_destination(tmp_path):
    with pytest.raises(ValueError, match="Incomplete"):
        installer.install(tmp_path / "missing", tmp_path / "destination")
    assert not (tmp_path / "destination").exists()


def test_overlap_rejected():
    with pytest.raises(ValueError, match="separate"):
        installer.install(installer.SOURCE, installer.SOURCE / ".agents" / "skills" / "jobferret")


def test_permission_error_has_actionable_recovery(tmp_path, capsys):
    with patch.object(installer, "install", side_effect=PermissionError("denied")):
        assert installer.main(["--host", "codex", "--project", str(tmp_path)]) == 1
    assert "--scope project --project PATH" in capsys.readouterr().err
