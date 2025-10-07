from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from uuid import uuid4
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable, Optional
from urllib.parse import urlparse

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from loguru import logger

from rigging_bridge.config import AppSettings, get_settings
from rigging_bridge.models import ConversionArtifact, ConversionRequest, ConversionResponse


class BlenderConversionError(RuntimeError):
    """Raised when Blender exits with a non-zero status."""


@dataclass
class ConversionResult:
    artifacts: list[ConversionArtifact]
    logs: list[str]


class ConversionService:
    """Coordinate Blender based rig conversions."""

    def __init__(self, settings: Optional[AppSettings] = None) -> None:
        self.settings = settings or get_settings()
        self._s3_client = None

    def convert(self, request: ConversionRequest) -> ConversionResponse:
        logger.info("Starting conversion for {source}", source=request.source_uri)

        with TemporaryDirectory(prefix="rig-transformer-") as temp_dir:
            working_dir = Path(temp_dir)
            input_path = self._materialise_input(request.source_uri, working_dir)
            output_dir = working_dir / "output"
            output_dir.mkdir(parents=True, exist_ok=True)

            job_id = uuid4().hex
            destination_uri = request.output_uri or self._default_output_uri(job_id)

            cmd = self._build_blender_command(request, input_path, output_dir)
            logger.debug("Executing Blender command: {}", " ".join(shlex.quote(part) for part in cmd))

            env = os.environ.copy()
            src_root = str(Path(__file__).resolve().parents[1])
            if env.get("PYTHONPATH"):
                env["PYTHONPATH"] = os.pathsep.join([src_root, env["PYTHONPATH"]])
            else:
                env["PYTHONPATH"] = src_root
            logger.debug("Setting PYTHONPATH to: {}", env["PYTHONPATH"])

            completed = subprocess.run(
                cmd,
                cwd=working_dir,
                check=False,
                text=True,
                capture_output=True,
                env=env,
            )

            logs: list[str] = []
            if completed.stdout:
                logs.extend(completed.stdout.splitlines())
            if completed.stderr:
                logs.extend(completed.stderr.splitlines())

            if completed.returncode != 0:
                logger.error("Blender exited with status {}", completed.returncode)
                raise BlenderConversionError(
                    f"Blender exited with status {completed.returncode}: {completed.stderr}"
                )

            artifacts = list(self._collect_artifacts(output_dir, destination_uri))
            logger.info("Conversion complete with %d artifact(s)", len(artifacts))

            return ConversionResponse(status="COMPLETED", artifacts=artifacts, logs=logs)

    def _default_output_uri(self, job_id: str) -> Optional[str]:
        bucket = self.settings.output_bucket
        if not bucket:
            return None
        return f"s3://{bucket}/jobs/{job_id}"

    # Internal helpers -------------------------------------------------

    def _materialise_input(self, uri: str, working_dir: Path) -> Path:
        if self._is_s3_uri(uri):
            bucket, key = self._split_s3_uri(uri)
            filename = Path(key).name
            destination = working_dir / filename
            logger.debug("Downloading input from S3 %s to %s", uri, destination)
            self._s3().download_file(bucket, key, str(destination))
            return destination

        # Assume local path otherwise
        path = Path(uri)
        if not path.exists():
            msg = f"Input path does not exist: {uri}"
            raise FileNotFoundError(msg)
        if path.is_dir():
            msg = "Input path must be a file, not a directory"
            raise IsADirectoryError(msg)
        return path

    def _collect_artifacts(
        self,
        output_dir: Path,
        destination_uri: Optional[str],
    ) -> Iterable[ConversionArtifact]:
        files = sorted(output_dir.glob("*.glb"))
        for file_path in files:
            yield self._dispatch_artifact(file_path, destination_uri)

    def _dispatch_artifact(
        self,
        artifact_path: Path,
        destination_uri: Optional[str],
    ) -> ConversionArtifact:
        if destination_uri and self._is_s3_uri(destination_uri):
            bucket, key_prefix = self._split_s3_uri(destination_uri)
            if key_prefix and not key_prefix.endswith("/"):
                key_prefix = f"{key_prefix}/"
            target_key = f"{key_prefix}{artifact_path.name}" if key_prefix else artifact_path.name
            logger.debug("Uploading artifact %s to s3://%s/%s", artifact_path, bucket, target_key)
            self._s3().upload_file(str(artifact_path), bucket, target_key)
            return ConversionArtifact(
                uri=f"s3://{bucket}/{target_key}",
                content_type="model/gltf-binary",
            )

        target_dir: Path
        if destination_uri:
            target_dir = Path(destination_uri)
        else:
            target_dir = self.settings.work_dir / "artifacts"

        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / artifact_path.name
        logger.debug("Copying artifact %s to %s", artifact_path, target_path)
        shutil.copy2(artifact_path, target_path)
        return ConversionArtifact(uri=str(target_path), content_type="model/gltf-binary")

    def _build_blender_command(
        self,
        request: ConversionRequest,
        input_path: Path,
        output_dir: Path,
    ) -> list[str]:
        script_path = self._blender_script()
        command = [
            str(self.settings.blender_executable),
            "-b",
            "-P",
            str(script_path),
            "--",
            "--input",
            str(input_path),
            "--output-dir",
            str(output_dir),
        ]

        if request.collection:
            command.extend(["--collection", request.collection])
        if request.include_extra_bones:
            command.append("--include-extra-bones")
        if not request.t_pose:
            command.append("--skip-t-pose")
        if not request.export_textures:
            command.append("--skip-textures")
        if not request.remove_fingers:
            command.append("--keep-fingers")

        return command

    def _blender_script(self) -> Path:
        from importlib import resources

        script = resources.files("rigging_bridge.blender") / "run_conversion.py"
        return Path(script)

    def _is_s3_uri(self, uri: str) -> bool:
        return uri.startswith("s3://")

    def _split_s3_uri(self, uri: str) -> tuple[str, str]:
        parsed = urlparse(uri)
        if parsed.scheme != "s3" or not parsed.netloc:
            msg = f"Invalid S3 URI: {uri}"
            raise ValueError(msg)
        key = parsed.path.lstrip("/")
        return parsed.netloc, key

    def _s3(self):
        if self._s3_client is None:
            try:
                self._s3_client = boto3.client("s3", region_name=self.settings.aws_region)
            except (BotoCoreError, ClientError) as exc:  # pragma: no cover - boto specific
                logger.error("Unable to create S3 client: %s", exc)
                raise
        return self._s3_client


__all__ = [
    "BlenderConversionError",
    "ConversionResult",
    "ConversionService",
]
