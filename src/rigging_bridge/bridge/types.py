"""
Data models and types for the Rig Interop Bridge.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

try:
    import bpy
    from mathutils import Vector
    BLENDER_AVAILABLE = True
except ImportError:
    # Allow imports outside of Blender context for type checking
    BLENDER_AVAILABLE = False
    Vector = tuple  # type: ignore


class RigType(str, Enum):
    """Supported rig types."""

    ARP = "arp"
    CC3 = "cc3"
    CC4 = "cc4"
    MIXAMO = "mixamo"
    VRM = "vrm"
    METAHUMAN = "metahuman"
    UE5_MANNEQUIN = "ue5_mannequin"
    UNKNOWN = "unknown"


class RestPose(str, Enum):
    """Supported rest poses."""

    T_POSE = "t_pose"
    A_POSE = "a_pose"
    CUSTOM = "custom"


@dataclass
class JointPosition:
    """3D position and metadata for a single joint."""

    name: str
    position: Vector
    parent: Optional[str] = None
    children: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "position": tuple(self.position),
            "parent": self.parent,
            "children": self.children,
        }


@dataclass
class RigMetadata:
    """Metadata about a detected rig."""

    rig_type: RigType
    rest_pose: RestPose
    bone_count: int
    confidence: float  # 0.0 - 1.0
    detected_bones: List[str] = field(default_factory=list)
    extra_metadata: Dict[str, any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "rig_type": self.rig_type.value,
            "rest_pose": self.rest_pose.value,
            "bone_count": self.bone_count,
            "confidence": self.confidence,
            "detected_bones": self.detected_bones,
            "extra_metadata": self.extra_metadata,
        }


@dataclass
class JointMapping:
    """Mapping between source and target joint positions."""

    source_positions: Dict[str, JointPosition]
    target_positions: Dict[str, JointPosition]
    unmapped_source: List[str] = field(default_factory=list)
    unmapped_target: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "source_positions": {k: v.to_dict() for k, v in self.source_positions.items()},
            "target_positions": {k: v.to_dict() for k, v in self.target_positions.items()},
            "unmapped_source": self.unmapped_source,
            "unmapped_target": self.unmapped_target,
        }


@dataclass
class ConversionResult:
    """Result of a rig conversion operation."""

    success: bool
    output_path: Optional[str] = None
    rig_metadata: Optional[RigMetadata] = None
    joint_mapping: Optional[JointMapping] = None
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "output_path": self.output_path,
            "rig_metadata": self.rig_metadata.to_dict() if self.rig_metadata else None,
            "joint_mapping": self.joint_mapping.to_dict() if self.joint_mapping else None,
            "warnings": self.warnings,
            "errors": self.errors,
        }


@dataclass
class ConversionOptions:
    """Configuration options for rig conversion."""

    target_rig_type: RigType = RigType.UE5_MANNEQUIN
    target_rest_pose: RestPose = RestPose.T_POSE
    preserve_proportions: bool = True
    include_extra_bones: bool = False
    remove_fingers: bool = False
    export_textures: bool = True
    validate_weights: bool = True
    falloff_exponent: float = 20.0  # For weight redistribution

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "target_rig_type": self.target_rig_type.value,
            "target_rest_pose": self.target_rest_pose.value,
            "preserve_proportions": self.preserve_proportions,
            "include_extra_bones": self.include_extra_bones,
            "remove_fingers": self.remove_fingers,
            "export_textures": self.export_textures,
            "validate_weights": self.validate_weights,
            "falloff_exponent": self.falloff_exponent,
        }
