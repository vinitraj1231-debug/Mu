from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from yt_dlp import YoutubeDL


@dataclass
class Track:
    title: str
    webpage_url: str
    stream_url: str
    duration: int
    requester: str
    source: str = "yt-dlp"


def _is_url(text: str) -> bool:
    try:
        parsed = urlparse(text)
        return bool(parsed.scheme and parsed.netloc)
    except Exception:
        return False


def _ydl_extract(query: str) -> dict[str, Any]:
    ydl_opts = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "skip_download": True,
        "cachedir": False,
    }
    with YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(query, download=False)


async def resolve_track(query: str, requester: str, cache_get=None, cache_set=None) -> Track:
    cache_key = f"track:{query.strip().lower()}"
    if cache_get:
        cached = await cache_get(cache_key)
        if cached and cached.get("stream_url"):
            return Track(
                title=cached["title"],
                webpage_url=cached["webpage_url"],
                stream_url=cached["stream_url"],
                duration=int(cached.get("duration", 0)),
                requester=requester,
                source=cached.get("source", "cache"),
            )

    def _resolve() -> Track:
        data = _ydl_extract(query)
        if "entries" in data and data["entries"]:
            data = data["entries"][0]

        stream_url = data.get("url")
        if not stream_url and data.get("formats"):
            audio_formats = [f for f in data["formats"] if f.get("url")]
            audio_formats.sort(key=lambda f: (f.get("abr") or 0, f.get("tbr") or 0), reverse=True)
            if audio_formats:
                stream_url = audio_formats[0]["url"]

        if not stream_url:
            raise RuntimeError("yt-dlp could not resolve a playable stream URL")

        return Track(
            title=data.get("title") or "Unknown title",
            webpage_url=data.get("webpage_url") or query,
            stream_url=stream_url,
            duration=int(data.get("duration") or 0),
            requester=requester,
            source="yt-dlp",
        )

    if _is_url(query):
        # direct URL path still goes through yt-dlp to normalize and cache metadata
        pass

    track = await asyncio.to_thread(_resolve)

    if cache_set:
        await cache_set(
            cache_key,
            {
                "title": track.title,
                "webpage_url": track.webpage_url,
                "stream_url": track.stream_url,
                "duration": track.duration,
                "source": track.source,
            },
            6 * 3600,
        )

    return track
