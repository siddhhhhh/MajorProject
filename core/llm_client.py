import os
from groq import Groq
from google import genai
from typing import Dict, Any, Optional, List
from config.settings import settings
import time
import hashlib

class LLMClient:
    def __init__(self):
        # Initialize Groq client
        self.groq_client = Groq(api_key=settings.GROQ_API_KEY)
        
        # Initialize Gemini client
        self.gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
        
        # PHASE 8: Add caching for LLM responses
        self.response_cache: Dict[str, str] = {}  # hash(prompt) -> response
        self.gemini_quota_exceeded = False  # Track if Gemini is rate-limited
        self.groq_quota_exceeded = False    # Track if Groq is rate-limited
        
        # Test and get available models
        self.available_gemini_models = self._get_available_gemini_models()
        self.available_groq_models = self._get_available_groq_models()
        
        # Select best available models
        self.gemini_model_name = self._select_best_gemini_model()
        
        self.groq_model_name = self._select_best_groq_model()
        self.groq_fast_model = self._select_fast_groq_model()
        
        print(f"✅ LLM Client initialized")
        print(f"   - Gemini model: {self.gemini_model_name}")
        print(f"   - Groq model: {self.groq_model_name}")
        print(f"   - Groq fast model: {self.groq_fast_model}")
        print(f"   - Response caching: ENABLED (PHASE 8)")
    
    def _hash_prompt(self, prompt: str) -> str:
        """Create hash of prompt for caching"""
        return hashlib.md5(prompt.encode()).hexdigest()
    
    def _get_cached_response(self, prompt: str) -> Optional[str]:
        """PHASE 8: Check if response is cached"""
        cache_key = self._hash_prompt(prompt)
        if cache_key in self.response_cache:
            print(f"✅ Cache HIT - Using cached LLM response (saved API call)")
            return self.response_cache[cache_key]
        return None
    
    def _cache_response(self, prompt: str, response: str):
        """PHASE 8: Cache the response"""
        cache_key = self._hash_prompt(prompt)
        self.response_cache[cache_key] = response
    
    def _detect_quota_exceeded(self, error_msg: str) -> tuple:
        """PHASE 8: Detect quota exhaustion from error message"""
        error_lower = error_msg.lower()
        quotas = {
            'gemini': 'resource_exhausted' in error_lower or 'rate_limit' in error_lower or '429' in error_msg,
            'groq': 'rate_limit' in error_lower or '429' in error_msg or 'quota' in error_lower
        }
        return quotas['gemini'], quotas['groq']
    
    def _get_available_gemini_models(self) -> List[str]:
        """List all available Gemini models"""
        try:
            models = []
            for m in self.gemini_client.models.list():
                model_name = getattr(m, "name", "") or ""
                if model_name:
                    models.append(model_name.replace('models/', ''))
            
            print(f"📋 Available Gemini models: {len(models)} found")
            return models
        except Exception as e:
            print(f"⚠️ Could not list Gemini models: {e}")
            return []
    
    def _get_available_groq_models(self) -> List[str]:
        """Get available Groq models"""
        try:
            # As of Oct 2025, these are production models
            return [
                "llama-3.3-70b-versatile",
                "meta-llama/llama-4-scout-17b-16e-instruct",
                "meta-llama/llama-4-maverick-17b-128e-instruct",
                "llama-3.1-8b-instant",
                "qwen/qwen3-32b",
                "meta-llama/llama-guard-4-12b"
            ]
        except Exception as e:
            print(f"⚠️ Could not list Groq models: {e}")
            return ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
    
    def _select_best_gemini_model(self) -> str:
        """Select the best available Gemini model"""
        # Priority order for 2025 models
        preferred_models = [
            "gemini-2.5-flash", 
            "gemini-2.0-flash",
            "gemini-1.5-pro-latest",
            "gemini-1.5-flash-latest",
            "gemini-pro"
        ]
        
        for model in preferred_models:
            if model in self.available_gemini_models:
                return model
        
        # If no preferred model found, use first available
        if self.available_gemini_models:
            return self.available_gemini_models[0]
        
        # Fallback
        return "gemini-2.5-flash"
    
    def _select_best_groq_model(self) -> str:
        """Select best production Groq model"""
        preferred = [
            "llama-3.3-70b-versatile",  # Best overall
            "meta-llama/llama-4-scout-17b-16e-instruct",  # Llama 4
            "qwen/qwen3-32b"
        ]
        
        for model in preferred:
            if model in self.available_groq_models:
                return model
        
        return "llama-3.3-70b-versatile"
    
    def _select_fast_groq_model(self) -> str:
        """Select fastest Groq model for simple tasks"""
        fast_models = [
            "llama-3.1-8b-instant",
            "meta-llama/llama-4-scout-17b-16e-instruct"
        ]
        
        for model in fast_models:
            if model in self.available_groq_models:
                return model
        
        return "llama-3.1-8b-instant"
    
    def call_groq(self, messages: list, model: str = None, 
                  temperature: float = 0.0, max_retries: int = 3,
                  use_fast: bool = False) -> str:
        """
        Fast inference using Groq
        use_fast=True uses smaller/faster model for simple tasks
        """
        if model is None:
            model = self.groq_fast_model if use_fast else self.groq_model_name
        
        for attempt in range(max_retries):
            try:
                response = self.groq_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=8000
                )
                return response.choices[0].message.content
            except Exception as e:
                error_msg = str(e)
                print(f"⚠️ Groq API error (attempt {attempt + 1}/{max_retries}): {error_msg}")
                
                # If model deprecated, try alternative
                if "decommissioned" in error_msg or "deprecated" in error_msg:
                    print("🔄 Model deprecated, switching to alternative...")
                    if attempt == 0:
                        # Try Llama 3.3 70B
                        model = "llama-3.3-70b-versatile"
                        continue
                    elif attempt == 1:
                        # Try Llama 4
                        model = "meta-llama/llama-4-scout-17b-16e-instruct"
                        continue
                
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    return None
    
    def call_gemini(self, prompt: str, temperature: float = 0.1, 
                   max_retries: int = 3, use_pro: bool = False) -> str:
        """Complex reasoning using Gemini"""

        # Ensure deterministic generation for research reproducibility.
        temperature = 0.0 if temperature is None else float(temperature)
        
        # PHASE 8: Check cache first
        cached_response = self._get_cached_response(prompt)
        if cached_response:
            return cached_response
        
        # PHASE 8: If Gemini quota exhausted, use Groq directly
        if self.gemini_quota_exceeded:
            print(f"⚠️ Gemini quota exhausted - using Groq fallback")
            messages = [{"role": "user", "content": prompt}]
            return self.call_groq(messages)
        
        for attempt in range(max_retries):
            try:
                # Switch to Pro model if requested and available
                model_name = "gemini-2.5-pro" if use_pro and "gemini-2.5-pro" in self.available_gemini_models else self.gemini_model_name

                response = self.gemini_client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config={
                        "temperature": temperature,
                        "max_output_tokens": 8000,
                    },
                )
                
                result = getattr(response, "text", None)
                if not result:
                    # Defensive fallback for SDK response variations
                    candidates = getattr(response, "candidates", None) or []
                    if candidates:
                        content = getattr(candidates[0], "content", None)
                        parts = getattr(content, "parts", None) or []
                        if parts:
                            result = getattr(parts[0], "text", "")
                # PHASE 8: Cache successful response
                self._cache_response(prompt, result)
                self.gemini_quota_exceeded = False  # Reset flag on success
                return result
                
            except Exception as e:
                error_msg = str(e)
                print(f"⚠️ Gemini API error (attempt {attempt + 1}/{max_retries}): {error_msg}")
                
                # PHASE 8: Detect quota exhaustion
                is_gemini_quota_exceeded, _ = self._detect_quota_exceeded(error_msg)
                if is_gemini_quota_exceeded:
                    self.gemini_quota_exceeded = True
                    print("🔴 GEMINI QUOTA EXHAUSTED - Auto-fallback to Groq")
                    messages = [{"role": "user", "content": prompt}]
                    result = self.call_groq(messages)
                    if result:
                        # PHASE 8: Cache the Groq response
                        self._cache_response(prompt, result)
                    return result
                
                # If model not found, try to switch to alternative
                if "404" in error_msg or "not found" in error_msg:
                    print("🔄 Trying alternative Gemini model...")
                    if attempt == 0 and self.available_gemini_models:
                        # Try next available model
                        alt_model = self.available_gemini_models[0]
                        self.gemini_model_name = alt_model
                        print(f"   Switched to: {alt_model}")
                        continue
                
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    # PHASE 8: Fallback to Groq on final failure
                    print("🔄 Gemini failed, falling back to Groq")
                    messages = [{"role": "user", "content": prompt}]
                    return self.call_groq(messages)
    
    def call_with_fallback(self, prompt: str, use_gemini_first: bool = True) -> str:
        """
        Try Gemini first for complex tasks, fallback to Groq
        Or vice versa based on use_gemini_first flag
        
        PHASE 8: Enhanced with caching and quota detection
        """
        # PHASE 8: Check cache first
        cached_response = self._get_cached_response(prompt)
        if cached_response:
            return cached_response
        
        # PHASE 8: If Gemini quota exhausted, use Groq directly
        if self.gemini_quota_exceeded and use_gemini_first:
            print("⏳ Gemini quota exhausted - using Groq directly")
            messages = [{"role": "user", "content": prompt}]
            result = self.call_groq(messages)
            if result:
                self._cache_response(prompt, result)
            return result
        
        if use_gemini_first:
            print("⏳ Trying Gemini...")
            result = self.call_gemini(prompt)
            if result:
                print("✅ Gemini succeeded")
                self._cache_response(prompt, result)
                return result
            
            print("🔄 Falling back to Groq...")
            messages = [{"role": "user", "content": prompt}]
            result = self.call_groq(messages)
            if result:
                print("✅ Groq succeeded")
                self._cache_response(prompt, result)
                return result
        else:
            print("⏳ Trying Groq...")
            messages = [{"role": "user", "content": prompt}]
            result = self.call_groq(messages)
            if result:
                print("✅ Groq succeeded")
                self._cache_response(prompt, result)
                return result
            
            print("🔄 Falling back to Gemini...")
            result = self.call_gemini(prompt)
            if result:
                print("✅ Gemini succeeded")
                self._cache_response(prompt, result)
                return result
        
        print("❌ Both LLMs failed")
        return None

# Global instance
llm_client = LLMClient()
