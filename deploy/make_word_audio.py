#!/usr/bin/env python3
"""Make one mp3 per Japanese word in content/<country>/words.yaml (edge-tts, voice ja-JP-NanamiNeural).

The mp3s are committed under static/audio/<country>/<reading>.mp3, so the server needs no TTS.
Run again after a word is added: python3 deploy/make_word_audio.py [country] (EDGE_TTS = path to the edge-tts binary).
Existing files are kept; pass --force to remake them.
"""
import os
import pathlib
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
EDGE_TTS = os.environ.get("EDGE_TTS", "edge-tts")
VOICE = "ja-JP-NanamiNeural"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    country = args[0] if args else "japan"
    force = "--force" in sys.argv
    module = yaml.safe_load((ROOT / "content" / country / "words.yaml").read_text())
    out = ROOT / "static" / "audio" / country
    out.mkdir(parents=True, exist_ok=True)
    for activity in module["activities"]:
        for w in activity.get("words", []):
            path = out / f"{w['reading']}.mp3"
            if path.exists() and not force:
                continue
            subprocess.run([EDGE_TTS, "--voice", VOICE, "--rate=-15%", "--text", w["japanese"], "--write-media", str(path)], check=True)
            print(path.relative_to(ROOT), path.stat().st_size)


if __name__ == "__main__":
    main()
