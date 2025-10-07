import argparse
import sys
from pathlib import Path

# Add the source directory to Python path for local development
script_path = Path(__file__).resolve()
src_path = script_path.parents[2]  # Go up from blender/ -> rigging_bridge/ -> src/
if src_path not in [Path(p) for p in sys.path]:
    sys.path.insert(0, str(src_path))

import bpy
from importlib import resources

from rigging_bridge.blender import arp_to_ue5_glb_converter as converter


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ARP to UE5 GLB converter")
    parser.add_argument("--input", dest="input_path", required=True, help="Source asset path")
    parser.add_argument(
        "--output-dir",
        dest="output_dir",
        required=True,
        help="Directory where converted assets will be written",
    )
    parser.add_argument("--collection", default="", help="Optional collection hint for the converter")
    parser.add_argument("--include-extra-bones", action="store_true")
    parser.add_argument("--skip-t-pose", action="store_true")
    parser.add_argument("--skip-textures", action="store_true")
    parser.add_argument("--keep-fingers", action="store_true")
    return parser.parse_args(argv)


def _append_ue5_armature() -> None:
    if "root" in bpy.data.objects:
        return

    resource = resources.files("rigging_bridge.blender") / "UE5_Armature.blend"
    with resources.as_file(resource) as blend_path:
        if not blend_path.exists():
            raise FileNotFoundError(f"UE5 armature asset missing: {blend_path}")

        with bpy.data.libraries.load(str(blend_path), link=False) as (data_from, data_to):
            if "root" not in data_from.objects:
                raise RuntimeError("UE5 armature file does not contain an object named 'root'")
            data_to.objects = ["root"]

        for obj in data_to.objects:
            if obj is None:
                continue
            bpy.context.scene.collection.objects.link(obj)
            obj.hide_viewport = False
            obj.hide_set(False)


def _import_source_asset(path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif suffix == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path))
    elif suffix == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(path))
    else:
        raise ValueError(f"Unsupported input type: {path.suffix}")


def _find_source_armature() -> bpy.types.Object:
    for obj in bpy.data.objects:
        if obj.type == "ARMATURE" and obj.name != "root":
            return obj
    raise RuntimeError("Unable to locate source armature in scene")


def main(argv: list[str]) -> None:
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    args = _parse_args(argv)

    input_path = Path(args.input_path)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    _import_source_asset(input_path)

    _append_ue5_armature()

    armature = _find_source_armature()
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.select_all(action="DESELECT")
    armature.select_set(True)

    session_file = output_dir / "session.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(session_file))

    converter.convert_rig(
        armature_source=armature,
        inc_extra_bones=args.include_extra_bones,
        t_pose=not args.skip_t_pose,
        export_textures=not args.skip_textures,
        remove_fingers=not args.keep_fingers,
        collection=args.collection,
    )


if __name__ == "__main__":  # pragma: no cover - Blender entrypoint
    main(sys.argv)
