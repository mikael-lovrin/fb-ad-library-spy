# Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `No ads in page HTML` twice, then `Nothing to save` | Meta served the throttled (lightweight) page | Wait 30-90 min; run links sequentially, not in parallel; `--headed` sometimes helps |
| `The Library returned 0 results for this link` then `Server-side media filter returned nothing: retrying…` | Meta's `media_type=image/video` filter returns 0 on some `view_all_page_id` pages that do run those formats | Automatic: the harvester re-collects with `media_type=all` (oversampling to 4× `--max`, min 2,000) and filters locally |
| Collected far fewer than the Library shows | Scrolling stopped (4 idle scrolls) or `--max` reached | Re-run with `--headed` to watch, raise `--max` |
| `profile_active_ads` is `n/a` for one profile | That profile's page load was throttled 3× or the page has no public active ads in that country | Harmless; re-run later if needed |
| Library count differs from collected for images | The Library count covers all media before our `--media` filter, or DCO ads mixing video + image | Expected; `--media all` to see everything |
| Transcription skipped | `faster-whisper` not installed | `pip install faster-whisper` (first run downloads the model) |
| No `frames/` | `ffmpeg`/`ffprobe` not on PATH | Install ffmpeg, or pass `--no-frames` |
| Transcript in an unrelated language | Keyword searches also match unrelated advertisers | Normal for keyword links; classify it as off-topic and exclude it from the synthesis |
| Image CDN URLs in `raw.json` stop working | Meta's signed CDN URLs expire after ~24-48 h | Files are already downloaded; re-harvest to refresh the URLs |
| A saved `.html` yields only ~30 ads | Only the first page is server-rendered | Use the URL instead |
| Two different creatives grouped together | Extremely similar images with identical captions | `--no-dedupe` |
