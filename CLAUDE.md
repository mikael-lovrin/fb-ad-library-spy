# fb-ad-library-spy — source repo

This is the source repo of the `fb-ad-library-spy` Claude Code skill. Edit here, then run `Install.bat`
(or `install.sh`) to copy `skills/fb-ad-library-spy/` into `~/.claude/skills/`. Don't harvest into this repo:
harvest output (`spy/`) is git-ignored and contains third-party ad content that must never be committed.

- Code and docs in English; README is bilingual (EN first, then PT-BR).
- `scripts/harvest.py` is deterministic and self-contained (no dependency on the older `FB Ads Spy` pipeline).
- Keep field names in `ANALYSIS_FIELDS`/`VIDEO_FIELDS`, `references/analysis-schema.md` and the README in sync.
- License: CC BY-NC-ND 4.0.
