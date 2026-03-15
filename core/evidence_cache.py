"""
Centralized Evidence Cache System
Prevents redundant API calls across multiple agents by storing evidence once and reusing it
"""

import json
import os
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from pathlib import Path


class EvidenceCache:
    """
    Singleton cache for evidence data
    - In-memory cache for current workflow session
    - Persistent disk cache with 24-hour TTL
    - Prevents redundant API calls across agents
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.session_cache: Dict[str, Any] = {}
        self.cache_dir = Path("cache/evidence")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_hours = 24
        self._initialized = True
        
        print("✅ Evidence Cache initialized")
    
    def _generate_cache_key(self, company: str, query_suffix: str = "") -> str:
        """Generate cache key from company name and optional query"""
        company_clean = company.lower().strip().replace(" ", "_")
        
        if query_suffix:
            # Hash the query suffix to keep key manageable
            query_hash = hashlib.md5(query_suffix.encode()).hexdigest()[:8]
            return f"{company_clean}_{query_hash}"
        
        return company_clean
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """Get file path for cached evidence"""
        return self.cache_dir / f"{cache_key}.json"
    
    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cache file exists and is within TTL"""
        if not cache_path.exists():
            return False
        
        # Check file age
        modified_time = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age = datetime.now() - modified_time
        
        return age < timedelta(hours=self.ttl_hours)
    
    def has_evidence(self, company: str, query_suffix: str = "") -> bool:
        """Check if evidence exists in cache"""
        cache_key = self._generate_cache_key(company, query_suffix)
        
        # Check in-memory cache first
        if cache_key in self.session_cache:
            return True
        
        # Check disk cache
        cache_path = self._get_cache_path(cache_key)
        return self._is_cache_valid(cache_path)
    
    def get_evidence(self, company: str, query_suffix: str = "") -> Optional[Dict[str, Any]]:
        """
        Retrieve cached evidence
        Returns None if cache miss or expired
        """
        cache_key = self._generate_cache_key(company, query_suffix)
        
        # Try in-memory cache first
        if cache_key in self.session_cache:
            print(f"📦 Using in-memory cache for {company}")
            return self.session_cache[cache_key]
        
        # Try disk cache
        cache_path = self._get_cache_path(cache_key)
        
        if self._is_cache_valid(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Load into session cache
                self.session_cache[cache_key] = data
                
                # Calculate cache age
                age = datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)
                age_str = f"{age.seconds // 3600}h {(age.seconds % 3600) // 60}m"
                
                print(f"📦 Using disk cache for {company} (age: {age_str}) - ZERO API calls")
                return data
                
            except Exception as e:
                print(f"⚠️ Cache read error: {e}")
                return None
        
        return None
    
    def store_evidence(self, company: str, evidence: Dict[str, Any], query_suffix: str = ""):
        """
        Store evidence in both memory and disk cache
        """
        cache_key = self._generate_cache_key(company, query_suffix)
        
        # Add metadata
        evidence['_cache_metadata'] = {
            'company': company,
            'cached_at': datetime.now().isoformat(),
            'cache_key': cache_key
        }
        
        # Store in memory
        self.session_cache[cache_key] = evidence
        
        # Persist to disk
        cache_path = self._get_cache_path(cache_key)
        
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(evidence, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Evidence cached for {company} (TTL: {self.ttl_hours}h)")
            
        except Exception as e:
            print(f"⚠️ Cache write error: {e}")
    
    def clear_session_cache(self):
        """Clear in-memory cache (keeps disk cache)"""
        self.session_cache.clear()
        print("🗑️ Session cache cleared")
    
    def clear_all_cache(self):
        """Clear both memory and disk cache"""
        self.session_cache.clear()
        
        # Delete all cache files
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
            except Exception as e:
                print(f"⚠️ Error deleting {cache_file}: {e}")
        
        print("🗑️ All cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        disk_files = list(self.cache_dir.glob("*.json"))
        
        valid_files = [f for f in disk_files if self._is_cache_valid(f)]
        expired_files = [f for f in disk_files if not self._is_cache_valid(f)]
        
        return {
            'session_cache_entries': len(self.session_cache),
            'disk_cache_valid': len(valid_files),
            'disk_cache_expired': len(expired_files),
            'cache_directory': str(self.cache_dir)
        }
    
    def print_cache_stats(self):
        """Print cache statistics"""
        stats = self.get_cache_stats()
        
        print(f"\n{'='*60}")
        print(f"📊 EVIDENCE CACHE STATISTICS")
        print(f"{'='*60}")
        print(f"In-Memory Entries: {stats['session_cache_entries']}")
        print(f"Valid Disk Cache:  {stats['disk_cache_valid']}")
        print(f"Expired Cache:     {stats['disk_cache_expired']}")
        print(f"Cache Directory:   {stats['cache_directory']}")
        print(f"{'='*60}\n")


# Global singleton instance
evidence_cache = EvidenceCache()
