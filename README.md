# Justin's Magic Music Box

Local-first macOS app: drop in a song → get instrument stems + the notation a musician needs to play it.

**v0 scope (built for Justin):**
- Hero outputs: **guitar tabs** (GP5 + ASCII + MIDI) and **violin sheet music** (MusicXML + PDF + MIDI)
- Phil hosts on his Mac. Outputs land in `~/Music/Justin's Magic Music Box/<song>/` for hand-off via Drive.
- Free-first: only OFL fonts and OSS libraries until the concept proves out.

Full plan: see `Projects/Justins Magic Music Box.md` in Obsidian.

## Stack

- Python 3.11 (via `uv`) · FastAPI · SQLite · SQLAlchemy
- Demucs v4 (htdemucs / htdemucs_6s) · Spotify Basic Pitch · music21 + MuseScore · pyguitarpro
- Vite + React + TypeScript (Phase 2+)

## Quick start (host: Phil's Mac)

```bash
cd ~/projects/justins-magic-music-box
just bootstrap   # one-time: install deps, create venvs, fetch models
just dev         # run API on http://127.0.0.1:8765
```

## Layout

```
app/                 FastAPI backend
  src/jmb/           Python package
workers/             Per-stage isolated venvs (Demucs, Basic Pitch, madmom)
ui/                  Vite + React frontend (Phase 2+)
scripts/             bootstrap, dev runner, model downloads
docs/                Architecture notes
```
