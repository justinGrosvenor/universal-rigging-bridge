"""
Rig Interop Bridge Orchestrator

Main entry point for the rig normalization pipeline.
Coordinates all modules to convert diverse rigs to canonical skeleton.

Workflow:
1. Detect source rig type
2. Capture joint positions from source
3. Create mapping to canonical skeleton
4. Adjust canonical skeleton to match source proportions
5. Transfer skin weights
6. Reset to canonical rest pose
7. Export with metadata
"""

from pathlib import Path
from typing import Optional

try:
    import bpy
    BLENDER_AVAILABLE = True
except ImportError:
    BLENDER_AVAILABLE = False
    bpy = None  # type: ignore

from rigging_bridge.bridge.rig_detector import RigDetector
from rigging_bridge.bridge.joint_matcher import JointMatcher
from rigging_bridge.bridge.skeleton_adjuster import CanonicalSkeletonAdjuster
from rigging_bridge.bridge.weight_transfer import WeightTransfer
from rigging_bridge.bridge.pose_reset import PoseReset
from rigging_bridge.bridge.types import (
    ConversionOptions,
    ConversionResult,
    RigType,
)


class RigInteropBridge:
    """
    Main orchestrator for rig normalization pipeline.

    Converts source rigs (ARP, CC3/4, Mixamo, VRM, etc.) to a canonical
    skeleton (UE5 Mannequin) while preserving character proportions.
    """

    def __init__(self, options: Optional[ConversionOptions] = None):
        """
        Initialize the Rig Interop Bridge.

        Args:
            options: Configuration options for conversion
        """
        self.options = options or ConversionOptions()

        # Initialize all modules
        self.detector = RigDetector()
        self.matcher = JointMatcher()
        self.adjuster = CanonicalSkeletonAdjuster()
        self.weight_transfer = WeightTransfer()
        self.pose_reset = PoseReset()

    def convert(
        self,
        source_armature: "bpy.types.Object",
        source_mesh: "bpy.types.Object",
        canonical_armature: "bpy.types.Object",
        output_path: Optional[Path] = None,
    ) -> ConversionResult:
        """
        Convert source rig to canonical skeleton.

        This is the main entry point that orchestrates the entire pipeline.

        Args:
            source_armature: Source character's armature
            source_mesh: Source character's mesh
            canonical_armature: Canonical skeleton to adopt
            output_path: Optional path to export result

        Returns:
            ConversionResult with metadata and status
        """
        if not BLENDER_AVAILABLE or bpy is None:
            return ConversionResult(
                success=False,
                errors=["Blender API is not available"],
            )

        result = ConversionResult(success=False)

        try:
            # Step 1: Detect rig type
            print("Step 1: Detecting rig type...")
            rig_metadata = self.detector.detect(source_armature)
            result.rig_metadata = rig_metadata

            if rig_metadata.rig_type == RigType.UNKNOWN:
                result.warnings.append(
                    f"Unknown rig type detected (confidence: {rig_metadata.confidence})"
                )

            print(f"  Detected: {rig_metadata.rig_type.value} "
                  f"(confidence: {rig_metadata.confidence:.2f})")

            # Step 2: Capture joint positions from source
            print("Step 2: Capturing joint positions...")
            source_positions = self.matcher.capture_positions(
                source_armature,
                rig_metadata.rig_type,
            )
            print(f"  Captured {len(source_positions)} joint positions")

            # Calculate metrics for validation
            metrics = self.matcher.calculate_metrics(source_positions)
            print(f"  Metrics: {metrics}")

            # Step 3: Create mapping to canonical skeleton
            print("Step 3: Creating joint mapping...")
            joint_mapping = self.matcher.create_mapping(
                source_positions,
                rig_metadata.rig_type,
            )
            result.joint_mapping = joint_mapping

            print(f"  Mapped {len(joint_mapping.target_positions)} joints")
            if joint_mapping.unmapped_source:
                print(f"  Unmapped source bones: {len(joint_mapping.unmapped_source)}")
                result.warnings.append(
                    f"{len(joint_mapping.unmapped_source)} source bones not mapped"
                )
            if joint_mapping.unmapped_target:
                print(f"  Unmapped target bones: {len(joint_mapping.unmapped_target)}")
                result.warnings.append(
                    f"{len(joint_mapping.unmapped_target)} target bones not found in source"
                )

            # Step 4: Adjust canonical skeleton to match source proportions
            if self.options.preserve_proportions:
                print("Step 4: Adjusting canonical skeleton to match source...")
                original_positions = self.adjuster.adjust_to_match(
                    canonical_armature,
                    joint_mapping,
                )
                print(f"  Adjusted {len(original_positions)} bones")

                # Validate adjustment
                is_valid, errors = self.adjuster.validate_adjustment(
                    canonical_armature,
                    joint_mapping,
                )
                if not is_valid:
                    result.warnings.extend(errors)
            else:
                print("Step 4: Skipping proportion preservation")
                original_positions = None

            # Step 5: Transfer skin weights
            print("Step 5: Transferring skin weights...")
            transfer_stats = self.weight_transfer.transfer_weights(
                source_mesh,
                canonical_armature,
                joint_mapping,
                method="hybrid",
            )
            print(f"  {transfer_stats}")

            # Swap armature
            self.weight_transfer.swap_armature(source_mesh, canonical_armature)

            # Validate weights
            if self.options.validate_weights:
                is_valid, warnings = self.weight_transfer.validate_weights(
                    source_mesh,
                    canonical_armature,
                )
                if not is_valid:
                    result.warnings.extend(warnings)

            # Step 6: Reset to canonical rest pose
            print("Step 6: Resetting to canonical rest pose...")
            self.pose_reset.reset_to_rest_pose(
                canonical_armature,
                original_positions=original_positions,
                target_pose=self.options.target_rest_pose,
            )

            # Validate rest pose
            is_valid, warnings = self.pose_reset.validate_rest_pose(
                canonical_armature,
                self.options.target_rest_pose,
            )
            if not is_valid:
                result.warnings.extend(warnings)

            # Step 7: Export (if path provided)
            if output_path:
                print(f"Step 7: Exporting to {output_path}...")
                self._export(source_mesh, canonical_armature, output_path)
                result.output_path = str(output_path)
            else:
                print("Step 7: Skipping export (no output path provided)")

            # Success!
            result.success = True
            print("Conversion complete!")

        except Exception as e:
            result.success = False
            result.errors.append(f"Conversion failed: {str(e)}")
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()

        return result

    def _export(
        self,
        mesh: "bpy.types.Object",
        armature: "bpy.types.Object",
        output_path: Path,
    ) -> None:
        """
        Export mesh and armature to GLB.

        Args:
            mesh: Mesh object to export
            armature: Armature to export
            output_path: Path to write GLB file
        """
        if not BLENDER_AVAILABLE or bpy is None:
            raise RuntimeError("Blender API is not available")

        # Select objects to export
        bpy.ops.object.select_all(action="DESELECT")
        mesh.select_set(True)
        armature.select_set(True)
        bpy.context.view_layer.objects.active = armature

        # Export as GLB
        bpy.ops.export_scene.gltf(
            filepath=str(output_path),
            use_selection=True,
            export_format="GLB",
            export_textures=self.options.export_textures,
            export_colors=True,
            export_materials="EXPORT" if self.options.export_textures else "NONE",
            export_skins=True,
            export_animations=False,  # We're normalizing rigs, not animations
        )

    def export_metadata(
        self,
        result: ConversionResult,
        output_path: Path,
    ) -> None:
        """
        Export conversion metadata to JSON.

        This creates a scene_data.json file with:
        - Original rig type
        - Conversion status
        - Joint mapping details
        - Warnings and errors

        Args:
            result: ConversionResult to serialize
            output_path: Path to write JSON file
        """
        import json

        metadata = result.to_dict()

        with open(output_path, "w") as f:
            json.dump(metadata, f, indent=2)

        print(f"Metadata exported to {output_path}")

    def validate_conversion(
        self,
        result: ConversionResult,
    ) -> tuple[bool, list[str]]:
        """
        Perform final validation checks on conversion result.

        Args:
            result: ConversionResult to validate

        Returns:
            Tuple of (is_valid, list of critical errors)
        """
        critical_errors: list[str] = []
        is_valid = True

        if not result.success:
            critical_errors.append("Conversion reported failure")
            is_valid = False

        if not result.rig_metadata:
            critical_errors.append("No rig metadata available")
            is_valid = False

        if not result.joint_mapping:
            critical_errors.append("No joint mapping available")
            is_valid = False

        if result.errors:
            critical_errors.extend(result.errors)
            is_valid = False

        # Check for excessive unmapped bones
        if result.joint_mapping:
            unmapped_pct = (
                len(result.joint_mapping.unmapped_target) /
                len(result.joint_mapping.target_positions)
                if result.joint_mapping.target_positions else 0
            )
            if unmapped_pct > 0.3:  # More than 30% unmapped
                critical_errors.append(
                    f"Too many unmapped target bones: {unmapped_pct:.1%}"
                )
                is_valid = False

        return is_valid, critical_errors
