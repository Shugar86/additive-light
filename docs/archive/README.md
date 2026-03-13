# Generative Design Intelligence (GDI)

**3D Scan → Parametric CAD → G-code**

GDI is a neurosymbolic AI system that converts raw 3D scans (STL) into parametric CAD models using a hybrid approach: deterministic sensors (Python) for geometry analysis and LLMs (Claude/GPT-4) for high-level design decisions.

## Architecture

```
Raw Mesh (STL)
    ↓
Step 0: HumanAlign (base plane, center axis)
    ↓
Step 1: Sensor (Multi-axis Slicer)
    ↓
Step 2: Approximator (Vector Regression, RANSAC)
    ↓
Step 3: Synthesizer (LLM Orchestrator)
    ↓
Step 4: Judge (2-phase validation)
    ↓
Step 5: Optimizer (Parametrization)
    ↓
Step 6: CAM Postprocessor (FreeCAD Path)
    ↓
G-code (.nc) + STEP (.step) + Manifest
```

## Project Structure

```
e:
├── gdi_core/              # Core business logic (web-ready)
│   ├── models/           # Pydantic YAML contract models
│   ├── sensors/          # Multi-axis slicer
│   ├── approximator/     # Zone detection with confidence
│   ├── judge/            # 2-phase validation
│   ├── synthesis/        # LLM orchestration
│   ├── optimizer/        # Code beautification
│   ├── cam/              # G-code generation
│   ├── utils/            # Manifest & logging
│   └── api.py            # Clean API boundary
│
├── gdi_app/              # Desktop applications
│   ├── cli/              # Typer CLI interface
│   └── gui/              # PyQt6 GUI
│
├── web/                  # Web application (Phase 2)
│   ├── backend/          # FastAPI + Celery
│   ├── frontend/         # React + Three.js
│   └── sandbox/          # Docker sandbox for code execution
│
├── benchmark_kit/        # Test data
│   ├── ideal/           # Perfect models
│   ├── noise/           # Synthetic noise
│   ├── corrupt/         # Manually damaged
│   └── real_scans/      # Real scanner data
│
├── requirements.txt      # Dependencies
└── README.md            # This file
```

## Installation

### Prerequisites
- Python 3.11+
- Redis (for web version)
- Docker (for sandbox)
- OpenSCAD (for dataset generation)

### Desktop (Phase 1)

```bash
# Install dependencies
pip install -r requirements.txt

# Run CLI
cd gdi_app/cli
python -m main process /path/to/file.stl --output output/

# Or run GUI
cd gdi_app/gui
python -m main_window
```

### Web (Phase 2)

```bash
cd web

# Start services
docker-compose up -d

# API: http://localhost:8000
# Frontend: http://localhost:3000
```

## Usage

### CLI

```bash
# Process single file
gdi process model.stl --axis Z --confidence 0.7

# Batch processing
gdi batch ./models/ --pattern "*.stl"

# Validate YAML
gdi validate output/model_telemetry.yaml

# System info
gdi info
```

### Python API

```python
from gdi_core import GDIAPI

api = GDIAPI(
    slice_step=0.1,
    confidence_threshold=0.7
)

# Run complete pipeline
manifest = api.run_pipeline(
    stl_file="model.stl",
    base_axis="Z"
)

print(f"Status: {manifest.status}")
print(f"Confidence: {manifest.approximation_result.global_confidence}")
print(f"Zones: {len(manifest.approximation_result.telemetry.topological_zones)}")
```

### Web API

```bash
# Upload file
curl -X POST -F "file=@model.stl" http://localhost:8000/api/v1/upload

# Create job
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{"source_stl": "uploads/...stl", "base_axis": "Z"}'

# Check status
curl http://localhost:8000/api/v1/jobs/{job_id}

# WebSocket for real-time updates
wscat -c ws://localhost:8000/ws/jobs/{job_id}
```

## Features

### Phase 1 (Desktop MVP) - COMPLETE

- [x] **Sensor**: Multi-axis slicing with Trimesh + Shapely
- [x] **Approximator**: RANSAC-based zone detection with confidence scoring
- [x] **YAML Contract**: Strict pydantic schema v1.0
- [x] **Judge**: 2-phase validation (syntax → IoU)
- [x] **Optimizer**: Code parametrization and beautification
- [x] **Run Manifest**: Full traceability (run_id, versions, IoU, errors)
- [x] **CLI**: Typer interface for batch processing
- [x] **GUI**: PyQt6 minimal interface
- [x] **CAM**: G-code export (FreeCAD integration)
- [x] **Benchmark Kit**: 8-12 STL with expected results

### Phase 2 (Web) - IMPLEMENTED

- [x] **FastAPI**: REST API with async support
- [x] **Celery + Redis**: Background task queue
- [x] **S3 Storage**: File upload/download
- [x] **WebSocket**: Real-time progress updates
- [x] **React + Three.js**: 3D web viewer
- [x] **Docker Sandbox**: Isolated code execution
- [x] **Scalable**: Horizontal worker scaling

## YAML Contract v1.0

The communication protocol between sensors and LLM:

```yaml
Global_State:
  target_action: "Generate parametric B-Rep code"
  target_library: "build123d"
  base_axis: "Z"
  total_height: 40.0
  yaml_version: "1.0"

Topological_Zones:
  - zone_id: 1
    span_z: [0.0, 40.0]
    geometry: "Constant_Profile"
    cross_section: "Circle"
    parameters:
      radius: 20.0
    sensor_hint: "Stable RANSAC fit. Probably a base cylinder..."
    confidence: 0.95

Agent_Task:
  rules:
    - "Do not use visual assumptions..."
    - "Use 'with BuildPart():' context managers..."
  thought_process: "..."
  code_output: "..."
```

## Benchmark Kit

Expected results for regression testing:

| Model | Type | Min IoU | Confidence |
|-------|------|---------|------------|
| ideal_cylinder | Perfect | 0.99 | 0.95 |
| noise_cylinder | Noisy | 0.96 | 0.80 |
| corrupt_cylinder | Damaged | 0.80 | 0.40 |
| real_scan_1 | Raw scan | 0.85 | 0.60 |

## Development

### Testing

```bash
# Run tests
pytest tests/ -v

# Run on benchmark
python -m pytest tests/test_benchmark.py --benchmark
```

### Code Style

```bash
# Format code
black gdi_core/ gdi_app/ web/

# Type check
mypy gdi_core/
```

## License

MIT License - See LICENSE file

## Contributing

1. Fork the repository
2. Create a feature branch
3. Follow the VibeCraft Engineering Rules (see `.cursor/rules/`)
4. Submit a pull request

## Acknowledgments

- build123d / OCP (OpenCASCADE) for CAD operations
- Trimesh for mesh processing
- LangGraph for LLM orchestration
- FastAPI for web framework
