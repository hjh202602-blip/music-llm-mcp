"""MCP server entry point (stdio transport).

stdout is the MCP protocol channel: never print() in this package. Logs go to stderr.
"""

import logging
import sys
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, Field

from . import music
from .config import Settings, load_settings
from .providers import LLMClient, ProviderError

log = logging.getLogger("music_llm_mcp")

Key = Annotated[str, Field(description="Key such as 'C major', 'A minor', 'F# minor'", max_length=12)]
Bars = Annotated[int, Field(ge=1, le=32, description="Number of 4/4 bars")]
Tempo = Annotated[int, Field(ge=30, le=300, description="Tempo in BPM")]
Filename = Annotated[str, Field(description="Output file name without extension: letters, digits, '_' or '-'")]

class ChordResult(BaseModel):
    key: str
    chords: list[str]
    source: str


class MidiResult(BaseModel):
    path: str
    tempo: int
    note_count: int
    length_beats: float
    lowest: str
    highest: str


SYSTEM_PROMPT = (
    "You are a music composition assistant inside an automated tool. "
    "Reply with a single JSON object only, exactly in the requested shape, with no prose."
)


def build_server(settings: Settings) -> MCPServer:
    llm = LLMClient(settings)
    server = MCPServer(
        "music-llm-mcp",
        instructions=(
            "Composition helpers backed by another LLM "
            f"({settings.provider}/{settings.model}). "
            "Use suggest_chords for a progression, generate_melody to write a melody over it to a MIDI file, "
            "and export_midi to save notes you wrote yourself."
        ),
    )

    async def ask(prompt: str) -> str:
        try:
            return await llm.complete_json(SYSTEM_PROMPT, prompt)
        except ProviderError as e:
            raise ToolError(str(e)) from None

    @server.tool()
    async def suggest_chords(
        key: Key,
        bars: Bars = 8,
        mood: Annotated[str, Field(max_length=200, description="Feel of the piece, e.g. 'warm, nostalgic'")] = "",
    ) -> ChordResult:
        """Ask the configured LLM for a chord progression, one chord per bar."""
        try:
            music.parse_key(key)
        except ValueError as e:
            raise ToolError(str(e)) from None

        if settings.provider == "mock":
            chords = music.mock_chords(key, bars)
        else:
            raw = await ask(
                f"Write a chord progression in {key}, exactly {bars} chords (one per bar)."
                + (f" Mood: {mood}." if mood else "")
                + ' Use standard chord symbols like "Am7" or "G/B". Shape: {"chords": ["C", "G", ...]}'
            )
            try:
                chords = music.parse_chord_reply(raw)
            except ValueError as e:
                raise ToolError(f"{settings.provider}: {e}") from None

        return ChordResult(key=key, chords=chords, source=f"{settings.provider}/{settings.model}")

    @server.tool()
    async def generate_melody(
        key: Key,
        chords: Annotated[list[str], Field(min_length=1, max_length=music.MAX_CHORDS, description="One chord per bar")],
        filename: Filename,
        tempo: Tempo = 100,
        overwrite: bool = False,
    ) -> MidiResult:
        """Ask the configured LLM for a melody over the chords and save it as a MIDI file.

        Returns the file path and a short summary, not the full note list.
        """
        try:
            music.parse_key(key)
            music.validate_chords(chords)
            path = music.safe_output_path(settings.output_dir, filename)
        except ValueError as e:
            raise ToolError(str(e)) from None
        if path.exists() and not overwrite:
            raise ToolError(f"{path.name} already exists. Pass overwrite=true or choose another filename.")

        bars = len(chords)
        if settings.provider == "mock":
            notes = music.mock_melody(key, bars)
        else:
            raw = await ask(
                f"Write a singable melody in {key}, 4/4, {bars} bars ({bars * 4} beats), "
                f"over these chords, one per bar: {', '.join(chords)}. "
                "start and duration are in beats, pitch is a MIDI number between 55 and 84. "
                'Shape: {"notes": [{"pitch": 60, "start": 0, "duration": 1, "velocity": 90}, ...]}'
            )
            try:
                notes = music.parse_melody_reply(raw)
            except ValueError as e:
                raise ToolError(f"{settings.provider}: {e}") from None

        music.write_midi(notes, tempo, path)
        return MidiResult(path=str(path), tempo=tempo, **music.summarize(notes))

    @server.tool()
    def export_midi(
        notes: Annotated[list[music.Note], Field(min_length=1, max_length=music.MAX_NOTES)],
        filename: Filename,
        tempo: Tempo = 100,
        overwrite: bool = False,
    ) -> MidiResult:
        """Save notes you wrote yourself to a MIDI file in the output folder."""
        try:
            path = music.safe_output_path(settings.output_dir, filename)
        except ValueError as e:
            raise ToolError(str(e)) from None
        if path.exists() and not overwrite:
            raise ToolError(f"{path.name} already exists. Pass overwrite=true or choose another filename.")

        music.write_midi(notes, tempo, path)
        return MidiResult(path=str(path), tempo=tempo, **music.summarize(notes))

    return server


def main() -> None:
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        settings = load_settings()
    except ValueError as e:
        log.error("configuration error: %s", e)
        sys.exit(1)
    log.info("provider=%s model=%s output=%s", settings.provider, settings.model, settings.output_dir)
    build_server(settings).run("stdio")


if __name__ == "__main__":
    main()
