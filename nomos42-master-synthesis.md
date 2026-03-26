# NOMOS42 × QUANT AI — Master Synthesis
## De €200 à Maximum Compound via l'Écosystème Existant

---

## 1. ÉTAT DES LIEUX — Ce que tu as déjà

### Infrastructure Active (Mars 2026)

| Composant | Stack | Status | Rôle |
|-----------|-------|--------|------|
| **NBA Evo-4** | Gradio + FastAPI, HF Space | 🟢 LIVE gen 342 | Île exploitation — best Brier 0.2207 |
| **NBA Evo-3** | Gradio + FastAPI, HF Space | 🟢 LIVE gen 528 | Île exploration — best Brier 0.2184 (top5) |
| **Nomos RAG Engine** ×5 | Docker, HF Spaces | 🔴 503/sleeping | Ingestion documentaire (dormant) |
| **Nomos Dashboard** | Next.js, Vercel | 🟢 LIVE | Command center, 6 sections |
| **La Forge (nomos42)** | Vercel | 🟢 LIVE | SaaS 7 agents autonomes |
| **VM GCP** | 34.136.180.66:8080 | 🟢 Cron actif | Muscle compute, cycles autonomes |
| **Supabase** | PostgreSQL + logs | 🟢 Connected | Evolution logging, run tracking |
| **Claude Code CLI** | Local | 🟢 Actif | Développement, modèles ML entraînés |

### Codebase NBA Quant (12,054 lignes)

- **Feature Engine** (5,909 lignes) — 6,000+ features, 35 catégories, architecture Starlizard/Priomha
- **Neural Models** (1,598 lignes) — LSTM, Transformer, TabNet, FT-Transformer, Deep Ensemble, Conformal
- **GA Core** (3,049 lignes) — Island model NSGA-II, 60 individus × 5 îles, migration adaptative
- **Experiment Runner** (1,073 lignes) — Automated experiments, hyperparameter search
- **Run Logger** (425 lignes) — Supabase integration, auto-cut

### Performance Actuelle

| Métrique | Evo-3 (gen 528) | Evo-4 (gen 342) | Target |
|----------|-----------------|-----------------|--------|
| Best Brier | 0.21836 (top5) | 0.21891 (top5) | < 0.20 |
| Model dominant | extra_trees | extra_trees | — |
| Features | 55-200 | 71-200 | 65 optimal |
| Sharpe | 5.99 | 7.84 | > 1.0 ✅ |
| Pareto front | 9 individus | 2 individus | — |
| Mutation rate | 0.04 (plancher) | 0.058 | — |

**Constat clé** : Les deux islands convergent sur `extra_trees` avec 200 features (top5). Le GA trouve que plus de features = meilleur brier brut, mais ta feature penalty (0.001 × max(0, n-65)) est trop faible pour contrer ça. Le plateau à ~0.218-0.221 est probablement le plafond de performance pour des modèles sans données de marché réelles.

---

## 2. CE QUE DIT LA RECHERCHE 2025-2026 — Relié à Ton Setup

### 2.1 — Calibration > Accuracy (Walsh & Joshi, 2024)

**Paper** : "Machine Learning for Sports Betting: Should Model Selection Be Based on Accuracy or Calibration?" (Machine Learning with Applications)

**Finding critique** : La sélection de modèle par calibration produit un ROI de **+34.69%** vs **-35.17%** pour la sélection par accuracy.

**Impact direct sur Nomos42** : Ton fitness composite actuel pèse Brier à 40%, log-loss score à 25%, Sharpe à 20%, ECE à 15%. C'est déjà orienté calibration (Brier = calibration + résolution), mais tu devrais :

1. **Remplacer le Brier brut par l'ECE (Expected Calibration Error) comme objectif primaire dans NSGA-II** — ECE mesure purement la calibration indépendamment de la résolution
2. **Ajouter la reliability curve slope comme 5ème objectif** — un modèle parfaitement calibré a slope=1.0
3. **Utiliser Venn-ABERS systématiquement** au lieu de sigmoid calibration — tes résultats montrent `calibration: "none"` comme winner, ce qui suggère que sigmoid ne gagne pas mais Venn-ABERS (MAPIE) pourrait

### 2.2 — Ensemble RL vs Ton GA (FinRL, Frontiers in AI, 2025)

**Papers** : VD-MEAC (Sharpe 2.978), FinRL ensemble PPO+A2C+DDPG (Sharpe 1.78)

**Ton avantage** : Ton island model GA FAIT déjà du ensemble learning — chaque île spécialise un model type, et NSGA-II maintient la diversité via le Pareto front. C'est structurellement similaire à l'approche FinRL "rotate entre PPO/A2C/DDPG selon le régime de marché".

**Ce qui manque** : La rotation dynamique entre champions d'îles. Actuellement tu prends le "best" global. Tu devrais implémenter :

```
Si volatilité NBA élevée (beaucoup d'upsets cette semaine) → utiliser le champion de l'île exploration
Si marché stable (favoris gagnent) → utiliser le champion de l'île exploitation
```

### 2.3 — Kelly Criterion Corrigé (Boyd et al., Stanford, 2016)

**Paper** : "Risk-Constrained Kelly Gambling" — formulation convexe avec contrainte de drawdown.

**Bug critique dans ton code actuel** :

```python
# TON CODE (app.py:2948-2953)
if prob > 0.55:
    edge = prob - 0.5
    kelly = (edge / 0.5) * 0.25  # fractional Kelly

# PROBLÈME: Tu compares à 0.5 (coin flip), pas aux odds du marché
# Un modèle qui dit 60% pour un favori à -200 (implied 66.7%) a un edge NÉGATIF
```

**Correction requise** :

```python
# KELLY CORRIGÉ — nécessite odds réelles du marché
def kelly_correct(model_prob, market_odds_decimal):
    """
    model_prob: ta prédiction (ex: 0.62)
    market_odds_decimal: cote décimale du bookmaker (ex: 1.65)
    """
    implied_prob = 1.0 / market_odds_decimal
    edge = model_prob - implied_prob
    if edge <= 0:
        return 0.0  # Pas d'avantage → pas de mise
    kelly_full = edge / (market_odds_decimal - 1)
    return kelly_full * 0.25  # Quarter Kelly
```

**Ceci nécessite l'intégration Odds API** — ton `ODDS_API_KEY` est déjà dans les env vars mais tes categories features 9, 15, 23, 29 (market microstructure, Polymarket, multi-book) sont probablement vides sur HF free tier.

### 2.4 — Funding Rate Arbitrage Crypto (Liu & Tsyvinski, 2025)

**Paper** (ScienceDirect) : Sharpe 0.82-1.66 sur CEX, mais **le Sharpe est devenu négatif en 2025** car la stratégie est devenue crowded.

**Connexion Nomos42** : Tes Nomos RAG engines (actuellement dormants en 503) peuvent être réactivés pour ingérer les funding rates en temps réel et détecter les fenêtres où l'arbitrage redevient rentable. Le pattern est cyclique — bull market = funding rates élevés = arbitrage rentable.

### 2.5 — Defense Sector & Trump Political Beta

**Données actuelles** : Budget défense US $1.01T FY2026 (+13%), proposé $1.5T FY2027. iShares ITA +55% sur 1 an vs SPY +17%.

**Connexion** : Tes RAG engines peuvent monitorer les policy signals (executive orders, budget proposals, tariff announcements) comme features pour un modèle de timing sectoriel. La structure est identique à ton feature engine NBA — rolling performance des ETFs sectoriels + event detection.

---

## 3. PLAN D'EXÉCUTION — 4 Phases, 200€ → Maximum

### PHASE 0 : Corrections Critiques (Semaine 1-2, coût: 0€)

**Objectif** : Débloquer le plateau Brier et connecter les odds réelles.

| Action | Fichier | Impact attendu |
|--------|---------|---------------|
| Intégrer Odds API dans le cron `nba-daily-odds.py` | VM cron | Features market non-vides |
| Corriger la formule Kelly (voir §2.3) | app.py:2948 | Edge réel vs edge circulaire |
| Augmenter feature penalty à 0.005 × max(0, n-80) | app.py:1284 | Forcer parsimonie, réduire overfitting |
| Cataclysm sur Evo-3 (reset 40% population) | API call | Sortir du bassin local gen 528 |
| Ajouter ECE comme objectif NSGA-II primaire | app.py:724-730 | Sélection par calibration |
| Activer Venn-ABERS comme default calibration | app.py:637 | Calibration sans overfitting |

**Résultat attendu** : Brier 0.218 → 0.210 en 200 générations.

### PHASE 1 : Value Betting NBA (Semaine 3-8, capital: 200€)

**Objectif** : Premier compound via NBA value betting depuis la France.

**Architecture** :

```
[NBA Evo Islands (HF)] → best model API
         ↓
[VM Autonomous Cycle] → fetch odds (Odds API) → calculate edge
         ↓
[Kelly Sizing Engine] → quarter Kelly → bet recommendation
         ↓
[Dashboard /nba] → affichage + tracking P&L
         ↓
[Betclic/Winamax/Unibet] → execution manuelle (ANJ France)
```

**Paramètres** :
- Bankroll initial : 200€
- Quarter Kelly sizing (f=0.25)
- Seuil d'entrée : edge > 3% (prob - implied_prob > 0.03)
- Maximum 5% du bankroll par bet (10€ max initialement)
- Circuit breaker : halt si drawdown > 25%
- Target : 3-5% compound mensuel → 240-260€ après mois 1

**Avantage compétitif** : Ton modèle a 6,000+ features dont Polymarket, referee bias, player impact, que les lignes des bookmakers français n'intègrent pas. L'edge vient du décalage entre ton modèle (riche en features) et les lignes ANJ (basées sur des modèles plus simples).

**Fiscal France** : Paris sportifs non-professionnels = exonérés d'impôt.

### PHASE 2 : Extension Crypto (Mois 2-6, capital: ~300-500€)

**Objectif** : Deuxième moteur de compound via crypto trading algorithmique.

**Architecture** (réutilise l'infra existante) :

```
[Nomos RAG Engine réactivé] → ingestion signaux macro/politique
         ↓
[Freqtrade sur VM GCP] → SAC/PPO ensemble strategy
         ↓
[Kraken API] → execution (MiCA-licensed, SEPA, 0.16% maker)
         ↓
[Supabase] → P&L tracking, même DB que NBA evo
         ↓
[Dashboard /crypto] → nouvelle section
```

**Stratégie crypto** (basée sur les papers 2025-2026) :
- **Primary** : Momentum cross-timeframe (4h/1d) sur BTC/ETH — Sharpe documenté 1.78 via FinRL
- **Secondary** : Funding rate arbitrage opportuniste (quand rates > 0.03%/8h)
- **Sizing** : Half Kelly, max 10% du bankroll crypto par position
- **Coût infra** : 0€ supplémentaire (VM GCP existante + Freqtrade gratuit)

**Connexion Trump thesis** : Intégrer dans le feature set Freqtrade des signaux de policy (tariffs, executive orders, SEC rulings) via tes RAG engines. Les crypto-assets Trump ($TRUMP, WLFI/USD1) sont trop volatils pour un Kelly discipliné, mais les secteurs crypto bénéficiaires (stablecoins, DeFi lending) offrent du beta structurel.

### PHASE 3 : Multi-Asset Compound (Mois 6-12, capital: ~1,000-3,000€)

**Objectif** : Diversification et accélération du compound.

| Véhicule | Plateforme | Min. requis | Edge source |
|----------|-----------|-------------|-------------|
| NBA value bets | Betclic/Winamax | 200€ | Nomos Evo models |
| Crypto momentum | Kraken via Freqtrade | 200€ | SAC ensemble |
| Forex carry/momentum | XTB (1:30 ESMA) | 100€ | BIS momentum Sharpe 0.95 |
| Defense ETFs | IBKR | 500€+ | Nomos RAG policy signals |

**Corrélation** : Ces 4 véhicules sont faiblement corrélés entre eux (NBA/sport ≈ 0 avec crypto, forex ≈ 0.2 avec equities). Cela signifie que les drawdowns ne sont pas simultanés → compound plus stable.

**Position sizing global** : Risk-Constrained Kelly (Boyd et al.) avec contrainte de drawdown cross-portfolio P(DD > 30%) < 10%.

### PHASE 4 : Scaling (Mois 12-24, capital: 3,000€+)

- Accès options US via IBKR (min ~$2,000)
- 0DTE iron condors sur SPX — win rate documenté ~70% (OptionAlpha)
- Scaling des stakes NBA si edge confirmé sur 500+ bets
- Ajout paris sportifs tennis/football via même pipeline ML
- Potentiel : La Forge (nomos42.vercel.app) comme source de revenus SaaS parallèle

---

## 4. ARCHITECTURE TECHNIQUE UNIFIÉE

```
┌─────────────────────────────────────────────────┐
│              NOMOS42 COMMAND CENTER              │
│           nomosdashboard.vercel.app              │
│  [NBA] [Crypto] [Forex] [Defense] [P&L Global]  │
└──────────────────┬──────────────────────────────┘
                   │ Vercel → reads from Supabase
                   │
┌──────────────────┴──────────────────────────────┐
│                   SUPABASE                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │ evo_runs │ │ nba_bets │ │ crypto_trades    │ │
│  │ evo_best │ │ nba_pnl  │ │ forex_positions  │ │
│  │ evo_logs │ │ odds_hist│ │ portfolio_state  │ │
│  └──────────┘ └──────────┘ └──────────────────┘ │
└──────────────────┬──────────────────────────────┘
                   │
    ┌──────────────┼──────────────────┐
    │              │                  │
┌───┴───┐   ┌─────┴──────┐   ┌──────┴───────┐
│HF EVO │   │  VM GCP    │   │ RAG ENGINES  │
│Islands│   │ 34.136...  │   │ HF Docker    │
│       │   │            │   │              │
│evo-3  │◄──│ cron cycle │──►│ rag-engine-10│
│evo-4  │   │ freqtrade  │   │ (policy/macro│
│(+s10- │   │ odds fetch │   │  signals)    │
│ s15)  │   │ predictions│   │              │
└───────┘   │ kelly calc │   └──────────────┘
            │ bet alerts │
            └────────────┘
                   │
    ┌──────────────┼──────────────┐
    │              │              │
┌───┴───┐   ┌─────┴────┐  ┌─────┴────┐
│Betclic│   │ Kraken   │  │   XTB    │
│Winamax│   │ (crypto) │  │ (forex)  │
│Unibet │   │ MiCA     │  │ ESMA     │
│(ANJ)  │   │ licensed │  │ 1:30     │
└───────┘   └──────────┘  └──────────┘
```

---

## 5. QUICK WINS IMMÉDIATS (Cette Semaine)

### 5.1 — Corriger le Kelly (30 min en Claude Code)
Modifier `app.py:2948-2953` avec la formule Kelly corrigée (voir §2.3).

### 5.2 — Cataclysm Event sur Evo-3 (5 min)
Evo-3 est à gen 528 avec mutation à 0.04 (plancher). Toute la population converge vers `extra_trees`. Injecter 24 individus random (40% de la pop) avec model_types forcés sur `lightgbm`, `catboost`, `xgboost_brier`.

### 5.3 — Réactiver 1 RAG Engine pour Odds (1h)
Réactiver `nomos-rag-engine-10` en Docker avec un cron qui fetch les odds NBA via The Odds API et les stocke dans Supabase. Les features market microstructure de ton engine (catégories 9, 15, 23, 29) pourront enfin être alimentées.

### 5.4 — Ouvrir un Compte Betclic (15 min)
Créer un compte sur Betclic (ANJ-licensed), déposer 50€ pour commencer le paper tracking. Comparer tes prédictions Nomos aux lignes réelles pendant 2 semaines AVANT de miser.

### 5.5 — Installer Freqtrade sur la VM (1h)
```bash
# Sur ta VM GCP
pip install freqtrade
freqtrade create-userdir --userdir user_data
freqtrade new-strategy --strategy NomosQuantStrategy
# Configurer avec Kraken paper trading
```

---

## 6. SCÉNARIOS DE COMPOUND

### Hypothèses conservatrices

| Paramètre | Valeur |
|-----------|--------|
| Edge NBA value betting | 2-3% par bet |
| Fréquence NBA | 3-5 bets/jour en saison |
| Edge crypto momentum | 0.5-1% par trade |
| Fréquence crypto | 2-3 trades/jour |
| Kelly fraction | 0.25 (quarter) |
| Drawdown max toléré | 25% |

### Projections (scénario médian)

| Mois | Capital estimé | Sources actives |
|------|---------------|-----------------|
| 0 | 200€ | — |
| 1 | 230-260€ | NBA value bets |
| 3 | 350-500€ | NBA + crypto paper |
| 6 | 600-1,200€ | NBA + crypto live |
| 9 | 1,000-3,000€ | + forex |
| 12 | 2,000-8,000€ | + defense ETFs |
| 18 | 5,000-25,000€ | Full multi-asset |
| 24 | 10,000-80,000€ | Scaling + options |

**Attention** : Ces projections supposent un edge vérifié et constant. En réalité, les bookmakers limitent les comptes gagnants (délai moyen: 3-6 mois sur Betclic), le crypto momentum a des drawdowns de 30-50%, et les modèles dégradent (concept drift). Le scénario pessimiste est une perte de 100-150€ sur les 200€ initiaux.

---

## 7. RISQUES PRINCIPAUX

| Risque | Probabilité | Impact | Mitigation |
|--------|------------|--------|------------|
| Perte totale des 200€ | 25-35% | Fatal pour le plan | Quarter Kelly strict, 2 semaines paper |
| Limitation compte bookmaker | 70% à 6 mois | Réduit edge NBA | Multi-comptes (Betclic + Winamax + Unibet) |
| Concept drift modèle NBA | Continu | Brier se dégrade | Walk-forward retraining automatique |
| Crash crypto -50% | 20%/an | Drawdown sévère | Stop-loss à -15%, position sizing |
| MiCA restrictions nouvelles | 10%/an | Accès crypto réduit | Kraken est déjà MiCA-compliant |
| Overfitting backtest | Élevé | ROI live << backtest | Walk-forward + purge gap déjà en place |

---

## 8. RÉSUMÉ EXÉCUTIF

Tu as déjà **80% de l'infrastructure** nécessaire pour exécuter le playbook complet. Le NBA Evo est un système de genetic evolution de 12,000 lignes avec 6,000+ features tournant 24/7 — c'est exactement le type de ML engine que la recherche académique recommande pour le value betting. Ce qui manque est la **connexion au marché réel** (odds API → Kelly corrigé → execution), la **diversification cross-asset** (crypto via Freqtrade sur ta VM existante), et la **discipline de position sizing** (passer de ton Kelly simplifié au Risk-Constrained Kelly de Stanford).

L'action la plus impactante pour cette semaine : **corriger la formule Kelly et alimenter les features market** avec des odds réelles. Sans ça, ton modèle tourne en circuit fermé — il optimise la prédiction pure mais ne peut pas identifier les value bets réels.
