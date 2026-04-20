# Research Scan: tf-proposals-pol-options-overlay-2026-04-20


## problem
POL TF currently trades ETFs (SPY/TLT/GLD/XL*) directional only. Around volatility events (FOMC, CPI, jobs report, election nights) spot moves underprice the vol risk → options overlay captures both direction AND vol term-structure move.


## solution
Add 2 new POL TF personas + catalyst calendar + options-execution path. Reuses PQTF's 5-strategy engine (long_call/vertical_debit/iron_condor/straddle/butterfly).


## new_personas

- **PoliticalVolArb**: 
- **MacroDirectional**: 

## acceptance_criteria

- POL TF status returns 19 agents (not 17)
- catalyst_calendar.json refreshed daily with >= 30 forward events
- At least 3 option trades by pol-vol-1 in first 5 trading days
- Langfuse traces tagged fleet=pol-options
- Dashboard /political gains 'Options Overlay' section

## risks_and_mitigations

- **?**: 
- **?**: 
- **?**: 
- **?**: 

## phased_rollout

- **?**: 
- **?**: 
- **?**: 
- **?**: 