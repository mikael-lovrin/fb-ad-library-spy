---
name: fb-ad-library-spy
description: >
  Turns Meta (Facebook/Instagram) Ad Library links into a clean, classified competitor swipe folder:
  downloads every image or video creative, saves each ad's primary text, the headline/description next to the
  button, the button (CTA), landing page and stats (advertiser, advertiser's active ads, ads running the same
  creative, days live) as one .md per creative, builds an INDEX.md + data.xlsx, then classifies every creative
  (angle, persona, visual format, hook, awareness level, mechanism, offer, caption structure, what to steal;
  plus first-3-seconds and video format for videos, using hook frames and a local transcript) and writes a
  synthesis. Then closes the testing loop: turns the spy into a test matrix (angles × awareness levels × image
  variations) that feeds a long-form / ad generator, and after the round validates the ad-level results to update
  the kill list and the winners registry. Use whenever the user pastes one or more Ad Library URLs (or a saved Ad Library .html) and asks to
  spy on, download, scrape, extract, clean up, classify or analyse a competitor's ads, images, videos or captions.
  Also use for "build the next test matrix from the spy" and "validate this round / update the kill list".
  Triggers: "spy on this ad library link", "download these competitor ads", "extract images and captions from the
  ad library", "faz spy na biblioteca de anúncios", "baixa os ads desse concorrente".
user-invokable: true
argument-hint: "<Ad Library URL(s) or .html> [Name] [images only | videos only | all] [max N]"
license: CC BY-NC-ND 4.0
metadata:
  author: Mikael Lovrin
  version: "2.0.0"
  category: competitive-intelligence
---

# FB Ad Library Spy

You turn Ad Library links into a swipe folder a copy team can actually use: every creative downloaded and
numbered, every caption and button block saved next to it, identical ads collapsed into one item with a scale
count, and every creative classified by a consistent taxonomy, closed by a synthesis. Then you turn that
intelligence into a falsifiable test matrix, and after the round you read the results back into a kill list and a
winners registry, so each cycle starts smarter than the last:

```
spy (Steps 1-4) → test matrix (5) → round, written by the user's generator → validation (6) → kill list / winners → spy
```

The deterministic part (collecting, downloading, de-duplicating, tabulating) is done by scripts. Your part is the
judgement: reading every image/frame and caption, classifying it, and writing the synthesis. Never skip the
classification or improvise the collection by browsing manually.

Scripts live next to this file: `scripts/harvest.py`, `scripts/apply_analysis.py`, `scripts/validate_round.py`.
Reference files, read at the step that needs them:
`references/analysis-schema.md` (fields + taxonomy, Step 2), `references/synthesis-guide.md` (Step 3),
`references/matrix-guide.md` (Step 5), `references/troubleshooting.md` (when something fails).

---

## Step 0: Parse the request

**Always ask the scope first** (one AskUserQuestion, before harvesting anything), unless the user already said it:
"Only this link, or the full cycle: this link plus every advertiser profile found in it, one folder per profile,
pulling everything each profile runs?" Recommend the full cycle for keyword searches and for pages that run
partnership / whitelisted ads (other pages carry part of the volume). The answer decides whether Step 1b runs.

For each link the user gives, decide:

| Decision | Rule |
|---|---|
| Media | Default **images only** (`--media image`), even if the link says `media_type=all`: users paste generic links. "videos" → `--media video --transcribe`; "everything" → `--media all --transcribe`. |
| Name | The user's name if given, otherwise omit `--name`: the script derives it (advertiser name for `view_all_page_id` links, the search term for keyword links) and prints it. |
| Output | Omit `--out` and pass `--root <root>`: the folder is named automatically **`<Page name> Image Ads DD.MM.YYYY`** (`Video Ads` / `All Ads` by media; date with dots, e.g. `Acme Image Ads 23.09.2026`; keyword links use the search term). Root: the folder the user names, else a `spy/` folder in the current project. File prefix stays PascalCase (`Acme_001.jpg`). |
| Language | Match the user: `--lang pt` for Portuguese speakers, `--lang en` otherwise. Write the analysis and synthesis in that language too. |
| Duplicates across links | If two links are the same search, or the same page/media was already harvested today, say so and don't re-harvest unless asked. Never delete an existing folder (the date in the folder name keeps re-harvests on other days apart). |
| Size | Big advertisers (1,000+ active ads) are fine: images/videos are a subset, `--max` defaults to 500. |

## Step 1: Harvest (deterministic)

```bash
python "<skill_dir>/scripts/harvest.py" --url "<URL>" --root "<root>" --lang pt|en [--media image|video|all] [--transcribe] [--name Name]
```

Run several links **sequentially** (one background shell job chaining them), never in parallel: parallel
sessions get throttled by Meta. Each run prints `Name prefix`, results reported, ads collected, creatives after
grouping. It prints the output folder. Output per folder: `<Name>_NNN.<jpg|png|mp4>`, `<Name>_NNN.md`, `frames/` (videos), `INDEX.md`,
`data.csv`, `data.xlsx`, `raw.json`, `meta.json`.

Sanity checks after each run: collected ≈ what the Library reports for that media type; `INDEX.md` profile table
has totals (a single `n/a` is fine); a spot-read `.md` has caption + button block. If 0 ads: see troubleshooting.

### Step 1b: Expand to every advertiser (when the user chose the full cycle in Step 0)

A keyword search only returns the ads whose text contains the words; each advertiser page holds all of its active
ads (a persona page found with 3 ads in the search often runs 50-100). For a single advertiser page, the
"advertisers found in it" are the persona / creator / publisher pages that run its partnership ads:

```bash
python "<skill_dir>/scripts/harvest.py" --pages-from "<keyword harvest folder>" --lang pt|en [--media image] [--country ALL]
```

One folder per advertiser (`<Page name> Image Ads DD.MM.YYYY`, next to the parent folder), sequential with a
pause between pages. Every creative that already appeared in the parent harvest is marked in `also_in` (and in the
.md stats), so the analysis can focus on what is new. Use `--country ALL` unless the user asks for a market:
the country filter changes what the Library shows (a page can show 4 image ads for US and 8 for ALL).
Classify each advertiser folder like any other (Step 2); in the synthesis, treat the expansion as one operation:
which pages carry which angles, and what the brand runs only outside the keyword.

## Step 2: Classify every creative (you look at each one)

Read `references/analysis-schema.md` first. Then split the codes into batches of ~18-20 and launch
`general-purpose` subagents **in parallel, in one message**. Give each subagent: the folder, its code range, the
full field list and fixed category list copied from the schema file, the language, and this procedure:

1. `Read` the image (`<code>.jpg|png`, or `<code>_1.*` for carousels). For videos read the frames listed in the
   .md (`frames/<code>_t000.0.jpg` … `_t003.0.jpg` are the hook) and the transcript section.
2. `Read` `<code>.md` (caption, button block, stats).
3. Fill every field from what is actually there; never invent. Flag contradictions (image vs caption) and
   captions that are cut off in the ad itself.
4. Write `<folder>/analysis_partK.json` as `{"<code>": {field: value}}`, valid UTF-8, touching no other file.
5. Reply with 3-5 pattern observations across its batch.

Then run `python "<skill_dir>/scripts/apply_analysis.py" --dir "<folder>"` (fills the .md files, the INDEX table and
the xlsx/csv columns; safe to re-run).

## Step 3: Synthesis

Read `references/synthesis-guide.md`. Compute every number with pandas from `data.csv`, weighting by
`ads_with_this_creative`; never count from memory or from the subagents' prose. Verify every creative code you
cite against `data.csv` before writing it. Save `<folder>/synthesis.md`, re-run `apply_analysis.py` to inject it
into `INDEX.md`.

With several folders from one request, finish each folder's synthesis, then add a short cross-competitor
comparison (who runs what, shared patterns, gaps nobody covers) at `<root>/_comparison-<YYYY-MM-DD>.md`.

## Step 4: Report

Tell the user, per folder: ads → creatives, top 3-5 findings, the strongest creatives to use as a base (with codes
and why), and any compliance red flags (health claims, fake credentials, sensitive targeting, lookalikes) so
nobody copies them blindly. Then offer Step 5.

## Step 5: Test matrix (spy → next round)

When the user wants the spy to become tests (or asks for "the matrix", "the next round", "what should we test"),
read `references/matrix-guide.md`, the product's `kill-list.md` / `winners.md` if they exist, and the product
facts. Write `test-matrix.md` + `test-matrix.json` in the round's folder (ask where if unclear): N angles ×
M awareness levels × K image variations, every cell backed by spy evidence (codes + signal) or marked as a gap
bet, with hypothesis, lock and naming id.

If the user has a long-form / ad generator skill installed (e.g. `longform-builder`), its matrix rules win and
this matrix is the **proposal** its matrix phase starts from: invoke it with the `Skill` tool for the round itself
and never bypass its gates. Present the compact table and wait for approval before anything is written.

## Step 6: Validate the round → kill list and winners

When the round has spent enough to read, ask for the ad-level export (Meta Ads Manager CSV/XLSX or similar) and the
thresholds (target CPA, spend floor, minimum conversions; reuse `thresholds` from `test-matrix.json` if set), then:

```bash
python "<skill_dir>/scripts/validate_round.py" --matrix "<round>/test-matrix.json" --results "<export.csv>" \
  --target-cpa 45 --min-spend 150 --min-conversions 3 \
  --kill-list "<product>/kill-list.md" --winners "<product>/winners.md"
```

It writes `round-results.md`, updates every cell's status, appends killed cells to the kill list and winning
**assets** (copy file + best image) to winners. Read `round-results.md`, explain the verdicts, list unmatched ads
(naming problems), and propose: scale the winning assets as-is, re-test `keep_testing` cells, and the next spy
targets to refill the angle pipeline. The loop is: spy → matrix → round → validation → kill list / winners → spy.

---

## Hard rules

- Classification and synthesis are not optional, even when the user only said "download".
  Skip them only if the user explicitly says so.
- Keep the fixed category list identical across all batches and folders of the same niche, or comparisons break.
- Competitor copy is reference material: extract structure and mechanics, never recommend copying claims.
- Never publish or share harvested creatives outside the user's machine without being asked.
