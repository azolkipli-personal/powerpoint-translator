"""
Translation service interface and implementations.
Supports GLM-4, Kimi/Moonshot, MiniMax, Qwen, Gemini, OpenCode Zen/Go, and Ollama.
"""
from abc import ABC, abstractmethod
from typing import Optional
import httpx
import asyncio

from app.config import Settings


class TranslatorInterface(ABC):
    """Abstract interface for translation services."""
    
    @abstractmethod
    async def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        context: Optional[str] = None,
    ) -> tuple[str, bool]:
        """
        Translate text from source to target language.
        
        Returns:
            (translated_text, success)
        """
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """Return the model identifier."""
        pass


class GeminiTranslator(TranslatorInterface):
    """Google Gemini translator (free tier available)."""
    
    def __init__(self, settings: Settings, model: str = "gemini-2.5-flash-lite"):
        self.api_url = settings.gemini_api_url
        self.api_key = settings.gemini_api_key
        self.model = model
    
    async def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        context: Optional[str] = None,
    ) -> tuple[str, bool]:
        if not self.api_key:
            return text, False
        
        lang_map = {
            'ja': 'Japanese',
            'en': 'English',
        }
        
        parts = []
        if context:
            parts.append(context.strip())
        parts.append(
            f"Translate the following {lang_map.get(source_lang, source_lang)} text to {lang_map.get(target_lang, target_lang)}."
        )
        parts.append(
            "CRITICAL: Return ONLY the translated text. Do NOT include the original text, "
            "do NOT include arrows (→), do NOT include colons or labels, "
            "do NOT include the glossary or any other metadata. Just the translation itself."
        )
        parts.append(f"Text:\n{text}")
        parts.append("Translation:")
        prompt = "\n\n".join(parts)
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.api_url}/models/{self.model}:generateContent",
                    headers={
                        "Content-Type": "application/json",
                    },
                    params={"key": self.api_key},
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "temperature": 0.3,
                            "maxOutputTokens": 2048,
                        },
                    },
                )
                
                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [{}])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            translated = parts[0].get("text", text)
                            return translated.strip(), True
                return text, False
        except Exception as e:
            print(f"Gemini translation error ({self.model}): {e}")
            return text, False
    
    def get_model_name(self) -> str:
        return self.model


class OpenCodeTranslator(TranslatorInterface):
    """OpenCode Zen/Go translator - unified access to GLM, Kimi, MiniMax."""
    
    def __init__(self, settings: Settings, model: str = "auto"):
        self.api_url = settings.opencode_api_url
        self.api_key = settings.opencode_api_key
        self.model = model
    
    async def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        context: Optional[str] = None,
    ) -> tuple[str, bool]:
        if not self.api_key:
            return text, False
        
        lang_map = {
            'ja': 'Japanese',
            'en': 'English',
        }
        
        prompt = f"""Translate from {lang_map.get(source_lang, source_lang)} to {lang_map.get(target_lang, target_lang)}.
Preserve formatting. Output only the translation.

{f'Context: {context}' if context else ''}

Original: {text}
Translation:"""
        
        # Model selection: auto picks best available
        model_id = self.model if self.model != "auto"else"deepseek-v4-flash"
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.api_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model_id,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                    },
                )
                
                if response.status_code == 200:
                    data = response.json()
                    translated = data.get("choices", [{}])[0].get("message", {}).get("content", text)
                    return translated.strip(), True
                print(f"OpenCode HTTP {response.status_code} ({self.model}): {response.text[:200]}")
                return text, False
        except Exception as e:
            # Include the exception type: many network errors stringify to an
            # empty message (TimeoutError), which is useless for diagnosis.
            print(f"OpenCode translation error [{type(e).__name__}]: {e}")
            return text, False
    
    def get_model_name(self) -> str:
        return f"opencode-{self.model}"


class GLMTranslator(TranslatorInterface):
    """GLM-4 translator via BigModel API."""
    
    def __init__(self, settings: Settings):
        self.api_url = settings.glm_api_url
        self.api_key = settings.glm_api_key
    
    async def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        context: Optional[str] = None,
    ) -> tuple[str, bool]:
        if not self.api_key:
            return text, False
        
        lang_map = {
            'ja': 'Japanese',
            'en': 'English',
        }
        
        prompt = f"""Translate the following text from {lang_map.get(source_lang, source_lang)} to {lang_map.get(target_lang, target_lang)}.
Preserve the original formatting and structure. Only provide the translation, no explanations.

{f'Context: {context}' if context else ''}

Text to translate:
{text}

Translation:"""
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.api_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "glm-4",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                    },
                )
                
                if response.status_code == 200:
                    data = response.json()
                    translated = data.get("choices", [{}])[0].get("message", {}).get("content", text)
                    return translated.strip(), True
                return text, False
        except Exception as e:
            print(f"GLM translation error: {e}")
            return text, False
    
    def get_model_name(self) -> str:
        return "glm-4"


class KimiTranslator(TranslatorInterface):
    """Kimi (Moonshot) translator via Moonshot API."""
    
    def __init__(self, settings: Settings):
        self.api_url = settings.kimi_api_url
        self.api_key = settings.kimi_api_key
    
    async def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        context: Optional[str] = None,
    ) -> tuple[str, bool]:
        if not self.api_key:
            return text, False
        
        lang_map = {
            'ja': 'Japanese',
            'en': 'English',
        }
        
        prompt = f"""Translate from {lang_map.get(source_lang, source_lang)} to {lang_map.get(target_lang, target_lang)}.
Maintain formatting. Output only the translation.

{f'Context: {context}' if context else ''}

Original:
{text}

Translation:"""
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.api_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "moonshot-v1-8k",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                    },
                )
                
                if response.status_code == 200:
                    data = response.json()
                    translated = data.get("choices", [{}])[0].get("message", {}).get("content", text)
                    return translated.strip(), True
                return text, False
        except Exception as e:
            print(f"Kimi translation error: {e}")
            return text, False
    
    def get_model_name(self) -> str:
        return "kimi"


class MiniMaxTranslator(TranslatorInterface):
    """MiniMax translator."""
    
    def __init__(self, settings: Settings):
        self.api_url = settings.minimax_api_url
        self.api_key = settings.minimax_api_key
        self.group_id = settings.minimax_group_id
    
    async def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        context: Optional[str] = None,
    ) -> tuple[str, bool]:
        if not self.api_key or not self.group_id:
            return text, False
        
        lang_map = {
            'ja': 'Japanese',
            'en': 'English',
        }
        
        prompt = f"""Translate from {lang_map.get(source_lang, source_lang)} to {lang_map.get(target_lang, target_lang)}.
{f'Context: {context}' if context else ''}

Original: {text}
Translation:"""
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.api_url}/text/chatcompletion_v2",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "abab6.5s-chat",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                    },
                )
                
                if response.status_code == 200:
                    data = response.json()
                    translated = data.get("choices", [{}])[0].get("message", {}).get("content", text)
                    return translated.strip(), True
                return text, False
        except Exception as e:
            print(f"MiniMax translation error: {e}")
            return text, False
    
    def get_model_name(self) -> str:
        return "minimax"


class QwenTranslator(TranslatorInterface):
    """Qwen translator via DashScope API."""
    
    def __init__(self, settings: Settings):
        self.api_url = settings.qwen_api_url
        self.api_key = settings.qwen_api_key
    
    async def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        context: Optional[str] = None,
    ) -> tuple[str, bool]:
        if not self.api_key:
            return text, False
        
        lang_map = {
            'ja': 'Japanese',
            'en': 'English',
        }
        
        prompt = f"""Translate from {lang_map.get(source_lang, source_lang)} to {lang_map.get(target_lang, target_lang)}.
{f'Context: {context}' if context else ''}

Original: {text}
Translation:"""
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.api_url}/services/aigc/text-generation/generation",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "qwen-turbo",
                        "input": {"messages": [{"role": "user", "content": prompt}]},
                        "parameters": {"temperature": 0.3},
                    },
                )
                
                if response.status_code == 200:
                    data = response.json()
                    translated = data.get("output", {}).get("text", text)
                    return translated.strip(), True
                return text, False
        except Exception as e:
            print(f"Qwen translation error: {e}")
            return text, False
    
    def get_model_name(self) -> str:
        return "qwen"


class OllamaTranslator(TranslatorInterface):
    """Local translation via Ollama."""
    
    def __init__(self, settings: Settings):
        self.api_url = settings.ollama_url or "http://localhost:11434"
    
    async def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        context: Optional[str] = None,
    ) -> tuple[str, bool]:
        lang_map = {
            'ja': 'Japanese',
            'en': 'English',
        }
        
        prompt = f"""Translate from {lang_map.get(source_lang, source_lang)} to {lang_map.get(target_lang, target_lang)}.
{f'Context: {context}' if context else ''}

Original: {text}
Translation:"""
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.api_url}/api/generate",
                    json={
                        "model": "llama3",
                        "prompt": prompt,
                        "stream": False,
                    },
                )
                
                if response.status_code == 200:
                    data = response.json()
                    translated = data.get("response", text)
                    return translated.strip(), True
                return text, False
        except Exception as e:
            print(f"Ollama translation error: {e}")
            return text, False
    
    def get_model_name(self) -> str:
        return "ollama"


class GoogleCloudTranslator(TranslatorInterface):
    """Google Cloud Translation API (fast, reliable, no context awareness)."""
    
    def __init__(self, settings: Settings):
        self.api_key = settings.google_cloud_api_key
    
    async def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        context: Optional[str] = None,
    ) -> tuple[str, bool]:
        if not self.api_key:
            return text, False
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    "https://translation.googleapis.com/language/translate/v2",
                    params={"key": self.api_key},
                    json={
                        "q": [text],
                        "target": target_lang,
                        "format": "text",
                    },
                )
                
                if response.status_code == 200:
                    data = response.json()
                    translations = data.get("data", {}).get("translations", [])
                    if translations:
                        translated = translations[0].get("translatedText", text)
                        return translated, True
                return text, False
        except Exception as e:
            print(f"Google Cloud translation error: {e}")
            return text, False
    
    def get_model_name(self) -> str:
        return "google-cloud"


class TranslationService:
    """
    Translation service that routes to appropriate translator.
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.translators = {
            # Gemini models (queried from live API)
            'gemini-pro': GeminiTranslator(settings, 'gemini-3-pro-preview'),
            'gemini-flash': GeminiTranslator(settings, 'gemini-3.5-flash'),
            'gemini-flash-lite': GeminiTranslator(settings, 'gemini-3.1-flash-lite'),
            'gemini-25-flash-lite': GeminiTranslator(settings, 'gemini-2.5-flash-lite'),
            # OpenCode models (proxy to the best available)
            'opencode-deepseek': OpenCodeTranslator(settings, 'deepseek-v4-flash'),
            'opencode-kimi': OpenCodeTranslator(settings, 'kimi-k2.5'),
            'opencode-qwen': OpenCodeTranslator(settings, 'qwen3.7-plus'),
            'opencode-minimax': OpenCodeTranslator(settings, 'minimax-m2.5'),
            # Fallback / direct APIs (kept for compatibility)
            'glm': GLMTranslator(settings),
            'kimi': KimiTranslator(settings),
            'minimax': MiniMaxTranslator(settings),
            'qwen': QwenTranslator(settings),
            'ollama': OllamaTranslator(settings),
            'google-cloud': GoogleCloudTranslator(settings),
        }
    
    def get_translator(self, model: str) -> TranslatorInterface:
        """Get the appropriate translator for a model."""
        if model == 'auto':
            # Auto-select based on availability (Gemini 2.5 Flash Lite avoids free tier spending caps)
            if self.settings.gemini_api_key:
                return self.translators['gemini-25-flash-lite']
            if self.settings.opencode_api_key:
                return self.translators['opencode-deepseek']
            if self.settings.google_cloud_api_key:
                return self.translators['google-cloud']
            if self.settings.qwen_api_key:
                return self.translators['qwen']
            if self.settings.ollama_url:
                return self.translators['ollama']
            return self.translators['google-cloud']
        
        # Direct match (e.g. 'gemini-pro', 'opencode-kimi')
        if model in self.translators:
            return self.translators[model]
        
        # Handle opencode sub-models by prefix
        if model.startswith('opencode-'):
            submodel = model.replace('opencode-', '')
            return OpenCodeTranslator(self.settings, submodel)
        
        # Default to Gemini flash lite
        return self.translators.get('gemini-flash-lite', self.translators['gemini-flash-lite'])
    
    def _failover_chain(self, model: str) -> list[str]:
        """Fallback providers to try when the primary fails. Key-gated."""
        if model.startswith('opencode'):
            return ['gemini-25-flash-lite'] if self.settings.gemini_api_key else []
        if model.startswith('gemini') or model == 'auto':
            return ['opencode-deepseek'] if self.settings.opencode_api_key else []
        return ['gemini-25-flash-lite'] if self.settings.gemini_api_key else []

    async def translate_text(
        self,
        text: str,
        source_lang: str = 'ja',
        target_lang: str = 'en',
        model: str = 'auto',
        context: Optional[str] = None,
    ) -> tuple[str, str, bool]:
        """
        Translate text using the specified model.
        On provider failure, automatically falls back to an alternate provider
        so a dead upstream doesn't poison a whole job with passthrough runs.

        Returns:
            (translated_text, model_used, success)
        """
        translator = self.get_translator(model)
        translated, success = await translator.translate(text, source_lang, target_lang, context)
        model_used = translator.get_model_name()

        if success:
            return translated, model_used, True

        # Auto-failover: try alternate providers (one level deep, no loops)
        for fb_key in self._failover_chain(model):
            fb = self.translators.get(fb_key)
            if fb is None:
                continue
            fb_translated, fb_success = await fb.translate(text, source_lang, target_lang, context)
            if fb_success:
                print(f"  [FAILOVER] {model_used} failed → {fb.get_model_name()} used")
                return fb_translated, fb.get_model_name(), True

        return translated, model_used, False

    async def batch_translate(
        self,
        texts: list[str],
        source_lang: str = 'ja',
        target_lang: str = 'en',
        model: str = 'auto',
        context: Optional[str] = None,
        concurrency: int = 5,
        progress_callback=None,
    ) -> list[tuple[str, str, bool]]:
        """
        Translate multiple texts concurrently.

        Args:
            progress_callback: Optional sync callable invoked after each run
                completes, receiving the count of completed runs so far.

        Returns:
            List of (translated_text, model_used, success)
        """
        semaphore = asyncio.Semaphore(concurrency)
        completed = 0

        async def translate_with_limit(text: str):
            nonlocal completed
            async with semaphore:
                result = await self.translate_text(text, source_lang, target_lang, model, context)
            if progress_callback is not None:
                completed += 1
                try:
                    progress_callback(completed)
                except Exception:
                    pass  # progress reporting must never break translation
            return result

        results = await asyncio.gather(*[translate_with_limit(t) for t in texts])
        return list(results)