"""
Rig Detection Module

Automatically identifies the type of rig (ARP, CC3/4, Mixamo, VRM, etc.)
based on bone naming conventions, hierarchy patterns, and bone counts.
"""

from typing import Dict, List, Optional, Set

try:
    import bpy
    BLENDER_AVAILABLE = True
except ImportError:
    BLENDER_AVAILABLE = False
    bpy = None  # type: ignore

from rigging_bridge.bridge.types import RigType, RigMetadata, RestPose


class RigDetector:
    """
    Detects rig type from armature bone naming and structure.

    Detection is performed using pattern matching on bone names and
    hierarchy analysis. Returns a confidence score for each detection.
    """

    # Bone name patterns for each rig type
    RIG_SIGNATURES: Dict[RigType, Dict[str, any]] = {
        RigType.ARP: {
            "required_bones": ["root.x", "spine_01.x", "spine_02.x", "spine_03.x"],
            "pattern_bones": ["c_traj", "arm_stretch", "forearm_stretch", "thigh_stretch"],
            "min_confidence": 0.7,
        },
        RigType.CC3: {
            "required_bones": ["CC_Base_Hip", "CC_Base_Spine01"],
            "pattern_bones": ["CC_Base_L_Upperarm", "CC_Base_R_Upperarm"],
            "min_confidence": 0.8,
        },
        RigType.CC4: {
            "required_bones": ["CC_Base_Hips", "CC_Base_Spine01"],
            "pattern_bones": ["CC_Base_L_Upperarm", "CC_Base_R_Upperarm"],
            "min_confidence": 0.8,
        },
        RigType.MIXAMO: {
            "required_bones": ["Hips", "Spine"],
            "pattern_bones": ["LeftUpLeg", "RightUpLeg", "LeftArm", "RightArm"],
            "min_confidence": 0.6,
        },
        RigType.VRM: {
            "required_bones": ["J_Bip_C_Hips"],
            "pattern_bones": ["J_Bip_L_UpperArm", "J_Bip_R_UpperArm"],
            "min_confidence": 0.7,
        },
        RigType.METAHUMAN: {
            "required_bones": ["pelvis", "spine_01", "spine_02"],
            "pattern_bones": ["FACIAL_C_FacialRoot", "neck_01", "head"],
            "min_confidence": 0.8,
        },
        RigType.UE5_MANNEQUIN: {
            "required_bones": ["pelvis", "spine_01", "clavicle_l", "clavicle_r"],
            "pattern_bones": ["thigh_l", "thigh_r", "upperarm_l", "upperarm_r"],
            "min_confidence": 0.8,
        },
    }

    def __init__(self):
        """Initialize the rig detector."""
        pass

    def detect(self, armature: "bpy.types.Object") -> RigMetadata:
        """
        Detect the rig type of the given armature.

        Args:
            armature: Blender armature object

        Returns:
            RigMetadata with detected type and confidence score
        """
        if not BLENDER_AVAILABLE or bpy is None:
            raise RuntimeError("Blender API is not available")

        if armature.type != "ARMATURE":
            raise ValueError(f"Object {armature.name} is not an armature")

        bone_names = self._get_bone_names(armature)
        bone_count = len(bone_names)

        # Try to detect each rig type
        detections: List[tuple[RigType, float]] = []

        for rig_type, signature in self.RIG_SIGNATURES.items():
            confidence = self._calculate_confidence(bone_names, signature)
            if confidence >= signature["min_confidence"]:
                detections.append((rig_type, confidence))

        # Sort by confidence descending
        detections.sort(key=lambda x: x[1], reverse=True)

        if detections:
            rig_type, confidence = detections[0]
            rest_pose = self._detect_rest_pose(armature, rig_type)
        else:
            rig_type = RigType.UNKNOWN
            confidence = 0.0
            rest_pose = RestPose.CUSTOM

        return RigMetadata(
            rig_type=rig_type,
            rest_pose=rest_pose,
            bone_count=bone_count,
            confidence=confidence,
            detected_bones=list(bone_names),
        )

    def _get_bone_names(self, armature: "bpy.types.Object") -> Set[str]:
        """Extract all bone names from the armature."""
        return {bone.name for bone in armature.data.bones}

    def _calculate_confidence(
        self,
        bone_names: Set[str],
        signature: Dict[str, any],
    ) -> float:
        """
        Calculate confidence score for a rig signature.

        Confidence is based on:
        - Required bones present (must have all)
        - Pattern bones present (bonus points)
        """
        required = signature["required_bones"]
        patterns = signature.get("pattern_bones", [])

        # Check required bones
        required_found = sum(1 for bone in required if bone in bone_names)
        if required_found < len(required):
            return 0.0  # Missing required bones = no match

        # Check pattern bones
        pattern_found = sum(1 for bone in patterns if bone in bone_names)
        pattern_score = pattern_found / len(patterns) if patterns else 0.0

        # Base confidence from required bones (0.6) + pattern bonus (0.4)
        confidence = 0.6 + (0.4 * pattern_score)

        return confidence

    def _detect_rest_pose(
        self,
        armature: "bpy.types.Object",
        rig_type: RigType,
    ) -> RestPose:
        """
        Attempt to detect the rest pose of the armature.

        This is a simplified heuristic based on arm bone orientations.
        A more robust implementation would analyze actual bone angles.
        """
        # For now, use common conventions per rig type
        pose_defaults = {
            RigType.ARP: RestPose.A_POSE,
            RigType.CC3: RestPose.A_POSE,
            RigType.CC4: RestPose.A_POSE,
            RigType.MIXAMO: RestPose.T_POSE,
            RigType.VRM: RestPose.A_POSE,
            RigType.METAHUMAN: RestPose.A_POSE,
            RigType.UE5_MANNEQUIN: RestPose.T_POSE,
        }

        return pose_defaults.get(rig_type, RestPose.CUSTOM)

    def detect_from_bone_list(self, bone_names: List[str]) -> RigMetadata:
        """
        Detect rig type from a list of bone names (without Blender context).

        Useful for testing and validation.

        Args:
            bone_names: List of bone name strings

        Returns:
            RigMetadata with detected type and confidence
        """
        bone_set = set(bone_names)
        bone_count = len(bone_names)

        detections: List[tuple[RigType, float]] = []

        for rig_type, signature in self.RIG_SIGNATURES.items():
            confidence = self._calculate_confidence(bone_set, signature)
            if confidence >= signature["min_confidence"]:
                detections.append((rig_type, confidence))

        detections.sort(key=lambda x: x[1], reverse=True)

        if detections:
            rig_type, confidence = detections[0]
        else:
            rig_type = RigType.UNKNOWN
            confidence = 0.0

        return RigMetadata(
            rig_type=rig_type,
            rest_pose=RestPose.CUSTOM,
            bone_count=bone_count,
            confidence=confidence,
            detected_bones=bone_names,
        )
