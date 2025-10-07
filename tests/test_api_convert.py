from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess
from typing import Any

import pytest
from fastapi.testclient import TestClient

from rigging_bridge.api import app
from rigging_bridge.config import get_settings


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def mock_blender(monkeypatch: pytest.MonkeyPatch):
    def _runner(cmd: list[str], cwd: Path | None = None, **_: Any):
        output_dir = Path(cmd[cmd.index("--output-dir") + 1])
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "UE5_sample.glb").write_bytes(b"glb")
        return CompletedProcess(args=cmd, returncode=0, stdout="mock", stderr="")

    monkeypatch.setattr("rigging_bridge.services.conversion.subprocess.run", _runner)
    return _runner


def test_convert_endpoint_local_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, client: TestClient, mock_blender):
    source_file = tmp_path / "sample.glb"
    source_file.write_bytes(b"dummy")

    work_dir = tmp_path / "artifacts"
    monkeypatch.setenv("WORK_DIR", str(work_dir))

    get_settings.cache_clear()  # ensure settings pick up new WORK_DIR

    payload = {
        "source_uri": str(source_file),
        "collection": "as",
        "include_extra_bones": False,
        "t_pose": True,
        "export_textures": True,
        "remove_fingers": True,
    }

    response = client.post("/v1/convert", json=payload)

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["artifacts"], "Artifacts list should not be empty"

    artifact_path = Path(body["artifacts"][0]["uri"])
    assert artifact_path.exists()
    assert artifact_path.suffix == ".glb"
