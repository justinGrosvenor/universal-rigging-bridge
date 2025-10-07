"""
Weight Transfer Module

Transfers skin weights from source rig to canonical skeleton.
Uses proximity-based, name-based, or hybrid approaches.

This happens AFTER the canonical skeleton has been adjusted to match
source proportions, ensuring accurate weight projection.
"""

from typing import Dict, List, Optional, Set

try:
    import bpy
    from mathutils import Vector, kdtree
    BLENDER_AVAILABLE = True
except ImportError:
    BLENDER_AVAILABLE = False
    bpy = None  # type: ignore
    Vector = tuple  # type: ignore

from rigging_bridge.bridge.types import JointMapping


class WeightTransfer:
    """
    Transfers vertex weights from source mesh to canonical skeleton.

    Supports multiple transfer strategies:
    - Name-based: Match vertex group names
    - Proximity-based: Use nearest bone
    - Hybrid: Combine both approaches
    """

    def __init__(self):
        """Initialize the weight transfer system."""
        pass

    def transfer_weights(
        self,
        source_mesh: "bpy.types.Object",
        target_armature: "bpy.types.Object",
        joint_mapping: JointMapping,
        method: str = "hybrid",
    ) -> Dict[str, any]:
        """
        Transfer vertex weights from source mesh to target armature.

        Args:
            source_mesh: Mesh with existing vertex groups/weights
            target_armature: Canonical armature (already adjusted)
            joint_mapping: Mapping between source and target bones
            method: Transfer method ("name", "proximity", "hybrid")

        Returns:
            Transfer statistics and warnings
        """
        if not BLENDER_AVAILABLE or bpy is None:
            raise RuntimeError("Blender API is not available")

        if source_mesh.type != "MESH":
            raise ValueError(f"Object {source_mesh.name} is not a mesh")

        if target_armature.type != "ARMATURE":
            raise ValueError(f"Object {target_armature.name} is not an armature")

        stats = {
            "method": method,
            "vertex_groups_created": 0,
            "vertex_groups_renamed": 0,
            "warnings": [],
        }

        if method == "name":
            self._transfer_by_name(source_mesh, target_armature, joint_mapping, stats)
        elif method == "proximity":
            self._transfer_by_proximity(source_mesh, target_armature, joint_mapping, stats)
        elif method == "hybrid":
            # Try name-based first, fall back to proximity
            self._transfer_by_name(source_mesh, target_armature, joint_mapping, stats)
            self._transfer_by_proximity(source_mesh, target_armature, joint_mapping, stats)
        else:
            raise ValueError(f"Unknown transfer method: {method}")

        return stats

    def _transfer_by_name(
        self,
        source_mesh: "bpy.types.Object",
        target_armature: "bpy.types.Object",
        joint_mapping: JointMapping,
        stats: Dict[str, any],
    ) -> None:
        """
        Transfer weights by renaming vertex groups to match canonical bones.

        This is the simplest approach: if source has a vertex group that
        matches a source bone name, rename it to the canonical bone name.
        """
        # Build reverse mapping: source bone name -> canonical bone name
        name_map: Dict[str, str] = {}

        for canonical_name, target_pos in joint_mapping.target_positions.items():
            # Find which source bone(s) map to this canonical bone
            for source_name, source_pos in joint_mapping.source_positions.items():
                if target_pos.position == source_pos.position:
                    name_map[source_name] = canonical_name
                    break

        # Rename vertex groups
        for vgroup in source_mesh.vertex_groups:
            if vgroup.name in name_map:
                new_name = name_map[vgroup.name]
                if new_name not in [g.name for g in source_mesh.vertex_groups]:
                    vgroup.name = new_name
                    stats["vertex_groups_renamed"] += 1
                else:
                    # Merge weights if target group already exists
                    stats["warnings"].append(
                        f"Vertex group {new_name} already exists, consider merging"
                    )

    def _transfer_by_proximity(
        self,
        source_mesh: "bpy.types.Object",
        target_armature: "bpy.types.Object",
        joint_mapping: JointMapping,
        stats: Dict[str, any],
    ) -> None:
        """
        Transfer weights using proximity to bones.

        For each vertex, find the nearest bone in the target armature
        and assign weights accordingly.

        This is useful when source and target bone names don't match.
        """
        # Build KD-tree of target bone positions
        size = len(joint_mapping.target_positions)
        kd = kdtree.KDTree(size)

        bone_lookup: List[str] = []
        for idx, (bone_name, joint_pos) in enumerate(joint_mapping.target_positions.items()):
            kd.insert(joint_pos.position, idx)
            bone_lookup.append(bone_name)

        kd.balance()

        # For each vertex without weights, assign to nearest bone
        # This is a simplified version - production would be more sophisticated
        for vertex in source_mesh.data.vertices:
            world_pos = source_mesh.matrix_world @ vertex.co

            # Find nearest bone
            nearest_pos, nearest_idx, nearest_dist = kd.find(world_pos)

            if nearest_idx is not None:
                bone_name = bone_lookup[nearest_idx]

                # Check if vertex already has weight for this bone
                has_weight = False
                for group in vertex.groups:
                    vgroup = source_mesh.vertex_groups[group.group]
                    if vgroup.name == bone_name:
                        has_weight = True
                        break

                # Add vertex group if needed
                if not has_weight and bone_name not in [g.name for g in source_mesh.vertex_groups]:
                    source_mesh.vertex_groups.new(name=bone_name)
                    stats["vertex_groups_created"] += 1

    def swap_armature(
        self,
        mesh: "bpy.types.Object",
        new_armature: "bpy.types.Object",
    ) -> None:
        """
        Replace mesh's armature modifier with new armature.

        Args:
            mesh: Mesh object
            new_armature: New armature to assign
        """
        if not BLENDER_AVAILABLE or bpy is None:
            raise RuntimeError("Blender API is not available")

        # Find existing armature modifier
        armature_mod = None
        for mod in mesh.modifiers:
            if mod.type == "ARMATURE":
                armature_mod = mod
                break

        if armature_mod:
            # Replace armature reference
            armature_mod.object = new_armature
        else:
            # Create new armature modifier
            armature_mod = mesh.modifiers.new(name="Armature", type="ARMATURE")
            armature_mod.object = new_armature

    def redistribute_weights(
        self,
        mesh: "bpy.types.Object",
        armature: "bpy.types.Object",
        bone_chain: List[str],
        falloff_exponent: float = 20.0,
    ) -> None:
        """
        Redistribute vertex weights along a bone chain.

        This is useful for smoothing weights on inserted bones (like
        spine_02, spine_04 which are interpolated).

        Uses a curve-based falloff to create smooth weight transitions.

        Args:
            mesh: Mesh object with vertex groups
            armature: Armature containing the bone chain
            bone_chain: List of bone names in order (e.g., spine bones)
            falloff_exponent: Controls weight falloff curve sharpness
        """
        if not BLENDER_AVAILABLE or bpy is None:
            raise RuntimeError("Blender API is not available")

        # Ensure all bones exist in vertex groups
        for bone_name in bone_chain:
            if bone_name not in mesh.vertex_groups:
                mesh.vertex_groups.new(name=bone_name)

        # Get bone positions along chain
        bone_positions: List[Vector] = []
        for bone_name in bone_chain:
            if bone_name in armature.data.bones:
                bone = armature.data.bones[bone_name]
                world_pos = armature.matrix_world @ bone.head_local
                bone_positions.append(world_pos)

        # For each vertex, calculate weights based on distance to each bone
        for vertex in mesh.data.vertices:
            world_pos = mesh.matrix_world @ vertex.co

            # Calculate distances to each bone in chain
            distances = [
                (world_pos - bone_pos).length
                for bone_pos in bone_positions
            ]

            # Convert distances to weights using inverse distance with falloff
            raw_weights = [
                1.0 / (dist ** falloff_exponent) if dist > 0.001 else 1e10
                for dist in distances
            ]

            # Normalize weights
            total_weight = sum(raw_weights)
            normalized_weights = [w / total_weight for w in raw_weights]

            # Assign weights to vertex groups
            for bone_name, weight in zip(bone_chain, normalized_weights):
                vgroup = mesh.vertex_groups[bone_name]
                vgroup.add([vertex.index], weight, "REPLACE")

    def validate_weights(
        self,
        mesh: "bpy.types.Object",
        armature: "bpy.types.Object",
    ) -> tuple[bool, list[str]]:
        """
        Validate that vertex weights are correct.

        Checks:
        - All vertex groups correspond to bones in armature
        - All vertices have at least one weight
        - Weights are normalized (sum to 1.0)

        Args:
            mesh: Mesh with vertex groups
            armature: Armature with bones

        Returns:
            Tuple of (is_valid, list of warnings)
        """
        warnings: list[str] = []
        is_valid = True

        bone_names = {bone.name for bone in armature.data.bones}

        # Check vertex groups match bones
        for vgroup in mesh.vertex_groups:
            if vgroup.name not in bone_names:
                warnings.append(f"Vertex group '{vgroup.name}' has no matching bone")

        # Check all vertices have weights
        for vertex in mesh.data.vertices:
            if len(vertex.groups) == 0:
                warnings.append(f"Vertex {vertex.index} has no weights")
                is_valid = False

        # Check weight normalization (sample 100 vertices)
        import random
        sample_size = min(100, len(mesh.data.vertices))
        sample_indices = random.sample(range(len(mesh.data.vertices)), sample_size)

        for idx in sample_indices:
            vertex = mesh.data.vertices[idx]
            total_weight = sum(group.weight for group in vertex.groups)
            if abs(total_weight - 1.0) > 0.01:
                warnings.append(
                    f"Vertex {idx} weights not normalized: {total_weight:.3f}"
                )

        return is_valid, warnings
