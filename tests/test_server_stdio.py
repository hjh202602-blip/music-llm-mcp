"""End-to-end: start the real server over stdio in mock mode and call its tools."""

import asyncio
import sys

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def _run(tmp_path):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "music_llm_mcp.server"],
        env={"MUSIC_LLM_PROVIDER": "mock", "MUSIC_LLM_OUTPUT_DIR": str(tmp_path)},
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()

        tools = await session.list_tools()
        assert {t.name for t in tools.tools} == {"suggest_chords", "generate_melody", "export_midi"}

        chords = await session.call_tool("suggest_chords", {"key": "C major", "bars": 4})
        assert not chords.is_error
        assert chords.structured_content["chords"] == ["C", "G", "Am", "F"]

        melody = await session.call_tool(
            "generate_melody", {"key": "C major", "chords": ["C", "G", "Am", "F"], "filename": "demo"}
        )
        assert not melody.is_error
        assert (tmp_path / "demo.mid").exists()
        assert melody.structured_content["note_count"] == 16

        again = await session.call_tool(
            "generate_melody", {"key": "C major", "chords": ["C"], "filename": "demo"}
        )
        assert again.is_error  # refuses to overwrite

        escape = await session.call_tool(
            "export_midi", {"notes": [{"pitch": 60, "start": 0, "duration": 1}], "filename": "../escape"}
        )
        assert escape.is_error
        assert not (tmp_path.parent / "escape.mid").exists()


def test_stdio_end_to_end(tmp_path):
    asyncio.run(_run(tmp_path))


async def _missing_key(tmp_path):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "music_llm_mcp.server"],
        env={"MUSIC_LLM_PROVIDER": "openai", "OPENAI_API_KEY": "", "MUSIC_LLM_OUTPUT_DIR": str(tmp_path)},
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool("suggest_chords", {"key": "C major"})
        assert result.is_error
        assert "OPENAI_API_KEY is not set" in result.content[0].text


def test_missing_key_is_a_clean_tool_error(tmp_path):
    asyncio.run(_missing_key(tmp_path))
