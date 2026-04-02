import os
import uuid
import time
from pathlib import Path

import requests
from PIL import Image
from moviepy.editor import (
    ImageClip, AudioFileClip, TextClip, CompositeVideoClip,
    concatenate_videoclips, VideoFileClip, CompositeAudioClip,
)

from modules.config import section, ROOT
from modules import llm, tts
from modules.auth import get_api_key

OUTPUT_DIR = ROOT / "output"
SHORTS_DIR = ROOT / "shorts"
OUTPUT_DIR.mkdir(exist_ok=True)
SHORTS_DIR.mkdir(exist_ok=True)

WIDTH, HEIGHT, FPS = 1080, 1920, 30


def _fetch_pexels_videos(query: str, count: int = 5) -> list[str]:
    cfg = section("visuals")
    api_key = get_api_key("pexels") or cfg.get("pexels_api_key", "")
    if not api_key:
        raise RuntimeError("No Pexels API key. Run: python main.py auth keys")

    resp = requests.get(
        "https://api.pexels.com/videos/search",
        headers={"Authorization": api_key},
        params={
            "query": query,
            "per_page": count,
            "orientation": "portrait",
            "size": "medium",
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    paths = []
    for video in data.get("videos", [])[:count]:
        files = video.get("video_files", [])
        hd = [f for f in files if f.get("height", 0) >= 1080 and f["file_type"] == "video/mp4"]
        url = hd[0]["link"] if hd else files[0]["link"]

        dl = requests.get(url, timeout=30)
        path = OUTPUT_DIR / f"stock_{uuid.uuid4().hex[:8]}.mp4"
        path.write_bytes(dl.content)
        paths.append(str(path))

    return paths


def _generate_dalle_images(prompts: list[str]) -> list[str]:
    from g4f.client import Client

    client = Client()

    paths = []
    for prompt in prompts:
        resp = client.images.generate(
            model="dall-e-3",
            prompt=f"Vertical 9:16 image for a YouTube Short: {prompt}",
            response_format="url",
        )
        img_url = resp.data[0].url
        dl = requests.get(img_url, timeout=30)
        path = OUTPUT_DIR / f"ai_{uuid.uuid4().hex[:8]}.png"
        path.write_bytes(dl.content)
        paths.append(str(path))
        time.sleep(1)

    return paths


def _build_video_from_stock(clips_paths: list[str], audio_path: str,
                            srt_path: str | None) -> str:
    audio = AudioFileClip(audio_path)
    duration = audio.duration

    raw_clips = []
    for p in clips_paths:
        try:
            c = VideoFileClip(p)
            c = c.resize(height=HEIGHT).crop(
                x_center=c.w / 2, y_center=c.h / 2, width=WIDTH, height=HEIGHT
            )
            raw_clips.append(c)
        except Exception:
            continue

    if not raw_clips:
        raise RuntimeError("No valid stock clips found")

    each_dur = duration / len(raw_clips)
    trimmed = [c.subclip(0, min(each_dur, c.duration)) for c in raw_clips]
    video = concatenate_videoclips(trimmed, method="compose")

    if video.duration < duration:
        video = video.loop(duration=duration)
    else:
        video = video.subclip(0, duration)

    video = video.set_audio(audio)

    if srt_path and Path(srt_path).exists():
        video = _add_subtitles(video, srt_path)

    out_path = str(SHORTS_DIR / f"short_{uuid.uuid4().hex[:8]}.mp4")
    video.write_videofile(out_path, fps=FPS, codec="libx264",
                          audio_codec="aac", threads=4, logger=None)
    audio.close()
    for c in raw_clips:
        c.close()
    return out_path


def _build_video_from_images(image_paths: list[str], audio_path: str,
                             srt_path: str | None) -> str:
    audio = AudioFileClip(audio_path)
    duration = audio.duration
    each_dur = duration / len(image_paths)

    clips = []
    for img_path in image_paths:
        img = Image.open(img_path).resize((WIDTH, HEIGHT), Image.LANCZOS)
        resized = OUTPUT_DIR / f"resized_{uuid.uuid4().hex[:6]}.png"
        img.save(str(resized))
        clip = ImageClip(str(resized)).set_duration(each_dur)
        clips.append(clip)

    video = concatenate_videoclips(clips, method="compose")
    video = video.set_audio(audio)

    if srt_path and Path(srt_path).exists():
        video = _add_subtitles(video, srt_path)

    out_path = str(SHORTS_DIR / f"short_{uuid.uuid4().hex[:8]}.mp4")
    video.write_videofile(out_path, fps=FPS, codec="libx264",
                          audio_codec="aac", threads=4, logger=None)
    audio.close()
    return out_path


def _add_subtitles(video, srt_path: str):
    from moviepy.video.tools.subtitles import SubtitlesClip

    def make_text(txt):
        return TextClip(
            txt, fontsize=60, color="yellow", font="Arial-Bold",
            stroke_color="black", stroke_width=3,
            size=(WIDTH - 100, None), method="caption",
        )

    subs = SubtitlesClip(srt_path, make_text)
    return CompositeVideoClip([
        video,
        subs.set_position(("center", HEIGHT * 0.7)),
    ])


def generate_short(topic: str | None = None) -> dict:
    yt_cfg = section("youtube")
    niche = yt_cfg.get("niche", "interesting facts")
    sentences = yt_cfg.get("script_sentences", 5)

    print("Step 1/5: Generating script...")
    if not topic:
        topic = llm.generate(
            f"Generate a single compelling video topic about: {niche}. "
            "Just the topic, nothing else. Max 10 words."
        )
    print(f"  Topic: {topic}")

    script = llm.generate(
        f"Write a YouTube Shorts script about: {topic}\n"
        f"Rules:\n"
        f"- Exactly {sentences} sentences\n"
        f"- Hook the viewer in the first sentence\n"
        f"- Conversational, energetic tone\n"
        f"- No stage directions, just spoken text\n"
        f"- Under 60 seconds when spoken aloud",
        system="You are a viral YouTube Shorts scriptwriter."
    )
    print(f"  Script: {script[:100]}...")

    print("Step 2/5: Generating metadata...")
    meta = llm.generate_json(
        f'For this YouTube Short script, generate a JSON object with '
        f'"title" (under 70 chars, catchy) and "description" (2-3 sentences with relevant hashtags).\n\n'
        f'Script: {script}'
    )
    title = meta.get("title", topic[:70])
    description = meta.get("description", "")
    print(f"  Title: {title}")

    print("Step 3/5: Generating audio + subtitles...")
    stem = f"narration_{uuid.uuid4().hex[:6]}"
    audio_path, srt_path = tts.synthesize(script, stem)
    print(f"  Audio: {audio_path}")

    print("Step 4/5: Fetching visuals...")
    vis_cfg = section("visuals")
    source = vis_cfg.get("source", "pexels")

    if source == "pexels":
        search_terms = llm.generate(
            f"Give me a single 2-3 word search term for stock footage that matches this topic: {topic}. "
            "Just the search term, nothing else."
        )
        visual_paths = _fetch_pexels_videos(search_terms.strip('"').strip("'"), count=4)
    else:
        prompts = llm.generate_json(
            f"Generate a JSON array of 3-4 image description prompts for a vertical video about: {topic}. "
            "Each prompt should be vivid and photographic."
        )
        if isinstance(prompts, dict):
            prompts = list(prompts.values())[0]
        visual_paths = _generate_dalle_images(prompts)

    print("Step 5/5: Assembling video...")
    if source == "pexels":
        video_path = _build_video_from_stock(visual_paths, str(audio_path), str(srt_path) if srt_path else None)
    else:
        video_path = _build_video_from_images(visual_paths, str(audio_path), str(srt_path) if srt_path else None)

    print(f"  Video: {video_path}")

    _cleanup_temp_files(visual_paths, str(audio_path), str(srt_path) if srt_path else None)

    return {
        "video_path": video_path,
        "title": title,
        "description": description,
        "topic": topic,
        "script": script,
    }


def _cleanup_temp_files(visual_paths: list[str], audio_path: str,
                        srt_path: str | None):
    for p in visual_paths:
        try:
            os.remove(p)
        except OSError:
            pass
    for p in [audio_path, srt_path]:
        if p:
            try:
                os.remove(p)
            except OSError:
                pass
    for p in OUTPUT_DIR.glob("resized_*.png"):
        try:
            p.unlink()
        except OSError:
            pass
