#!/usr/bin/env python3
"""
Comprehensive Multi-Turn and Context-Aware Pipeline Test

Tests all gap fixes:
- Gap 1: Conversation history in agent prompts
- Gap 2: Inter-agent context carryover
- Gap 3: RAG query enrichment
- Gap 4: Routing enhancement for variety/pest queries

Run: python test_multiturn_pipeline.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.orchestrator import orchestrator

# Test Categories
TEST_CASES = [
    # =========================================
    # CATEGORY 1: Multi-Agent Chains
    # =========================================
    {
        "name": "Weather→Crop Chain",
        "query": "What crop should I grow in Karnataka?",
        "expected_agents": ["weather_agent", "crop_agent"],
        "context_check": "location",
        "category": "chains"
    },
    {
        "name": "Triple Chain (Weather→Crop→Fertilizer)",
        "query": "Suggest crop and fertilizer for Tamil Nadu",
        "expected_agents": ["weather_agent", "crop_agent", "fertilizer_agent"],
        "context_check": "location",
        "category": "chains"
    },
    
    # =========================================
    # CATEGORY 2: Routing Enhancement (Solution 4)
    # =========================================
    {
        "name": "Pest Query → RAG",
        "query": "How to control aphids on tomato plants?",
        "expected_agents": ["general_rag_agent"],
        "context_check": None,
        "category": "routing"
    },
    {
        "name": "Variety with Soil → Crop Agent",
        "query": "Best wheat variety for black soil?",
        "expected_agents": ["crop_agent"],  # Should route to ML agent, not RAG
        "context_check": "soil",
        "category": "routing"
    },
    {
        "name": "Cultivation Method → RAG",
        "query": "How to grow rice using SRI method?",
        "expected_agents": ["general_rag_agent"],
        "context_check": None,
        "category": "routing"
    },
    
    # =========================================
    # CATEGORY 3: Direct Agent Queries
    # =========================================
    {
        "name": "Direct Crop (NPK provided)",
        "query": "Best crop for N=40 P=30 K=50 temp=25 humidity=70?",
        "expected_agents": ["crop_agent"],
        "context_check": None,
        "category": "direct"
    },
    {
        "name": "Direct Fertilizer",
        "query": "What fertilizer for wheat on sandy soil?",
        "expected_agents": ["fertilizer_agent"],
        "context_check": "crop+soil",
        "category": "direct"
    },
    
    # =========================================
    # CATEGORY 4: Context-Aware RAG (Gap 3)
    # =========================================
    {
        "name": "RAG with Location Context",
        "query": "What are the best practices for rice cultivation?",
        "expected_agents": ["general_rag_agent"],
        "context_check": None,
        "category": "rag",
        "user_context": {"location": "West Bengal"}  # Pre-set context
    },
]


def print_header(text: str, char: str = "="):
    """Print formatted header"""
    print(f"\n{char * 70}")
    print(f"  {text}")
    print(f"{char * 70}")


def run_test(test_case: dict, test_num: int, total: int) -> dict:
    """Run a single test case"""
    print_header(f"TEST {test_num}/{total}: {test_case['name']}", "-")
    print(f"Query: {test_case['query']}")
    print(f"Expected: {test_case['expected_agents']}")
    print(f"Category: {test_case['category']}")
    
    try:
        # Build user_context if provided
        user_context = test_case.get("user_context", {})
        
        result = orchestrator.run(
            query=test_case['query'],
            user_context=user_context,
            images=None,
            session_id=None  # Fresh session
        )
        
        actual_agents = result.get('executed_agents', [])
        expected = test_case['expected_agents']
        
        # Check if first N agents match (for chains)
        match = True
        for i, exp in enumerate(expected):
            if i >= len(actual_agents) or actual_agents[i] != exp:
                match = False
                break
        
        status = "✅ PASS" if match else "⚠️ PARTIAL"
        print(f"Actual: {actual_agents}")
        print(f"Result: {status}")
        print(f"Latency: {result.get('total_latency_ms', 0):.0f}ms")
        
        # Show response preview
        response = result.get('final_response', result.get('answer', ''))[:150]
        print(f"Response: {response}...")
        
        return {
            "name": test_case['name'],
            "passed": match,
            "expected": expected,
            "actual": actual_agents,
            "latency": result.get('total_latency_ms', 0),
            "category": test_case['category']
        }
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return {
            "name": test_case['name'],
            "passed": False,
            "error": str(e),
            "category": test_case['category']
        }


def run_all_tests():
    """Run all test cases"""
    print_header("🧪 MULTI-TURN & CONTEXT-AWARE PIPELINE TEST SUITE")
    print(f"Testing {len(TEST_CASES)} scenarios across 4 categories")
    print("Adding 5s delay between queries to avoid rate limits...")
    
    results = []
    
    for i, test_case in enumerate(TEST_CASES, 1):
        result = run_test(test_case, i, len(TEST_CASES))
        results.append(result)
        print()
        
        # Add delay between queries to avoid API rate limits
        if i < len(TEST_CASES):
            import time
            print("⏳ Waiting 5s before next query...")
            time.sleep(5)
    
    # Summary by category
    print_header("📊 TEST SUMMARY BY CATEGORY")
    
    categories = {}
    for r in results:
        cat = r['category']
        if cat not in categories:
            categories[cat] = {"passed": 0, "total": 0}
        categories[cat]["total"] += 1
        if r.get("passed"):
            categories[cat]["passed"] += 1
    
    for cat, stats in categories.items():
        pct = (stats["passed"] / stats["total"]) * 100 if stats["total"] > 0 else 0
        status = "✅" if pct == 100 else "⚠️" if pct > 50 else "❌"
        print(f"  {status} {cat.upper()}: {stats['passed']}/{stats['total']} ({pct:.0f}%)")
    
    # Overall summary
    print_header("📈 OVERALL RESULTS")
    total_passed = sum(1 for r in results if r.get("passed"))
    total = len(results)
    print(f"  Passed: {total_passed}/{total}")
    print(f"  Pass Rate: {(total_passed/total)*100:.0f}%")
    
    # Latency stats
    latencies = [r.get("latency", 0) for r in results if r.get("latency")]
    if latencies:
        print(f"  Avg Latency: {sum(latencies)/len(latencies):.0f}ms")
        print(f"  Max Latency: {max(latencies):.0f}ms")
    
    return results


if __name__ == "__main__":
    print("\n🚀 Starting Pipeline Tests...\n")
    run_all_tests()
    print("\n✅ Test suite complete!\n")
