# -*- coding: utf-8 -*-
"""
FB Ad Library Spy — apply analysis
==================================
harvest.py leaves the qualitative fields as placeholders. Claude looks at each
creative and writes one or more `analysis*.json` files into the folder:

    {"Acme_001": {"angle": "...", "angle_category": "...", "persona": "...",
                  "visual_format": "...", "hook": "...", "awareness": "...",
                  "mechanism": "...", "offer": "...", "structure": "...", "steal": "...",
                  "hook_3s": "...", "video_format": "..."}, ...}      # last two: videos only

plus, optionally, `synthesis.md`. This script writes the values into every
<code>.md, rebuilds INDEX.md (creative table + Synthesis section) and
data.csv / data.xlsx. Idempotent: re-run it whenever the JSON changes.

Usage:
    python apply_analysis.py --dir spy/Acme
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harvest import ANALYSIS_FIELDS, LABELS, PLACEHOLDER, VIDEO_FIELDS, write_index, write_tables  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="Harvest folder (contains data.csv and meta.json)")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    d = Path(args.dir)
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    L = LABELS[meta.get("lang", "en")]

    analysis = {}
    for f in sorted(d.glob("analysis*.json")):
        analysis.update(json.loads(f.read_text(encoding="utf-8")))

    with open(d / "data.csv", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    missing = []
    for r in rows:
        a = analysis.get(r["code"])
        if not a:
            missing.append(r["code"])
            continue
        md_path = d / f"{r['code']}.md"
        text = md_path.read_text(encoding="utf-8")
        for field in ANALYSIS_FIELDS + VIDEO_FIELDS:
            value = (a.get(field) or "").strip()
            if field in r:
                r[field] = value
            if value:
                label = re.escape(L["f_" + field])
                text = re.sub(rf"^- \*\*{label}:\*\* .*$", lambda m: f"- **{L['f_' + field]}:** {value}",
                              text, flags=re.M)
        md_path.write_text(text, encoding="utf-8")

    synthesis_file = next((d / n for n in ("synthesis.md", "sintese.md") if (d / n).exists()), None)
    synthesis = synthesis_file.read_text(encoding="utf-8").strip() if synthesis_file else ""
    write_tables(rows, d)
    write_index(rows, meta, d, synthesis)

    pending = sum(1 for p in d.glob(f"{meta['name']}_*.md") if PLACEHOLDER in p.read_text(encoding="utf-8"))
    print(f"Applied analysis to {len(rows) - len(missing)}/{len(rows)} creatives"
          + (f"; missing: {', '.join(missing)}" if missing else "")
          + (f"; {pending} .md still have pending fields" if pending else "")
          + ("; synthesis injected" if synthesis else "; no synthesis.md yet"))


if __name__ == "__main__":
    main()
