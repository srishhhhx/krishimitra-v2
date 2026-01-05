#!/usr/bin/env python3
"""
Advanced Stress Test - Complex & Confusing Queries

Tests edge cases:
1. Ambiguous queries (could go to multiple agents)
2. Hindi/Hinglish queries
3. Multi-entity confusion
4. Incomplete/vague queries
5. Compound queries with mixed intents
6. Context dependency tests
7. Adversarial/unusual patterns

Run: python test_stress_advanced.py
"""

import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.orchestrator import orchestrator

# STRESS TEST QUERIES
STRESS_TESTS = [
    # =========================================
    # CATEGORY 1: Ambiguous Intent
    # =========================================
    {
        "name": "Ambiguous: Crop vs Fertilizer",
        "query": "What should I use for my sandy soil wheat field?",
        "notes": "Could be crop advice OR fertilizer advice. Should clarify or pick one.",
        "category": "ambiguous"
    },
    {
        "name": "Ambiguous: Treatment vs Prevention",
        "query": "My rice plants are yellowing, what to do?",
        "notes": "Could be disease OR nutrient deficiency. Should ask for image or details.",
        "category": "ambiguous"
    },
    
    # =========================================
    # CATEGORY 2: Hindi/Hinglish Queries
    # =========================================
    {
        "name": "Hindi: Crop Recommendation",
        "query": "मेरे पास काली मिट्टी है, कौन सी फसल उगाऊं?",
        "notes": "Should extract: soil_type=black, intent=crop recommendation",
        "category": "hindi"
    },
    {
        "name": "Hinglish: Fertilizer",
        "query": "Wheat ke liye konsa fertilizer best hai?",
        "notes": "Should extract: crop=wheat, intent=fertilizer",
        "category": "hindi"
    },
    
    # =========================================
    # CATEGORY 3: Multi-Intent Compound Queries
    # =========================================
    {
        "name": "Compound: Weather + Crop + Disease",
        "query": "Weather kaisa hai Lucknow mein? Aur tomato mein disease ho gayi, treatment batao",
        "notes": "THREE intents: weather, crop context, disease. Should handle sequentially.",
        "category": "compound"
    },
    {
        "name": "Compound: Compare Two Locations",
        "query": "Should I grow rice in Kerala or wheat in Punjab?",
        "notes": "Comparing two location-crop pairs. Complex reasoning needed.",
        "category": "compound"
    },
    
    # =========================================
    # CATEGORY 4: Vague/Incomplete Queries
    # =========================================
    {
        "name": "Vague: No Context",
        "query": "Help me with my farm",
        "notes": "Extremely vague. Should ask clarifying questions.",
        "category": "vague"
    },
    {
        "name": "Vague: Partial Info",
        "query": "What fertilizer?",
        "notes": "Missing crop and soil. Should clarify.",
        "category": "vague"
    },
    
    # =========================================
    # CATEGORY 5: Edge Case Locations
    # =========================================
    {
        "name": "Edge: Unknown Location",
        "query": "What crop should I grow in Timbuktu?",
        "notes": "Non-Indian location. Should handle gracefully.",
        "category": "edge"
    },
    {
        "name": "Edge: Misspelled Location",
        "query": "Weather in Bangalor and best crop?",
        "notes": "Misspelled 'Bangalore'. Should fuzzy match.",
        "category": "edge"
    },
    
    # =========================================
    # CATEGORY 6: Contradictory Information
    # =========================================
    {
        "name": "Contradictory: Impossible Conditions",
        "query": "I want to grow rice in desert with no water, what fertilizer?",
        "notes": "Should point out contradictions or limitations.",
        "category": "contradict"
    },
    
    # =========================================
    # CATEGORY 7: Real-World Farmer Queries
    # =========================================
    {
        "name": "Real: Seasonal Planning",
        "query": "Kharif season shuru ho rahi hai, mere paas 2 acre zameen hai Maharashtra mein, kya ugaun aur kitna kharcha aayega?",
        "notes": "Real farmer query: season, area, location, cost estimate. Complex multi-agent.",
        "category": "real"
    },
    {
        "name": "Real: Problem Diagnosis",
        "query": "Pichle saal cotton mein bohot loss hua, is saal kya different karu?",
        "notes": "Past experience, asking for different approach. Needs reasoning.",
        "category": "real"
    },
]


def print_header(text: str, char: str = "="):
    print(f"\n{char * 70}")
    print(f"  {text}")
    print(f"{char * 70}")


def analyze_response(result: dict, test_case: dict) -> dict:
    """Deep analysis of response quality"""
    analysis = {
        "agents_used": result.get("executed_agents", []),
        "latency": result.get("total_latency_ms", 0),
        "has_response": bool(result.get("final_response") or result.get("answer")),
        "response_length": len(result.get("final_response", result.get("answer", ""))),
        "issues": []
    }
    
    response_text = result.get("final_response", result.get("answer", "")).lower()
    
    # Check for common issues
    if not analysis["has_response"]:
        analysis["issues"].append("❌ NO_RESPONSE")
    elif analysis["response_length"] < 50:
        analysis["issues"].append("⚠️ TOO_SHORT")
    
    if "error" in response_text or "failed" in response_text:
        analysis["issues"].append("❌ ERROR_IN_RESPONSE")
    
    if not analysis["agents_used"]:
        analysis["issues"].append("⚠️ NO_AGENTS_EXECUTED")
    
    if analysis["latency"] > 15000:
        analysis["issues"].append("⚠️ SLOW_RESPONSE")
    
    # Check for hallucination indicators
    if "i don't have" not in response_text and "cannot" not in response_text:
        if test_case["category"] == "edge" and "timbuktu" in test_case["query"].lower():
            if "crop" in response_text and "recommend" in response_text:
                analysis["issues"].append("⚠️ POSSIBLE_HALLUCINATION")
    
    return analysis


def run_stress_test(test_case: dict, num: int, total: int) -> dict:
    """Run single stress test with detailed monitoring"""
    print_header(f"TEST {num}/{total}: {test_case['name']}", "-")
    print(f"Query: {test_case['query']}")
    print(f"Notes: {test_case['notes']}")
    print(f"Category: {test_case['category']}")
    
    try:
        result = orchestrator.run(
            query=test_case['query'],
            user_context={},
            images=None,
            session_id=None
        )
        
        analysis = analyze_response(result, test_case)
        
        print(f"\n📊 ANALYSIS:")
        print(f"  Agents: {analysis['agents_used']}")
        print(f"  Latency: {analysis['latency']:.0f}ms")
        print(f"  Response Length: {analysis['response_length']} chars")
        
        if analysis["issues"]:
            print(f"  Issues: {', '.join(analysis['issues'])}")
        else:
            print(f"  Issues: None ✅")
        
        # Show response preview
        response = result.get("final_response", result.get("answer", ""))[:200]
        print(f"\n📝 RESPONSE PREVIEW:")
        print(f"  {response}...")
        
        return {
            "name": test_case["name"],
            "category": test_case["category"],
            "passed": len(analysis["issues"]) == 0,
            "issues": analysis["issues"],
            "agents": analysis["agents_used"],
            "latency": analysis["latency"]
        }
        
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        return {
            "name": test_case["name"],
            "category": test_case["category"],
            "passed": False,
            "issues": [f"EXCEPTION: {str(e)[:50]}"],
            "agents": [],
            "latency": 0
        }


def run_all_stress_tests():
    """Run all stress tests"""
    print_header("🔥 ADVANCED STRESS TEST SUITE")
    print(f"Testing {len(STRESS_TESTS)} complex scenarios")
    print("Adding 6s delay between queries...")
    
    results = []
    
    for i, test_case in enumerate(STRESS_TESTS, 1):
        result = run_stress_test(test_case, i, len(STRESS_TESTS))
        results.append(result)
        
        if i < len(STRESS_TESTS):
            print("\n⏳ Waiting 6s...")
            time.sleep(6)
    
    # Summary by category
    print_header("📊 RESULTS BY CATEGORY")
    categories = {}
    for r in results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"passed": 0, "total": 0, "issues": []}
        categories[cat]["total"] += 1
        if r["passed"]:
            categories[cat]["passed"] += 1
        else:
            categories[cat]["issues"].extend(r["issues"])
    
    for cat, stats in categories.items():
        pct = (stats["passed"] / stats["total"]) * 100 if stats["total"] > 0 else 0
        status = "✅" if pct >= 80 else "⚠️" if pct >= 50 else "❌"
        print(f"  {status} {cat.upper()}: {stats['passed']}/{stats['total']} ({pct:.0f}%)")
        if stats["issues"]:
            print(f"      Issues: {set(stats['issues'])}")
    
    # Overall
    print_header("📈 OVERALL STRESS TEST RESULTS")
    total_passed = sum(1 for r in results if r["passed"])
    print(f"  Passed: {total_passed}/{len(results)}")
    print(f"  Pass Rate: {(total_passed/len(results))*100:.0f}%")
    
    latencies = [r["latency"] for r in results if r["latency"] > 0]
    if latencies:
        print(f"  Avg Latency: {sum(latencies)/len(latencies):.0f}ms")
    
    # Detailed issues summary
    all_issues = []
    for r in results:
        all_issues.extend(r["issues"])
    
    if all_issues:
        print_header("🔍 COMMON ISSUES FOUND")
        from collections import Counter
        issue_counts = Counter(all_issues)
        for issue, count in issue_counts.most_common():
            print(f"  {issue}: {count} occurrences")
    
    return results


if __name__ == "__main__":
    print("\n🚀 Starting Advanced Stress Tests...\n")
    run_all_stress_tests()
    print("\n✅ Stress test complete!\n")
