# Universal Rigging Bridge

**Open-source character rig normalization pipeline for game engines.**

Converts diverse character rigs (Auto-Rig Pro, Character Creator 3/4, Mixamo, VRM, Metahuman) to a canonical **UE5 Mannequin Skeleton** while preserving per-character proportions and enabling cross-platform animation retargeting.

Built with Blender
Example infrastructure for deployment as a FastAPI microservice on AWS Fargate.

---

## 🎯 What This Does

Character rigs from different sources (ARP, CC3/4, Mixamo, VRM) have incompatible bone hierarchies, naming conventions, and rest poses. This makes animation reuse impossible without manual retargeting.

**Universal Rigging Bridge** solves this by:

1. **Auto-detecting** rig type from bone structure
2. **Capturing** joint positions from the source character
3. **Adjusting** a canonical skeleton to match the character's unique proportions (wide shoulders, long legs, etc.)
4. **Transferring** skin weights to the adjusted skeleton
5. **Resetting** to a standard rest pose (T-pose) for animation compatibility
6. **Exporting** a clean GLB + metadata for Unity/Unreal

### 🧠 The Key Innovation

Unlike traditional retargeting (which keeps the original rig and maps animation), **Universal Rigging Bridge replaces the rig entirely** while **preserving character proportions**:

```
❌ Naïve approach: Force all characters onto fixed UE5 skeleton
   → Result: Characters with wide shoulders get compressed
   → Animations look wrong

✅ Universal Rigging Bridge approach: Pose UE5 skeleton to match each character
   → Match shoulder width, leg length, spine height
   → Transfer weights while skeleton is posed
   → Reset to canonical pose
   → Result: Perfect deformation + shared animations
```



---

## 🏗️ Architecture

### Rig Interop Bridge

The core conversion pipeline is modular and extensible:

```
┌─────────────────────────────────────────────────────────────┐
│                    Rig Interop Bridge                        │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  1. RigDetector        → Auto-detect rig type (ARP, CC, etc) │
│  2. JointMatcher       → Capture joint positions             │
│  3. SkeletonAdjuster   → Pose canonical to match source      │
│  4. WeightTransfer     → Transfer skin weights               │
│  5. PoseReset          → Reset to canonical T-pose           │
│  6. Export             → GLB + scene_data.json               │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

Each module is:
- ✅ **Testable** - Isolated, unit-testable functions
- ✅ **Extensible** - Add new rig types via config
- ✅ **Reusable** - Use standalone or as part of pipeline

---

## 📦 Supported Rig Types

| Rig Type | Detection | Bone Mapping | Notes |
|----------|-----------|--------------|-------|
| **Auto-Rig Pro (ARP)** | ✅ Automatic | ✅ Complete | Detects deformation rig from UE/Unity export |
| **Character Creator 3/4** | ✅ Automatic | 🚧 In Progress | Critical for large-scale asset libraries |
| **Mixamo** | ✅ Automatic | 🚧 In Progress | Common for indie/prototype characters |
| **VRM** | ✅ Automatic | 🚧 In Progress | VTuber and avatar standard |
| **Metahuman** | ✅ Automatic | ✅ Complete | Reduces to UE5 Mannequin core |
| **UE5 Mannequin** | ✅ Automatic | — | Target skeleton (canonical output) |

### Adding New Rig Types

Two steps:
1. Add detection pattern to `bridge/rig_detector.py`
2. Add bone mapping to `bridge/joint_matcher.py`

See [`MIGRATION_GUIDE.md`](MIGRATION_GUIDE.md) for examples.

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Blender 4.4+ (for local development)
- Docker (optional, for containerized deployment)

### 1. Install

```bash
git clone https://github.com/justinGrosvenor/universal-rigging-bridge.git
cd universal-rigging-bridge

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -e .[dev]
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and set:
```bash
# Required: Path to Blender executable
BLENDER_EXECUTABLE=/Applications/Blender.app/Contents/MacOS/Blender

# Optional: For S3 integration
AWS_REGION=us-east-1
INPUT_BUCKET=my-input-bucket
OUTPUT_BUCKET=my-output-bucket
```

### 3. Run the API

```bash
uvicorn bridge.app:app --reload --host 0.0.0.0 --port 8000
```

Visit http://localhost:8000/docs for interactive API documentation.

### 4. Convert a Character

```bash
curl -X POST http://localhost:8000/v1/convert \
  -H "Content-Type: application/json" \
  -d '{
    "source_uri": "/path/to/character.glb",
    "output_uri": "./output",
    "t_pose": true,
    "remove_fingers": false,
    "export_textures": true
  }'
```

**Response:**
```json
{
  "status": "COMPLETED",
  "artifacts": [
    {
      "uri": "./output/UE5_character.glb",
      "content_type": "model/gltf-binary"
    }
  ]
}
```

---

## 🧪 Using the Bridge Directly (Blender Script)

For custom workflows, use the Rig Interop Bridge directly in Blender:

```python
import bpy
from pathlib import Path
from bridge.bridge import (
    RigInteropBridge,
    ConversionOptions,
    RigType,
    RestPose,
)

# Configure conversion
options = ConversionOptions(
    target_rig_type=RigType.UE5_MANNEQUIN,
    target_rest_pose=RestPose.T_POSE,
    preserve_proportions=True,  # ← Critical for fidelity
    remove_fingers=False,
    export_textures=True,
)

# Initialize bridge
bridge = RigInteropBridge(options)

# Convert
result = bridge.convert(
    source_armature=bpy.data.objects["armature"],
    source_mesh=bpy.data.objects["Body"],
    canonical_armature=bpy.data.objects["root"],  # UE5 Mannequin
    output_path=Path("output/character.glb"),
)

# Export metadata
bridge.export_metadata(result, Path("output/scene_data.json"))

# Check results
print(f"Success: {result.success}")
print(f"Detected rig: {result.rig_metadata.rig_type}")
print(f"Confidence: {result.rig_metadata.confidence:.2%}")
print(f"Warnings: {result.warnings}")
```

**Output (`scene_data.json`):**
```json
{
  "success": true,
  "rig_metadata": {
    "rig_type": "cc4",
    "rest_pose": "a_pose",
    "bone_count": 94,
    "confidence": 0.92
  },
  "joint_mapping": {
    "target_positions": { ... },
    "unmapped_source": ["CC_Base_FacialBone", ...],
    "unmapped_target": []
  },
  "warnings": [
    "2 source bones not mapped to canonical skeleton"
  ]
}
```

---

## 🐳 Docker Deployment

### Build Image

```bash
docker build -t rig-transformer:latest .
```

### Run Locally

```bash
docker compose up
```

API available at http://localhost:8000

### Push to ECR (for AWS deployment)

```bash
# Authenticate
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin <ecr-repo-url>

# Tag and push
docker tag rig-transformer:latest <ecr-repo-url>:latest
docker push <ecr-repo-url>:latest
```

---

## ☁️ AWS Deployment (Terraform)

Deploy to **ECS Fargate** with load balancer, S3 storage, and CloudWatch logging.

### Prerequisites

- Terraform 1.5+
- AWS credentials with VPC/ECS/IAM/S3 permissions

### Deploy

```bash
cd terraform
terraform init

export TF_VAR_project_name=rig-transformer
export TF_VAR_aws_region=us-east-1

terraform plan
terraform apply
```

### Automated Deployment Script

```bash
AWS_REGION=us-east-1 IMAGE_TAG=v1.0.0 scripts/deploy.sh
```

**Outputs:**
- ALB DNS name (API endpoint)
- S3 artifact bucket
- ECR repository URL

See [`terraform/README.md`](terraform/README.md) for details.

---

## 🧩 API Reference

### `POST /v1/convert`

Convert a rigged character to UE5 Mannequin skeleton.

**Request:**
```json
{
  "source_uri": "s3://bucket/character.glb",  // or local path
  "output_uri": "s3://bucket/output/",        // or local path
  "collection": "",                            // optional rig hint
  "include_extra_bones": false,
  "t_pose": true,
  "export_textures": true,
  "remove_fingers": false
}
```

**Response:**
```json
{
  "status": "COMPLETED",
  "artifacts": [
    {
      "uri": "s3://bucket/output/UE5_character.glb",
      "content_type": "model/gltf-binary"
    }
  ],
  "logs": ["Step 1: Detecting rig type...", "..."]
}
```

### `GET /v1/health`

Health check endpoint.

**Response:**
```json
{
  "status": "ok"
}
```

---

## 📖 Documentation

- **[MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)** - Upgrading from proprietary ARP converter
- **[EXTRACTION_SUMMARY.md](EXTRACTION_SUMMARY.md)** - What was extracted and why
- **[info.txt](info.txt)** - Original vision and technical deep-dive

### Core Modules

- `bridge/rig_detector.py` - Automatic rig type detection
- `bridge/joint_matcher.py` - Joint position capture and mapping
- `bridge/skeleton_adjuster.py` - Per-character skeleton adjustment
- `bridge/weight_transfer.py` - Skin weight transfer
- `bridge/pose_reset.py` - Rest pose normalization
- `bridge/pose_deformation.py` - T-pose conversion with shape key preservation
- `bridge/utils.py` - Reusable Blender utilities

---

## 🧬 Technical Details

### Why Use the UE5 Mannequin Skeleton?

The UE5 Mannequin skeleton is the canonical target because:

1. **Native to Unreal Engine 5** - Full IK Retargeter support
2. **Unity-compatible** - Maps cleanly to Unity Humanoid Avatar
3. **Minimal hierarchy** - ~80 bones, no control rig clutter
4. **Forward-compatible with Metahuman** - Metahuman is a superset
5. **Retargeting-optimized** - Designed for animation reuse
6. **Extensible** - Can add facial, cloth, twist bones without breaking base

### Per-Character Joint Adjustment

**The critical innovation:**

Instead of forcing all characters onto a fixed skeleton (which causes compression/stretching), we:

1. Measure the source character's joint spacing (shoulder width, leg length, etc.)
2. **Pose the canonical skeleton to match those proportions**
3. Transfer weights while the skeleton is posed
4. Reset to canonical rest pose

This ensures:
- ✅ Visual fidelity (character looks correct)
- ✅ Animation compatibility (shares canonical skeleton)
- ✅ No distortion (proportions preserved)

Example:
```
Character A: Shoulder width = 0.6m
Character B: Shoulder width = 0.4m

Without adjustment:
  → Both get 0.5m UE5 shoulders
  → Character A compressed, B stretched
  → Animations look wrong

With adjustment:
  → UE5 skeleton adjusted to 0.6m for A, 0.4m for B during weight transfer
  → Reset to canonical 0.5m after transfer
  → Weights compensate for the difference
  → Animations look correct on both
```

See [info.txt](info.txt) lines 963-1010 for the mathematical explanation.

---

## 🤝 Contributing

This is an open-source project. Contributions welcome!

### Areas for Contribution

1. **Complete bone mappings** - CC3/4, Mixamo, VRM bone mappings
2. **Add rig types** - Support for more character systems
3. **Improve detection** - Better confidence scoring algorithms
4. **Add tests** - Unit tests for each module
5. **Documentation** - Tutorials, examples, diagrams

### Development Setup

```bash
# Install dev dependencies
pip install -e .[dev]

# Run tests
pytest

# Lint
ruff check .

# Format
ruff format .
```

---

## 📜 License

MIT License - See [LICENSE](LICENSE) file.

---

## 🚦 Project Status

- ✅ **Core architecture** - Complete and tested
- ✅ **ARP support** - Full bone mapping and conversion
- ✅ **Metahuman support** - Reduction to core skeleton
- 🚧 **CC3/4 support** - Bone mapping in progress (critical for scale)
- 🚧 **Mixamo support** - Bone mapping in progress
- 🚧 **VRM support** - Bone mapping in progress
- ✅ **API microservice** - Production-ready
- ✅ **AWS deployment** - Terraform IaC complete
- 🚧 **Test coverage** - In progress
- 🚧 **Documentation** - In progress

---

## 📞 Contact

Questions? Issues? Contributions?

- **Issues**: https://github.com/your-org/rig-transformer/issues
- **Discussions**: https://github.com/your-org/rig-transformer/discussions

---

## 🔮 Roadmap

### v1.0 (Current)
- [x] Rig Interop Bridge architecture
- [x] ARP and Metahuman support
- [x] FastAPI microservice
- [x] AWS deployment infrastructure
- [ ] Complete CC3/4 bone mappings
- [ ] Test coverage >80%

### v1.1 (Planned)
- [ ] Mixamo and VRM full support
- [ ] Facial rig preservation (optional)
- [ ] Unity export validation
- [ ] Batch processing API
- [ ] Web UI for conversions

### v2.0 (Future)
- [ ] Animation retargeting (not just rig)
- [ ] Clothing/accessory preservation
- [ ] ML-based rig detection
- [ ] Cloud-native processing (Lambda/Cloud Run)

---

Built with ❤️ for the game dev community.
