#!/usr/bin/env python3
"""Make one mp3 per Japanese word in content/<country>/*.yaml (edge-tts, voice ja-JP-NanamiNeural).

A word is any `words` entry or `cards` entry with both `japanese` and `reading` (e.g. the food cards),
and in a lesson any page, spot or card with both (a reading of plain letters and spaces only).

The mp3s are committed under static/audio/<country>/<reading>.mp3, so the server needs no TTS.
Run again after a word is added: python3 deploy/make_word_audio.py [country] (EDGE_TTS = path to the edge-tts binary).
Existing files are kept; pass --force to remake them.

If edge-tts fails (not installed, or Microsoft answers 403, as from the build server since 2026-10-11),
the script uses Google Translate TTS instead (a different Japanese voice, no key, stdlib only).
Pass --google to skip edge-tts. Pass --dry-run to list the missing mp3s and make nothing.
"""
import os
import pathlib
import re
import subprocess
import sys
import urllib.parse
import urllib.request

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
EDGE_TTS = os.environ.get("EDGE_TTS", "edge-tts")
VOICE = "ja-JP-NanamiNeural"
GOOGLE_TTS = "https://translate.google.com/translate_tts?ie=UTF-8&tl=ja&client=tw-ob&ttsspeed=0.8&q="


def edge(text, path):
    """True when edge-tts wrote a non-empty mp3. A failed run leaves a 0-byte file: remove it."""
    try:
        subprocess.run([EDGE_TTS, "--voice", VOICE, "--rate=-15%", "--text", text, "--write-media", str(path)],
                       check=True, capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        pass
    if path.exists() and path.stat().st_size > 0:
        return True
    path.unlink(missing_ok=True)
    return False


def google(text, path):
    req = urllib.request.Request(GOOGLE_TTS + urllib.parse.quote(text), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
        if r.headers.get_content_type() != "audio/mpeg" or not data:
            raise RuntimeError(f"Google TTS gave {r.headers.get_content_type()}, {len(data)} bytes for {text}")
    path.write_bytes(data)


def sayable(country):
    for f in sorted((ROOT / "content" / country).glob("*.yaml")):
        module = yaml.safe_load(f.read_text()) or {}
        for activity in module.get("activities", []):
            for w in activity.get("words", []) + activity.get("cards", []):
                if w.get("japanese") and w.get("reading"):
                    yield w
            for page in activity.get("pages", []):
                for w in [page] + page.get("spots", []) + page.get("cards", []):
                    if w.get("japanese") and re.fullmatch(r"[a-z]+( [a-z]+)*", w.get("reading", "")):
                        yield w


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    country = args[0] if args else "japan"
    force, use_google, dry = "--force" in sys.argv, "--google" in sys.argv, "--dry-run" in sys.argv
    out = ROOT / "static" / "audio" / country
    out.mkdir(parents=True, exist_ok=True)
    done = set()
    for w in sayable(country):
        path = out / f"{w['reading']}.mp3"
        if path in done or (path.exists() and not force):
            continue
        done.add(path)
        if dry:
            print("missing", path.relative_to(ROOT), w["japanese"])
            continue
        source = "edge"
        if use_google or not edge(w["japanese"], path):
            source = "google"
            google(w["japanese"], path)
        print(path.relative_to(ROOT), path.stat().st_size, source)


if __name__ == "__main__":
    main()
