#!/usr/bin/env python3
"""
Agentic Workflow Test Script

Tests the ReAct-style reasoning and multi-agent workflows.
Run from backend directory: python test_agentic_workflows.py
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.orchestrator import orchestrator

# Test queries designed to trigger different workflows
TEST_QUERIES = [
    # 1. Multi-agent chain: Weather → Crop
    {
        "query": "What crop should I grow in Punjab?",
        "expected_agents": ["weather_agent", "crop_agent"],
        "description": "Location-based crop query → should trigger weather first"
    },
    
    # 2. Single agent: Direct crop recommendation
    {
        "query": "Best crop for N=40, P=30, K=50, temperature=25, humidity=70?",
        "expected_agents": ["crop_agent"],
        "description": "Explicit parameters → direct to crop_agent"
    },
    
    # 3. Triple chain: Weather → Crop → Fertilizer
    {
        "query": "Suggest crop and fertilizer for Maharashtra",
        "expected_agents": ["weather_agent", "crop_agent", "fertilizer_agent"],
        "description": "Multi-intent query → three agent chain"
    },
    
    # 4. Single agent: Fertilizer
    {
        "query": "What fertilizer for wheat on black soil?",
        "expected_agents": ["fertilizer_agent"],
        "description": "Direct fertilizer query with crop/soil"
    },
    
    # 5. General RAG
    {
        "query": "How to control aphids on tomato plants?",
        "expected_agents": ["general_rag_agent"],
        "description": "Knowledge question → RAG agent"
    },
]


def print_header(text: str):
    """Print a formatted header"""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80)


def print_result(query_info: dict, result: dict):
    """Print test result summary"""
    print("\n" + "-" * 60)
    print(f"Query: {query_info['query'][:60]}...")
    print(f"Expected: {query_info['expected_agents']}")
    print(f"Actual:   {result.get('executed_agents', [])}")
    
    # Check if expectations met
    actual = result.get('executed_agents', [])
    expected = query_info['expected_agents']
    
    # Check if all expected agents were executed (order matters for chains)
    match = True
    for i, exp in enumerate(expected):
        if i >= len(actual) or actual[i] != exp:
            match = False
            break
    
    if match:
        print(f"✅ PASS - Agents executed in expected order")
    else:
        print(f"⚠️  PARTIAL - Agent plan differed from expected")
    
    # Show response preview
    response = result.get('final_response', result.get('answer', ''))[:100]
    print(f"Response: {response}...")
    print(f"Latency: {result.get('total_latency_ms', 0):.0f}ms")


def run_tests():
    """Run all test queries"""
    print_header("🧪 AGENTIC WORKFLOW TEST SUITE")
    print(f"Testing {len(TEST_QUERIES)} workflows...\n")
    
    results = []
    
    for i, query_info in enumerate(TEST_QUERIES, 1):
        print_header(f"TEST {i}: {query_info['description']}")
        
        try:
            result = orchestrator.run(
                query=query_info['query'],
                user_context={},
                images=None,
                session_id=None  # New session for each test
            )
            
            print_result(query_info, result)
            results.append({
                "query": query_info['query'],
                "expected": query_info['expected_agents'],
                "actual": result.get('executed_agents', []),
                "success": True
            })
            
        except Exception as e:
            print(f"❌ ERROR: {e}")
            results.append({
                "query": query_info['query'],
                "expected": query_info['expected_agents'],
                "actual": [],
                "success": False,
                "error": str(e)
            })
        
        print()
    
    # Summary
    print_header("📊 TEST SUMMARY")
    passed = sum(1 for r in results if r['success'])
    print(f"Passed: {passed}/{len(results)}")
    
    for r in results:
        status = "✅" if r['success'] else "❌"
        match = r['actual'] == r['expected'] if r['success'] else False
        match_status = "exact" if match else "partial"
        print(f"  {status} {r['query'][:50]}... [{match_status}]")


if __name__ == "__main__":
    print("\n🚀 Starting Agentic Workflow Tests...\n")
    print("This will test ReAct-style reasoning and multi-agent chains.\n")
    
    run_tests()
    
    print("\n✅ Test suite complete!\n")
