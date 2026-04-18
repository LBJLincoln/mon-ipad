---
name: diegetic panels research Apr 17
description: Research and proposal for in-world diegetic data panels in pixel-art trading floor; 20-panel catalog, fake-detect UX, zone layout, implementation approach
type: project
---

Proposal written 2026-04-17 at `/home/termius/mon-ipad/data/research/pixel-world-diegetic-panels-apr17.md`.

Top 5 SOTA refs: pablodelucca/pixel-agents, Stanford Smallville, AgentLens (arXiv 2402.08995), Factorio Display Panel (FFF-419), STONKS-9800.

Architecture decision: DOM-overlay-first (panels as absolute-positioned divs over PixiJS canvas). Panel frames as PixiJS Graphics drawn once at init. Data binding via single `WorldState` polled every 10s/60s.

Zone layout: A=Market (left), B=Model (center-left), C=Agent Desks (center), D=Cooperation (right), E=History (bottom).

20 panels catalogued (P01-P20). Min viable set = P01 + P04 + P06 + P10 + P12 + P20.

Fake-detect UX: CSS `static-noise` animation for NO_SIGNAL, amber STALE badge on age threshold, red border + SUSPECT watermark for identical/suspicious values, FROZEN indicator for unchanged values across polls.

**Why:** The existing pixel world has all data in a right-side panel (non-diegetic). Making fake/missing data visually obvious as "blank screens" accelerates debug and makes the system credible to outside observers.

**How to apply:** When nomos-lab asks about /world redesign or panel architecture, point to this proposal. DOM-overlay pattern is confirmed correct — do not recommend moving panel content into the PixiJS canvas.
