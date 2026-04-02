import asyncio
import tempfile
from pathlib import Path

import edge_tts

from modules.config import section, ROOT

OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


async def _edge_tts(text: str, output_stem: str) -> tuple[Path, Path]:
    cfg = section("tts")
    voice = cfg.get("voice", "en-US-ChristopherNeural")
    rate = cfg.get("rate", "+0%")

    audio_path = OUTPUT_DIR / f"{output_stem}.mp3"
    srt_path = OUTPUT_DIR / f"{output_stem}.srt"

    communicate = edge_tts.Communicate(text, voice, rate=rate)
    submaker = edge_tts.SubMaker()

    with open(audio_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                submaker.feed(chunk)

    srt_content = submaker.generate_subs()
    srt_path.write_text(srt_content, encoding="utf-8")

    return audio_path, srt_path


def _openai_tts(text: str, output_stem: str) -> tuple[Path, None]:
    from openai import OpenAI

    cfg = section("tts")
    client = OpenAI(api_key=cfg["openai_api_key"])
    voice = cfg.get("openai_voice", "onyx")

    audio_path = OUTPUT_DIR / f"{output_stem}.mp3"

    response = client.audio.speech.create(model="tts-1", voice=voice, input=text)
    response.stream_to_file(str(audio_path))

    return audio_path, None


def synthesize(text: str, output_stem: str = "narration") -> tuple[Path, Path | None]:
    cfg = section("tts")
    provider = cfg.get("provider", "edge")

    if provider == "edge":
        return asyncio.run(_edge_tts(text, output_stem))
    elif provider == "openai":
        return _openai_tts(text, output_stem)
    else:
        raise ValueError(f"Unknown TTS provider: {provider}")
