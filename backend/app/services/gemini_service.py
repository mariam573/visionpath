"""
Gemini Service — LLM brain for scene understanding and navigation Q&A
"""
from typing import List, Tuple, Any
from loguru import logger

from app.core.config import settings

# System prompt that shapes Gemini's navigation persona
SYSTEM_PROMPT = """You are VisionPath, an AI assistant helping visually impaired users navigate indoor environments safely.

Your responses must be:
1. CONCISE — maximum 2 sentences for navigation guidance
2. SPATIAL — always use clock-face directions (e.g. "at your 2 o'clock") and metric distances
3. PRIORITY-ORDERED — mention hazards first (steps, obstacles in path), then useful landmarks
4. CALM but URGENT when needed — for immediate hazards, use clear urgent language
5. In English by default (Arabic support coming in Phase 2)

NEVER say "I see" or "I detect" — speak as if the user is experiencing the environment.
Example: "Chair at your 10 o'clock, 1.2 meters. Door straight ahead, 3 meters."
"""


class GeminiService:
    def __init__(self):
        self._client = None

    def _get_client(self):
        """Lazy-initialize Gemini client."""
        if self._client is None:
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self._client = genai.GenerativeModel(
                model_name=settings.GEMINI_MODEL,
                system_instruction=SYSTEM_PROMPT,
            )
        return self._client

    def _format_objects(self, objects: List[Any]) -> str:
        """Format detected objects into a structured context string."""
        if not objects:
            return "No objects detected."
        lines = []
        for obj in objects:
            lines.append(
                f"- {obj.label}: {obj.clock_direction} o'clock, "
                f"{obj.distance_meters:.1f}m away (confidence: {getattr(obj, 'confidence', 1.0):.0%})"
            )
        return "\n".join(lines)

    async def describe_scene(
        self, objects: List[Any], user_query: str = "", scene_context: str = "indoor"
    ) -> Tuple[str, str]:
        """
        Generate a scene narrative and detect priority hazards.
        Returns (narrative, priority_alert).
        """
        client = self._get_client()
        objects_str = self._format_objects(objects)

        prompt = f"""Scene context: {scene_context}
Detected objects:
{objects_str}

User query: "{user_query if user_query else 'Describe my surroundings.'}"

Provide:
1. A brief spatial scene description (1-2 sentences)
2. Any immediate hazard alert (empty string if none)

Respond as JSON: {{"narrative": "...", "alert": "..."}}"""

        response = client.generate_content(prompt)
        text = response.text.strip()

        # Parse JSON response
        import json
        try:
            # Strip markdown code fences if present
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            data = json.loads(text.strip())
            return data.get("narrative", text), data.get("alert", "")
        except Exception:
            logger.warning("Gemini returned non-JSON, using raw text")
            return text, ""

    async def answer_navigation_query(
        self, query: str, objects: List[Any], scene_context: str = "indoor"
    ) -> str:
        """Answer a specific navigation question from the user."""
        client = self._get_client()
        objects_str = self._format_objects(objects)

        prompt = f"""Scene context: {scene_context}
Currently detected objects:
{objects_str}

User's question: "{query}"

Answer concisely with spatial directions. Use clock-face directions and metric distances."""

        response = client.generate_content(prompt)
        return response.text.strip()
