"""
Source Tracker - Monitor which data sources return results
Tracks API success rates and generates usage reports
"""

import functools
import json
import os
from datetime import datetime
from typing import Any, Callable, Dict, List


class SourceTracker:
    """
    Tracks data source performance and generates usage reports
    Used to monitor which APIs are working and returning results
    """
    
    def __init__(self):
        self.stats = {
            "sources_called": [],
            "sources_with_results": [],
            "sources_failed": [],
            "results_per_source": {},
            "error_messages": {}
        }
        self.start_time = None
        self.end_time = None
    
    def reset(self):
        """Reset tracking stats for new analysis"""
        self.stats = {
            "sources_called": [],
            "sources_with_results": [],
            "sources_failed": [],
            "results_per_source": {},
            "error_messages": {}
        }
        self.start_time = datetime.now()
        self.end_time = None
    
    def track(self, source_name: str):
        """
        Decorator to track individual source method calls
        
        Usage:
            @source_tracker.track("NewsAPI")
            def search_newsapi(self, ...):
                ...
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs) -> List[Dict]:
                if not self.start_time:
                    self.start_time = datetime.now()
                
                self.stats["sources_called"].append(source_name)
                
                try:
                    results = func(*args, **kwargs)
                    count = len(results) if results else 0
                    self.stats["results_per_source"][source_name] = count
                    
                    if count > 0:
                        self.stats["sources_with_results"].append(source_name)
                        print(f"   ✅ {source_name}: {count} results")
                    else:
                        self.stats["sources_failed"].append(source_name)
                        print(f"   ⏭️ {source_name}: No results")
                    
                    return results
                
                except Exception as e:
                    error_msg = str(e)[:200]
                    self.stats["sources_failed"].append(source_name)
                    self.stats["results_per_source"][source_name] = 0
                    self.stats["error_messages"][source_name] = error_msg
                    print(f"   ❌ {source_name}: Error - {error_msg[:80]}")
                    return []
            
            return wrapper
        return decorator
    
    def save_report(self, company: str, output_dir: str = "reports") -> Dict[str, Any]:
        """
        Save detailed source usage report to JSON file
        
        Args:
            company: Company name being analyzed
            output_dir: Directory to save report (default: reports/)
        
        Returns:
            Report dictionary with full statistics
        """
        self.end_time = datetime.now()
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"source_usage_{company.replace(' ', '_')}_{timestamp_str}.json"
        filepath = os.path.join(output_dir, filename)
        
        # Calculate metrics
        total_sources = len(self.stats["sources_called"])
        successful_sources = len(self.stats["sources_with_results"])
        failed_sources = len(self.stats["sources_failed"])
        success_rate = (successful_sources / max(total_sources, 1)) * 100
        
        total_results = sum(self.stats["results_per_source"].values())
        
        # Build comprehensive report
        report = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "company": company,
                "analysis_duration_seconds": (self.end_time - self.start_time).total_seconds() if self.start_time and self.end_time else 0
            },
            "summary": {
                "total_sources_called": total_sources,
                "sources_with_results": successful_sources,
                "sources_failed": failed_sources,
                "success_rate_percent": round(success_rate, 2),
                "total_results_retrieved": total_results,
                "avg_results_per_source": round(total_results / max(total_sources, 1), 2)
            },
            "detailed_stats": {
                "sources_called": self.stats["sources_called"],
                "sources_with_results": self.stats["sources_with_results"],
                "sources_failed": self.stats["sources_failed"],
                "results_per_source": self.stats["results_per_source"],
                "error_messages": self.stats["error_messages"]
            },
            "top_performers": self._get_top_performers(),
            "recommendations": self._generate_recommendations()
        }
        
        # Save to file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n📊 Source usage report saved: {filepath}")
        
        # Also save as "latest" for easy access
        latest_path = os.path.join(output_dir, "source_usage_latest.json")
        with open(latest_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        return report
    
    def _get_top_performers(self) -> List[Dict[str, Any]]:
        """Get top 5 sources by result count"""
        sorted_sources = sorted(
            self.stats["results_per_source"].items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [
            {"source": name, "results": count}
            for name, count in sorted_sources[:5]
            if count > 0
        ]
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on performance"""
        recommendations = []
        
        success_rate = (len(self.stats["sources_with_results"]) / 
                       max(len(self.stats["sources_called"]), 1)) * 100
        
        if success_rate < 30:
            recommendations.append("⚠️ LOW SUCCESS RATE: Consider checking API keys and network connectivity")
        
        if success_rate < 50:
            recommendations.append("⚠️ MODERATE SUCCESS RATE: Some sources may be down or rate-limited")
        
        # Check for specific problematic sources
        consistently_failing = [
            source for source, count in self.stats["results_per_source"].items()
            if count == 0 and source in self.stats["sources_called"]
        ]
        
        if len(consistently_failing) > 5:
            recommendations.append(
                f"❌ {len(consistently_failing)} sources consistently failing: "
                f"{', '.join(consistently_failing[:3])}..."
            )
        
        # Positive feedback
        if success_rate >= 80:
            recommendations.append("✅ EXCELLENT: Most sources are working well")
        
        if not recommendations:
            recommendations.append("✅ All sources performing as expected")
        
        return recommendations
    
    def print_summary(self):
        """Print a formatted summary to console"""
        print("\n" + "="*70)
        print("  📊 DATA SOURCE PERFORMANCE SUMMARY")
        print("="*70)
        
        total = len(self.stats["sources_called"])
        successful = len(self.stats["sources_with_results"])
        failed = len(self.stats["sources_failed"])
        success_rate = (successful / max(total, 1)) * 100
        
        print(f"\n📈 OVERALL STATISTICS:")
        print(f"   Total sources called: {total}")
        print(f"   ✅ Successful: {successful}")
        print(f"   ❌ Failed: {failed}")
        print(f"   Success rate: {success_rate:.1f}%")
        
        print(f"\n🏆 TOP PERFORMERS:")
        for performer in self._get_top_performers():
            print(f"   • {performer['source']}: {performer['results']} results")
        
        print(f"\n💡 RECOMMENDATIONS:")
        for rec in self._generate_recommendations():
            print(f"   {rec}")
        
        print("="*70 + "\n")


# Global instance
source_tracker = SourceTracker()
