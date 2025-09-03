import asyncio
import os
from openai import OpenAI


async def transcribe(path: str) -> str:
    """Transcribe audio file at ``path`` using Whisper (turbo)."""
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    with open(path, "rb") as f:
        resp = await asyncio.to_thread(
            client.audio.transcriptions.create,
            model="gpt-4o-mini-transcribe",
            file=f,
        )
    return resp.text
