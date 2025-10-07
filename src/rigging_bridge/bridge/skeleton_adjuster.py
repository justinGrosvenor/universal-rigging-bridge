"""
Canonical Skeleton Adjuster Module

Adjusts the canonical skeleton's joint positions to match the source character's
proportions BEFORE weight transfer. This is the critical step that preserves
visual fidelity while normalizing rig structure.

The workflow is:
1. Load canonical skeleton (UE5 Mannequin) in standard rest pose
2. Measure source character joint positions
3. MOVE canonical skeleton bones to match source proportions
4. Transfer weights while skeleton is adjusted
5. Reset to canonical rest pose (done by RestPoseReset module)
"""

from typing import Dict, Optional

try:
    import bpy
    from mathutils import Vector
    BLENDER_AVAILABLE = True
except ImportError:
    BLENDER_AVAILABLE = False
    bpy = None  # type: ignore
    Vector = tuple  # type: ignore

from rigging_bridge.bridge.types import JointPosition, JointMapping


class CanonicalSkeletonAdjuster:
    """
    Adjusts canonical skeleton bone positions to match source character proportions.

    This ensures that when weights are transferred, the deformation matches
    the original character's body shape (wide shoulders, long legs, etc.)
    """

    def __init__(self):
        """Initialize the skeleton adjuster."""
        pass

    def adjust_to_match(
        self,
        canonical_armature: "bpy.types.Object",
        joint_mapping: JointMapping,
    ) -> Dict[str, Vector]:
        """
        Adjust canonical skeleton bones to match source joint positions.

        This modifies the canonical armature in edit mode, moving bone heads
        and tails to match the proportions of the source character.

        Args:
            canonical_armature: Target canonical skeleton (e.g., UE5 Mannequin)
            joint_mapping: Mapping from source to target joint positions

        Returns:
            Dictionary of original bone positions (for reset/undo)
        """
        if not BLENDER_AVAILABLE or bpy is None:
            raise RuntimeError("Blender API is not available")

        if canonical_armature.type != "ARMATURE":
            raise ValueError(f"Object {canonical_armature.name} is not an armature")

        # Store original positions for later reset
        original_positions: Dict[str, Vector] = {}

        # Enter edit mode to modify bone positions
        bpy.context.view_layer.objects.active = canonical_armature
        bpy.ops.object.mode_set(mode="EDIT")

        edit_bones = canonical_armature.data.edit_bones

        try:
            for canonical_name, target_pos in joint_mapping.target_positions.items():
                if canonical_name not in edit_bones:
                    continue

                bone = edit_bones[canonical_name]

                # Store original position
                original_positions[canonical_name] = bone.head.copy()

                # Move bone head to match source position
                bone.head = target_pos.position.copy()

                # Adjust tail to maintain bone length and orientation
                # This is simplified - production version would handle orientation better
                original_length = (bone.tail - original_positions[canonical_name]).length
                bone_direction = (bone.tail - bone.head).normalized()
                bone.tail = bone.head + (bone_direction * original_length)

        finally:
            # Return to object mode
            bpy.ops.object.mode_set(mode="OBJECT")

        return original_positions

    def adjust_proportional(
        self,
        canonical_armature: "bpy.types.Object",
        joint_mapping: JointMapping,
        preserve_bone_length: bool = True,
    ) -> Dict[str, Vector]:
        """
        Adjust canonical skeleton with proportional scaling.

        Instead of moving bones to exact positions, this method scales
        bone chains proportionally to match source proportions while
        preserving the canonical hierarchy shape.

        This can produce better results for characters with extreme
        proportions (very tall, very wide, etc.)

        Args:
            canonical_armature: Target canonical skeleton
            joint_mapping: Mapping from source to target
            preserve_bone_length: Whether to maintain relative bone lengths

        Returns:
            Dictionary of original bone positions
        """
        if not BLENDER_AVAILABLE or bpy is None:
            raise RuntimeError("Blender API is not available")

        # Calculate scaling factors for key dimensions
        scale_factors = self._calculate_scale_factors(joint_mapping)

        # Store original positions
        original_positions: Dict[str, Vector] = {}

        bpy.context.view_layer.objects.active = canonical_armature
        bpy.ops.object.mode_set(mode="EDIT")

        edit_bones = canonical_armature.data.edit_bones

        try:
            # Apply scaling to bone chains
            self._scale_spine_chain(edit_bones, scale_factors, original_positions)
            self._scale_arm_chains(edit_bones, scale_factors, original_positions)
            self._scale_leg_chains(edit_bones, scale_factors, original_positions)

        finally:
            bpy.ops.object.mode_set(mode="OBJECT")

        return original_positions

    def _calculate_scale_factors(
        self,
        joint_mapping: JointMapping,
    ) -> Dict[str, float]:
        """
        Calculate scale factors for different body parts.

        Compares distances between joints in source vs canonical.
        """
        factors: Dict[str, float] = {}

        target = joint_mapping.target_positions

        # Shoulder width scale
        if "clavicle_l" in target and "clavicle_r" in target:
            source_width = (target["clavicle_l"].position - target["clavicle_r"].position).length
            # Would compare to canonical width here
            # For now, use placeholder
            factors["shoulder_width"] = 1.0

        # Spine height scale
        if "pelvis" in target and "spine_01" in target:
            spine_height = (target["pelvis"].position - target["spine_01"].position).length
            factors["spine_height"] = 1.0

        # Leg length scale
        if "thigh_l" in target and "calf_l" in target and "foot_l" in target:
            leg_length = 0.0
            leg_length += (target["thigh_l"].position - target["calf_l"].position).length
            leg_length += (target["calf_l"].position - target["foot_l"].position).length
            factors["leg_length"] = 1.0

        return factors

    def _scale_spine_chain(
        self,
        edit_bones,
        scale_factors: Dict[str, float],
        original_positions: Dict[str, Vector],
    ) -> None:
        """Scale spine bone chain proportionally."""
        spine_bones = ["spine_01", "spine_02", "spine_03", "spine_04", "spine_05"]

        scale = scale_factors.get("spine_height", 1.0)

        for bone_name in spine_bones:
            if bone_name in edit_bones:
                bone = edit_bones[bone_name]
                original_positions[bone_name] = bone.head.copy()
                # Apply scaling logic here

    def _scale_arm_chains(
        self,
        edit_bones,
        scale_factors: Dict[str, float],
        original_positions: Dict[str, Vector],
    ) -> None:
        """Scale arm bone chains proportionally."""
        # Left arm
        arm_bones_l = ["clavicle_l", "upperarm_l", "lowerarm_l", "hand_l"]
        # Right arm
        arm_bones_r = ["clavicle_r", "upperarm_r", "lowerarm_r", "hand_r"]

        for bone_name in arm_bones_l + arm_bones_r:
            if bone_name in edit_bones:
                bone = edit_bones[bone_name]
                original_positions[bone_name] = bone.head.copy()
                # Apply scaling logic here

    def _scale_leg_chains(
        self,
        edit_bones,
        scale_factors: Dict[str, float],
        original_positions: Dict[str, Vector],
    ) -> None:
        """Scale leg bone chains proportionally."""
        leg_bones_l = ["thigh_l", "calf_l", "foot_l", "ball_l"]
        leg_bones_r = ["thigh_r", "calf_r", "foot_r", "ball_r"]

        scale = scale_factors.get("leg_length", 1.0)

        for bone_name in leg_bones_l + leg_bones_r:
            if bone_name in edit_bones:
                bone = edit_bones[bone_name]
                original_positions[bone_name] = bone.head.copy()
                # Apply scaling logic here

    def validate_adjustment(
        self,
        canonical_armature: "bpy.types.Object",
        joint_mapping: JointMapping,
        tolerance: float = 0.01,
    ) -> tuple[bool, list[str]]:
        """
        Validate that bones were adjusted correctly.

        Args:
            canonical_armature: Adjusted canonical armature
            joint_mapping: Expected joint positions
            tolerance: Maximum allowed position error (in Blender units)

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors: list[str] = []
        is_valid = True

        for canonical_name, expected_pos in joint_mapping.target_positions.items():
            if canonical_name not in canonical_armature.data.bones:
                continue

            bone = canonical_armature.data.bones[canonical_name]
            actual_pos = canonical_armature.matrix_world @ bone.head_local

            distance = (actual_pos - expected_pos.position).length

            if distance > tolerance:
                is_valid = False
                errors.append(
                    f"Bone {canonical_name} position error: {distance:.4f} "
                    f"(tolerance: {tolerance})"
                )

        return is_valid, errors
