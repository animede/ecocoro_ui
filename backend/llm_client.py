"""Thin OpenAI-compatible chat completions client for prompt expansion/translation."""
import httpx
from fastapi import HTTPException

TIMEOUT = httpx.Timeout(60.0, connect=10.0)

SYSTEM_MESSAGE_UPSAMPLING_T2I = """You are an expert prompt engineer for FLUX.2 by Black Forest Labs. Rewrite user prompts to be more descriptive while strictly preserving their core subject and intent.

Guidelines:
1. Structure: Keep structured inputs structured (enhance within fields). Convert natural language to detailed paragraphs.
2. Details: Add concrete visual specifics - form, scale, textures, materials, lighting (quality, direction, color), shadows, spatial relationships, and environmental context.
3. Text in Images: Put ALL text in quotation marks, matching the prompt's language. Always provide explicit quoted text for objects that would contain text in reality (signs, labels, screens, etc.) - without it, the model generates gibberish.

Output only the revised prompt and nothing else.

Additional note for this model (ecocoro): it understands a mix of Danbooru-style tags and natural language, in the order [period/safety tags/highreso] [subject count] [general tags] followed by a natural language description (e.g. "recent, highreso, 1girl, solo, close-up, brown hair, blue eyes, ..."). If the user's instruction is in Japanese, translate it and output the final prompt in English, mixing danbooru tags and natural language in that style."""

SYSTEM_MESSAGE_UPSAMPLING_I2I = """You are FLUX.2 by Black Forest Labs, an image-editing expert. You convert editing requests into one concise instruction (50-80 words, ~30 for brief requests).

Rules:
- Single instruction only, no commentary
- Use clear, analytical language (avoid "whimsical," "cascading," etc.)
- Specify what changes AND what stays the same (face, lighting, composition)
- Reference actual image elements
- Turn negatives into positives ("don't change X" → "keep X")
- Make abstractions concrete ("futuristic" → "glowing cyan neon, metallic panels")
- Keep content PG-13

Output only the final instruction in plain text and nothing else."""

SYSTEM_MESSAGE_TRANSLATE_JA2EN = (
    "あなたは画像生成プロンプトの専門翻訳者です。入力された日本語テキストを、"
    "画像生成に適した自然な英語に翻訳し、翻訳結果のみを出力してください。"
)
SYSTEM_MESSAGE_TRANSLATE_EN2JA = (
    "あなたは画像生成プロンプトの専門翻訳者です。入力された英語テキストを、"
    "自然な日本語に翻訳し、翻訳結果のみを出力してください。"
)


class LLMClient:
    def __init__(self, endpoint: str, model: str, api_key: str):
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.api_key = api_key

    async def chat(self, system_message: str, user_message: str) -> str:
        url = f"{self.endpoint}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.7,
        }
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.post(url, json=payload, headers=headers)
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"LLMサーバーへの接続に失敗しました ({url}): {exc}",
            ) from exc

        if resp.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"LLMサーバーがエラーを返しました (status={resp.status_code}): {resp.text[:500]}",
            )

        try:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            raise HTTPException(
                status_code=502,
                detail=f"LLMサーバーの応答形式が不正です: {exc}",
            ) from exc

        return content.strip()
