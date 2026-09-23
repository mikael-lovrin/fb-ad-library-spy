# Analysis schema

Every creative gets these fields in `analysis_partK.json`. One line each, specific, in the user's language.
`structure` and `steal` may take up to two lines. Base everything on what is visible or written; never invent.

| Field | What to write | Example |
|---|---|---|
| `angle` | The specific angle, as a label a copywriter would reuse | Urologist reveals ED is blood flow, not testosterone, and bans Viagra |
| `angle_category` | Exactly ONE value from the category list below | Medical authority |
| `persona` | Who speaks / who is shown. Flag persona pages (a person's or community's name instead of the brand) | Urologist, 1st person; persona page "American Men Society" |
| `visual_format` | What the image (or video) is, incl. overlay text | AI illustration, transparent anatomy + female doctor, no overlay text |
| `hook` | Visual hook + first caption line, short | Anatomy image + "I'm a Urologist, and this is exactly what I tell…" |
| `awareness` | One of: Unaware, Problem aware, Solution aware, Product aware, Most aware | Problem aware |
| `mechanism` | Named cause/mechanism, or "None" | Nitric Oxide Collapse (blood flow) |
| `offer` | Promise + offer mechanics present (dose, guarantee, discount, quiz, bundle) | 2 gummies/day, 60-day guarantee, quiz funnel |
| `structure` | Caption blocks in order, separated by `>`; say "short caption" when short | Authority hook > pain > false causes > mechanism > anti-Viagra > product > ingredients > week-by-week > scarcity > guarantee > CTA |
| `steal` | The single most reusable element | The "you've been pointed at the wrong problem" reframe |

Videos only (leave out for images):

| Field | What to write |
|---|---|
| `hook_3s` | What happens in the first 3 seconds: visual + spoken/on-screen words (from `_t000`-`_t003` frames + transcript) |
| `video_format` | UGC talking head, podcast clip, street interview, doctor explainer, slideshow, animation, green screen, skit, etc. + pacing (cuts per ~5 s) |

## Category list

Default list (built for health / supplements / DTC). Adapt it to the niche **before** Step 2, then keep it
identical for every batch and every folder of that niche:

- Medical authority
- Personal story / confession
- Partner / relationship
- Mechanism / science
- Anti-drug / anti-competitor
- Social proof / testimonial
- News / discovery
- Offer / promotion
- Humor / meme
- Age / vitality
- Size / performance
- Other

Portuguese equivalents (use with `--lang pt`): Autoridade médica, História pessoal/confissão,
Parceira/relacionamento, Mecanismo/ciência, Anti-remédio/anti-concorrente, Prova social/depoimento,
Notícia/descoberta, Oferta/promoção, Humor/meme, Idade/virilidade, Tamanho/performance, Outro.

## Things to flag inside the fields

- Caption cut off in the ad itself (common: many captions exceed 15k characters and still come through whole,
  so a truncated one is truncated at the source).
- Image and caption that contradict each other (e.g., a 55-year-old in the photo, a 32-year-old narrator).
- Same copy as another code (write "same copy as NNN, image test" / "destination test: quiz vs PDP").
- Compliance risk: cure/size claims, fake credentials, celebrity/performer lookalikes, sensitive-attribute targeting.
