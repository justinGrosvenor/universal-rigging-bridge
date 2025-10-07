"""
Rig Interop Bridge

Core system for normalizing diverse character rigs to a canonical skeleton.
Supports ARP, CC3/4, Mixamo, VRM, and Metahuman source rigs.
"""

from rigging_bridge.bridge.orchestrator import RigInteropBridge
from rigging_bridge.bridge.types import RigType, ConversionResult

__all__ = [
    "RigInteropBridge",
    "RigType",
    "ConversionResult",
]
