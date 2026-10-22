"""Music data, validation of LLM output, and MIDI writing.

Everything another LLM returns goes through the parsers here. Only validated
structured data (chord symbols, numeric notes) ever reaches the MCP client, so
free text injected into a model's reply cannot pass through as instructions.
"""

import json
import re
from pathlib import Path

from midiutil import MIDIFile
from pydantic import BaseModel, Field, ValidationError

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLATS = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}

KEY_RE = re.compile(r"^([A-G][#b]?) (major|minor)$")
CHORD_RE = re.compile(r"^[A-G][#b]?[a-zA-Z0-9#b+()]{0,10}(/[A-G][#b]?)?$")
FILENAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

MAX_NOTES = 512
MAX_CHORDS = 64


class Note(BaseModel):
    pitch: int = Field(ge=0, le=127, description="MIDI note number, 60 = middle C")
    start: float = Field(ge=0, le=1024, description="Start time in beats")
    duration: float = Field(gt=0, le=16, description="Length in beats")
    velocity: int = Field(default=90, ge=1, le=127)


class _ChordReply(BaseModel):
    chords: list[str] = Field(min_length=1, max_length=MAX_CHORDS)


class _MelodyReply(BaseModel):
    notes: list[Note] = Field(min_length=1, max_length=MAX_NOTES)


def parse_key(key: str) -> tuple[int, str]:
    """'A minor' -> (9, 'minor'). Raises ValueError for anything else."""
    m = KEY_RE.match(key.strip())
    if not m:
        raise ValueError(f"key must look like 'C major' or 'F# minor', got {key!r}")
    tonic, mode = m.groups()
    return NOTE_NAMES.index(FLATS.get(tonic, tonic)), mode


def validate_chords(chords: list[str]) -> list[str]:
    bad = [c for c in chords if not CHORD_RE.match(c)]
    if bad:
        raise ValueError(f"invalid chord symbols: {bad[:5]}")
    return chords


def _load_json(raw: str) -> object:
    text = raw.strip()
    # Some models wrap JSON in ```json fences despite being told not to.
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise ValueError("model did not return valid JSON") from None


def parse_chord_reply(raw: str) -> list[str]:
    try:
        reply = _ChordReply.model_validate(_load_json(raw))
    except ValidationError as e:
        raise ValueError(f"model returned chords in the wrong shape: {e.error_count()} errors") from None
    return validate_chords(reply.chords)


def parse_melody_reply(raw: str) -> list[Note]:
    try:
        reply = _MelodyReply.model_validate(_load_json(raw))
    except ValidationError as e:
        raise ValueError(f"model returned notes in the wrong shape: {e.error_count()} errors") from None
    return reply.notes


def safe_output_path(output_dir: Path, filename: str) -> Path:
    """Resolve filename inside output_dir. Rejects anything that could escape it."""
    if not FILENAME_RE.match(filename):
        raise ValueError("filename may only contain letters, digits, '_' and '-' (max 64), no extension")
    path = (output_dir / f"{filename}.mid").resolve()
    if not path.is_relative_to(output_dir):
        raise ValueError("filename resolves outside the output folder")
    return path


def write_midi(notes: list[Note], tempo: int, path: Path) -> None:
    midi = MIDIFile(1)
    midi.addTempo(track=0, time=0, tempo=tempo)
    for n in notes:
        midi.addNote(track=0, channel=0, pitch=n.pitch, time=n.start, duration=n.duration, volume=n.velocity)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        midi.writeFile(f)


def summarize(notes: list[Note]) -> dict:
    """Short description returned to the client instead of the full note list."""
    pitches = [n.pitch for n in notes]
    return {
        "note_count": len(notes),
        "length_beats": max(n.start + n.duration for n in notes),
        "lowest": NOTE_NAMES[min(pitches) % 12] + str(min(pitches) // 12 - 1),
        "highest": NOTE_NAMES[max(pitches) % 12] + str(max(pitches) // 12 - 1),
    }


# --- Deterministic output for the mock provider (no API key needed) ---

def mock_chords(key: str, bars: int) -> list[str]:
    tonic, mode = parse_key(key)
    if mode == "major":
        degrees = [(0, ""), (7, ""), (9, "m"), (5, "")]  # I V vi IV
    else:
        degrees = [(0, "m"), (8, ""), (3, ""), (10, "")]  # i VI III VII
    return [NOTE_NAMES[(tonic + off) % 12] + q for off, q in (degrees * bars)[:bars]]


def mock_melody(key: str, bars: int) -> list[Note]:
    tonic, mode = parse_key(key)
    scale = [0, 2, 4, 5, 7, 9, 11] if mode == "major" else [0, 2, 3, 5, 7, 8, 10]
    shape = [0, 2, 4, 2, 1, 3, 5, 4]
    return [
        Note(pitch=60 + tonic + scale[shape[i % len(shape)] % 7], start=i, duration=1)
        for i in range(bars * 4)
    ]
