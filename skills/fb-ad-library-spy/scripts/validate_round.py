# -*- coding: utf-8 -*-
"""
FB Ad Library Spy — validate a test round and update the kill list
==================================================================
Closes the loop  spy → matrix → round → **validation** → kill list / winners → next spy.

Input
  --matrix   test-matrix.json written in Step 5 (or a long-form builder's
             tracking/batches.json: Portuguese keys angulo/nivel/imagens are accepted)
  --results  the ad-level performance export of the round (Meta Ads Manager CSV/XLSX,
             Triple Whale, Motion… anything with an ad-name column + spend + conversions)

Each result row is matched to a matrix cell by finding the cell id (e.g. "B3-A")
and, when present, the image variant (e.g. "B3-A2") inside the ad name, so the
round's naming convention must carry the cell id, e.g. "MK BR-BB T102-B3-A2".

Verdict per cell (all its image variants summed) and per image variant:
  inconclusive  spend < --min-spend  (not enough money to read)
  winner        conversions >= --min-conversions and CPA <= --target-cpa
  killed        spend >= --min-spend and (0 conversions or CPA > --kill-multiple × target)
  keep_testing  everything in between

Output (next to the matrix unless --out is given)
  round-results.md    table per cell and per image, verdicts, what to scale, what dies
  test-matrix.json    statuses updated in place (winner / killed / keep_testing / inconclusive)
  kill-list.md        appended: killed cells with angle, level, hook, files and numbers
  winners.md          appended: winning ASSETS (copy file + best image), not angle labels,
                      because what scales is that copy with that image

Usage
  python validate_round.py --matrix T102/test-matrix.json --results export.csv \
      --target-cpa 45 --min-spend 150 --min-conversions 3 \
      --kill-list brand/kill-list.md --winners brand/winners.md
"""

import argparse
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

COLS = {  # first match wins, case-insensitive substring match on the header
    "name": ["ad name", "nome do anúncio", "nome do anuncio", "ad_name", "creative", "name"],
    "spend": ["amount spent", "valor usado", "spend", "cost", "investimento", "gasto"],
    "conversions": ["purchases", "compras", "conversions", "results", "resultados", "orders", "vendas"],
    "revenue": ["purchase conversion value", "valor de conversão", "revenue", "receita", "sales"],
    "impressions": ["impressions", "impressões", "impressoes"],
    "clicks": ["link clicks", "cliques no link", "outbound clicks", "clicks", "cliques"],
}


def _num(v) -> float:
    if v in (None, ""):
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d,.\-]", "", str(v))
    if s.count(",") and s.count("."):          # 1.234,56 or 1,234.56
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif s.count(","):
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def load_results(path: Path) -> list[dict]:
    if path.suffix.lower() in (".xlsx", ".xls"):
        from openpyxl import load_workbook
        ws = load_workbook(path, read_only=True, data_only=True).active
        rows = list(ws.iter_rows(values_only=True))
        header = [str(h or "") for h in rows[0]]
        return [dict(zip(header, r)) for r in rows[1:]]
    with open(path, encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        return list(csv.DictReader(f, dialect=dialect))


def map_columns(header: list[str], overrides: dict) -> dict:
    found = {}
    for key, candidates in COLS.items():
        if overrides.get(key):
            found[key] = overrides[key]
            continue
        low = {h: h.lower() for h in header}
        found[key] = next((h for c in candidates for h, l in low.items() if c in l), None)
    if not found["name"] or not found["spend"] or not found["conversions"]:
        sys.exit(f"Could not find ad-name/spend/conversions columns in {header}. "
                 f"Pass --col-name / --col-spend / --col-conversions.")
    return found


def load_matrix(path: Path) -> tuple[dict, list[dict]]:
    m = json.loads(path.read_text(encoding="utf-8"))
    cells = m.get("cells") or m.get("batches") or []
    for c in cells:  # accept the long-form builder's Portuguese schema
        c.setdefault("angle", c.get("angulo", ""))
        c.setdefault("level", c.get("nivel", ""))
        c.setdefault("images", c.get("imagens", []))
        c.setdefault("hook", c.get("gancho", c.get("gancho_referencia", "")))
    return m, cells


def verdict(spend, conv, a) -> str:
    cpa = spend / conv if conv else None
    if spend < a.min_spend:
        return "inconclusive"
    if conv >= a.min_conversions and cpa is not None and cpa <= a.target_cpa:
        return "winner"
    if conv == 0 or (cpa is not None and cpa > a.kill_multiple * a.target_cpa):
        return "killed"
    return "keep_testing"


def main():
    ap = argparse.ArgumentParser(description="Validate a test round and update kill list / winners")
    ap.add_argument("--matrix", required=True)
    ap.add_argument("--results", required=True)
    ap.add_argument("--target-cpa", type=float, required=True, help="CPA that makes a cell a winner")
    ap.add_argument("--min-spend", type=float, required=True, help="Spend floor below which nothing is read")
    ap.add_argument("--min-conversions", type=int, default=3)
    ap.add_argument("--kill-multiple", type=float, default=2.0, help="Kill when CPA > this × target")
    ap.add_argument("--kill-list", help="kill-list.md to append to (default: next to the matrix)")
    ap.add_argument("--winners", help="winners.md to append to (default: next to the matrix)")
    ap.add_argument("--out", help="Folder for round-results.md (default: next to the matrix)")
    ap.add_argument("--dry-run", action="store_true", help="Write round-results.md only")
    for k in COLS:
        ap.add_argument(f"--col-{k}", help=f"Header of the {k} column, if auto-detection fails")
    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    mpath = Path(a.matrix)
    base = Path(a.out) if a.out else mpath.parent
    meta, cells = load_matrix(mpath)
    rows = load_results(Path(a.results))
    col = map_columns(list(rows[0]), {k: getattr(a, f"col_{k}") for k in COLS})

    # longest ids first so "B1-A2" wins over "B1-A"
    ids = sorted({c["id"] for c in cells}, key=len, reverse=True)
    agg = {c["id"]: {"spend": 0.0, "conv": 0.0, "rev": 0.0, "imp": 0.0, "clk": 0.0, "images": {}} for c in cells}
    unmatched = []
    for r in rows:
        name = str(r.get(col["name"]) or "")
        cid = next((i for i in ids if re.search(rf"(?<![A-Za-z0-9]){re.escape(i)}", name, re.I)), None)
        if not cid:
            if _num(r.get(col["spend"])) > 0:
                unmatched.append(name)
            continue
        vals = {k: _num(r.get(col[c])) if col.get(c) else 0.0
                for k, c in (("spend", "spend"), ("conv", "conversions"), ("rev", "revenue"),
                             ("imp", "impressions"), ("clk", "clicks"))}
        m = re.search(rf"{re.escape(cid)}(\d+)", name, re.I)
        variant = f"{cid}{m.group(1)}" if m else cid
        for k, v in vals.items():
            agg[cid][k] += v
            agg[cid]["images"].setdefault(variant, {"spend": 0.0, "conv": 0.0, "rev": 0.0, "imp": 0.0, "clk": 0.0})
            agg[cid]["images"][variant][k] += v

    today = date.today().isoformat()
    test = meta.get("test") or meta.get("teste") or mpath.parent.name
    fmt = lambda x: f"{x:,.2f}"
    cpa_s = lambda s, c: fmt(s / c) if c else "-"
    roas_s = lambda rv, s: f"{rv / s:.2f}" if s and rv else "-"
    ctr_s = lambda cl, im: f"{100 * cl / im:.2f}%" if im else "-"

    L = [f"# Round results · {test}", "",
         f"Validated on {today} · target CPA {fmt(a.target_cpa)} · spend floor {fmt(a.min_spend)} · "
         f"min conversions {a.min_conversions} · kill above {a.kill_multiple}× target", "",
         "| Cell | Angle | Level | Spend | Conv. | CPA | ROAS | CTR | Verdict |", "|---|---|---|---|---|---|---|---|---|"]
    killed, winners = [], []
    for c in cells:
        g = agg[c["id"]]
        v = verdict(g["spend"], g["conv"], a)
        c["status"] = v
        c["result"] = {"spend": round(g["spend"], 2), "conversions": g["conv"], "revenue": round(g["rev"], 2),
                       "validated": today}
        L.append(f"| {c['id']} | {c['angle']} | {c['level']} | {fmt(g['spend'])} | {g['conv']:g} | "
                 f"{cpa_s(g['spend'], g['conv'])} | {roas_s(g['rev'], g['spend'])} | {ctr_s(g['clk'], g['imp'])} | **{v}** |")
        if v == "killed":
            killed.append(c)
        if v == "winner":
            best = min(g["images"].items(), key=lambda kv: (kv[1]["spend"] / kv[1]["conv"]) if kv[1]["conv"] else 1e12)
            winners.append((c, best))

    L += ["", "## Per image variant", "", "| Variant | Spend | Conv. | CPA | CTR | Verdict |", "|---|---|---|---|---|---|"]
    for c in cells:
        for var, g in sorted(agg[c["id"]]["images"].items()):
            L.append(f"| {var} | {fmt(g['spend'])} | {g['conv']:g} | {cpa_s(g['spend'], g['conv'])} | "
                     f"{ctr_s(g['clk'], g['imp'])} | {verdict(g['spend'], g['conv'], a)} |")
    L += ["", "## Decisions", "",
          f"- **Scale ({len(winners)}):** " + (", ".join(f"{c['id']} with image {b[0]}" for c, b in winners) or "none"),
          f"- **Kill ({len(killed)}):** " + (", ".join(c["id"] for c in killed) or "none"),
          f"- **Keep testing:** " + (", ".join(c["id"] for c in cells if c["status"] == "keep_testing") or "none"),
          f"- **Below floor:** " + (", ".join(c["id"] for c in cells if c["status"] == "inconclusive") or "none")]
    if unmatched:
        L += ["", f"## Unmatched ads with spend ({len(unmatched)})", "",
              "Their names carry no matrix cell id; fix the naming or map them by hand:", ""] + [f"- {n}" for n in unmatched]
    base.mkdir(parents=True, exist_ok=True)
    (base / "round-results.md").write_text("\n".join(L) + "\n", encoding="utf-8")

    if not a.dry_run:
        mpath.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        kl = Path(a.kill_list) if a.kill_list else mpath.parent / "kill-list.md"
        wl = Path(a.winners) if a.winners else mpath.parent / "winners.md"
        if killed:
            new = not kl.exists()
            with open(kl, "a", encoding="utf-8") as f:
                if new:
                    f.write("# Kill list\n\nAngles, hooks and assets that were tested and lost. "
                            "Never bring them back in a new matrix without a new reason.\n\n"
                            "| Date | Test | Cell | Angle | Level | Hook | Spend | Conv. | CPA | Files |\n"
                            "|---|---|---|---|---|---|---|---|---|---|\n")
                for c in killed:
                    g = agg[c["id"]]
                    f.write(f"| {today} | {test} | {c['id']} | {c['angle']} | {c['level']} | "
                            f"{str(c.get('hook', ''))[:80]} | {fmt(g['spend'])} | {g['conv']:g} | "
                            f"{cpa_s(g['spend'], g['conv'])} | {' '.join(c.get('images') or [])} |\n")
        if winners:
            new = not wl.exists()
            with open(wl, "a", encoding="utf-8") as f:
                if new:
                    f.write("# Winners\n\nWhat scales is the ASSET (this copy with this image), not the angle "
                            "label. Re-use the files; don't rewrite the angle from scratch.\n\n"
                            "| Date | Test | Cell | Angle | Level | Best image | Spend | Conv. | CPA | Copy file |\n"
                            "|---|---|---|---|---|---|---|---|---|---|\n")
                for c, (var, g) in winners:
                    f.write(f"| {today} | {test} | {c['id']} | {c['angle']} | {c['level']} | {var} | "
                            f"{fmt(g['spend'])} | {g['conv']:g} | {cpa_s(g['spend'], g['conv'])} | "
                            f"{c.get('copy_file', '')} |\n")
    print(f"{len(cells)} cells: {len(winners)} winner, {len(killed)} killed, "
          f"{sum(c['status'] == 'keep_testing' for c in cells)} keep testing, "
          f"{sum(c['status'] == 'inconclusive' for c in cells)} below floor"
          + (f"; {len(unmatched)} unmatched ads" if unmatched else "") + f" → {base / 'round-results.md'}")


if __name__ == "__main__":
    main()
