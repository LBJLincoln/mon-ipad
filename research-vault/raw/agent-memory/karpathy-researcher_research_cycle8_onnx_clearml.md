---
name: Cycle 8 ONNX + ClearML Research (Apr 3, 2026)
description: Tree model inference acceleration (ONNX, Timber) + experiment tracking (ClearML vs DagsHub) for 6-island evolution
type: project
---

## ONNX Runtime for NBA Prediction

### Speedup Reality Check
- **Timber (AOT C99 compiler):** 336× faster than Python XGBoost (2 µs single-sample)
  - Trade-off: requires compilation; best for batch predictions <100 samples ✓ (daily games fit)
- **ONNX Runtime standard:** 5-10× slower than native on CPU (older data; improved in v1.17+)
- **CatBoost native:** Already 35× faster than XGBoost, 83× faster than LightGBM
  - **Recommendation:** Native libraries sufficient for HF Spaces (CPU-only anyway)

### Conversion Stack
| Tool | Best For | Our Stack |
|------|----------|-----------|
| **onnxmltools** | XGB + LGBM + CatBoost + sklearn | ✓ USE THIS (covers all 4) |
| **sklearn-onnx** | scikit-learn pipelines + preprocessing | ✓ Complement onnxmltools |
| **Timber** | Native C99 binary (microsecond latency) | Consider for daily predictions |

### Integration Pattern
```python
# Train with native (fast)
xgb_model = xgb.train(params, dtrain, num_boost_round=100)

# Convert for portability/freezing preprocessing
onnx_model = onnxmltools.convert_xgboost(
    xgb_model, 
    initial_types=[('float_input', FloatTensorType([None, 200]))]
)
onnx.save(onnx_model, f'models/xgb_gen_{gen}.onnx')

# Inference (daily predictions)
sess = rt.InferenceSession('xgb_gen_N.onnx')
preds = sess.run([...], {input_name: X_daily})
```

### Critical Gotchas
1. **Feature count mismatch:** ONNX fails if tree ensemble feature indices ≠ input tensor shape
   - Solution: Pad X with zeros if feature selection < MAX_FEATURES
2. **Categorical encoding divergence:** One-hot encoder in ONNX pipeline ≠ training
   - Solution: Preprocess categorical features BEFORE conversion (inside sklearn pipeline)
3. **Data type mismatch:** ONNX expects float32, numpy defaults float64
   - Solution: Always cast to `.astype(np.float32)`

---

## ClearML vs DagsHub vs MLflow for Evolution Tracking

### ClearML (RECOMMENDED for parallel islands)
**Free tier:** 3 users, 100 GB storage, 1M API calls/mo
**Why best for us:**
- ✓ Auto-logs all hyperparams + code + config
- ✓ **Task = 1 generation** (automatic structure)
- ✓ Pipeline orchestration (coordinate 6 islands S10-S15)
- ✓ Artifact registry (model checkpoints per generation)
- ✓ Dashboard shows Brier trends per island

**Setup:** 5 min (pip install clearml + clearml-init + API key)

**Code pattern:**
```python
from clearml import Task, Logger

task = Task.init(project_name='NBA_Evolution', task_name=f'S10_Gen_{gen}')
task.connect_configuration(dict(mutation=0.09, max_features=200))

logger = task.get_logger()
logger.report_scalar('Brier', 'validation', brier_score, iteration=gen)
logger.report_scalar('Fitness', 'best', best_fit, iteration=gen)

task.upload_artifact(name=f'model_gen_{gen}', artifact_object=model)
task.close()
```

### DagsHub (Secondary: Git-native backup)
- Free for public repos (unlimited users, git-native MLflow server auto-created)
- Simpler than ClearML (git push = auto-log)
- Less pipeline control
- Good fallback: every autonomous-cycle.sh commit auto-tracked

### MLflow (Simplest standalone)
- Pure open-source, zero server management
- Works locally (`mlflow ui` command)
- No auto-logging of code/config (manual log_params/log_metrics)
- Good for local testing, not great for 6 parallel islands

### Recommended Hybrid Architecture
```
ClearML (primary) ← Task.init() from HF Spaces
         ↓
     Dashboard (trends, Brier per island)

DagsHub (backup)  ← Git commits auto-logged to MLflow
         ↓
     Dagshub.com/LBJLincoln/mon-ipad/mlflow (read-only archive)

MLflow local      ← Local fallback if internet down
```

---

## Implementation Priority

### Quick Win (2h): ClearML minimal
1. Create free account at https://clear.ml/clearml-experiment
2. Run `clearml-init` on VM
3. Wrap S10 evolution: `Task.init()` → run GA → `logger.report_scalar()` → `task.close()`
4. Verify dashboard at https://app.clear.ml/projects/NBA_Evolution

### Phase 2 (4h): Multi-island coordination
- Extend to S11-S15
- Unified Brier trend dashboard
- Tag each task with island ID + generation

### Phase 3 (2-4h): ONNX inference optimization
- Benchmark ONNX vs native on daily predictions
- If speedup >2×, integrate into predict_today.py
- Keep native for training (batch gradient updates)

### Phase 4 (2h): Auto-reporting
- Query ClearML API for last 10 gens per island
- Push Brier trend chart to Telegram @Nomos42Bot
- Archive to data/evolution/clearml-trends.json

---

## Data Files
- Full research: `/tmp/onnx-clearml-research.md` (4500+ lines with code examples)
- Code snippets ready to copy-paste for all 4 libraries (XGB, LGBM, CatBoost, ExtraTrees)

---

## Next Steps for Karpathy Loop
1. Integrate ClearML logging into autonomous-cycle.sh
2. Push Phase 1 (minimal ClearML) this week
3. Monitor Brier trends on dashboard, feed insights back to research cycle
4. Decide ONNX vs native based on actual benchmarks on HF Spaces
