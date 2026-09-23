# Synthesis guide

`synthesis.md` is injected under the `## Synthesis` heading of `INDEX.md`, so start its headings at `###`.
Every number comes from pandas over `data.csv`, weighted by `ads_with_this_creative` unless stated. Every code
you cite must be checked against `data.csv` (subagents' prose can carry numbering mistakes).

## Signals, strongest first

1. **Duplication**: the same creative running as several ads, especially across several pages
   (`ads_with_this_creative`, `ad_ids`). Advertisers only multiply what works.
2. **Library rank**: the numbering follows the Library order (impressions, when the URL sorts by
   `total_impressions`).
3. **Days running**: long-lived ads are winners, but many DR advertisers rotate creatives every few days. If the
   median is near 0, say that days running can't separate winners here and lean on 1 and 2.
4. **Testing grid**: the same copy with several images (image test), the same image with several captions
   (`same_image_other_copy`), the same creative to quiz vs product page (destination test), or variants
   that change a single block.

## Sections

### 1. How the operation is set up
Brand page vs persona pages (who carries volume), active ads per profile, landing-page split (quiz, advertorial,
listicle, PDP), visible testing grid.

### 2. Angles and personas
Table of `angle_category` (creatives, ads) with example codes. Awareness distribution. Recurring personas.

### 3. Caption skeleton
Length (`caption_chars`: median, IQR, max) and the recurring block order, with the lines that recur verbatim.
For videos: hook patterns in the first 3 s, formats, typical length.

### 4. Button block
Headline patterns, the fixed descriptions they rotate, CTA split.

### 5. Visuals
What the images/frames do (text or not, product shown or not, emotional register) and exceptions.

### 6. Strongest creatives to use as a base
5-10 codes, each with the evidence (rank, duplications, pages, days) and why.

### Red flags
What must not be copied (claims, fake credentials, lookalikes, sensitive targeting) and captions cut off at source.

Keep it dense: bullets and tables, codes everywhere, no filler.
