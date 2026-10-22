# music-llm-mcp

MCP 클라이언트(Claude Code, Claude Desktop 등)가 **다른 LLM**(OpenAI, Gemini, Ollama)에게
코드 진행과 멜로디를 요청하고, 결과를 **MIDI 파일**로 저장하는 MCP 서버입니다.

> Anthropic, OpenAI, Google과 관련 없는 비공식 커뮤니티 프로젝트입니다.

## 도구

| 도구 | 하는 일 |
|---|---|
| `suggest_chords(key, bars, mood)` | 설정된 LLM에게 코드 진행을 받아옵니다 (마디당 1코드) |
| `generate_melody(key, chords, filename, tempo)` | LLM이 만든 멜로디를 MIDI로 저장하고, 경로와 요약만 반환합니다 |
| `export_midi(notes, filename, tempo)` | 클라이언트가 직접 쓴 음표를 MIDI로 저장합니다 |

## 설치와 등록

키 없이 `mock` 모드로 바로 시험할 수 있습니다.

**Claude Code**

```bash
claude mcp add music-llm -e MUSIC_LLM_PROVIDER=mock -- uv run --directory /path/to/music-llm-mcp music-llm-mcp
```

**Claude Desktop** (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "music-llm": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/music-llm-mcp", "music-llm-mcp"],
      "env": {
        "MUSIC_LLM_PROVIDER": "openai",
        "OPENAI_API_KEY": "sk-..."
      }
    }
  }
}
```

## 설정 (환경변수)

| 변수 | 기본값 | 설명 |
|---|---|---|
| `MUSIC_LLM_PROVIDER` | `mock` | `mock` / `openai` / `gemini` / `ollama` |
| `MUSIC_LLM_MODEL` | 제공자별 기본값 | 사용할 모델 이름 |
| `OPENAI_API_KEY`, `GEMINI_API_KEY` | – | 각 제공자의 공식 API 키 |
| `OLLAMA_HOST` | `http://localhost:11434` | 로컬 Ollama 주소 |
| `MUSIC_LLM_OUTPUT_DIR` | `~/music-llm-output` | MIDI 저장 폴더 (이 밖으로는 쓰지 않음) |
| `MUSIC_LLM_TIMEOUT` | `60` | LLM 호출 타임아웃(초) |
| `MUSIC_LLM_MAX_TOKENS` | `2000` | 호출당 최대 출력 토큰 |
| `MUSIC_LLM_MAX_CALLS` | `50` | 서버 실행당 최대 LLM 호출 수 (비용 보호) |

전체 목록은 [.env.example](.env.example)을 참고하세요.

## 안전 설계

- **API 키**는 환경변수로만 읽고, 로그·에러 메시지·도구 결과에 절대 넣지 않습니다.
- **다른 LLM의 응답은 신뢰하지 않습니다.** JSON으로 받아 스키마(코드 기호 형식, MIDI 음 범위, 개수 상한)로 검증한 뒤 구조화된 데이터만 돌려줍니다. 응답 안의 자유 텍스트는 클라이언트에 전달되지 않습니다.
- **파일 쓰기**는 출력 폴더 안으로만 합니다. 파일 이름은 영문, 숫자, `_`, `-`만 허용되고, 기존 파일은 `overwrite=true` 없이 덮어쓰지 않습니다.
- **stdout은 MCP 통신 전용**입니다. 로그는 모두 stderr로 보냅니다.
- **큰 결과**는 파일로 저장하고, 경로와 요약만 반환해 클라이언트의 컨텍스트를 아낍니다.
- 셸 실행이나 임의 URL 호출 같은 범용 도구는 없습니다.

## 개발

```bash
uv sync
uv run pytest
```

## 저작권 안내

- AI가 생성한 음악은 저작권 보호를 받지 못할 수 있습니다. 대부분의 나라에서 사람의 창작적 기여가 있어야 보호됩니다.
- 저작권이 있는 곡의 MIDI나 샘플을 이 저장소에 기여하지 마세요.

## 라이선스

MIT
