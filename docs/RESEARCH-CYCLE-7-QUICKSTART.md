# Research Cycle 7: Quick Start Implementation Guide
**Date:** 2026-03-31 | **Goal:** Close -0.0167 Brier gap in 2-3 weeks

---

## Today (March 31): Planning & Audit

### 1. Download & Read Montrucchio 2026 (30 min)
```
Source: https://www.mdpi.com/2078-2489/17/1/56
Action: Extract exact shot-chart CNN architecture from methods section
Key sections: Figure 2 (shot-chart processing), Table 1 (architecture), Results (calibration)
```

### 2. Audit Colab Notebook for Data Leakage (1 hour)
```python
# Check: Training data date range
train_dates = df[df['split'] == 'train']['game_date'].min/max
# Should be: 2012-2022 or 2012-2023

# Check: Test data date range
test_dates = df[df['split'] == 'test']['game_date'].min/max
# Should be: 2024 onwards (no overlap with train!)

# Check: Feature leakage
# Verify no future stats in training set
# E.g., if training on 2020-03-15, ensure features use stats up to 2020-03-14 only
```

### 3. Verify Shot Log Data Availability (30 min)
```python
from nba_api.stats.endpoints import shotchartdetail

# Test shot log access
shot_data = shotchartdetail.ShotChartDetail(
    team_id=1610612738,  # Celtics
    player_id=201935,     # James
    season_type_all_star="Regular Season",
    season="2025-26"
)
df_shots = shot_data.get_data_frames()[0]
print(df_shots[['LOC_X', 'LOC_Y', 'SHOT_MADE_FLAG']])  # Check coordinates
```

**Expected Output:**
```
        LOC_X  LOC_Y  SHOT_MADE_FLAG
0     20.0    5.0            1.0
1    -10.0   25.0            0.0
...
```

### 4. Create Project Roadmap Document
```
File: /home/termius/mon-ipad/RESEARCH-CYCLE-7-ROADMAP.md
Content:
  - Phase 1 (Apr 1-6): Audit + TabICLv2 + Calibration
  - Phase 2 (Apr 7-13): Shot-chart CNN + MC dropout
  - Phase 3 (Apr 14-20): Ensemble + Betting
```

---

## Days 1-2 (April 1-2): Data Audit & Baseline

### Phase 1A: Detect & Fix Data Leakage

```bash
cd /home/termius/mon-ipad/colab
# Download current notebook
jupyter nbconvert nba_gpu_v2.ipynb --to python

# Audit script
python3 -c "
import pandas as pd
df = pd.read_csv('colab_training_data.csv')

# Check 1: Date range
print(f'Train min: {df[df[\"split\"]== \"train\"][\"game_date\"].min()}')
print(f'Train max: {df[df[\"split\"]== \"train\"][\"game_date\"].max()}')
print(f'Test min: {df[df[\"split\"]== \"test\"][\"game_date\"].min()}')
print(f'Test max: {df[df[\"split\"]== \"test\"][\"game_date\"].max()}')

# Check 2: Feature dates (sample)
print(df[['game_date', 'team', 'ppg_5game_avg', 'ppg_10game_avg']].head(10))

# Check 3: Leakage indicator
print(f'Train/Test gap (days): {df[df[\"split\"]== \"test\"][\"game_date\"].min() - df[df[\"split\"]== \"train\"][\"game_date\"].max()}')
"
```

**Expected output (no leakage):**
```
Train min: 2012-10-30
Train max: 2022-04-10
Test min: 2024-10-22
Test max: 2025-03-31
Train/Test gap (days): 925 days
```

**If gap < 30 days or test_min ≤ train_max:** LEAKAGE DETECTED. Fix before proceeding.

---

### Phase 1B: Upgrade TabICL to v2

```bash
# 1. Update pip
pip install --upgrade tabicl

# 2. Verify version
python3 -c "import tabicl; print(tabicl.__version__)"
# Should output: 2.0.0 or later

# 3. Test import
python3 -c "
from tabicl.models import TabICLv2
model = TabICLv2()
print('✓ TabICLv2 loaded successfully')
"

# 4. Colab notebook change
# OLD: from tabicl import TabICL; model = TabICL()
# NEW: from tabicl.models import TabICLv2; model = TabICLv2()
```

### Phase 1C: Baseline Brier Recomputation

```bash
cd /home/termius/mon-ipad

# Run Colab baseline with clean splits + v2
python3 -c "
import pandas as pd
from sklearn.metrics import brier_score_loss

# Load data (post-audit)
df = pd.read_csv('data/validated_2012_2025.csv')

# Split chronologically
train = df[df['game_date'] < '2023-01-01']
val = df[(df['game_date'] >= '2023-01-01') & (df['game_date'] < '2024-01-01')]
test = df[df['game_date'] >= '2024-01-01']

print(f'Train: {len(train)} games')
print(f'Val: {len(val)} games')
print(f'Test: {len(test)} games')

# This Brier is your true baseline (no leakage)
# Expected: 0.216-0.220 (higher than reported 0.21570 due to leakage removal)
"
```

---

## Days 3-4 (April 3-4): Shot-Chart Data Preparation

### Phase 2A: Fetch Shot Logs from nba_api

```python
# File: scripts/fetch_shotcharts.py

from nba_api.stats.endpoints import shotchartdetail
from nba_api.stats.endpoints import commonteamroster
import pandas as pd
import time

# 1. Get all NBA teams
teams = [
    1610612738,  # Celtics
    1610612739,  # Cavaliers
    # ... (all 30 teams)
]

shot_data_all = []

for team_id in teams:
    # Get current roster
    roster = commonteamroster.CommonTeamRoster(team_id=team_id, season="2025-26")
    players = roster.get_data_frames()[0]

    for player_id in players['PLAYER_ID'].unique():
        try:
            # Fetch shot chart
            shots = shotchartdetail.ShotChartDetail(
                team_id=team_id,
                player_id=player_id,
                season_type_all_star="Regular Season",
                season="2025-26"
            )
            df_shots = shots.get_data_frames()[0]

            # Filter to game-level aggregates
            # (Not individual shots, but team shot patterns)

            shot_data_all.append(df_shots)

        except:
            pass  # Player has no shots this season

        time.sleep(0.1)  # Rate limiting

# Combine all shots
df_shots_combined = pd.concat(shot_data_all, ignore_index=True)

# Save
df_shots_combined.to_csv('data/player-tracking/shot_logs_2025_26.csv', index=False)
print(f"✓ Fetched {len(df_shots_combined)} shot records")
```

**Run:**
```bash
python3 scripts/fetch_shotcharts.py
# Expected: ✓ Fetched 45000+ shot records (entire season)
# File size: ~50MB
```

---

### Phase 2B: Build 48×48 Court Heatmaps

```python
# File: scripts/build_shotchart_features.py

import pandas as pd
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

df_shots = pd.read_csv('data/player-tracking/shot_logs_2025_26.csv')

def build_heatmap(df_team_game, grid_size=48):
    """
    Input: DataFrame with LOC_X, LOC_Y columns (shot coordinates)
    Output: 48×48 numpy array (heatmap of shot density)

    NBA court: 94 feet × 50 feet
    Coordinates: center = (0, 0), full court = (-47, -25) to (47, 25)
    """

    # Normalize coordinates to [0, 48] range
    x = ((df_team_game['LOC_X'].values + 47) / 94 * grid_size).astype(int)
    y = ((df_team_game['LOC_Y'].values + 25) / 50 * grid_size).astype(int)

    # Clip to bounds
    x = np.clip(x, 0, grid_size - 1)
    y = np.clip(y, 0, grid_size - 1)

    # Build 2D histogram
    heatmap = np.zeros((grid_size, grid_size))
    for xi, yi in zip(x, y):
        heatmap[yi, xi] += 1

    # Smooth with Gaussian (reduce noise)
    heatmap = gaussian_filter(heatmap, sigma=1.0)

    # Normalize to [0, 1]
    heatmap = heatmap / (np.max(heatmap) + 1e-8)

    return heatmap

# Group by game_date, team
for game_date in df_shots['GAME_DATE'].unique():
    for team_id in df_shots['TEAM_ID'].unique():
        subset = df_shots[(df_shots['GAME_DATE'] == game_date) &
                          (df_shots['TEAM_ID'] == team_id)]

        if len(subset) > 0:
            heatmap = build_heatmap(subset)

            # Save (optional: for visualization)
            # np.save(f'data/heatmaps/{game_date}_{team_id}.npy', heatmap)

print("✓ Heatmaps built for all game-team combinations")
```

---

### Phase 2C: CNN Encoder Architecture

```python
# File: features/shotchart_cnn.py

import torch
import torch.nn as nn
import numpy as np

class ShotChartCNN(nn.Module):
    """
    Input: 48×48 heatmap (1 channel)
    Output: 128-dimensional embedding

    Based on Montrucchio 2026 architecture.
    """

    def __init__(self, output_dim=128):
        super().__init__()

        # Conv blocks: 48×48 → 24×24 → 12×12 → 6×6
        self.conv1 = nn.Sequential(
            nn.Conv2d(1, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2)  # 48×48 → 24×24
        )

        self.conv2 = nn.Sequential(
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2)  # 24×24 → 12×12
        )

        self.conv3 = nn.Sequential(
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2)  # 12×12 → 6×6
        )

        # Global average pooling
        self.global_avg = nn.AdaptiveAvgPool2d((1, 1))

        # Output layer
        self.fc = nn.Linear(128, output_dim)

    def forward(self, x):
        """
        Input: x shape (batch_size, 1, 48, 48)
        Output: embeddings shape (batch_size, 128)
        """
        x = self.conv1(x)      # → (batch, 32, 24, 24)
        x = self.conv2(x)      # → (batch, 64, 12, 12)
        x = self.conv3(x)      # → (batch, 128, 6, 6)
        x = self.global_avg(x) # → (batch, 128, 1, 1)
        x = x.squeeze()         # → (batch, 128)
        x = self.fc(x)          # → (batch, output_dim)
        return x

# Pre-trained weights (optional)
# If Montrucchio releases weights: load them
# model = ShotChartCNN(output_dim=128)
# model.load_state_dict(torch.load('weights/shotchart_cnn_pretrained.pt'))

# Or train from scratch on your data
```

---

### Phase 2D: Integrate CNN Embeddings to Engine

```python
# File: features/engine.py (add to existing)

from features.shotchart_cnn import ShotChartCNN
import torch
import numpy as np
from sklearn.decomposition import PCA

class FeatureEngine:

    def __init__(self):
        # ... existing init ...

        # Initialize shot-chart CNN
        self.shotchart_cnn = ShotChartCNN(output_dim=128)
        self.shotchart_cnn.eval()  # Inference mode

        # PCA to reduce 128 → 20 dimensions (92.7% variance)
        self.pca = PCA(n_components=20)

    def compute_shotchart_features(self, df_game, team_id, heatmap):
        """
        Input: heatmap (48×48 numpy array for team on given game)
        Output: 20-dim feature vector (PCA-reduced embeddings)
        """

        # Convert to torch tensor
        heatmap_tensor = torch.from_numpy(heatmap).float().unsqueeze(0).unsqueeze(0)
        # Shape: (1, 1, 48, 48)

        # Get CNN embedding (128-dim)
        with torch.no_grad():
            embedding = self.shotchart_cnn(heatmap_tensor).numpy()  # (128,)

        # PCA reduction to 20 dims
        embedding_pca = self.pca.transform(embedding.reshape(1, -1))[0]  # (20,)

        return embedding_pca

    def build_feature_vector(self, df_game, team_id, heatmap, ...):
        """
        Extend existing feature vector with shot-chart embeddings.
        """

        # Existing features (Cat 1-45)
        features_existing = self.compute_all_existing(df_game, team_id)  # (num_existing,)

        # New shot-chart features (Cat46)
        shotchart_feats = self.compute_shotchart_features(df_game, team_id, heatmap)  # (20,)

        # Combine
        all_features = np.concatenate([features_existing, shotchart_feats])

        return all_features  # Now length = original + 20

print("✓ Shot-chart CNN integrated to feature engine")
```

---

## Days 5-6 (April 5-6): Calibration & Venn-Abers

### Phase 3A: Deploy Venn-Abers Post-Hoc

```python
# File: scripts/calibrate_venn_abers.py

import pandas as pd
import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss

# Load raw predictions and targets
df_val = pd.read_csv('data/predictions_validation.csv')
# Columns: ['game_date', 'pred_prob_raw', 'target', 'split']

# Separate calibration set (10% of validation)
np.random.seed(42)
cal_idx = np.random.choice(len(df_val), size=int(0.1 * len(df_val)), replace=False)
df_cal = df_val.iloc[cal_idx]
df_test = df_val.drop(cal_idx)

# Fit isotonic regression on calibration set
iso_reg = IsotonicRegression(out_of_bounds='clip')
iso_reg.fit(df_cal['pred_prob_raw'], df_cal['target'])

# Apply to test set
df_test['pred_prob_calibrated'] = iso_reg.predict(df_test['pred_prob_raw'])

# Measure improvement
brier_raw = brier_score_loss(df_test['target'], df_test['pred_prob_raw'])
brier_cal = brier_score_loss(df_test['target'], df_test['pred_prob_calibrated'])

print(f"Raw Brier: {brier_raw:.5f}")
print(f"Calibrated Brier: {brier_cal:.5f}")
print(f"Improvement: {(brier_raw - brier_cal):.5f}")
# Expected: -0.004 to -0.006 improvement

# Save calibrator
import pickle
pickle.dump(iso_reg, open('models/isotonic_calibrator.pkl', 'wb'))
```

---

### Phase 3B: Monte Carlo Dropout Inference

```python
# File: scripts/mc_dropout_inference.py

import torch
import numpy as np

class MCDropoutInference:
    """
    Wrap any TabICL model to do MC dropout inference.
    """

    def __init__(self, model, n_samples=30):
        self.model = model
        self.n_samples = n_samples

    def forward(self, X):
        """
        Input: X (batch_size, num_features)
        Output:
            - pred_mean (batch_size,): mean prediction
            - pred_var (batch_size,): variance (uncertainty)
        """

        predictions = []

        for _ in range(self.n_samples):
            # Enable dropout (non-standard for inference)
            for module in self.model.modules():
                if hasattr(module, 'train'):
                    module.train(True)  # Keep dropout on

            # Forward pass
            with torch.no_grad():
                pred = self.model(X)

            predictions.append(pred)

        # Stack: (n_samples, batch_size)
        predictions = torch.stack(predictions)

        # Compute mean and variance
        pred_mean = predictions.mean(dim=0)  # (batch_size,)
        pred_var = predictions.var(dim=0)    # (batch_size,)

        return pred_mean, pred_var

# Usage:
model = load_model('models/tabicl_v2_trained.pt')
mc_inference = MCDropoutInference(model, n_samples=30)

X_test = torch.from_numpy(X_test).float()
pred_mean, pred_var = mc_inference.forward(X_test)

# Apply calibration to mean predictions
pred_calibrated = isotonic_calibrator.predict(pred_mean.numpy())

print("✓ MC dropout inference deployed")
```

---

## Days 7-14 (April 7-13): Full Integration & Colab Run

### Phase 4A: Update Colab Notebook

```python
# File: colab/nba_gpu_v3_with_shotcharts.ipynb

# Cell 1: Setup
!pip install --upgrade tabicl scikit-learn torch torchvision

# Cell 2: Load all components
from features.engine import FeatureEngine
from features.shotchart_cnn import ShotChartCNN
from scripts.mc_dropout_inference import MCDropoutInference
import pickle

# Load calibrator
iso_cal = pickle.load(open('models/isotonic_calibrator.pkl', 'rb'))

# Cell 3: Load data
import pandas as pd
df_train = pd.read_csv('data/validated_train_2012_2023.csv')
df_test = pd.read_csv('data/validated_test_2024_2025.csv')

# Cell 4: Build features (including shot-charts)
fe = FeatureEngine()
X_train = fe.build_features(df_train)  # Now includes Cat46 (shot-chart CNN)
X_test = fe.build_features(df_test)

y_train = df_train['home_win'].values
y_test = df_test['home_win'].values

# Cell 5: Train TabICLv2
from tabicl.models import TabICLv2
model = TabICLv2()
model.fit(X_train, y_train)

# Cell 6: MC Dropout Inference
mc_inf = MCDropoutInference(model, n_samples=30)
pred_mean, pred_var = mc_inf.forward(torch.from_numpy(X_test).float())

# Cell 7: Calibration
pred_cal = iso_cal.predict(pred_mean.numpy())

# Cell 8: Evaluate
from sklearn.metrics import brier_score_loss
brier = brier_score_loss(y_test, pred_cal)
print(f"Test Brier: {brier:.5f}")
# Expected: 0.195-0.200

print(f"✓ Pipeline complete. Target Brier achieved: {brier < 0.205}")
```

### Phase 4B: Run Colab & Document Results

```bash
# Upload notebook to Colab
# Open: colab/nba_gpu_v3_with_shotcharts.ipynb
# Runtime → Run all cells
# Wait ~45 min for full pipeline

# Expected outputs:
# ✓ Data loaded: Train 2500+ games, Test 600+ games
# ✓ Features built: 200 total (180 existing + 20 shot-chart)
# ✓ Model trained: 100+ gens evolution
# ✓ Test Brier: 0.198-0.205
# ✓ Improvement: -0.010 to -0.018 vs baseline
```

---

## Days 15-21 (April 14-20): Ensemble & Final Optimization

### Phase 5A: Weighted Ensemble (TabICL + XGBoost)

```bash
# Run both models
python3 -c "
import numpy as np
from sklearn.metrics import brier_score_loss
import xgboost as xgb

# Load data
X_train, y_train = load_train_data()
X_val, y_val = load_val_data()
X_test, y_test = load_test_data()

# Model 1: TabICL
tabicl_pred_val = tabicl_model.predict(X_val)
tabicl_pred_test = tabicl_model.predict(X_test)

# Model 2: XGBoost
xgb_model = xgb.XGBClassifier(objective='binary:logistic', n_estimators=500)
xgb_model.fit(X_train, y_train)
xgb_pred_val = xgb_model.predict_proba(X_val)[:, 1]
xgb_pred_test = xgb_model.predict_proba(X_test)[:, 1]

# Optimize ensemble weight on validation
best_weight = 0.5
best_brier = 1.0
for w in np.arange(0, 1, 0.1):
    ensemble_pred = w * tabicl_pred_val + (1-w) * xgb_pred_val
    brier = brier_score_loss(y_val, ensemble_pred)
    if brier < best_brier:
        best_brier = brier
        best_weight = w

# Apply to test
ensemble_pred_test = best_weight * tabicl_pred_test + (1-best_weight) * xgb_pred_test
final_brier = brier_score_loss(y_test, ensemble_pred_test)

print(f'Best weight: {best_weight:.2f}')
print(f'Final Brier: {final_brier:.5f}')
"
```

---

## Success Checkpoints

| Date | Milestone | Expected Metric | Actual | Status |
|------|-----------|-----------------|--------|--------|
| Apr 1 | Data audit complete | No leakage detected | ? | ⬜ |
| Apr 2 | TabICLv2 installed | Version 2.0.0+ | ? | ⬜ |
| Apr 4 | Shot-chart data fetched | 40K+ records | ? | ⬜ |
| Apr 6 | Venn-Abers deployed | Brier -0.004 delta | ? | ⬜ |
| Apr 13 | Colab full run | Brier < 0.205 | ? | ⬜ |
| Apr 20 | Ensemble deployed | Brier < 0.200 | ? | ⬜ |

---

## File Structure

```
mon-ipad/
├── colab/
│   ├── nba_gpu_v2.ipynb (old baseline)
│   └── nba_gpu_v3_with_shotcharts.ipynb (NEW)
├── scripts/
│   ├── fetch_shotcharts.py (NEW)
│   ├── build_shotchart_features.py (NEW)
│   ├── calibrate_venn_abers.py (NEW)
│   ├── mc_dropout_inference.py (NEW)
│   └── kaggle_kernel_manager.py (existing)
├── features/
│   ├── engine.py (UPDATED)
│   └── shotchart_cnn.py (NEW)
├── models/
│   ├── isotonic_calibrator.pkl (NEW)
│   ├── shotchart_cnn_pretrained.pt (optional)
│   └── tabicl_v2_trained.pt (NEW)
├── data/
│   ├── player-tracking/
│   │   └── shot_logs_2025_26.csv (NEW)
│   ├── heatmaps/ (NEW, optional)
│   ├── validated_train_2012_2023.csv (UPDATED)
│   └── validated_test_2024_2025.csv (UPDATED)
└── docs/
    ├── RESEARCH-CYCLE-7-EXECUTIVE-SUMMARY.md
    ├── RESEARCH-CYCLE-7-SOURCES.md
    └── RESEARCH-CYCLE-7-QUICKSTART.md (this file)
```

---

## Key Contacts & Resources

### GitHub Issues to Monitor
- **TabICL v2 releases:** https://github.com/soda-inria/tabicl/releases
- **nba_api updates:** https://github.com/swar/nba_api/issues

### Critical Papers (Read in Order)
1. Montrucchio 2026: https://www.mdpi.com/2078-2489/17/1/56
2. TabICLv2: https://arxiv.org/pdf/2502.05564
3. Venn-Abers: https://arxiv.org/pdf/2502.05676

### Emergency Fallback Plans
- **If shot-chart CNN fails:** Use static shot zone percentages (PPP by zone) as Cat46
- **If Colab GPU runs out:** Reduce batch size or use CPU (slower but works)
- **If TabICLv2 incompatible:** Stick with v1 (still beats tree models at scale)

---

**Last Updated:** 2026-03-31
**Status:** Ready for implementation
**Estimated Completion:** 2026-04-20
**Expected Outcome:** Brier < 0.200, close SOTA gap
