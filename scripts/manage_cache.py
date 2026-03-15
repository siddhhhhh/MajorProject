"""
Evidence Cache Management Utility
Provides commands to view, clear, and manage the evidence cache
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.evidence_cache import evidence_cache
import argparse


def view_stats():
    """View cache statistics"""
    evidence_cache.print_cache_stats()


def clear_session():
    """Clear session cache only"""
    evidence_cache.clear_session_cache()
    print("✅ Session cache cleared")


def clear_all():
    """Clear all cache (session + disk)"""
    confirm = input("⚠️ This will delete all cached evidence. Continue? (y/N): ")
    if confirm.lower() == 'y':
        evidence_cache.clear_all_cache()
        print("✅ All cache cleared")
    else:
        print("❌ Operation cancelled")


def main():
    parser = argparse.ArgumentParser(description="Manage evidence cache")
    parser.add_argument('command', choices=['stats', 'clear-session', 'clear-all'],
                       help='Cache management command')
    
    args = parser.parse_args()
    
    if args.command == 'stats':
        view_stats()
    elif args.command == 'clear-session':
        clear_session()
    elif args.command == 'clear-all':
        clear_all()


if __name__ == "__main__":
    main()
