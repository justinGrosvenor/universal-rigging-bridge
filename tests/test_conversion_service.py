from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from subprocess import CompletedProcess

from rigging_bridge.models import ConversionRequest
from rigging_bridge.services.conversion import ConversionService
from rigging_bridge.config import AppSettings


@pytest.fixture
def fake_blender_run():
    def _runner(cmd: list[str], cwd: Path | None = None, **_: Any):
        try:
            output_dir_index = cmd.index("--output-dir") + 1
        except ValueError as exc:  # pragma: no cover - defensive guard
            raise AssertionError("--output-dir flag not forwarded to Blender command") from exc

        output_dir = Path(cmd[output_dir_index])
        output_dir.mkdir(parents=True, exist_ok=True)
        artifact = output_dir / "UE5_sample.glb"
        artifact.write_bytes(b"glb")

        return CompletedProcess(args=cmd, returncode=0, stdout="mock stdout", stderr="")

    return _runner


def test_convert_local_asset(tmp_path: Path, fake_blender_run):
    source_file = tmp_path / "input.glb"
    source_file.write_bytes(b"dummy data")

    work_dir = tmp_path / "work"
    settings = AppSettings(work_dir=work_dir)
    service = ConversionService(settings=settings)

    with patch("rigging_bridge.services.conversion.subprocess.run", side_effect=fake_blender_run):
        response = service.convert(ConversionRequest(source_uri=str(source_file)))

    assert response.status == "COMPLETED"
    assert response.artifacts, "Expected at least one artifact"

    artifact_path = Path(response.artifacts[0].uri)
    assert artifact_path.exists()
    assert artifact_path.suffix == ".glb"

    expected_artifact = settings.work_dir / "artifacts" / artifact_path.name
    assert artifact_path == expected_artifact
    assert "mock stdout" in response.logs
