#!/usr/bin/env python3
"""
Nomos42 ONNX Model Exporter
============================
Exports tree-based models (XGBoost, LightGBM, Extra Trees, CatBoost) to ONNX format
for faster inference.

Usage (on GPU machine -- Kaggle/Colab, NOT on VM):
    python3 scripts/monitoring/onnx-export.py --input model.pkl --output model.onnx
    python3 scripts/monitoring/onnx-export.py --input model.pkl --model-type xgboost --features 110
    python3 scripts/monitoring/onnx-export.py --input model.cbm --model-type catboost --features 200

Supported model types:
    - xgboost (XGBClassifier/XGBRegressor)
    - lightgbm (LGBMClassifier/LGBMRegressor)
    - extra_trees (ExtraTreesClassifier/ExtraTreesRegressor)
    - random_forest (RandomForestClassifier/RandomForestRegressor)
    - catboost (CatBoostClassifier/CatBoostRegressor)
    - sklearn (any scikit-learn tree-based model)

NOTE: This script is meant to run on GPU machines (Kaggle/Colab) where models
are trained. It requires onnxmltools, skl2onnx, and the relevant ML libraries.
Do NOT run model training on the VM (1 vCPU / 969 MB RAM).
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path


def check_dependencies():
    """Check which export backends are available."""
    deps = {}

    try:
        import onnxmltools
        deps["onnxmltools"] = True
    except ImportError:
        deps["onnxmltools"] = False

    try:
        import skl2onnx
        deps["skl2onnx"] = True
    except ImportError:
        deps["skl2onnx"] = False

    try:
        import onnx
        deps["onnx"] = True
    except ImportError:
        deps["onnx"] = False

    try:
        import numpy
        deps["numpy"] = True
    except ImportError:
        deps["numpy"] = False

    # ML frameworks
    for lib in ["xgboost", "lightgbm", "catboost", "sklearn"]:
        try:
            __import__(lib if lib != "sklearn" else "sklearn.ensemble")
            deps[lib] = True
        except ImportError:
            deps[lib] = False

    return deps


def load_model(input_path: str, model_type: str = None):
    """Load a model from file."""
    path = Path(input_path)

    if not path.exists():
        print(f"ERROR: Model file not found: {input_path}")
        sys.exit(1)

    ext = path.suffix.lower()

    # CatBoost native format
    if ext == ".cbm" or model_type == "catboost":
        try:
            from catboost import CatBoostClassifier
            model = CatBoostClassifier()
            model.load_model(str(path))
            return model, "catboost"
        except Exception as e:
            print(f"ERROR loading CatBoost model: {e}")
            sys.exit(1)

    # XGBoost native format
    if ext == ".xgb" or ext == ".json" and model_type == "xgboost":
        try:
            import xgboost as xgb
            model = xgb.XGBClassifier()
            model.load_model(str(path))
            return model, "xgboost"
        except Exception as e:
            print(f"ERROR loading XGBoost model: {e}")
            sys.exit(1)

    # LightGBM native format
    if ext == ".lgb" or ext == ".txt" and model_type == "lightgbm":
        try:
            import lightgbm as lgb
            model = lgb.Booster(model_file=str(path))
            return model, "lightgbm"
        except Exception as e:
            print(f"ERROR loading LightGBM model: {e}")
            sys.exit(1)

    # Pickle / joblib (most common)
    if ext in (".pkl", ".pickle", ".joblib", ".gz"):
        try:
            import joblib
            model = joblib.load(str(path))
        except ImportError:
            import pickle
            with open(path, "rb") as f:
                model = pickle.load(f)

        # Auto-detect type
        detected_type = _detect_model_type(model)
        if model_type and model_type != detected_type:
            print(f"  WARNING: specified type '{model_type}' but detected '{detected_type}'")
        return model, model_type or detected_type

    print(f"ERROR: Unsupported file format: {ext}")
    print("Supported: .pkl, .pickle, .joblib, .gz, .cbm, .xgb, .lgb, .json, .txt")
    sys.exit(1)


def _detect_model_type(model) -> str:
    """Auto-detect model type from object."""
    class_name = type(model).__name__.lower()
    module = type(model).__module__ or ""

    if "xgb" in module or "xgboost" in class_name:
        return "xgboost"
    elif "lightgbm" in module or "lgbm" in class_name:
        return "lightgbm"
    elif "catboost" in module or "catboost" in class_name:
        return "catboost"
    elif "extratrees" in class_name:
        return "extra_trees"
    elif "randomforest" in class_name:
        return "random_forest"
    elif "gradientboosting" in class_name:
        return "sklearn"
    elif "sklearn" in module:
        return "sklearn"
    else:
        return "unknown"


def export_to_onnx(model, model_type: str, output_path: str, n_features: int = 200):
    """Export a model to ONNX format."""
    import numpy as np

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    print(f"  Model type: {model_type}")
    print(f"  Features: {n_features}")
    print(f"  Output: {output}")

    start = time.time()

    if model_type == "xgboost":
        _export_xgboost(model, output, n_features)
    elif model_type == "lightgbm":
        _export_lightgbm(model, output, n_features)
    elif model_type == "catboost":
        _export_catboost(model, output, n_features)
    elif model_type in ("extra_trees", "random_forest", "sklearn"):
        _export_sklearn(model, output, n_features)
    else:
        # Try sklearn fallback
        print(f"  Unknown type '{model_type}', trying sklearn export...")
        _export_sklearn(model, output, n_features)

    elapsed = time.time() - start
    file_size = output.stat().st_size if output.exists() else 0

    print(f"  Export completed in {elapsed:.2f}s")
    print(f"  ONNX file size: {file_size / 1024:.1f} KB")

    # Validate
    _validate_onnx(output, n_features)

    return {
        "model_type": model_type,
        "n_features": n_features,
        "output_path": str(output),
        "file_size_kb": file_size / 1024,
        "export_time_s": elapsed,
    }


def _export_xgboost(model, output: Path, n_features: int):
    """Export XGBoost model to ONNX."""
    try:
        from onnxmltools import convert_xgboost
        from onnxmltools.convert.common.data_types import FloatTensorType

        initial_type = [("features", FloatTensorType([None, n_features]))]
        onnx_model = convert_xgboost(model, initial_types=initial_type)
        with open(output, "wb") as f:
            f.write(onnx_model.SerializeToString())
        print("  Exported via onnxmltools.convert_xgboost")
    except Exception as e:
        print(f"  onnxmltools failed: {e}")
        print("  Trying skl2onnx fallback...")
        _export_sklearn(model, output, n_features)


def _export_lightgbm(model, output: Path, n_features: int):
    """Export LightGBM model to ONNX."""
    try:
        from onnxmltools import convert_lightgbm
        from onnxmltools.convert.common.data_types import FloatTensorType

        initial_type = [("features", FloatTensorType([None, n_features]))]
        onnx_model = convert_lightgbm(model, initial_types=initial_type)
        with open(output, "wb") as f:
            f.write(onnx_model.SerializeToString())
        print("  Exported via onnxmltools.convert_lightgbm")
    except Exception as e:
        print(f"  onnxmltools failed: {e}")
        print("  Trying skl2onnx fallback...")
        _export_sklearn(model, output, n_features)


def _export_catboost(model, output: Path, n_features: int):
    """Export CatBoost model to ONNX."""
    try:
        # CatBoost has native ONNX export
        model.save_model(str(output), format="onnx",
                         export_parameters={"onnx_domain": "ai.catboost",
                                            "onnx_model_version": 1})
        print("  Exported via CatBoost native ONNX export")
    except Exception as e:
        print(f"  CatBoost native export failed: {e}")
        try:
            from onnxmltools import convert_catboost
            from onnxmltools.convert.common.data_types import FloatTensorType

            initial_type = [("features", FloatTensorType([None, n_features]))]
            onnx_model = convert_catboost(model, initial_types=initial_type)
            with open(output, "wb") as f:
                f.write(onnx_model.SerializeToString())
            print("  Exported via onnxmltools.convert_catboost")
        except Exception as e2:
            print(f"  ERROR: All CatBoost export methods failed: {e2}")
            sys.exit(1)


def _export_sklearn(model, output: Path, n_features: int):
    """Export scikit-learn model to ONNX via skl2onnx."""
    try:
        from skl2onnx import convert_sklearn
        from skl2onnx.common.data_types import FloatTensorType

        initial_type = [("features", FloatTensorType([None, n_features]))]
        onnx_model = convert_sklearn(model, initial_types=initial_type)
        with open(output, "wb") as f:
            f.write(onnx_model.SerializeToString())
        print("  Exported via skl2onnx.convert_sklearn")
    except Exception as e:
        print(f"  ERROR: sklearn export failed: {e}")
        sys.exit(1)


def _validate_onnx(output: Path, n_features: int):
    """Validate the exported ONNX model."""
    try:
        import onnx
        model = onnx.load(str(output))
        onnx.checker.check_model(model)
        print("  ONNX validation: PASSED")

        # Try inference test
        try:
            import onnxruntime as ort
            import numpy as np
            session = ort.InferenceSession(str(output))
            input_name = session.get_inputs()[0].name
            dummy = np.random.randn(1, n_features).astype(np.float32)
            result = session.run(None, {input_name: dummy})
            print(f"  Inference test: PASSED (output shape: {[r.shape for r in result]})")
        except ImportError:
            print("  Inference test: SKIPPED (onnxruntime not installed)")
        except Exception as e:
            print(f"  Inference test: WARNING ({e})")

    except ImportError:
        print("  ONNX validation: SKIPPED (onnx not installed)")
    except Exception as e:
        print(f"  ONNX validation: FAILED ({e})")


def batch_export(input_dir: str, output_dir: str, n_features: int = 200):
    """Export all models in a directory."""
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    extensions = {".pkl", ".pickle", ".joblib", ".gz", ".cbm", ".xgb", ".lgb"}
    model_files = [f for f in input_path.iterdir() if f.suffix.lower() in extensions]

    if not model_files:
        print(f"No model files found in {input_dir}")
        return []

    print(f"Found {len(model_files)} model files to export")
    results = []

    for model_file in model_files:
        print(f"\n--- Exporting: {model_file.name} ---")
        try:
            model, mtype = load_model(str(model_file))
            onnx_path = output_path / f"{model_file.stem}.onnx"
            result = export_to_onnx(model, mtype, str(onnx_path), n_features)
            results.append(result)
        except Exception as e:
            print(f"  FAILED: {e}")
            results.append({"file": model_file.name, "error": str(e)})

    # Write manifest
    manifest_path = output_path / "export-manifest.json"
    manifest = {
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "n_features": n_features,
        "models": results,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"\nManifest written to {manifest_path}")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Nomos42 ONNX Model Exporter — convert tree models for fast inference",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single model
  python3 onnx-export.py --input best_model.pkl --output best_model.onnx

  # With explicit type and features
  python3 onnx-export.py --input model.pkl --model-type xgboost --features 110

  # CatBoost native format
  python3 onnx-export.py --input model.cbm --model-type catboost

  # Batch export all models in a directory
  python3 onnx-export.py --batch-dir ./models/ --output-dir ./onnx_models/

  # Check available dependencies
  python3 onnx-export.py --check-deps
        """,
    )

    parser.add_argument("--input", "-i", help="Input model file path (.pkl, .joblib, .cbm, .xgb, .lgb)")
    parser.add_argument("--output", "-o", help="Output ONNX file path (default: <input>.onnx)")
    parser.add_argument("--model-type", "-t",
                        choices=["xgboost", "lightgbm", "catboost", "extra_trees", "random_forest", "sklearn"],
                        help="Model type (auto-detected if not specified)")
    parser.add_argument("--features", "-f", type=int, default=200,
                        help="Number of input features (default: 200)")
    parser.add_argument("--batch-dir", help="Directory containing multiple model files to export")
    parser.add_argument("--output-dir", help="Output directory for batch export")
    parser.add_argument("--check-deps", action="store_true", help="Check available dependencies and exit")

    args = parser.parse_args()

    print("=" * 60)
    print("  NOMOS42 ONNX MODEL EXPORTER")
    print("=" * 60)

    if args.check_deps:
        deps = check_dependencies()
        print("\nDependency Status:")
        for name, available in sorted(deps.items()):
            status = "OK" if available else "MISSING"
            icon = "+" if available else "-"
            print(f"  [{icon}] {name:15s} {status}")
        print()
        if not deps.get("onnxmltools") and not deps.get("skl2onnx"):
            print("WARNING: Neither onnxmltools nor skl2onnx is available.")
            print("Install: pip install onnxmltools skl2onnx")
        sys.exit(0)

    if args.batch_dir:
        output_dir = args.output_dir or str(Path(args.batch_dir) / "onnx")
        batch_export(args.batch_dir, output_dir, args.features)
        return

    if not args.input:
        parser.print_help()
        print("\nERROR: --input is required (or use --batch-dir for batch export)")
        sys.exit(1)

    model, model_type = load_model(args.input, args.model_type)
    output = args.output or str(Path(args.input).with_suffix(".onnx"))
    result = export_to_onnx(model, model_type, output, args.features)

    print("\n  Export Summary:")
    print(json.dumps(result, indent=2))
    print("=" * 60)


if __name__ == "__main__":
    main()
