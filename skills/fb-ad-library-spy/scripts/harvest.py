# -*- coding: utf-8 -*-
"""
FB Ad Library Spy — harvest
===========================
Turn any Meta Ad Library URL (keyword search or a single advertiser's
view_all_page_id page) — or a saved Ad Library .html file — into a clean,
numbered swipe folder:

    <Name>_001.jpg | .mp4        the creative (carousel cards → _1, _2 …)
    <Name>_001.md                primary text, the button block (headline,
                                 description, CTA, display domain, landing
                                 URL), stats, video transcript, analysis slots
    frames/<Name>_001_t00.0.jpg  video only: hook keyframes (needs ffmpeg)
    INDEX.md                     advertisers, CTAs, landing pages, creatives
    data.csv / data.xlsx         one row per creative, filterable
    raw.json / meta.json         untouched API payload + run metadata

How the data is obtained
------------------------
The first ~30 results are server-side rendered into the page as a large
<script type="application/json"> blob; the remaining pages arrive as GraphQL
responses while the page scrolls. We load the page with Playwright, parse the
SSR blob, then scroll and intercept every GraphQL response that contains a
`search_results_connection` until Meta reports `has_next_page = false`.

Generic links
-------------
`--media image|video|all` rewrites the URL's `media_type` parameter before
loading (so Meta filters server-side) AND filters client-side, so any generic
link a user pastes can be narrowed to images only / videos only.

Duplicates
----------
Advertisers run the same creative as many ads (often across several persona
pages). Meta re-encodes the image per ad, so byte hashes differ; we group by a
64-bit perceptual difference hash of the image (or the video's preview frame)
plus the whitespace-normalised primary text. `ads_with_this_creative` is the
resulting count — a scale signal. The same image under a different caption is
cross-referenced in `same_image_other_copy`.

Usage
-----
    python harvest.py --url "<ad library url>"                  # → spy/<Page name> Image Ads DD.MM.YYYY/
    python harvest.py --url "<ad library url>" --name Acme
    python harvest.py --url "<url>" --name Acme --media video --transcribe
    python harvest.py --html saved.html --name Acme --lang pt
"""

import argparse
import asyncio
import csv
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter, OrderedDict
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlparse, urlunparse

import requests

logger = logging.getLogger("harvest")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
LIBRARY = "https://www.facebook.com/ads/library/"
PLACEHOLDER = "_(pending)_"

# Analysis fields filled later by Claude (apply_analysis.py). Order = column order.
ANALYSIS_FIELDS = ["angle", "angle_category", "persona", "visual_format", "hook", "awareness",
                   "mechanism", "offer", "structure", "steal"]
VIDEO_FIELDS = ["hook_3s", "video_format"]

LABELS = {
    "en": {
        "profile": "Profile", "files": "File(s)", "library": "Ad Library", "stats": "Stats",
        "metric": "Metric", "value": "Value", "ads_same": "Ads running this creative",
        "same_img": "Same image, different caption", "also_in": "Already in the parent harvest", "profile_total": "Profile's active ads (all formats)",
        "profile_here": "Profile's ads in this search", "profile_creatives": "Profile's distinct creatives in this search",
        "format": "Format", "since": "Live since", "days": "days", "platforms": "Platforms",
        "rank": "Rank (library order)", "caption_len": "Caption length", "chars": "characters",
        "caption": "Primary text (caption)", "button": "Button block", "headline": "Headline (next to the button)",
        "description": "Description", "cta": "Button (CTA)", "domain": "Display domain", "landing": "Landing URL",
        "cards": "Carousel cards", "card": "Card", "dco": "Text variations (DCO)",
        "same_creative_ads": "Ads using this same creative", "identical": "Headline, button and link identical in all.",
        "transcript": "Video transcript", "frames": "Hook frames", "analysis": "Analysis",
        "collected": "Collected on", "source": "source", "empty": "(empty)", "none": "(no media downloaded)",
        "likes": "likes", "nocat": "no category", "paid_by": "paid by", "partnership": "partnership ad",
        "f_angle": "Angle", "f_angle_category": "Angle category", "f_persona": "Persona / who speaks",
        "f_visual_format": "Visual format", "f_hook": "Hook (visual + first line)", "f_awareness": "Awareness level",
        "f_mechanism": "Mechanism", "f_offer": "Offer / promise", "f_structure": "Caption structure",
        "f_steal": "What to steal", "f_hook_3s": "First 3 seconds", "f_video_format": "Video format",
        "i_title": "Spy", "i_results": "Results the Library shows", "i_collected": "Ads collected",
        "i_distinct": "distinct creatives (identical ads grouped)", "i_profiles": "Advertiser profiles",
        "i_files": "Each creative has `<code>.<jpg|png|mp4>` + `<code>.md` (caption, button block, stats, "
                   "analysis). Full table in `data.xlsx` / `data.csv`; untouched payload in `raw.json`.",
        "i_prof_h": "Profiles", "i_prof_cols": "Profile | Active ads (profile total) | Ads in this search | Distinct creatives | Likes",
        "i_cta_h": "Buttons, domains and landing pages", "i_cta": "Button (CTA)", "i_domain": "Domain",
        "i_landing": "Landing page", "i_ads": "Ads", "i_creatives": "Creatives (library order)",
        "i_cols": "# | Creative | Profile | Ads w/ creative | Days | Button headline | CTA | Angle | Persona | Visual format | Caption start",
        "i_synth": "Synthesis",
    },
    "pt": {
        "profile": "Perfil", "files": "Arquivo(s)", "library": "Biblioteca", "stats": "Estatísticas",
        "metric": "Métrica", "value": "Valor", "ads_same": "Ads com esse criativo",
        "same_img": "Mesma imagem com outra legenda", "also_in": "Já estava na coleta de origem", "profile_total": "Ads ativos do perfil (total, todos formatos)",
        "profile_here": "Ads do perfil nesta busca", "profile_creatives": "Criativos distintos do perfil nesta busca",
        "format": "Formato", "since": "No ar desde", "days": "dias", "platforms": "Plataformas",
        "rank": "Posição (ordem da biblioteca)", "caption_len": "Tamanho da legenda", "chars": "caracteres",
        "caption": "Legenda (texto principal)", "button": "Bloco do botão", "headline": "Headline (ao lado do botão)",
        "description": "Descrição", "cta": "Botão (CTA)", "domain": "Domínio exibido", "landing": "Link de destino",
        "cards": "Cards do carrossel", "card": "Card", "dco": "Variações de texto (DCO)",
        "same_creative_ads": "Ads que usam esse mesmo criativo", "identical": "Headline, botão e link idênticos em todos.",
        "transcript": "Transcrição do vídeo", "frames": "Frames do hook", "analysis": "Análise",
        "collected": "Coletado em", "source": "fonte", "empty": "(vazio)", "none": "(sem mídia baixada)",
        "likes": "curtidas", "nocat": "sem categoria", "paid_by": "pago por", "partnership": "anúncio de parceria",
        "f_angle": "Ângulo", "f_angle_category": "Categoria do ângulo", "f_persona": "Personagem / quem fala",
        "f_visual_format": "Formato visual", "f_hook": "Hook (visual + 1ª linha)", "f_awareness": "Nível de consciência",
        "f_mechanism": "Mecanismo citado", "f_offer": "Oferta / promessa", "f_structure": "Estrutura da legenda",
        "f_steal": "O que roubar", "f_hook_3s": "Primeiros 3 segundos", "f_video_format": "Formato do vídeo",
        "i_title": "Spy", "i_results": "Resultados que a Biblioteca mostra", "i_collected": "Ads coletados",
        "i_distinct": "criativos distintos (ads idênticos agrupados)", "i_profiles": "Perfis anunciando",
        "i_files": "Cada criativo tem `<codigo>.<jpg|png|mp4>` + `<codigo>.md` (legenda, bloco do botão, "
                   "estatísticas, análise). Tabela completa em `data.xlsx` / `data.csv`; resposta bruta em `raw.json`.",
        "i_prof_h": "Perfis", "i_prof_cols": "Perfil | Ads ativos (total do perfil) | Ads nesta busca | Criativos distintos | Curtidas",
        "i_cta_h": "Botões, domínios e páginas de destino", "i_cta": "Botão (CTA)", "i_domain": "Domínio",
        "i_landing": "Página de destino", "i_ads": "Ads", "i_creatives": "Criativos (ordem da biblioteca)",
        "i_cols": "# | Criativo | Perfil | Ads c/ criativo | Dias | Headline do botão | Botão | Ângulo | Personagem | Formato visual | Início da legenda",
        "i_synth": "Síntese",
    },
}


# ── URL helpers ──────────────────────────────────────────────────────────────

def _qs(pairs) -> str:
    # Meta rejects percent-encoded brackets in sort_data[...] keys, so keys stay literal.
    return "&".join(f"{k}={quote(str(v), safe='')}" for k, v in pairs)


def force_media_type(url: str, media: str) -> str:
    """Rewrite the URL's media_type so Meta filters server-side (generic links)."""
    parts = urlparse(url)
    pairs = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "media_type"]
    pairs.append(("media_type", {"image": "image", "video": "video"}.get(media, "all")))
    return urlunparse(parts._replace(query=_qs(pairs)))


def display_name(url: str | None, items: list[dict]) -> str:
    """Human name: the advertiser's page name for page URLs, the search term (title-cased) for keyword URLs."""
    q = dict(parse_qsl(urlparse(url).query)) if url else {}
    if q.get("view_all_page_id") or not q.get("q"):
        names = Counter((i.get("snapshot") or {}).get("page_name") or i.get("page_name") for i in items)
        base = names.most_common(1)[0][0] if names else "Spy"
    else:
        base = " ".join(w[:1].upper() + w[1:] for w in q["q"].split())
    return re.sub(r'[<>:"/\|?*]+', "", base or "Spy").strip(" .") or "Spy"


def derive_name(url: str | None, items: list[dict]) -> str:
    """PascalCase file prefix built from display_name()."""
    return "".join(w[:1].upper() + w[1:] for w in re.findall(r"[A-Za-z0-9]+", display_name(url, items))) or "Spy"


def folder_name(display: str, media: str, when: datetime | None = None) -> str:
    """Default folder: '<Page name> Image Ads 23.09.2026' (Video Ads / All Ads)."""
    kind = {"image": "Image", "video": "Video"}.get(media, "All")
    safe = re.sub(r'[<>:"/\|?*]+', "", display).strip(" .") or "Spy"
    return f"{safe} {kind} Ads {(when or datetime.now()).strftime('%d.%m.%Y')}"


def page_url(page_id: str, country: str = "ALL") -> str:
    return LIBRARY + "?" + _qs([
        ("active_status", "active"), ("ad_type", "all"), ("country", country),
        ("is_targeted_country", "false"), ("media_type", "all"), ("view_all_page_id", page_id),
        ("sort_data[direction]", "desc"), ("sort_data[mode]", "total_impressions"),
    ])


# ── Parsing ──────────────────────────────────────────────────────────────────

_SCRIPT_RE = re.compile(
    r'<script[^>]+type="application/json"[^>]*data-content-len="(\d+)"[^>]*>(.*?)</script>', re.DOTALL)


def _walk_connections(obj, out, depth=0):
    if depth > 25:
        return
    if isinstance(obj, dict):
        if "search_results_connection" in obj:
            out.append(obj["search_results_connection"])
        for v in obj.values():
            _walk_connections(v, out, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            _walk_connections(v, out, depth + 1)


def _flatten(conn: dict) -> list[dict]:
    items = []
    for edge in conn.get("edges") or []:
        items.extend((edge.get("node") or {}).get("collated_results") or [])
    return items


def parse_html(html: str) -> tuple[int, list[dict]]:
    """(total_count, collated_results) from the SSR'd page; ([], 0) when throttled."""
    blobs = sorted(((int(m.group(1)), m.group(2)) for m in _SCRIPT_RE.finditer(html)
                    if int(m.group(1)) > 50_000), reverse=True)
    for _, blob in blobs:
        if "search_results_connection" not in blob:
            continue
        try:
            data = json.loads(blob)
        except json.JSONDecodeError:
            continue
        conns = []
        _walk_connections(data, conns)
        for c in conns:
            if c.get("edges"):
                return c.get("count", 0), _flatten(c)
    return 0, []


def parse_graphql(text: str) -> tuple[list[dict], dict | None]:
    """Meta may stream several JSON objects per response, one per line."""
    items, info = [], None
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{") or "search_results_connection" not in line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        conns = []
        _walk_connections(data, conns)
        for c in conns:
            info = c.get("page_info") or info
            items.extend(_flatten(c))
    return items, info


# ── Collection ───────────────────────────────────────────────────────────────

async def collect(url: str, max_ads: int, headless: bool, profile_totals: bool):
    from playwright.async_api import async_playwright

    items: list[dict] = []
    state = {"has_next": True}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        ctx = await browser.new_context(user_agent=UA, locale="en-US", timezone_id="America/New_York",
                                        viewport={"width": 1280, "height": 900})
        page = await ctx.new_page()

        async def on_response(resp):
            if "graphql" not in resp.url:
                return
            try:
                text = await resp.text()
            except Exception:
                return
            if "search_results_connection" in text:
                new, info = parse_graphql(text)
                items.extend(new)
                if info is not None:
                    state["has_next"] = bool(info.get("has_next_page"))

        page.on("response", on_response)
        total = 0
        for attempt in (1, 2):
            await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            for sel in ('button:has-text("Allow all cookies")', 'button:has-text("Accept all")'):
                try:
                    await page.click(sel, timeout=1_500)
                    break
                except Exception:
                    pass
            await page.wait_for_timeout(8_000)
            html = await page.content()
            total, first = parse_html(html)
            if first:
                items[:0] = first
                break
            if "search_results_connection" in html:  # real empty result, not throttling
                logger.info("The Library returned 0 results for this link")
                break
            logger.warning(f"No ads in page HTML (attempt {attempt}): Meta may be throttling")
            if attempt == 1:
                await asyncio.sleep(45)
        logger.info(f"Library reports {total} results; {len(items)} in first load")

        idle = 0
        while first and state["has_next"] and len(items) < max_ads and idle < 4:
            before = len(items)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(3_500)
            idle = idle + 1 if len(items) == before else 0
            logger.info(f"  scrolled: {len(items)} ads")

        totals = {}
        if profile_totals and items:
            country = dict(parse_qsl(urlparse(url).query)).get("country", "ALL")
            totals = await _profile_totals(ctx, items, country)
        await browser.close()
    return total, items, totals


async def _profile_totals(ctx, items, country) -> dict:
    """Each advertiser's total active ads (all formats) via its view_all_page_id page."""
    ids = list(OrderedDict.fromkeys(str(i.get("page_id")) for i in items if i.get("page_id")))
    totals, page = {}, await ctx.new_page()
    for pid in ids:
        totals[pid] = None
        for attempt in (1, 2, 3):
            try:
                await page.goto(page_url(pid, country), wait_until="domcontentloaded", timeout=45_000)
                await page.wait_for_timeout(6_000 + 4_000 * (attempt - 1))
                count, found = parse_html(await page.content())
                if found:
                    totals[pid] = count
                    break
            except Exception as e:
                logger.warning(f"  profile {pid}: attempt {attempt} failed ({e})")
        logger.info(f"  profile {pid}: {totals[pid]} active ads")
    await page.close()
    return totals


# ── Normalisation ────────────────────────────────────────────────────────────

def _ts(v):
    try:
        return datetime.fromtimestamp(int(v))
    except Exception:
        return None


def _clean(t):
    return re.sub(r"\n{3,}", "\n\n", (t or "").strip())


def _img(d):
    return d.get("original_image_url") or d.get("resized_image_url")


def _vid(d):
    return d.get("video_hd_url") or d.get("video_sd_url")


def normalize(item: dict) -> dict:
    s = item.get("snapshot") or {}
    cards = s.get("cards") or []
    media = []  # (kind, url); kind ∈ image | video | thumb
    for group in (s.get("images") or [], cards, s.get("extra_images") or []):
        media += [("image", _img(x)) for x in group if _img(x)]
    for group in (s.get("videos") or [], cards, s.get("extra_videos") or []):
        for x in group:
            if _vid(x):
                media.append(("video", _vid(x)))
                if x.get("video_preview_image_url"):
                    media.append(("thumb", x["video_preview_image_url"]))
    start, end = _ts(item.get("start_date")), _ts(item.get("end_date"))
    now = datetime.now()
    return {
        "ad_archive_id": str(item.get("ad_archive_id") or ""),
        "page_id": str(item.get("page_id") or s.get("page_id") or ""),
        # page_name = the identity shown in the feed (persona / publisher page on partnership ads);
        # advertiser = the account that pays, when different (whitelisting / branded content)
        "page_name": s.get("page_name") or item.get("page_name") or "",
        "advertiser": item.get("page_name") if item.get("page_name") and item.get("page_name") != s.get("page_name") else "",
        "partnership": bool(s.get("branded_content")),
        "page_url": s.get("page_profile_uri") or "",
        "page_likes": s.get("page_like_count"),
        "page_categories": ", ".join(s.get("page_categories") or []),
        "display_format": s.get("display_format") or "",
        "body": _clean((s.get("body") or {}).get("text")),
        "title": _clean(s.get("title")),
        "link_description": _clean(s.get("link_description")),
        "cta_text": s.get("cta_text") or "",
        "cta_type": s.get("cta_type") or "",
        "caption": s.get("caption") or "",
        "link_url": s.get("link_url") or "",
        "extra_texts": [_clean(t.get("text")) for t in s.get("extra_texts") or [] if t.get("text")],
        "cards": [{"body": _clean(c.get("body")), "title": _clean(c.get("title")),
                   "link_description": _clean(c.get("link_description")),
                   "cta_text": c.get("cta_text") or "", "link_url": c.get("link_url") or ""} for c in cards],
        "media": media,
        "is_video": any(k == "video" for k, _ in media),
        "start_date": start.strftime("%Y-%m-%d") if start else "",
        "days_running": (min(end or now, now) - start).days if start else None,
        "platforms": ", ".join(p.title() for p in item.get("publisher_platform") or []),
        "library_url": f"{LIBRARY}?id={item.get('ad_archive_id')}",
    }


# ── Download, hashing, grouping ──────────────────────────────────────────────

_http = requests.Session()
_http.headers["User-Agent"] = UA


def download(url: str) -> tuple[bytes | None, str]:
    for attempt in range(3):
        try:
            r = _http.get(url, timeout=120)
            if r.ok and r.content:
                ct = r.headers.get("content-type", "")
                ext = ".mp4" if "video" in ct else ".png" if "png" in ct else ".webp" if "webp" in ct else ".jpg"
                return r.content, ext
        except requests.RequestException:
            pass
        time.sleep(1.5 * (attempt + 1))
    return None, ""


def dhash(data: bytes) -> str:
    """64-bit difference hash: stable across Meta's per-ad re-encodes of one image."""
    try:
        from io import BytesIO
        from PIL import Image
        px = list(Image.open(BytesIO(data)).convert("L").resize((9, 8)).tobytes())
        return f"{sum(1 << i for i in range(64) if px[(i // 8) * 9 + i % 8] > px[(i // 8) * 9 + i % 8 + 1]):016x}"
    except Exception:
        return hashlib.sha1(data).hexdigest()


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").replace("’", "'")).strip().lower()


def group(ads: list[dict], media: str, dedupe: bool) -> list[dict]:
    groups: "OrderedDict[str, dict]" = OrderedDict()
    for i, ad in enumerate(ads, 1):
        files, hashes = [], []
        for kind, url in ad["media"]:
            keep = media == "all" or kind == media or (kind == "thumb" and media in ("video", "all"))
            if not keep:
                continue
            data, ext = download(url)
            if not data:
                continue
            files.append((data, ext, kind))
            if kind != "video":  # videos are identified by their preview frame
                hashes.append(dhash(data))
        if not hashes:  # video without a preview frame
            hashes = [hashlib.sha1(b"".join(f[0] for f in files)).hexdigest()] if files else []
        img_key = "|".join(hashes)
        key = f"{img_key}#{hashlib.sha1(_norm(ad['body']).encode()).hexdigest()}" if dedupe else ad["ad_archive_id"]
        logger.info(f"  [{i}/{len(ads)}] {ad['page_name'][:30]:30} {len(files)} file(s)")
        if key in groups:
            groups[key]["ads"].append(ad)
        else:
            groups[key] = {"ads": [ad], "files": files, "img_key": img_key}
    return list(groups.values())


# ── Video extras ─────────────────────────────────────────────────────────────

def extract_frames(video: Path, out_dir: Path, code: str) -> list[str]:
    """Hook frames at 0/1/2/3 s plus 4 evenly spaced frames. Needs ffmpeg on PATH."""
    if not shutil.which("ffmpeg"):
        return []
    try:
        dur = float(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
            capture_output=True, text=True, timeout=60).stdout.strip() or 0)
    except Exception:
        dur = 0
    stamps = [0.0, 1.0, 2.0, 3.0] + ([round(dur * f, 1) for f in (0.25, 0.5, 0.75, 0.95)] if dur > 8 else [])
    out_dir.mkdir(exist_ok=True)
    saved = []
    for t in sorted(set(s for s in stamps if s < max(dur, 0.1))):
        name = f"{code}_t{t:05.1f}.jpg"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t), "-i", str(video),
                        "-frames:v", "1", "-vf", "scale=540:-2", str(out_dir / name)], timeout=120)
        if (out_dir / name).exists():
            saved.append(f"frames/{name}")
    return saved


_whisper = None


def transcribe(video: Path, model_size: str) -> str:
    """Local, free transcription with faster-whisper (pip install faster-whisper)."""
    global _whisper
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        logger.warning("faster-whisper not installed: skipping transcription")
        return ""
    if _whisper is None:
        _whisper = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _ = _whisper.transcribe(str(video), vad_filter=True)
    return "\n".join(f"[{s.start:05.1f}s] {s.text.strip()}" for s in segments)


# ── Writing ──────────────────────────────────────────────────────────────────

def caption_metrics(body: str) -> tuple[int, str]:
    """Caption length + first 3 non-empty lines (what shows before 'See more')."""
    lines = [ln.strip() for ln in (body or "").splitlines() if ln.strip()]
    return len(body or ""), " / ".join(lines[:3])


def cell(v) -> str:
    return str(v if v is not None else "").replace("|", "/").replace("\n", " ").strip()


def quote_block(text: str, empty: str) -> str:
    return "\n".join("> " + ln if ln else ">" for ln in (text or empty).splitlines())


def write_outputs(groups, name, out: Path, source, total, totals, raw, lang, frames, do_transcribe, whisper_model,
                  also_in: dict | None = None):
    also_in = also_in or {}
    L = LABELS[lang]
    out.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    ads_per_page = Counter(a["page_id"] for g in groups for a in g["ads"])
    creatives_per_page = Counter(g["ads"][0]["page_id"] for g in groups)
    by_image: dict[str, list[str]] = {}
    for n, g in enumerate(groups, 1):
        if g["img_key"]:
            by_image.setdefault(g["img_key"], []).append(f"{name}_{n:03d}")
    any_video = any(g["ads"][0]["is_video"] for g in groups)
    rows = []

    for n, g in enumerate(groups, 1):
        code, ad = f"{name}_{n:03d}", g["ads"][0]
        saved, video_path = [], None
        multi = sum(1 for f in g["files"] if f[2] != "thumb") > 1
        for j, (data, ext, kind) in enumerate(g["files"], 1):
            fname = f"{code}{f'_{j}' if multi else ''}{'_thumb' if kind == 'thumb' else ''}{ext}"
            (out / fname).write_bytes(data)
            saved.append(fname)
            if kind == "video" and video_path is None:
                video_path = out / fname
        frame_files = extract_frames(video_path, out / "frames", code) if (video_path and frames) else []
        transcript = transcribe(video_path, whisper_model) if (video_path and do_transcribe) else ""

        pid = ad["page_id"]
        oldest = min((a["start_date"] for a in g["ads"] if a["start_date"]), default="")
        max_days = max((a["days_running"] or 0 for a in g["ads"]), default=0)
        chars, before_more = caption_metrics(ad["body"])
        row = {
            "code": code, "files": " ".join(saved), "profile": ad["page_name"], "profile_url": ad["page_url"],
            "advertiser": ad["advertiser"], "partnership": "yes" if ad["partnership"] else "",
            "page_id": pid, "profile_likes": ad["page_likes"], "profile_category": ad["page_categories"],
            "profile_active_ads": totals.get(pid), "profile_ads_in_search": ads_per_page[pid],
            "profile_creatives_in_search": creatives_per_page[pid], "ads_with_this_creative": len(g["ads"]),
            "same_image_other_copy": " ".join(c for c in by_image.get(g["img_key"], []) if c != code),
            "also_in": "; ".join(OrderedDict.fromkeys(also_in[a["ad_archive_id"]] for a in g["ads"]
                                                     if a["ad_archive_id"] in also_in)),
            "format": ad["display_format"] + (f" ({len(ad['cards'])} cards)" if ad["cards"] else ""),
            "live_since": oldest, "days_running": max_days, "platforms": ad["platforms"],
            "button_headline": ad["title"], "button_description": ad["link_description"], "cta": ad["cta_text"],
            "display_domain": ad["caption"], "landing_url": ad["link_url"],
            "caption_chars": chars, "before_see_more": before_more, "caption": ad["body"],
            "transcript": transcript,
            **{f: "" for f in ANALYSIS_FIELDS + (VIDEO_FIELDS if any_video else [])},
            "ad_ids": " ".join(OrderedDict.fromkeys(a["ad_archive_id"] for a in g["ads"])),
            "library_url": ad["library_url"],
        }
        rows.append(row)

        md = [
            f"# {code}", "",
            f"**{L['profile']}:** [{ad['page_name']}]({ad['page_url']}) · {ad['page_categories'] or L['nocat']}"
            f" · {ad['page_likes'] if ad['page_likes'] is not None else '?'} {L['likes']}"
            + (f" · {L['paid_by']}: **{ad['advertiser']}**" if ad["advertiser"] else "")
            + (f" · {L['partnership']}" if ad["partnership"] else ""),
            f"**{L['files']}:** {', '.join(saved) or L['none']}",
            f"**{L['library']}:** {ad['library_url']}", "",
            f"## {L['stats']}", "", f"| {L['metric']} | {L['value']} |", "|---|---|",
            f"| {L['ads_same']} | {len(g['ads'])} |",
            f"| {L['same_img']} | {row['same_image_other_copy'] or '-'} |",
            f"| {L['also_in']} | {row['also_in'] or '-'} |",
            f"| {L['profile_total']} | {totals.get(pid) if totals.get(pid) is not None else 'n/a'} |",
            f"| {L['profile_here']} | {ads_per_page[pid]} |",
            f"| {L['profile_creatives']} | {creatives_per_page[pid]} |",
            f"| {L['format']} | {row['format']} |",
            f"| {L['since']} | {oldest or '?'} ({max_days} {L['days']}) |",
            f"| {L['platforms']} | {ad['platforms']} |",
            f"| {L['rank']} | #{n} |",
            f"| {L['caption_len']} | {chars} {L['chars']} |", "",
            f"## {L['caption']}", "", quote_block(ad["body"], L["empty"]), "",
            f"## {L['button']}", "",
            f"- **{L['headline']}:** {ad['title'] or L['empty']}",
            f"- **{L['description']}:** {ad['link_description'] or L['empty']}",
            f"- **{L['cta']}:** {ad['cta_text'] or L['empty']}" + (f" `{ad['cta_type']}`" if ad["cta_type"] else ""),
            f"- **{L['domain']}:** {ad['caption'] or L['empty']}",
            f"- **{L['landing']}:** {ad['link_url'] or L['empty']}",
        ]
        if ad["cards"]:
            md += ["", f"## {L['cards']}", ""]
            for j, c in enumerate(ad["cards"], 1):
                md.append(f"**{L['card']} {j}**: {c['title'] or '-'} · {c['link_description'] or '-'} · "
                          f"{c['cta_text'] or '-'} · {c['link_url'] or '-'}")
                if c["body"] and c["body"] != ad["body"]:
                    md.append(quote_block(c["body"], L["empty"]))
                md.append("")
        extra = [t for t in ad["extra_texts"] if t and t != ad["body"]]
        if extra:
            md += ["", f"## {L['dco']}", ""] + [quote_block(t, L["empty"]) + "\n" for t in extra]
        if transcript:
            md += ["", f"## {L['transcript']}", "", "```", transcript, "```"]
        if frame_files:
            md += ["", f"## {L['frames']}", ""] + [f"- {f}" for f in frame_files]
        if len(g["ads"]) > 1:
            md += ["", f"## {L['same_creative_ads']}", "",
                   "| Ad ID | Profile | Start | Headline | CTA | Link |", "|---|---|---|---|---|---|"]
            md += [f"| [{a['ad_archive_id']}]({a['library_url']}) | {cell(a['page_name'])} | {a['start_date']} | "
                   f"{cell(a['title'])} | {cell(a['cta_text'])} | {cell(a['link_url'])} |" for a in g["ads"]]
            if all((a["title"], a["link_url"], a["cta_text"]) == (ad["title"], ad["link_url"], ad["cta_text"])
                   for a in g["ads"]):
                md += ["", f"_{L['identical']}_"]
        fields = ANALYSIS_FIELDS + (VIDEO_FIELDS if ad["is_video"] else [])
        md += ["", f"## {L['analysis']}", ""] + [f"- **{L['f_' + f]}:** {PLACEHOLDER}" for f in fields]
        md += ["", f"_{L['collected']} {today} · {L['source']}: {source}_"]
        (out / f"{code}.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    meta = {"name": name, "source": source, "total": total, "collected": today, "lang": lang}
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
    write_tables(rows, out)
    write_index(rows, meta, out)
    return rows


def write_tables(rows, out: Path):
    if not rows:
        return
    cols = list(rows[0])
    with open(out / "data.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font
        from openpyxl.utils import get_column_letter
    except ImportError:
        return
    wb = Workbook()
    ws = wb.active
    ws.title = "Creatives"
    ws.append(cols)
    for r in rows:
        ws.append([r[c] for c in cols])
    for c in ws[1]:
        c.font = Font(bold=True)
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = ws.dimensions
    wide = {"caption": 70, "transcript": 60, "button_headline": 40, "button_description": 30,
            "landing_url": 40, "files": 28, "before_see_more": 50}
    wrap = {get_column_letter(cols.index(c) + 1) for c in ("caption", "transcript") if c in cols}
    for i, c in enumerate(cols, 1):
        ws.column_dimensions[get_column_letter(i)].width = wide.get(c, 16)
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(vertical="top", wrap_text=c.column_letter in wrap)
    wb.save(out / "data.xlsx")


def write_index(rows, meta, out: Path, synthesis: str = ""):
    L = LABELS[meta.get("lang", "en")]
    n_ads = sum(int(r["ads_with_this_creative"]) for r in rows)
    pages = OrderedDict()
    for r in rows:
        p = pages.setdefault(r["profile"] or r["page_id"], {"name": r["profile"], "url": r["profile_url"], "creatives": 0,
                                            "ads": 0, "total": r["profile_active_ads"], "likes": r["profile_likes"]})
        p["creatives"] += 1
        p["ads"] += int(r["ads_with_this_creative"])
    weighted = lambda key: Counter(r[key] for r in rows for _ in range(int(r["ads_with_this_creative"])))
    landing = Counter(re.sub(r"^http://", "https://", r["landing_url"]).split("?")[0]
                      for r in rows for _ in range(int(r["ads_with_this_creative"])))
    na = lambda v: "n/a" if v in (None, "") else v

    X = [f"# {L['i_title']} · {meta['name']}", "",
         f"{L['collected']} **{meta['collected']}** · {L['source']}: {meta['source']}", "",
         f"- {L['i_results']}: **{meta['total']}**",
         f"- {L['i_collected']}: **{n_ads}** → **{len(rows)} {L['i_distinct']}**",
         f"- {L['i_profiles']}: **{len(pages)}**", "", L["i_files"], "",
         f"## {L['i_prof_h']}", "", f"| {L['i_prof_cols']} |", "|---|---|---|---|---|"]
    for p in sorted(pages.values(), key=lambda p: -p["ads"]):
        X.append(f"| [{cell(p['name'])}]({p['url']}) | {na(p['total'])} | {p['ads']} | {p['creatives']} | {na(p['likes'])} |")
    X += ["", f"## {L['i_cta_h']}"]
    for title, counter in ((L["i_cta"], weighted("cta")), (L["i_domain"], weighted("display_domain")),
                           (L["i_landing"], landing)):
        X += ["", f"| {title} | {L['i_ads']} |", "|---|---|"]
        X += [f"| {k or L['empty']} | {v} |" for k, v in counter.most_common()]
    X += ["", f"## {L['i_creatives']}", "", f"| {L['i_cols']} |", "|" + "---|" * 11]
    for r in rows:
        first = r["files"].split(" ")[0] if r["files"] else ""
        link = f"[{r['code']}]({first})" if first else r["code"]
        X.append(f"| {r['code'][-3:]} | {link} | {cell(r['profile'])} | {r['ads_with_this_creative']} | "
                 f"{r['days_running']} | {cell(r['button_headline'])[:70]} | {cell(r['cta'])} | "
                 f"{cell(r.get('angle')) or PLACEHOLDER} | {cell(r.get('persona')) or PLACEHOLDER} | "
                 f"{cell(r.get('visual_format')) or PLACEHOLDER} | {cell(r['caption'] or r.get('transcript'))[:90]}… |")
    X += ["", f"## {L['i_synth']}", "", synthesis or PLACEHOLDER, ""]
    (out / "INDEX.md").write_text("\n".join(X), encoding="utf-8")


# ── CLI ──────────────────────────────────────────────────────────────────────

def run_one(args, url: str | None = None, html_file: str | None = None, also_in: dict | None = None,
            name: str | None = None):
    """Harvest one link (or saved page) into its folder. Returns the output folder, or None if nothing matched."""
    totals: dict = {}
    if url:
        src_url = url
        url = force_media_type(src_url, args.media)
        total, items, totals = asyncio.run(collect(url, args.max, not args.headed, not args.no_profile_totals))
        if not items and args.media != "all":
            # Meta's media_type filter returns 0 on some links (seen on view_all_page_id pages that do run
            # image ads): collect everything and filter client-side instead. Oversample so --max still means
            # "kept ads" once the other formats are dropped.
            logger.info("Server-side media filter returned nothing: retrying with media_type=all, filtering locally")
            url = force_media_type(src_url, "all")
            total, items, totals = asyncio.run(collect(url, max(args.max * 4, 2000), not args.headed,
                                                       not args.no_profile_totals))
        source = url
    else:
        html = Path(html_file).read_text(encoding="utf-8", errors="replace")
        total, items = parse_html(html)
        if not items:
            items, _ = parse_graphql(html)
        source = f"file {Path(html_file).name}"

    seen, unique = set(), []
    for it in items:
        aid = str(it.get("ad_archive_id") or "")
        if aid and aid not in seen:
            seen.add(aid)
            unique.append(it)

    ads = [normalize(i) for i in unique]
    if args.media == "image":
        ads = [a for a in ads if not a["is_video"] and any(k == "image" for k, _ in a["media"])]
    elif args.media == "video":
        ads = [a for a in ads if a["is_video"]]
    ads = ads[: args.max]
    logger.info(f"{len(unique)} unique ads, {len(ads)} match --media {args.media}")
    if not ads:
        logger.error("Nothing to save for this link (no ads of that media type, or Meta is throttling: "
                     "retry in 30-90 min).")
        return None

    display = name or (display_name(url, unique) if url else "Spy")
    prefix = derive_name(None, [{"page_name": display}])
    logger.info(f"Name prefix: {prefix}")
    root = Path(args.root or os.environ.get("AD_SPY_ROOT", "spy"))
    out = Path(args.out) if (args.out and not args.pages_from) else root / folder_name(display, args.media)
    if out.exists() and any(out.iterdir()) and not args.out:  # never overwrite an earlier harvest
        base, k = out, 2
        while out.exists():
            out, k = base.with_name(f"{base.name} ({k})"), k + 1
    logger.info(f"Downloading media → {out.resolve()}")
    groups = group(ads, args.media, dedupe=not args.no_dedupe)
    kept = {a["ad_archive_id"] for a in ads}
    rows = write_outputs(groups, prefix, out, source, total, totals,
                         [i for i in unique if str(i.get("ad_archive_id")) in kept],
                         args.lang, not args.no_frames, args.transcribe, args.whisper_model, also_in or {})
    logger.info(f"Done: {len(ads)} ads → {len(rows)} creatives in {out.resolve()}")
    return out


def pages_from(folder: Path) -> tuple[list[tuple[str, str]], dict]:
    """Advertisers of an existing harvest (data.csv) → [(page_id, page name)], {ad_id: parent code}."""
    table = next((folder / n for n in ("data.csv", "dados.csv") if (folder / n).exists()), folder / "data.csv")
    with open(table, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    code_col = "code" if "code" in rows[0] else "codigo"
    name_col = "profile" if "profile" in rows[0] else "perfil"
    pages = list(OrderedDict((r["page_id"], r[name_col]) for r in rows if r.get("page_id")).items())
    parent = {aid: r[code_col] for r in rows for aid in (r.get("ad_ids") or "").split()}
    return pages, parent


def main():
    ap = argparse.ArgumentParser(description="Harvest a Meta Ad Library result set into a swipe folder")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--url", help="Ad Library URL (keyword search or view_all_page_id)")
    src.add_argument("--html", help="Saved Ad Library .html (holds only the first ~30 ads)")
    src.add_argument("--pages-from", help="Existing harvest folder: harvest the FULL page of every advertiser "
                                          "found in it, one folder per advertiser (keyword searches only show "
                                          "the ads that contain the words)")
    ap.add_argument("--country", default="ALL", help="Country for --pages-from (default ALL; the country "
                                                      "filter changes what the Library shows)")
    ap.add_argument("--name", help="Display name used for the folder and file prefix "
                                   "(default: the advertiser's page name or the search term)")
    ap.add_argument("--out", help="Exact output folder (overrides --root and the automatic folder name)")
    ap.add_argument("--root", help="Parent folder for the automatic '<Page name> Image Ads DD.MM.YYYY' folder "
                                   "(default: $AD_SPY_ROOT or ./spy; with --pages-from: the parent's folder)")
    ap.add_argument("--media", choices=["image", "video", "all"], default="image",
                    help="Keep only image ads, only video ads, or all (default: image)")
    ap.add_argument("--max", type=int, default=500, help="Max ads to keep per link (default 500)")
    ap.add_argument("--lang", choices=["en", "pt"], default="en", help="Language of .md/INDEX labels")
    ap.add_argument("--transcribe", action="store_true", help="Transcribe videos locally (faster-whisper)")
    ap.add_argument("--whisper-model", default="small", help="faster-whisper model size (default small)")
    ap.add_argument("--no-frames", action="store_true", help="Skip ffmpeg hook-frame extraction for videos")
    ap.add_argument("--no-dedupe", action="store_true", help="Keep identical creatives as separate items")
    ap.add_argument("--no-profile-totals", action="store_true", help="Skip each profile's active-ad total")
    ap.add_argument("--delay", type=int, default=20, help="Seconds between advertisers with --pages-from")
    ap.add_argument("--headed", action="store_true", help="Show the browser window")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

    if args.pages_from:
        parent_dir = Path(args.pages_from)
        pages, parent = pages_from(parent_dir)
        args.root = args.root or str(parent_dir.parent)
        also_in = {k: f"{parent_dir.name}/{v}" for k, v in parent.items()}
        logger.info(f"{len(pages)} advertisers found in {parent_dir.name}")
        done = []
        for n, (pid, pname) in enumerate(pages, 1):
            logger.info(f"\n=== [{n}/{len(pages)}] {pname} ({pid})")
            existing = Path(args.root) / folder_name(pname, args.media)
            if (existing / "data.csv").exists() and f"view_all_page_id={pid}" in (existing / "meta.json").read_text(
                    encoding="utf-8", errors="replace"):  # resume: this advertiser was already harvested today
                logger.info(f"  already harvested → {existing.name}, skipping")
                done.append((pname, existing))
                continue
            done.append((pname, run_one(args, url=page_url(pid, args.country), name=pname, also_in=also_in)))
            if n < len(pages):
                time.sleep(args.delay)
        logger.info("\nSummary:\n" + "\n".join(f"  {p}: {o.name if o else 'nothing saved'}" for p, o in done))
        return
    if not run_one(args, url=args.url, html_file=args.html, name=args.name):
        sys.exit(1)


if __name__ == "__main__":
    main()
