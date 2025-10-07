"""
Rest Pose Reset Module

Resets the canonical skeleton back to its standard rest pose after
weight transfer is complete.

This is the final step that ensures all output characters share the
same canonical rest pose, enabling animation retargeting.
"""

from typing import Dict, Optional

try:
    import bpy
    from mathutils import Vector, Matrix
    BLENDER_AVAILABLE = True
except ImportError:
    BLENDER_AVAILABLE = False
    bpy = None  # type: ignore
    Vector = tuple  # type: ignore
    Matrix = None  # type: ignore

from rigging_bridge.bridge.types import RestPose


class PoseReset:
    """
    Resets armature to canonical rest pose after weight transfer.

    The canonical rest pose is typically T-pose for UE5 Mannequin,
    ensuring all output characters can share animations.
    """

    def __init__(self):
        """Initialize the pose reset system."""
        pass

    def reset_to_rest_pose(
        self,
        armature: "bpy.types.Object",
        original_positions: Optional[Dict[str, Vector]] = None,
        target_pose: RestPose = RestPose.T_POSE,
    ) -> None:
        """
        Reset armature to canonical rest pose.

        If original_positions is provided, restores those exact positions.
        Otherwise, applies the standard rest pose for the target type.

        Args:
            armature: Armature to reset
            original_positions: Optional dict of bone name -> original position
            target_pose: Target rest pose type
        """
        if not BLENDER_AVAILABLE or bpy is None:
            raise RuntimeError("Blender API is not available")

        if armature.type != "ARMATURE":
            raise ValueError(f"Object {armature.name} is not an armature")

        bpy.context.view_layer.objects.active = armature

        if original_positions:
            # Restore exact original positions
            self._restore_exact_positions(armature, original_positions)
        else:
            # Apply standard rest pose
            if target_pose == RestPose.T_POSE:
                self._apply_t_pose(armature)
            elif target_pose == RestPose.A_POSE:
                self._apply_a_pose(armature)
            else:
                raise ValueError(f"Unknown rest pose type: {target_pose}")

        # Apply the pose as the new rest pose
        self._bake_as_rest_pose(armature)

    def _restore_exact_positions(
        self,
        armature: "bpy.types.Object",
        original_positions: Dict[str, Vector],
    ) -> None:
        """
        Restore bones to their exact original positions.

        This undoes the adjustment made by CanonicalSkeletonAdjuster.
        """
        bpy.ops.object.mode_set(mode="EDIT")

        edit_bones = armature.data.edit_bones

        for bone_name, original_pos in original_positions.items():
            if bone_name in edit_bones:
                bone = edit_bones[bone_name]

                # Calculate the offset needed
                current_head = bone.head.copy()
                offset = original_pos - current_head

                # Move bone back to original position
                bone.head = original_pos
                bone.tail = bone.tail + offset

        bpy.ops.object.mode_set(mode="OBJECT")

    def _apply_t_pose(self, armature: "bpy.types.Object") -> None:
        """
        Apply T-pose to armature.

        T-pose characteristics:
        - Arms extend straight out to sides (90° from body)
        - Legs straight down
        - Spine vertical
        """
        bpy.ops.object.mode_set(mode="POSE")

        pose_bones = armature.pose.bones

        # Reset all bone rotations first
        for bone in pose_bones:
            bone.rotation_mode = "QUATERNION"
            bone.rotation_quaternion = (1, 0, 0, 0)
            bone.location = (0, 0, 0)
            bone.scale = (1, 1, 1)

        # Rotate arms to T-pose (90° outward)
        arm_bones = ["clavicle_l", "upperarm_l", "lowerarm_l"]
        for bone_name in arm_bones:
            if bone_name in pose_bones:
                bone = pose_bones[bone_name]
                bone.rotation_mode = "XYZ"
                # Rotate around Z-axis for left arm
                bone.rotation_euler.z = 1.5708  # 90 degrees in radians

        arm_bones_r = ["clavicle_r", "upperarm_r", "lowerarm_r"]
        for bone_name in arm_bones_r:
            if bone_name in pose_bones:
                bone = pose_bones[bone_name]
                bone.rotation_mode = "XYZ"
                # Rotate around Z-axis for right arm
                bone.rotation_euler.z = -1.5708  # -90 degrees

        bpy.ops.object.mode_set(mode="OBJECT")

    def _apply_a_pose(self, armature: "bpy.types.Object") -> None:
        """
        Apply A-pose to armature.

        A-pose characteristics:
        - Arms angled down at ~45° from body
        - Legs straight down (may be slightly apart)
        - Spine vertical
        """
        bpy.ops.object.mode_set(mode="POSE")

        pose_bones = armature.pose.bones

        # Reset all bone rotations
        for bone in pose_bones:
            bone.rotation_mode = "QUATERNION"
            bone.rotation_quaternion = (1, 0, 0, 0)
            bone.location = (0, 0, 0)
            bone.scale = (1, 1, 1)

        # Rotate arms to A-pose (~45° downward)
        arm_bones_l = ["clavicle_l", "upperarm_l"]
        for bone_name in arm_bones_l:
            if bone_name in pose_bones:
                bone = pose_bones[bone_name]
                bone.rotation_mode = "XYZ"
                bone.rotation_euler.z = 0.7854  # 45 degrees

        arm_bones_r = ["clavicle_r", "upperarm_r"]
        for bone_name in arm_bones_r:
            if bone_name in pose_bones:
                bone = pose_bones[bone_name]
                bone.rotation_mode = "XYZ"
                bone.rotation_euler.z = -0.7854  # -45 degrees

        bpy.ops.object.mode_set(mode="OBJECT")

    def _bake_as_rest_pose(self, armature: "bpy.types.Object") -> None:
        """
        Bake the current pose as the new rest pose.

        This applies the pose transforms to the armature permanently.
        """
        bpy.context.view_layer.objects.active = armature
        bpy.ops.object.mode_set(mode="POSE")

        # Apply pose as rest pose
        bpy.ops.pose.armature_apply(selected=False)

        bpy.ops.object.mode_set(mode="OBJECT")

    def clear_all_transforms(self, armature: "bpy.types.Object") -> None:
        """
        Clear all transforms on armature bones.

        Useful for resetting to a known state before processing.

        Args:
            armature: Armature to clear
        """
        if not BLENDER_AVAILABLE or bpy is None:
            raise RuntimeError("Blender API is not available")

        bpy.context.view_layer.objects.active = armature
        bpy.ops.object.mode_set(mode="POSE")

        for bone in armature.pose.bones:
            bone.location = (0, 0, 0)
            bone.rotation_quaternion = (1, 0, 0, 0)
            bone.rotation_euler = (0, 0, 0)
            bone.scale = (1, 1, 1)

        bpy.ops.object.mode_set(mode="OBJECT")

    def validate_rest_pose(
        self,
        armature: "bpy.types.Object",
        target_pose: RestPose,
        tolerance: float = 0.1,
    ) -> tuple[bool, list[str]]:
        """
        Validate that armature is in the correct rest pose.

        Args:
            armature: Armature to validate
            target_pose: Expected rest pose type
            tolerance: Angle tolerance in radians

        Returns:
            Tuple of (is_valid, list of warnings)
        """
        warnings: list[str] = []
        is_valid = True

        # Check key bone orientations
        if target_pose == RestPose.T_POSE:
            # Check that arms are horizontal
            for side in ["l", "r"]:
                bone_name = f"upperarm_{side}"
                if bone_name in armature.pose.bones:
                    bone = armature.pose.bones[bone_name]
                    # Check Z rotation is ~90° or ~-90°
                    expected = 1.5708 if side == "l" else -1.5708
                    actual = bone.rotation_euler.z if bone.rotation_mode == "XYZ" else 0

                    if abs(actual - expected) > tolerance:
                        warnings.append(
                            f"Bone {bone_name} not in T-pose: "
                            f"Z rotation is {actual:.2f}, expected {expected:.2f}"
                        )
                        is_valid = False

        elif target_pose == RestPose.A_POSE:
            # Check that arms are at ~45°
            for side in ["l", "r"]:
                bone_name = f"upperarm_{side}"
                if bone_name in armature.pose.bones:
                    bone = armature.pose.bones[bone_name]
                    expected = 0.7854 if side == "l" else -0.7854
                    actual = bone.rotation_euler.z if bone.rotation_mode == "XYZ" else 0

                    if abs(actual - expected) > tolerance:
                        warnings.append(
                            f"Bone {bone_name} not in A-pose: "
                            f"Z rotation is {actual:.2f}, expected {expected:.2f}"
                        )
                        is_valid = False

        return is_valid, warnings
