# Test-matrix guide (Step 5)

The spy answers *what the market is running*. The matrix turns that into *what we will test next*, as a grid of
falsifiable cells, so the round's result is a lesson and not an opinion.

## Inputs (read all before writing a cell)

1. The synthesis of every relevant spy folder (and `_comparison-*.md` when there are several).
2. The user's **kill list** (`kill-list.md`) and **winners** (`winners.md`) for the product. Killed angles/hooks
   never come back without a new, stated reason. Winners come back as the *asset* (same copy + image), not as a
   rewritten angle.
3. The product's real facts and compliance limits (claims, guarantees, who can legitimately speak as an authority).
4. The user's downstream generator rules if one exists (e.g., a long-form builder's matrix phase, awareness-level
   definitions, character ranges, naming convention). **Its rules win over this guide.** In that case this step
   produces the *proposal* its matrix phase starts from; it does not replace that phase or its gates.

## Shape

`N angles × M awareness levels × K image variations`. Default 5 × 3 × 3 (15 copies, 45 images) for long-form
static; one copy per cell, the K images are the only thing that changes inside a cell.

- **Angles (rows):** 3-6. Each must be backed by spy evidence (duplications, rank, several pages running it) or
  be an explicit gap bet (nobody runs it, and why that could be an opportunity). Mark gap bets as such.
- **Awareness levels (columns):** structural, not cosmetic. Default: A = opens on a lived scene, mechanism late;
  B = opens on what already failed, mechanism explains the failure; C = opens on the mechanism as news. Test: the
  first three lines of A, B and C of the same angle must not be swappable.
- **Image variations (K):** one variable only (e.g., ethnicity, age band, setting), fixed across the whole round.

## Per cell

| Field | Content |
|---|---|
| `id` | `B{n}-{level}` (images `B{n}-{level}{k}`); the ad names in Ads Manager must contain it: validation depends on it |
| `angle`, `level` | Names |
| `hook` | Anchor hook (reference, not final copy) |
| `persona` / `page` | Narrator and the page that will run it (first-person copy needs a congruent persona page) |
| `mechanism_position` | late / after failed solution / opening |
| `evidence` | Spy codes it lateralises from (`Acme_013, Acme_031`) and the signal (duplicates, rank, pages) |
| `change_vs_competitor` | What we do differently (claim we can't make, voice, proof, offer) |
| `lock` | What is forbidden in this cell (claims, lookalikes, fake credentials, killed hooks) |
| `chars_target` | e.g., `[9000, 14000]`, from the competitor's caption length for that angle and the user's floor |
| `hypothesis` | One sentence: what a win or a loss here would teach |
| `status` | `planned` |

## Files

- `test-matrix.md`: human-readable grid (compact angles × levels table first, then one section per cell, then
  "why this matrix" with the evidence and 2-3 round-level hypotheses, then decisions the user must make).
- `test-matrix.json`: the same, machine-readable:

```json
{
  "test": "T102",
  "product": "ACME",
  "destination": "quiz",
  "created": "2026-09-24",
  "spy_sources": ["spy/Acme", "spy/Globex"],
  "thresholds": {"target_cpa": 45, "min_spend": 150, "min_conversions": 3},
  "cells": [
    {"id": "B1-A", "angle": "Flash-forward", "level": "A", "hook": "She noticed before I said a word",
     "persona": "Man 58, 1st person", "page": "Persona page", "mechanism_position": "late",
     "evidence": ["Acme_013 (4 ads)", "Acme_003"], "change_vs_competitor": "No size claim",
     "lock": ["cure claims", "size claims"], "chars_target": [9000, 14000],
     "images": ["B1-A1", "B1-A2", "B1-A3"], "copy_file": "", "hypothesis": "…", "status": "planned"}
  ]
}
```

`validate_round.py` (Step 6) reads this file (or a long-form builder's `tracking/batches.json`) and updates each
cell's `status` to `winner`, `killed`, `keep_testing` or `inconclusive`.

## Present and lock

Show the compact table, the hypotheses and the open decisions, and ask for approval. After the round starts being
written, the matrix does not change: changing a cell mid-round destroys the only thing the round produces, its
reading.
