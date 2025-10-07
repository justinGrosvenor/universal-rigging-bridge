"""
Joint Matcher Module

Captures joint positions from source rig and creates mappings to the
canonical skeleton. This is critical for preserving character proportions
during rig replacement.
"""

from typing import Dict, List, Optional

try:
    import bpy
    from mathutils import Vector
    BLENDER_AVAILABLE = True
except ImportError:
    BLENDER_AVAILABLE = False
    bpy = None  # type: ignore
    Vector = tuple  # type: ignore

from rigging_bridge.bridge.types import (
    JointPosition,
    JointMapping,
    RigType,
)


class JointMatcher:
    """
    Extracts joint positions from source rig and maps them to canonical skeleton.

    Key operations:
    1. Capture world-space positions of all joints in source rig
    2. Identify key anatomical landmarks (shoulders, hips, spine, etc.)
    3. Create mapping between source and target bone names
    4. Calculate joint spacing metrics (shoulder width, leg length, etc.)
    """

    # Mapping from source rig bones to canonical UE5 Mannequin bones
    # Format: {canonical_bone: [source_bone_patterns]}
    BONE_MAPPINGS: Dict[RigType, Dict[str, List[str]]] = {
        RigType.ARP: {
            "pelvis": ["root.x"],
            "spine_01": ["spine_01.x"],
            "spine_02": ["spine_02.x"],
            "spine_03": ["spine_03.x"],
            "clavicle_l": ["shoulder.l"],
            "clavicle_r": ["shoulder.r"],
            "upperarm_l": ["arm_stretch.l"],
            "upperarm_r": ["arm_stretch.r"],
            "lowerarm_l": ["forearm_stretch.l"],
            "lowerarm_r": ["forearm_stretch.r"],
            "hand_l": ["hand.l"],
            "hand_r": ["hand.r"],
            "thigh_l": ["thigh_stretch.l"],
            "thigh_r": ["thigh_stretch.r"],
            "calf_l": ["leg_stretch.l"],
            "calf_r": ["leg_stretch.r"],
            "foot_l": ["foot.l"],
            "foot_r": ["foot.r"],
            "neck_01": ["neck.x"],
            "head": ["head.x"],
        },
        RigType.CC3: {
            "pelvis": ["CC_Base_Hip", "CC_Base_Hips"],
            "spine_01": ["CC_Base_Spine01"],
            "spine_02": ["CC_Base_Spine02"],
            "upperarm_l": ["CC_Base_L_Upperarm"],
            "upperarm_r": ["CC_Base_R_Upperarm"],
            "lowerarm_l": ["CC_Base_L_Forearm"],
            "lowerarm_r": ["CC_Base_R_Forearm"],
            "hand_l": ["CC_Base_L_Hand"],
            "hand_r": ["CC_Base_R_Hand"],
            "thigh_l": ["CC_Base_L_Thigh"],
            "thigh_r": ["CC_Base_R_Thigh"],
            "calf_l": ["CC_Base_L_Calf"],
            "calf_r": ["CC_Base_R_Calf"],
            "foot_l": ["CC_Base_L_Foot"],
            "foot_r": ["CC_Base_R_Foot"],
            "neck_01": ["CC_Base_NeckTwist01"],
            "head": ["CC_Base_Head"],
        },
        RigType.CC4: {
            # CC4 uses similar naming to CC3
            "pelvis": ["CC_Base_Hips"],
            "spine_01": ["CC_Base_Spine01"],
            "upperarm_l": ["CC_Base_L_Upperarm"],
            "upperarm_r": ["CC_Base_R_Upperarm"],
            # ... (full mapping would continue)
        },
        RigType.MIXAMO: {
            "pelvis": ["Hips"],
            "spine_01": ["Spine"],
            "spine_02": ["Spine1"],
            "spine_03": ["Spine2"],
            "upperarm_l": ["LeftArm"],
            "upperarm_r": ["RightArm"],
            "lowerarm_l": ["LeftForeArm"],
            "lowerarm_r": ["RightForeArm"],
            "hand_l": ["LeftHand"],
            "hand_r": ["RightHand"],
            "thigh_l": ["LeftUpLeg"],
            "thigh_r": ["RightUpLeg"],
            "calf_l": ["LeftLeg"],
            "calf_r": ["RightLeg"],
            "foot_l": ["LeftFoot"],
            "foot_r": ["RightFoot"],
            "neck_01": ["Neck"],
            "head": ["Head"],
        },
    }

    def __init__(self):
        """Initialize the joint matcher."""
        pass

    def capture_positions(
        self,
        armature: "bpy.types.Object",
        rig_type: RigType,
    ) -> Dict[str, JointPosition]:
        """
        Capture world-space positions of all joints in the armature.

        Args:
            armature: Source armature object
            rig_type: Detected rig type

        Returns:
            Dictionary mapping bone names to JointPosition objects
        """
        if not BLENDER_AVAILABLE or bpy is None:
            raise RuntimeError("Blender API is not available")

        if armature.type != "ARMATURE":
            raise ValueError(f"Object {armature.name} is not an armature")

        positions: Dict[str, JointPosition] = {}

        for bone in armature.data.bones:
            # Get world space position
            world_pos = armature.matrix_world @ bone.head_local

            # Build hierarchy info
            parent_name = bone.parent.name if bone.parent else None
            child_names = [child.name for child in bone.children]

            positions[bone.name] = JointPosition(
                name=bone.name,
                position=world_pos.copy(),
                parent=parent_name,
                children=child_names,
            )

        return positions

    def create_mapping(
        self,
        source_positions: Dict[str, JointPosition],
        rig_type: RigType,
    ) -> JointMapping:
        """
        Create mapping from source rig to canonical UE5 Mannequin skeleton.

        Args:
            source_positions: Joint positions from source rig
            rig_type: Type of source rig

        Returns:
            JointMapping with matched and unmatched bones
        """
        if rig_type not in self.BONE_MAPPINGS:
            raise ValueError(f"No bone mapping defined for rig type: {rig_type}")

        mapping = self.BONE_MAPPINGS[rig_type]
        target_positions: Dict[str, JointPosition] = {}
        unmapped_source: List[str] = []
        unmapped_target: List[str] = []

        # Map canonical bones to source positions
        for canonical_bone, source_patterns in mapping.items():
            matched = False
            for pattern in source_patterns:
                if pattern in source_positions:
                    # Copy position but use canonical name
                    source_pos = source_positions[pattern]
                    target_positions[canonical_bone] = JointPosition(
                        name=canonical_bone,
                        position=source_pos.position,
                        parent=None,  # Will be set based on canonical hierarchy
                        children=[],
                    )
                    matched = True
                    break

            if not matched:
                unmapped_target.append(canonical_bone)

        # Find source bones not mapped to canonical
        mapped_source_bones = set()
        for patterns in mapping.values():
            mapped_source_bones.update(patterns)

        for source_bone in source_positions.keys():
            if source_bone not in mapped_source_bones:
                unmapped_source.append(source_bone)

        return JointMapping(
            source_positions=source_positions,
            target_positions=target_positions,
            unmapped_source=unmapped_source,
            unmapped_target=unmapped_target,
        )

    def calculate_metrics(
        self,
        positions: Dict[str, JointPosition],
    ) -> Dict[str, float]:
        """
        Calculate anatomical metrics from joint positions.

        Useful for validation and quality assurance.

        Metrics:
        - shoulder_width: Distance between shoulder joints
        - hip_width: Distance between hip/thigh joints
        - height: Distance from pelvis to head
        - arm_length: Total arm length (shoulder to hand)
        - leg_length: Total leg length (hip to foot)

        Args:
            positions: Joint positions

        Returns:
            Dictionary of metric names to values
        """
        metrics: Dict[str, float] = {}

        # Helper to calculate distance
        def distance(pos1: Vector, pos2: Vector) -> float:
            return (pos1 - pos2).length

        # Shoulder width
        if "clavicle_l" in positions and "clavicle_r" in positions:
            metrics["shoulder_width"] = distance(
                positions["clavicle_l"].position,
                positions["clavicle_r"].position,
            )

        # Hip width
        if "thigh_l" in positions and "thigh_r" in positions:
            metrics["hip_width"] = distance(
                positions["thigh_l"].position,
                positions["thigh_r"].position,
            )

        # Height (pelvis to head)
        if "pelvis" in positions and "head" in positions:
            metrics["height"] = distance(
                positions["pelvis"].position,
                positions["head"].position,
            )

        # Left arm length
        if all(k in positions for k in ["clavicle_l", "upperarm_l", "lowerarm_l", "hand_l"]):
            arm_length = 0.0
            arm_length += distance(
                positions["clavicle_l"].position,
                positions["upperarm_l"].position,
            )
            arm_length += distance(
                positions["upperarm_l"].position,
                positions["lowerarm_l"].position,
            )
            arm_length += distance(
                positions["lowerarm_l"].position,
                positions["hand_l"].position,
            )
            metrics["arm_length_l"] = arm_length

        # Left leg length
        if all(k in positions for k in ["thigh_l", "calf_l", "foot_l"]):
            leg_length = 0.0
            leg_length += distance(
                positions["pelvis"].position if "pelvis" in positions else positions["thigh_l"].position,
                positions["thigh_l"].position,
            )
            leg_length += distance(
                positions["thigh_l"].position,
                positions["calf_l"].position,
            )
            leg_length += distance(
                positions["calf_l"].position,
                positions["foot_l"].position,
            )
            metrics["leg_length_l"] = leg_length

        return metrics
