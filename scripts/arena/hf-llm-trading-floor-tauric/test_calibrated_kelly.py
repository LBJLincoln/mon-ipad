"""Unit tests for calibration-aware fractional Kelly (proposal #1, 2026-04-21).

We don't full-import app.py (it needs gradio + fastapi which aren't in CI).
Instead we extract the pure-stdlib helpers via AST isolation.

Run: python3 -m pytest scripts/arena/hf-llm-trading-floor/test_calibrated_kelly.py -q
"""
from __future__ import annotations

import ast
import json
import math
import os
import sys
import textwrap
import types
from pathlib import Path

import pytest


_APP_PATH = Path(__file__).parent / "app.py"


def _load_kelly_module() -> types.ModuleType:
    """Extract calibrated_kelly_fraction + ECE helpers from app.py into a
    standalone module by AST-splicing only the functions we need."""
    src = _APP_PATH.read_text()
    tree = ast.parse(src)
    wanted = {
        "calibrated_kelly_fraction",
        "get_agent_ece",
        "update_agent_calibration",
        "_conf_width_from_allocations",
        "_calib_load",
    }
    wanted_consts = {
        "_CALIB_DIR",
        "_CALIB_PATH",
        "_CALIB_WINDOW",
        "_CALIB_SEED_ECE",
        "_CALIB_CACHE",
    }
    picked: list[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in wanted:
            picked.append(node)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in wanted_consts:
                    picked.append(node)
                    break
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id in wanted_consts:
            picked.append(node)

    # Build minimal namespace: math, json, Path, Dict, List
    preamble = textwrap.dedent(
        """
        import math, json
        from pathlib import Path
        from typing import Dict, List, Optional
        """
    )
    body = "\n".join(ast.unparse(n) for n in picked)
    mod_src = preamble + "\n" + body
    mod = types.ModuleType("kelly_isolated")
    exec(compile(mod_src, "kelly_isolated", "exec"), mod.__dict__)
    return mod


@pytest.fixture(scope="module")
def kmod() -> types.ModuleType:
    return _load_kelly_module()


def test_floor_at_tiny_edge(kmod):
    assert kmod.calibrated_kelly_fraction(0.01, 0.15, 0.2) == 0.01


def test_cap_at_quarter_kelly(kmod):
    assert kmod.calibrated_kelly_fraction(1.0, 0.0, 1.0) == 0.25


def test_miscalibration_shrinks_fraction(kmod):
    good = kmod.calibrated_kelly_fraction(0.10, 0.02, 0.3)
    bad = kmod.calibrated_kelly_fraction(0.10, 0.40, 0.3)
    assert bad < good


def test_conf_width_widens_fraction(kmod):
    narrow = kmod.calibrated_kelly_fraction(0.10, 0.10, 0.05)
    wide = kmod.calibrated_kelly_fraction(0.10, 0.10, 0.80)
    assert wide > narrow


def test_sample_docstring_case(kmod):
    frac = kmod.calibrated_kelly_fraction(0.05, 0.10, 0.20)
    # 0.05 * 0.9 * sqrt(0.2) = 0.020124611797...
    assert abs(frac - 0.02012461) < 1e-5


def test_bad_inputs_return_floor(kmod):
    assert kmod.calibrated_kelly_fraction(None, None, None) == 0.01
    assert kmod.calibrated_kelly_fraction("bad", 0.1, 0.2) == 0.01


def test_ece_update_round_trip(kmod, tmp_path, monkeypatch):
    monkeypatch.setattr(kmod, "_CALIB_DIR", tmp_path)
    monkeypatch.setattr(kmod, "_CALIB_PATH", tmp_path / "calibration-rolling.json")
    kmod._CALIB_CACHE.clear()

    assert kmod.get_agent_ece("test-agent") == kmod._CALIB_SEED_ECE

    # Symmetric set: error magnitude = 0.3 on each -> ECE = 0.30
    for prob, outcome in [(0.7, 1), (0.7, 1), (0.3, 0), (0.3, 0)]:
        kmod.update_agent_calibration("test-agent", prob, outcome)
    assert abs(kmod.get_agent_ece("test-agent") - 0.30) < 1e-6

    # Persistence: blow away cache, force reload from disk
    kmod._CALIB_CACHE.clear()
    assert abs(kmod.get_agent_ece("test-agent") - 0.30) < 1e-6


def test_conf_width_helper_defaults_mid(kmod):
    assert kmod._conf_width_from_allocations([]) == 0.2
    assert kmod._conf_width_from_allocations([{"confidence": 0.7}]) == 0.2
    w = kmod._conf_width_from_allocations(
        [{"confidence": 0.6}, {"confidence": 0.8}, {"confidence": 0.5}]
    )
    assert abs(w - 0.3) < 1e-9
