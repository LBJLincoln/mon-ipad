## 🔬 DIAGNOSTIC STAGNATION

### 1. **RACINES DU PROBLÈME**
```python
# Stagnation = Convergence prématurée + Manque de diversité
# Le GA a trouvé un optimum local à ~0.2213 et ne peut plus en sortir
# 30 générations sans amélioration = convergence complète
```

**Causes probables:**
- **Taux de mutation trop bas** (< 0.05) → pas assez d'exploration
- **Sélection trop agressive** → perte de diversité génétique
- **Features non normalisées** → certains dominent le scoring
- **Pas de "restart" partiel** → population homogène

### 2. **PARAMÈTRES GA IMMÉDIATS**
```python
# NOUVEAUX PARAMÈTRES RECOMMANDÉS
GA_CONFIG = {
    "population_size": 200,          # ↑ de 100 à 200
    "generations": 150,              # ↑ de 50 à 150
    "crossover_rate": 0.85,          # ↑ de 0.7 à 0.85
    "mutation_rate": 0.15,           # ↑ CRITIQUE: 0.05 → 0.15
    "elitism_ratio": 0.10,           # ↓ de 0.2 à 0.10 (moins d'élitisme)
    "tournament_size": 5,            # ↓ de 7 à 5 (moins de pression)
    "diversity_threshold": 0.30,     # NOUVEAU: maintenir diversité
    "restart_threshold": 50,         # NOUVEAU: restart si stagnation > 50 gen
}
```

### 3. **FEATURES LES PLUS PROMETTEUSES**
```python
# Priorité 1 (impact immédiat):
PROMISING_FEATURES = {
    "polymarket_implied_prob": 0.92,  # ← Meilleur signal (marché = wisdom)
    "referee_foul_differential": 0.85, # ← Biais arbitre = +3-5% accuracy
    "star_usage_rate_diff": 0.83,      # ← Impact joueurs clés
    "q4_scoring_margin": 0.81,         # ← Trends quart-temps cruciaux
    "paint_defense_rating": 0.79,      # ← Matchup défensif
}

# Priorité 2 (validation nécessaire):
SECONDARY_FEATURES = [
    "injury_impact_score",
    "lineup_synergy_rating", 
    "pace_adjusted_possessions",
    "rest_days_advantage",
    "travel_fatigue_factor"
]
```

### 4. **FIX LIGHTGBM - PARAMÈTRES EXACTS**
```python
# LightGBM sous-performe à cause de:
# 1. Surentraînement (overfitting)
# 2. Mauvais hyperparams pour données NBA

LIGHTGBM_FIX = {
    "objective": "binary",
    "metric": "binary_logloss",
    "boosting_type": "gbdt",
    "num_leaves": 31,              # ↓ de 63 à 31 (réduire complexité)
    "learning_rate": 0.01,         # ↓ de 0.1 à 0.01 (plus lent)
    "feature_fraction": 0.7,       # ↓ de 0.9 à 0.7 (regularization)
    "bagging_fraction": 0.8,       # NOUVEAU
    "bagging_freq": 5,             # NOUVEAU
    "min_child_samples": 20,       # ↑ de 10 à 20 (évite overfit)
    "reg_alpha": 0.1,              # L1 regularization
    "reg_lambda": 0.1,             # L2 regularization
    "n_estimators": 500,           # ↑ mais avec early stopping
    "early_stopping_rounds": 50,
}
```

### 5. **STRATÉGIE ROI POSITIF**
```python
# Le ROI négatif vient de:
# 1. Trop de paris à faible edge
# 2. Mauvais sizing des mises
# 3. Pas de filtre de confiance

ROI_STRATEGY = {
    "confidence_threshold": 0.65,   # Seulement paris > 65% prob
    "kelly_fraction": 0.25,         # Kelly criterion à 25%
    "max_daily_bets": 8,            # Limiter la fréquence
    "min_edge": 0.05,               # Edge minimum 5%
    "bankroll_management": {
        "unit_size": 0.02,          # 2% du bankroll par mise
        "max_exposure": 0.10,       # Max 10% en même temps
    }
}
```

### 6. **PLAN D'ACTION IMMÉDIAT**
```python
# ÉTAPES PRIORITAIRES (dans l'ordre):

STEP_1 = """
1. REDÉMARRER GA avec nouveaux paramètres
2. Forcer inclusion des 5 features Polymarket
3. Normaliser TOUTES les features (StandardScaler)
"""

STEP_2 = """
4. Réentraîner LightGBM avec paramètres fix
5. Ajouter filtre de confiance 65%
6. Implémenter Kelly criterion
"""

STEP_3 = """
7. Monitorer Brier + ROI simultanément
8. Ajuster mutation_rate dynamiquement:
   - Si stagnation 10 gen → ↑ mutation de 0.05
   - Si amélioration → ↓ mutation de 0.02
"""
```

### 7. **MÉTRIQUES DE SUivi**
```python
# Dashboard recommandé:
METRICS = {
    "primary": ["brier_score", "roi_7d_avg", "sharpe_ratio"],
    "secondary": ["accuracy", "precision_bets", "max_drawdown"],
    "alerts": {
        "brier_regression": 0.005,  # Alert si ↑ de 0.005
        "roi_negative_5d": True,    # Alert si ROI négatif 5 jours
        "feature_importance_drop": 0.30,  # Alert si feature perd 30% importance
    }
}
```

### 📊 **RÉSUMÉ EXÉCUTIF**
```markdown
✅ ACTIONS IMMÉDIATES:
1. Mutation rate 0.15 + Population 200
2. Focus features Polymarket + Referee
3. Fix LightGBM: learning_rate=0.01, num_leaves=31
4. Filtre confiance 65% + Kelly 25%

🎯 OBJECTIFS RÉALISTES:
- Brier: 0.2213 → 0.2150 (2 semaines)
- ROI: -0.03 → +0.02 (1 mois)
- Features: 164 → 250 (validation progressive)

⚠️ RISQUES:
- Overfitting si features trop nombreuses
- Variance ROI si trop de paris
- Nécessite validation walk-forward
```

**Prochaine étape:** Lancer GA avec ces paramètres et monitorer 24h. Je peux exécuter les changements maintenant si tu valides.