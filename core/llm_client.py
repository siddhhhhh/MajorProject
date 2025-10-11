import os
from groq import Groq
import google.generativeai as genai
from typing import Dict, Any, Optional, List
from config.settings import settings
import time

class LLMClient:
    def __init__(self):
        # Initialize Groq client
        self.groq_client = Groq(api_key=settings.GROQ_API_KEY)
        
        # Initialize Gemini client
        genai.configure(api_key=settings.GEMINI_API_KEY)
        
        # Test and get available models
        self.available_gemini_models = self._get_available_gemini_models()
        self.available_groq_models = self._get_available_groq_models()
        
        # Select best available models
        self.gemini_model_name = self._select_best_gemini_model()
        self.gemini_model = genai.GenerativeModel(self.gemini_model_name)
        
        self.groq_model_name = self._select_best_groq_model()
        self.groq_fast_model = self._select_fast_groq_model()
        
        print(f"✅ LLM Client initialized")
        print(f"   - Gemini model: {self.gemini_model_name}")
        print(f"   - Groq model: {self.groq_model_name}")
        print(f"   - Groq fast model: {self.groq_fast_model}")
    
    def _get_available_gemini_models(self) -> List[str]:
        """List all available Gemini models"""
        try:
            models = []
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    models.append(m.name.replace('models/', ''))
            
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
            "gemini-2.5-pro",
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
                  temperature: float = 0.1, max_retries: int = 3,
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
        for attempt in range(max_retries):
            try:
                # Switch to Pro model if requested and available
                if use_pro and "gemini-2.5-pro" in self.available_gemini_models:
                    model = genai.GenerativeModel("gemini-2.5-pro")
                else:
                    model = self.gemini_model
                
                response = model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=temperature,
                        max_output_tokens=8000
                    )
                )
                return response.text
            except Exception as e:
                error_msg = str(e)
                print(f"⚠️ Gemini API error (attempt {attempt + 1}/{max_retries}): {error_msg}")
                
                # If model not found, try to switch to alternative
                if "404" in error_msg or "not found" in error_msg:
                    print("🔄 Trying alternative Gemini model...")
                    if attempt == 0 and self.available_gemini_models:
                        # Try next available model
                        alt_model = self.available_gemini_models[0]
                        try:
                            self.gemini_model = genai.GenerativeModel(alt_model)
                            self.gemini_model_name = alt_model
                            print(f"   Switched to: {alt_model}")
                            continue
                        except:
                            pass
                
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    return None
    
    def call_with_fallback(self, prompt: str, use_gemini_first: bool = True) -> str:
        """
        Try Gemini first for complex tasks, fallback to Groq
        Or vice versa based on use_gemini_first flag
        """
        if use_gemini_first:
            print("⏳ Trying Gemini...")
            result = self.call_gemini(prompt)
            if result:
                print("✅ Gemini succeeded")
                return result
            
            print("🔄 Falling back to Groq...")
            messages = [{"role": "user", "content": prompt}]
            result = self.call_groq(messages)
            if result:
                print("✅ Groq succeeded")
                return result
        else:
            print("⏳ Trying Groq...")
            messages = [{"role": "user", "content": prompt}]
            result = self.call_groq(messages)
            if result:
                print("✅ Groq succeeded")
                return result
            
            print("🔄 Falling back to Gemini...")
            result = self.call_gemini(prompt)
            if result:
                print("✅ Gemini succeeded")
                return result
        
        print("❌ Both LLMs failed")
        return None

# Global instance
llm_client = LLMClient()
