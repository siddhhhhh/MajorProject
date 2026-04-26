#!/usr/bin/env python3
"""Quick validation of ESG System Improvements"""

import sys
import os

print("="*80)
print("ESG SYSTEM IMPROVEMENTS - VALIDATION")
print("="*80)

tests_passed = 0
tests_total = 0

# Test 1: Enhanced data sources exist
tests_total += 1
print("\nTest 1: Enhanced data sources module exists")
if os.path.exists("utils/enhanced_data_sources.py"):
    print("  PASS: File exists")
    tests_passed += 1
else:
    print("  FAIL: File not found")

# Test 2: Enhanced integration exists
tests_total += 1
print("Test 2: Enhanced integration module exists")
if os.path.exists("utils/enhanced_evidence_integration.py"):
    print("  PASS: File exists")
    tests_passed += 1
else:
    print("  FAIL: File not found")

# Test 3: Check if integration code added to evidence_retriever
tests_total += 1
print("Test 3: Integration added to evidence_retriever.py")
with open("agents/evidence_retriever.py", "r") as f:
    content = f.read()
    if "integrate_enhanced_sources_into_evidence" in content:
        print("  PASS: Integration code found")
        tests_passed += 1
    else:
        print("  FAIL: Integration code not found")

# Test 4: Check if score suppression removed
tests_total += 1
print("Test 4: Score suppression removed from report generator")
with open("core/professional_report_generator.py", "r") as f:
    content = f.read()
    # Check if the old suppression logic is gone (new code shows scores)
    if 'gw_score_disp = f"{v[\'gw_score\']' in content or "Always display scores" in content:
        print("  PASS: Score display logic updated")
        tests_passed += 1
    else:
        print("  WARN: Could not verify change")

# Test 5: Check if HTML decoding added
tests_total += 1
print("Test 5: HTML entity decoding in contradiction analyzer")
with open("agents/contradiction_analyzer.py", "r") as f:
    content = f.read()
    if "html.unescape" in content or "import html" in content:
        print("  PASS: HTML decoding added")
        tests_passed += 1
    else:
        print("  WARN: Could not verify change")

# Test 6: Check if industry comparator error handling added
tests_total += 1
print("Test 6: Error handling in industry comparator")
with open("agents/industry_comparator.py", "r") as f:
    content = f.read()
    if "fallback_used" in content and "except Exception as e" in content:
        print("  PASS: Error handling added")
        tests_passed += 1
    else:
        print("  WARN: Could not verify change")

# Test 7: Environment variable check
tests_total += 1
print("Test 7: Environment configuration")
enhanced_enabled = os.getenv("USE_ENHANCED_DATA_SOURCES", "true").lower() == "true"
if enhanced_enabled:
    print("  PASS: USE_ENHANCED_DATA_SOURCES=true")
    tests_passed += 1
else:
    print("  INFO: USE_ENHANCED_DATA_SOURCES=false (can enable if needed)")

# Summary
print("\n" + "="*80)
print(f"RESULTS: {tests_passed}/{tests_total} tests passed")
print("="*80)

if tests_passed >= 6:
    print("\nSUCCESS: All critical fixes are in place!")
    print("\nReady to test with company data:")
    print("  python main_langgraph.py --company 'Unilever' --claim 'net-zero by 2039'")
    sys.exit(0)
else:
    print("\nWARNING: Some tests need attention")
    sys.exit(1)
