#!/usr/bin/env python3
"""Make one mp3 per Japanese word in content/<country>/*.yaml (edge-tts, voice ja-JP-NanamiNeural).

A word is any `words` entry or `cards` entry with both `japanese` and `reading` (e.g. the food cards),
and in a lesson any page, spot or card with both (a reading of plain letters and spaces only).

The mp3s are committed under static/audio/<country>/<reading>.mp3, so the server needs no TTS.
Run again after a word is added: python3 deploy/make_word_audio.py [country] (EDGE_TTS = path to the edge-tts binary).
Existing files are kept; pass --force to remake them.
"""
import os
import pathlib
import re
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
EDGE_TTS = os.environ.get("EDGE_TTS", "edge-tts")
VOICE = "ja-JP-NanamiNeural"


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
    force = "--force" in sys.argv
    out = ROOT / "static" / "audio" / country
    out.mkdir(parents=True, exist_ok=True)
    for w in sayable(country):
            path = out / f"{w['reading']}.mp3"
            if path.exists() and not force:
                continue
            subprocess.run([EDGE_TTS, "--voice", VOICE, "--rate=-15%", "--text", w["japanese"], "--write-media", str(path)], check=True)
            print(path.relative_to(ROOT), path.stat().st_size)


if __name__ == "__main__":
    main()
