# Nomos42 — Structure Juridique & Holding French Tech

> Rédigé le 2026-04-03 | Droit français | Conseil: à valider avec un expert-comptable et un avocat

---

## Principe: Structure Holding Tri-Entités

La structure recommandée crée une séparation nette entre:
1. La propriété intellectuelle (Tech)
2. L'activité pariante capitalistique (Capital)
3. La gouvernance et la consolidation fiscale (Holdings)

```
┌─────────────────────────────────────────────┐
│         NOMOS42 HOLDINGS SASU               │
│         (Entité mère / Holding pure)        │
│         Capital: 1 000 € minimum            │
│         Actionnaire unique: Fondateur       │
└──────────────┬──────────────────────────────┘
               │  100%          100%
       ┌───────┴───────┐  ┌─────┴──────────┐
       │  NOMOS42 TECH │  │ NOMOS42 CAPITAL│
       │     SASU      │  │     SASU       │
       │  AI / SaaS    │  │  Fonds paris   │
       │  Capital: 1K€ │  │  Capital: 10K€ │
       └───────────────┘  └────────────────┘
```

---

## Entité 1: Nomos42 Holdings SASU

**Rôle**: Entité faîtière pure. Détient 100% de Tech et Capital. Aucune activité opérationnelle directe.

**Objet social**: Prise de participations, gestion d'actifs financiers, coordination stratégique entre filiales.

**Capital recommandé**: 1 000 € (minimum légal SASU). Apports en numéraire.

**Avantages du holding:**
- Régime mère-fille: dividendes remontés des filiales exonérés d'IS à 95% (article 216 CGI)
- Intégration fiscale possible si détention >95% (consolide les pertes de Capital avec les profits de Tech)
- Protection patrimoniale: le fondateur est isolé derrière deux couches de SASU
- Cession future facilitée: vendre Tech ou Capital sans toucher la structure globale

**Siège**: Domiciliation possible chez expert-comptable (~50€/mois) ou adresse personnelle.

**Coût de constitution**: ~150 € (greffe) + ~300 € (publication Journal Officiel via service en ligne). Total: ~450 €.

---

## Entité 2: Nomos42 Tech SASU

**Rôle**: Opère le SaaS NBA/Politique. Détient toute la PI. Emploie les développeurs (si embauche).

**Objet social**: Développement et commercialisation de logiciels d'intelligence artificielle appliqués à la prédiction sportive et à l'analyse de données de marché. Vente d'abonnements API, licences logicielles, et conseil en data science.

**Capital recommandé**: 1 000 € minimum. Mais augmenter à 10 000–50 000 € si on anticipe des contrats B2B significatifs (crédibilité client) ou une levée de fonds.

**Revenus:**
- Abonnements API (Free/Scout/Edge/Whale)
- Agent marketplace (30% commission)
- Licences modèles (Whale tier B2B)
- Prestations R&D (sous-traitance à Capital pour les modèles partagés)

**Propriété intellectuelle à assigner à Tech:**
- Algorithmes d'évolution génétique (6 îles HF, Karpathy loop)
- Feature engine v3.1-46cat (6 253 features raw)
- Code source: `features/engine.py`, `scripts/`, `hf-space/`
- Datasets historiques NBA (9 551 matchs entraînés)
- Marque "Nomos42" + logos
- Modèles entraînés (checkpoints TabICL, CatBoost, XGBoost, etc.)

**Acte d'apport/cession PI**: L'apport de la PI doit être formalisé par un acte écrit lors de la constitution ou via une cession ultérieure (valorisation PI recommandée: faire établir par un expert indépendant pour éviter redressement fiscal).

**Coût de constitution**: ~150 € greffe + ~300 € publication. Total: ~450 €.

---

## Entité 3: Nomos42 Capital SASU

**Rôle**: Gestion du bankroll virtuel/réel. Entité ring-fencée pour l'activité pariante.

**Objet social**: Gestion pour compte propre de portefeuilles sur marchés financiers légaux et plateformes de paris sportifs agréées. Développement de stratégies quantitatives de gestion des risques.

**Capital recommandé**: 10 000 € minimum pour crédibilité opérationnelle. Si expansion bankroll réel: augmenter capital au fur et à mesure.

**Séparation réglementaire:**
- Les paris sportifs à titre habituel pour compte propre ne sont pas réglementés en France comme une activité d'investissement (pas d'agrément AMF requis pour compte propre).
- Interdiction de gérer de l'argent de tiers sans agrément AMF (PSI). Capital gère uniquement les fonds du groupe.
- Si un jour gestion pour clients: agrément Conseiller en Investissements Financiers (CIF) ou Prestataire de Services d'Investissement (PSI).

**Flux inter-compagnies**: Capital paie Tech une redevance (royalty) pour l'utilisation des modèles. Taux: 15–25% des revenus de paris (à documenter par contrat inter-société et étude de prix de transfert simplifiée).

**Coût de constitution**: ~150 € greffe + ~300 € publication. Total: ~450 €.

**Fiscalité paris**: Les gains de paris sportifs sont imposables comme BIC (Bénéfices Industriels et Commerciaux) si activité habituelle. IS applicable (25% standard, 15% sur les 42 500 premiers euros pour les PME).

---

## Coûts de Constitution Résumés

| Entité | Greffe | Publication JAL | Capital | Total |
|--------|--------|----------------|---------|-------|
| Holdings | ~150 € | ~300 € | 1 000 € | ~1 450 € |
| Tech | ~150 € | ~300 € | 1 000–50 000 € | ~1 450–50 450 € |
| Capital | ~150 € | ~300 € | 10 000 € | ~10 450 € |
| **Total structure** | **~450 €** | **~900 €** | **~12 000 €** | **~13 350 €** |

Note: Publications JAL via INPI (service en ligne) ou prestataire (~150–350 € selon département). Utiliser Legalstart, Indy, ou Greffe direct pour minimiser les frais.

**Frais récurrents annuels:**
- Expertise-comptable: ~1 500–3 000 €/an pour 3 entités légères
- CFE (Cotisation Foncière des Entreprises): ~200–500 €/entité selon commune
- Assurance RC Pro (Tech): ~500–1 000 €/an

---

## Dispositifs d'Aide French Tech

### 1. CIR — Crédit d'Impôt Recherche

**Éligibilité Nomos42**: OUI. Fort dossier.

Critères légaux (art. 244 quater B CGI):
- Recherche fondamentale ou appliquée: **OUI** — amélioration de l'état de l'art en prédiction ML (SOTA Montrucchio 2026: Brier 0.199, nous à 0.21570, gap mesurable, approche scientifique documentée)
- Incertitude scientifique/technique: **OUI** — aucun chemin certain pour atteindre Brier < 0.20
- Démarche systématique: **OUI** — Karpathy autoresearch loop documenté, 15 itérations Kaggle, 6 îles d'évolution, 14 papiers analysés

**Taux CIR**: 30% des dépenses R&D jusqu'à 100M€ (puis 5% au-delà).

**Dépenses éligibles pour Nomos42 Tech:**
- Salaires chercheurs/ingénieurs (si embauche): 100% éligibles
- Amortissement matériel de recherche: GPU burst (Vast.ai $0.16/hr), Colab, Kaggle Pro
- Sous-traitance R&D: dépenses HF Spaces, API Claude (si documenté comme outil R&D)
- Veille technologique: jusqu'à 60 000 €/an (abonnements papiers, conférences)
- Frais de dépôt PI (brevets): 100% éligibles

**Action**: Tenir un carnet de bord R&D dès jour 1. Documenter chaque itération (date, hypothèse, résultat, Brier avant/après). Les fichiers `data/departments/council-*.json` et l'historique git sont d'excellentes preuves.

**Remboursement**: Le CIR est remboursable si l'entreprise est en déficit (cas probable la première année). Remboursement immédiat pour jeunes entreprises.

---

### 2. CII — Crédit d'Impôt Innovation

**Éligibilité**: OUI pour les PME.

- 20% des dépenses d'innovation (prototypes, produits nouveaux)
- Plafond: 400 000 € de dépenses (soit 80 000 € max de crédit)
- Dépenses éligibles: développement du dashboard, de l'API SaaS, des nouveaux algorithmes

CII est complémentaire au CIR: R&D pure → CIR; Développement produit → CII.

---

### 3. Jeune Entreprise Innovante (JEI)

**Critères** (art. 44 sexies-0 A CGI):
- PME < 8 ans d'existence: **OUI** (entreprise nouvelle)
- Dépenses R&D >= 15% des charges totales: **OUI** (en phase early stage, la quasi-totalité est de la R&D)
- Capital détenu par personnes physiques ou autres JEI: **OUI**

**Avantages JEI:**
- Exonération IS totale les 2 premiers exercices bénéficiaires, 50% les 3 suivants
- Exonération charges sociales patronales sur salaires chercheurs (CDI/CDD en R&D)

**Action**: Déposer la demande JEI auprès du centre des impôts lors de la première déclaration fiscale.

---

### 4. Bpifrance — Financement R&D

#### i-Nov (Innovation)
- **Montant**: 200 000 € à 5 M€
- **Nature**: Subvention 45% + prêt complémentaire
- **Éligibilité Nomos42**: Forte. Catégorie "Intelligence Artificielle et Data Science". Le gap mesurable vs SOTA, l'architecture multi-agents, et l'application verticale (prédiction sportive quantitative) sont des arguments solides.
- **Timeline**: Appel à projets continu. Dossier ~3 mois de préparation.

#### Prêt Croissance Innovation
- **Montant**: 200 000 € à 5 M€ (sans garantie)
- **Usage**: Financement du BFR, développement commercial, recrutement
- **Taux**: Compétitif, souvent en co-investissement avec un investisseur privé

#### French Tech Bourse (pour fondateurs)
- **Montant**: 30 000 € (aide personnelle au fondateur)
- **Critères**: Projet innovant, fondateur à temps plein, accord d'un investisseur ou incubateur
- **Action immédiate**: Candider à un incubateur partenaire Bpifrance (Station F, 50 Partners, Euratechnologies)

---

### 5. BPI Deeptech

**Critères d'éligibilité Deeptech (Nomos42 QUALIFIE):**

| Critère | Nomos42 |
|---------|---------|
| Algorithmes originaux non publiés | OUI — Karpathy autoresearch loop, évolution génétique multi-îles avec pollinisation croisée |
| Performance mesurable vs SOTA | OUI — Brier 0.21570 vs SOTA 0.199 (gap documenté, mesure objective) |
| Barrières à l'entrée techniques | OUI — 6 253 features, 9 551 matchs d'historique, 2 408 générations d'évolution |
| Équipe à compétence PhD-level | OUI si le fondateur a background technique démontrable |
| Propriété intellectuelle défendable | OUI — PI assignée à Tech, code propriétaire, datasets |

**Programme French Tech Deeptech:**
- Accompagnement dédié Bpifrance (référent Deeptech)
- Accès aux guichets de financement accélérés
- Label "Deeptech" valorisé lors des levées de fonds

**Démarche**: Prendre contact avec le bureau Bpifrance régional + remplir le formulaire de qualification Deeptech sur bpifrance.fr.

---

### 6. Aides Régionales

| Région | Programme | Montant | Notes |
|--------|-----------|---------|-------|
| Île-de-France | PM'Up | 50 000–300 000 € | PME ambitieuses, croissance internationale |
| Île-de-France | Tech'In | 75 000–300 000 € | Startups deep tech |
| Hauts-de-France | Pass Innovation | 30 000–80 000 € | Si basé dans la région |
| Auvergne-Rhône-Alpes | Innovation numérique | 10 000–100 000 € | Projets IA |
| Occitanie | Cap Dev | 30 000–200 000 € | Scale-up tech |

Note: Les aides régionales sont cumulables avec CIR/CII/BPI dans la limite des règles de minimis (200 000 € sur 3 ans pour aides "de minimis").

---

## Structure du Capital — Recommandations

### Phase 1 (Bootstrap, 2026)

```
Fondateur: 100% Holdings
Holdings détient: 100% Tech + 100% Capital
```

**Aucune dilution. Conservation totale du contrôle.**

Valoriser la PI technologique (feature engine, modèles, code) comme apport en nature dans Tech. Faire établir un rapport de commissaire aux apports si valorisation > 30 000 € (obligatoire légalement pour les apports en nature en SASU).

### Phase 2 (Amorçage, si levée)

Options de dilution recommandées:
- **BSPCE** (Bons de Souscription de Parts de Créateur d'Entreprise): instrument fiscal idéal pour intéresser les premiers employés sans dilution immédiate. Imposés à 30% (PFU) à la cession, vs 45%+ en salaire.
- **Pacte d'actionnaires** dès l'entrée du premier investisseur externe: droits de préférence (pre-emption), clause de drag-along, anti-dilution.

### Phase 3 (Série A, si expansion)

Investisseurs entrent au niveau Holdings ou directement dans Tech (selon strategy):
- Entrée dans Holdings: conserve la séparation Capital/Tech
- Entrée dans Tech: plus simple pour les VCs tech, isole Capital

---

## Calendrier de Constitution

| Semaine | Action | Coût |
|---------|--------|------|
| S1 | Rédiger les statuts des 3 SASU (modèle INPI ou avocat) | 0–500 € |
| S1 | Ouvrir 3 comptes bancaires séparés (Shine, Qonto, ou banque classique) | 0 € |
| S2 | Déposer les capitaux en banque + obtenir attestations de dépôt | 0 € |
| S2 | Publier les 3 annonces légales (JAL ou INPI en ligne) | ~900 € |
| S3 | Déposer les 3 K-bis au greffe | ~450 € |
| S3 | Immatriculation INSEE (SIRET) | 0 € |
| S4 | Contrat d'apport/cession PI vers Tech (avec évaluation) | 500–2 000 € si avocat |
| S4 | Contrat inter-sociétés Holdings/Tech/Capital (redevances, flux) | 500–1 500 € si avocat |
| S5 | Demande JEI auprès du SIE (Service des Impôts des Entreprises) | 0 € |
| S6 | Dépôt marque "Nomos42" à l'INPI | 190–250 € par classe |

**Total constitution: ~2 000–5 000 € (avec accompagnement professionnel minimal)**

---

## Risques et Points d'Attention

1. **Prix de transfert**: Les redevances de Capital à Tech doivent être documentées et "at arm's length" (prix de marché). Risque de requalification si prix anormalement bas ou haut.

2. **TVA**: Les services SaaS B2C à des clients UE sont soumis au régime OSS (One Stop Shop) dès 10 000 € de CA. S'enregistrer en avance.

3. **Réglementation paris**: Vérifier que Capital opère sur des plateformes agréées ANJ (Autorité Nationale des Jeux). L'activité de paris pour compte propre n'est pas réglementée, mais la frontière avec le conseil à des tiers est claire: ne pas franchir sans agrément.

4. **RGPD**: Les données de prédictions utilisateurs (bankrolls, paris) sont des données personnelles. Nommer un responsable de traitement, rédiger une politique de confidentialité, et s'assurer que Supabase (hébergement EU) respecte les obligations.

5. **Publication des comptes**: Les SASU déposent leurs comptes annuels au greffe. Possibilité de demander la confidentialité (entreprises < 350 salariés et < 10M€ CA).
