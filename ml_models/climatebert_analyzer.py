"""
ClimateBERT NLP Integration
State-of-the-art transformer model fine-tuned on climate and sustainability text

Models available from HuggingFace:
- climatebert/distilroberta-base-climate-f: Climate text classification
- climatebert/environmental-claims: Environmental claim detection
- climatebert/distilroberta-base-climate-detector: Climate relevance detection
- climatebert/tcfd-recommendations: TCFD disclosure classification

Integrates with existing Sentiment Analyzer for enhanced greenwashing detection
"""

import os
import json
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

try:
    from huggingface_hub import login
except ImportError:
    login = None


class ClimateBERTAnalyzer:
    """
    ClimateBERT-powered ESG text analysis
    Provides academic-grade precision for greenwashing detection
    """
    
    def __init__(self, use_gpu: bool = False):
        self.name = "ClimateBERT NLP Analyzer"
        self.models_loaded = False
        self.models = {}
        self.tokenizers = {}
        
        # Lazy loading flags
        self._transformers_available = False
        self._torch_available = False
        
        # Model configurations
        self.model_configs = {
            "climate_detection": {
                "model_name": "climatebert/distilroberta-base-climate-detector",
                "task": "Climate relevance detection",
                "labels": ["not_climate", "climate"]
            },
            "environmental_claims": {
                "model_name": "climatebert/environmental-claims",
                "task": "Environmental claim classification",
                "labels": ["not_claim", "claim"]
            },
            "tcfd_classification": {
                "model_name": "climatebert/distilroberta-base-climate-f",
                "task": "TCFD disclosure classification",
                "labels": ["none", "governance", "strategy", "risk_management", "metrics_targets"]
            },
            "sentiment": {
                "model_name": "nlptown/bert-base-multilingual-uncased-sentiment",
                "task": "Climate sentiment analysis",
                "labels": ["very_negative", "negative", "neutral", "positive", "very_positive"]
            }
        }
        
        # Greenwashing detection patterns (pre-trained patterns for quick inference)
        self.greenwashing_patterns = {
            "vague_claims": [
                "sustainable", "green", "eco-friendly", "environmentally friendly",
                "planet-friendly", "nature-positive", "climate-positive"
            ],
            "unsubstantiated_targets": [
                "net zero", "carbon neutral", "100% renewable", "zero emissions",
                "carbon negative", "climate positive"
            ],
            "hedge_words": [
                "aim to", "strive to", "work towards", "hope to", "intend to",
                "committed to exploring", "aspire to"
            ],
            "temporal_vagueness": [
                "in the future", "soon", "eventually", "when feasible",
                "as technology allows", "in due course"
            ]
        }
        
        print(f"✅ {self.name} initialized")
        print(f"   Models: {len(self.model_configs)} available")
        print(f"   NOTE: Models loaded on-demand to save memory")
    
    def _load_models(self) -> bool:
        """
        Lazy-load ClimateBERT models from HuggingFace
        Returns True if successful, False otherwise
        """
        
        if self.models_loaded:
            return True
        
        try:
            print("📥 Loading ClimateBERT models from HuggingFace...")
            
            from transformers import AutoTokenizer, AutoModelForSequenceClassification
            import torch

            hf_token = os.getenv("HF_TOKEN")
            if hf_token and login is not None:
                try:
                    login(token=hf_token)
                except Exception:
                    pass
            
            self._transformers_available = True
            self._torch_available = True
            
            device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"   Device: {device}")
            
            # Load primary models
            for model_key in ["climate_detection", "environmental_claims"]:
                config = self.model_configs[model_key]
                model_name = config["model_name"]
                
                try:
                    print(f"   Loading {model_key}...")
                    self.tokenizers[model_key] = AutoTokenizer.from_pretrained(model_name)
                    self.models[model_key] = AutoModelForSequenceClassification.from_pretrained(
                        model_name,
                        ignore_mismatched_sizes=True,
                    )
                    self.models[model_key].to(device)
                    self.models[model_key].eval()
                except Exception as e:
                    print(f"   ⚠️ Could not load {model_key}: {e}")
            
            self.models_loaded = len(self.models) > 0
            print(f"✅ Loaded {len(self.models)} ClimateBERT models")
            return self.models_loaded
            
        except ImportError as e:
            print(f"⚠️ ClimateBERT requires: pip install transformers torch")
            print(f"   Running in fallback mode (pattern-based analysis)")
            return False
        except Exception as e:
            print(f"⚠️ Error loading models: {e}")
            return False
    
    def analyze_text(self, text: str, 
                    analysis_type: str = "comprehensive") -> Dict[str, Any]:
        """
        Analyze text using ClimateBERT models
        
        Args:
            text: Text to analyze
            analysis_type: "comprehensive", "quick", or specific model key
        
        Returns:
            Analysis results with scores and classifications
        """
        
        if not text:
            return {"error": "Empty text provided"}
        
        print(f"\n{'='*60}")
        print(f"🤖 {self.name}")
        print(f"{'='*60}")
        print(f"Text length: {len(text)} chars")
        print(f"Analysis type: {analysis_type}")
        
        # Try to load models
        models_available = self._load_models()
        
        if models_available and analysis_type == "comprehensive":
            result = self._comprehensive_analysis(text)
        elif models_available:
            result = self._model_inference(text, analysis_type)
        else:
            # Fallback to pattern-based analysis
            print("   Using pattern-based analysis (no GPU/models)")
            result = self._pattern_based_analysis(text)
        
        # Add greenwashing detection
        greenwashing_scores = self._detect_greenwashing_patterns(text)
        result["greenwashing_detection"] = greenwashing_scores
        
        # Generate overall assessment
        result["overall_assessment"] = self._generate_assessment(result)
        
        print(f"\n✅ ClimateBERT analysis complete")
        print(f"   Climate relevance: {result.get('climate_relevance', {}).get('score', 'N/A')}")
        print(f"   Greenwashing risk: {result['greenwashing_detection']['risk_level']}")
        
        return result
    
    def _comprehensive_analysis(self, text: str) -> Dict[str, Any]:
        """Run comprehensive analysis with all available models"""
        
        import torch
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "text_length": len(text),
            "models_used": []
        }
        
        # Truncate text if needed (max 512 tokens)
        text_truncated = text[:2000]
        
        for model_key, model in self.models.items():
            config = self.model_configs[model_key]
            tokenizer = self.tokenizers[model_key]
            
            try:
                # Tokenize
                inputs = tokenizer(
                    text_truncated,
                    return_tensors="pt",
                    truncation=True,
                    max_length=512,
                    padding=True
                )
                
                # Move to same device as model
                device = next(model.parameters()).device
                inputs = {k: v.to(device) for k, v in inputs.items()}
                
                # Inference
                with torch.no_grad():
                    outputs = model(**inputs)
                    probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
                    probs = probs.cpu().numpy()[0]
                
                # Get prediction
                pred_idx = np.argmax(probs)
                labels = config["labels"]
                
                results[model_key] = {
                    "task": config["task"],
                    "prediction": labels[pred_idx],
                    "confidence": float(probs[pred_idx]),
                    "scores": {labels[i]: float(probs[i]) for i in range(len(labels))}
                }
                results["models_used"].append(model_key)
                
            except Exception as e:
                results[model_key] = {"error": str(e)}
        
        # Derive climate relevance score
        if "climate_detection" in results and "scores" in results["climate_detection"]:
            climate_score = results["climate_detection"]["scores"].get("climate", 0)
            results["climate_relevance"] = {
                "score": round(climate_score * 100, 1),
                "is_climate_related": climate_score > 0.5
            }
        
        return results
    
    def _model_inference(self, text: str, model_key: str) -> Dict[str, Any]:
        """Run inference with specific model"""
        
        if model_key not in self.models:
            return {"error": f"Model {model_key} not loaded"}
        
        import torch
        
        model = self.models[model_key]
        tokenizer = self.tokenizers[model_key]
        config = self.model_configs[model_key]
        
        inputs = tokenizer(
            text[:2000],
            return_tensors="pt",
            truncation=True,
            max_length=512
        )
        
        device = next(model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = model(**inputs)
            probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
            probs = probs.cpu().numpy()[0]
        
        pred_idx = np.argmax(probs)
        labels = config["labels"]
        
        return {
            "model": model_key,
            "task": config["task"],
            "prediction": labels[pred_idx],
            "confidence": float(probs[pred_idx]),
            "scores": {labels[i]: float(probs[i]) for i in range(len(labels))}
        }
    
    def _pattern_based_analysis(self, text: str) -> Dict[str, Any]:
        """Fallback pattern-based analysis when models unavailable"""
        
        text_lower = text.lower()
        
        # Climate relevance detection
        climate_keywords = [
            "climate", "carbon", "emissions", "greenhouse", "ghg", "co2",
            "renewable", "solar", "wind", "sustainability", "sustainable",
            "net zero", "decarbonization", "environmental", "esg"
        ]
        
        climate_count = sum(1 for kw in climate_keywords if kw in text_lower)
        climate_score = min(100, climate_count * 15)
        
        # Environmental claim detection
        claim_keywords = [
            "we will", "we are committed", "our goal", "target", "achieve",
            "reduce", "by 2030", "by 2050", "net zero", "carbon neutral"
        ]
        
        claim_count = sum(1 for kw in claim_keywords if kw in text_lower)
        is_claim = claim_count >= 2
        
        return {
            "analysis_method": "pattern_based",
            "climate_relevance": {
                "score": climate_score,
                "is_climate_related": climate_score > 30
            },
            "environmental_claims": {
                "contains_claims": is_claim,
                "claim_indicators": claim_count
            },
            "models_used": []
        }
    
    def _detect_greenwashing_patterns(self, text: str) -> Dict[str, Any]:
        """Detect greenwashing language patterns"""
        
        text_lower = text.lower()
        findings = []
        
        # Check each pattern category
        scores = {}
        for category, patterns in self.greenwashing_patterns.items():
            matches = [p for p in patterns if p in text_lower]
            scores[category] = len(matches)
            
            if matches:
                findings.append({
                    "category": category,
                    "matches": matches,
                    "count": len(matches)
                })
        
        # Calculate greenwashing risk score
        total_patterns = sum(scores.values())
        
        # Weight certain patterns more heavily
        weighted_score = (
            scores["vague_claims"] * 10 +
            scores["unsubstantiated_targets"] * 25 +
            scores["hedge_words"] * 20 +
            scores["temporal_vagueness"] * 15
        )
        
        risk_score = min(100, weighted_score)
        
        if risk_score >= 60:
            risk_level = "HIGH"
        elif risk_score >= 30:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "pattern_counts": scores,
            "findings": findings,
            "total_patterns_found": total_patterns
        }
    
    def _generate_assessment(self, analysis_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate overall assessment from analysis results"""
        
        climate_score = analysis_results.get("climate_relevance", {}).get("score", 0)
        greenwashing_score = analysis_results.get("greenwashing_detection", {}).get("risk_score", 0)
        
        # Determine credibility
        if greenwashing_score < 20 and climate_score > 50:
            credibility = "HIGH"
            assessment = "Climate claims appear substantive with low greenwashing indicators"
        elif greenwashing_score > 60:
            credibility = "LOW"
            assessment = "High presence of greenwashing language patterns"
        elif greenwashing_score > 30:
            credibility = "MEDIUM"
            assessment = "Some greenwashing indicators present - verification recommended"
        else:
            credibility = "MEDIUM-HIGH"
            assessment = "Moderate climate relevance with acceptable language patterns"
        
        return {
            "credibility_level": credibility,
            "assessment": assessment,
            "climate_relevance_score": climate_score,
            "greenwashing_risk_score": greenwashing_score,
            "recommendations": self._get_recommendations(credibility, greenwashing_score)
        }
    
    def _get_recommendations(self, credibility: str, 
                            greenwashing_score: float) -> List[str]:
        """Generate recommendations based on analysis"""
        
        recommendations = []
        
        if greenwashing_score > 50:
            recommendations.append("Request specific metrics and timelines for environmental claims")
            recommendations.append("Verify claims against third-party data sources")
        
        if greenwashing_score > 30:
            recommendations.append("Check for Science Based Targets initiative (SBTi) validation")
            recommendations.append("Review TCFD-aligned disclosures for completeness")
        
        if credibility in ["LOW", "MEDIUM"]:
            recommendations.append("Cross-reference with CDP/GRI disclosures")
            recommendations.append("Request third-party assurance of ESG claims")
        
        if not recommendations:
            recommendations.append("Continue monitoring for consistency in reporting")
        
        return recommendations
    
    def analyze_claim_for_greenwashing(self, claim_text: str,
                                       evidence_texts: List[str] = None) -> Dict[str, Any]:
        """
        Specialized analysis for greenwashing detection
        Combines ClimateBERT inference with pattern detection
        
        Args:
            claim_text: The ESG claim to analyze
            evidence_texts: Optional supporting evidence
        
        Returns:
            Comprehensive greenwashing analysis
        """
        
        # Analyze claim
        claim_analysis = self.analyze_text(claim_text, "comprehensive")
        
        # Analyze evidence if provided
        evidence_analysis = None
        if evidence_texts:
            combined_evidence = " ".join(evidence_texts[:5])[:3000]
            evidence_analysis = self.analyze_text(combined_evidence, "quick")
        
        # Compare claim vs evidence
        comparison = None
        if evidence_analysis:
            claim_gw_score = claim_analysis.get("greenwashing_detection", {}).get("risk_score", 0)
            evidence_gw_score = evidence_analysis.get("greenwashing_detection", {}).get("risk_score", 0)
            
            comparison = {
                "claim_greenwashing_score": claim_gw_score,
                "evidence_greenwashing_score": evidence_gw_score,
                "score_difference": claim_gw_score - evidence_gw_score,
                "interpretation": self._interpret_comparison(claim_gw_score, evidence_gw_score)
            }
        
        return {
            "claim_analysis": claim_analysis,
            "evidence_analysis": evidence_analysis,
            "comparison": comparison,
            "final_verdict": self._final_greenwashing_verdict(claim_analysis, comparison)
        }
    
    def _interpret_comparison(self, claim_score: float, 
                             evidence_score: float) -> str:
        """Interpret claim vs evidence comparison"""
        
        diff = claim_score - evidence_score
        
        if diff > 30:
            return "Claim language significantly more promotional than evidence supports"
        elif diff > 15:
            return "Claim uses more aspirational language than evidence supports"
        elif diff < -15:
            return "Evidence more promotional than claim (unusual)"
        else:
            return "Claim language consistent with evidence"
    
    def _final_greenwashing_verdict(self, claim_analysis: Dict,
                                   comparison: Optional[Dict]) -> Dict[str, Any]:
        """Generate final greenwashing verdict"""
        
        base_score = claim_analysis.get("greenwashing_detection", {}).get("risk_score", 0)
        
        # Adjust based on comparison if available
        if comparison and comparison.get("score_difference", 0) > 20:
            base_score = min(100, base_score + 15)
        
        if base_score >= 60:
            verdict = "HIGH_RISK"
            explanation = "Strong indicators of greenwashing language and patterns"
        elif base_score >= 35:
            verdict = "MODERATE_RISK"
            explanation = "Some greenwashing indicators present - requires verification"
        else:
            verdict = "LOW_RISK"
            explanation = "Limited greenwashing indicators in language analysis"
        
        return {
            "verdict": verdict,
            "score": base_score,
            "explanation": explanation
        }


# Global instance
climatebert_analyzer = ClimateBERTAnalyzer()

def get_climatebert_analyzer() -> ClimateBERTAnalyzer:
    """Get global ClimateBERT analyzer instance"""
    return climatebert_analyzer


def climatebert_analyze(text: str, analysis_type: str = "comprehensive"):
    analyzer = ClimateBERTAnalyzer()
    return analyzer.analyze_text(text, analysis_type)
