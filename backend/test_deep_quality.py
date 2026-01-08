#!/usr/bin/env python3
"""
Deep Quality Test - 5 Diverse Queries with Response Analysis

Focus Areas:
1. ML Model Accuracy (Crop & Fertilizer predictions)
2. Response Quality (completeness, relevance)
3. Ground Truth Validation
4. Agent Performance Metrics

Run: python test_deep_quality.py
"""

import sys
import os
import time
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.orchestrator import orchestrator

# 5 DEEP QUALITY TEST QUERIES (Diverse + Challenging)
QUALITY_TESTS = [
    # =========================================
    # TEST 1: Direct Crop Prediction (Verifiable Ground Truth)
    # =========================================
    {
        "name": "Crop Prediction - Known Optimal Conditions for Rice",
        "query": "I have N=80 P=40 K=40 pH=6.5 rainfall=200mm temperature=25 humidity=80. What crop should I grow?",
        "expected_agent": "crop_agent",
        "ground_truth": {
            "optimal_crop": "rice",
            "why": "High humidity (80%), moderate temp (25°C), high rainfall (200mm), neutral pH - classic rice conditions",
            "confidence_expected": ">80%"
        },
        "validate_response": ["rice", "paddy"]  # Accept either term
    },
    
    # =========================================
    # TEST 2: Direct Fertilizer Prediction (Verifiable)
    # =========================================
    {
        "name": "Fertilizer Prediction - Wheat on Sandy Soil",
        "query": "What fertilizer should I use for wheat crop on sandy loam soil? My NPK is N=30 P=20 K=25",
        "expected_agent": "fertilizer_agent",
        "ground_truth": {
            "expected_fertilizers": ["Urea", "DAP", "NPK", "10-26-26", "20-20-0"],
            "why": "Low nitrogen (30) needs nitrogen-rich fertilizer like Urea; wheat is nitrogen-hungry"
        },
        "validate_response": ["urea", "dap", "npk", "nitrogen", "fertilizer"]
    },
    
    # =========================================
    # TEST 3: Weather + Crop Chain (Multi-Agent)
    # =========================================
    {
        "name": "Weather-Crop Chain - Real Location",
        "query": "What crop should I grow in Pune, Maharashtra?",
        "expected_agent": "weather_agent",  # Should start with weather
        "expected_chain": ["weather_agent", "crop_agent"],
        "ground_truth": {
            "pune_climate": "Semi-arid, avg 25-30°C, monsoon rainfall ~700mm",
            "suitable_crops": ["soybean", "cotton", "jowar", "bajra", "groundnut", "sugarcane"]
        },
        "validate_response": ["soybean", "cotton", "jowar", "bajra", "groundnut", "sugarcane", "temperature", "humidity"]
    },
    
    # =========================================
    # TEST 4: RAG Knowledge Query (Verifiable)
    # =========================================
    {
        "name": "RAG Query - Specific Agricultural Practice",
        "query": "What is the System of Rice Intensification (SRI) method and how to implement it?",
        "expected_agent": "general_rag_agent",
        "ground_truth": {
            "SRI_key_points": [
                "Single seedling transplanting",
                "Wider spacing (25x25cm)",
                "Alternate wetting and drying",
                "Mechanical weeding",
                "Organic matter application"
            ]
        },
        "validate_response": ["seedling", "spacing", "wetting", "drying", "organic", "transplant"]
    },
    
    # =========================================
    # TEST 5: Complex Multi-Intent Query
    # =========================================
    {
        "name": "Complex Query - Crop + Fertilizer Together",
        "query": "I'm in Kerala with laterite soil. What crop and fertilizer should I use this monsoon?",
        "expected_chain": ["weather_agent", "crop_agent", "fertilizer_agent"],
        "ground_truth": {
            "kerala_crops": ["rice", "coconut", "rubber", "pepper", "cardamom", "banana"],
            "laterite_characteristics": "Acidic, iron-rich, low in nutrients",
            "expected_fertilizers": ["DAP", "MOP", "lime for pH correction"]
        },
        "validate_response": ["rice", "coconut", "kerala", "monsoon", "fertilizer"]
    }
]


def print_header(text: str, char: str = "="):
    print(f"\n{char * 80}")
    print(f"  {text}")
    print(f"{char * 80}")


def analyze_response_quality(response: str, test_case: dict) -> dict:
    """Deep analysis of response quality against ground truth"""
    response_lower = response.lower()
    
    analysis = {
        "length": len(response),
        "word_count": len(response.split()),
        "validation_matches": [],
        "validation_misses": [],
        "quality_score": 0,
        "issues": []
    }
    
    # Check for validation keywords
    if "validate_response" in test_case:
        for keyword in test_case["validate_response"]:
            if keyword.lower() in response_lower:
                analysis["validation_matches"].append(keyword)
            else:
                analysis["validation_misses"].append(keyword)
        
        # Calculate quality score
        total = len(test_case["validate_response"])
        matched = len(analysis["validation_matches"])
        analysis["quality_score"] = (matched / total) * 100 if total > 0 else 0
    
    # Check for common issues
    if analysis["length"] < 100:
        analysis["issues"].append("TOO_SHORT")
    if "error" in response_lower or "failed" in response_lower:
        analysis["issues"].append("ERROR_IN_RESPONSE")
    if "i don't know" in response_lower or "cannot" in response_lower:
        analysis["issues"].append("UNCERTAIN_RESPONSE")
    if analysis["length"] < 50 and "?" in response:
        analysis["issues"].append("CLARIFICATION_REQUEST")
    
    return analysis


def run_quality_test(test_case: dict, num: int, total: int) -> dict:
    """Run single quality test with deep analysis"""
    print_header(f"TEST {num}/{total}: {test_case['name']}", "-")
    print(f"\n📝 QUERY: {test_case['query']}")
    print(f"📊 EXPECTED AGENT: {test_case.get('expected_agent', test_case.get('expected_chain', 'unknown'))}")
    
    if "ground_truth" in test_case:
        print(f"🎯 GROUND TRUTH:")
        for key, value in test_case["ground_truth"].items():
            print(f"   • {key}: {value}")
    
    try:
        start_time = time.time()
        
        result = orchestrator.run(
            query=test_case['query'],
            user_context={},
            images=None,
            session_id=None
        )
        
        end_time = time.time()
        latency = (end_time - start_time) * 1000
        
        agents_used = result.get("executed_agents", [])
        response = result.get("final_response", result.get("answer", ""))
        
        print(f"\n⚡ AGENTS EXECUTED: {agents_used}")
        print(f"⏱️  LATENCY: {latency:.0f}ms")
        
        # Deep response analysis
        quality = analyze_response_quality(response, test_case)
        
        print(f"\n📈 QUALITY ANALYSIS:")
        print(f"   • Response Length: {quality['length']} chars ({quality['word_count']} words)")
        print(f"   • Quality Score: {quality['quality_score']:.0f}%")
        print(f"   • Matched Keywords: {quality['validation_matches']}")
        print(f"   • Missing Keywords: {quality['validation_misses']}")
        
        if quality["issues"]:
            print(f"   • Issues: {quality['issues']}")
        
        # Show full response
        print(f"\n📝 FULL RESPONSE:")
        print("-" * 60)
        print(response[:2000] if len(response) > 2000 else response)
        print("-" * 60)
        
        # Check collected_findings for detailed data
        collected = result.get("collected_findings", {})
        if collected:
            print(f"\n🔍 COLLECTED FINDINGS:")
            for agent, data in collected.items():
                print(f"   [{agent}]:")
                if isinstance(data, dict):
                    for k, v in list(data.items())[:5]:  # Show first 5 items
                        print(f"      • {k}: {str(v)[:100]}")
        
        return {
            "name": test_case["name"],
            "passed": quality["quality_score"] >= 50 and not quality["issues"],
            "agents": agents_used,
            "latency": latency,
            "quality_score": quality["quality_score"],
            "response_length": quality["length"],
            "matched_keywords": quality["validation_matches"],
            "issues": quality["issues"]
        }
        
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        return {
            "name": test_case["name"],
            "passed": False,
            "agents": [],
            "latency": 0,
            "quality_score": 0,
            "response_length": 0,
            "matched_keywords": [],
            "issues": [f"EXCEPTION: {str(e)[:100]}"]
        }


def run_quality_suite():
    """Run quality test suite with delays"""
    print_header("🔬 DEEP QUALITY TEST SUITE - 5 DIVERSE QUERIES")
    print(f"Testing ML model accuracy, response quality, and ground truth validation")
    print(f"Adding 10s delay between queries to respect API limits...")
    
    results = []
    
    for i, test_case in enumerate(QUALITY_TESTS, 1):
        result = run_quality_test(test_case, i, len(QUALITY_TESTS))
        results.append(result)
        
        if i < len(QUALITY_TESTS):
            print(f"\n⏳ Waiting 10s before next query...")
            time.sleep(10)
    
    # Final Summary
    print_header("📊 QUALITY TEST SUMMARY")
    
    passed = sum(1 for r in results if r["passed"])
    avg_quality = sum(r["quality_score"] for r in results) / len(results)
    avg_latency = sum(r["latency"] for r in results if r["latency"] > 0) / max(1, sum(1 for r in results if r["latency"] > 0))
    
    print(f"\n  📈 OVERALL RESULTS:")
    print(f"     Tests Passed: {passed}/{len(results)}")
    print(f"     Average Quality Score: {avg_quality:.0f}%")
    print(f"     Average Latency: {avg_latency:.0f}ms")
    
    print(f"\n  📋 DETAILED RESULTS:")
    for r in results:
        status = "✅" if r["passed"] else "❌"
        print(f"     {status} {r['name']}")
        print(f"        Quality: {r['quality_score']:.0f}% | Latency: {r['latency']:.0f}ms")
        print(f"        Agents: {r['agents']}")
        print(f"        Matched: {r['matched_keywords']}")
        if r["issues"]:
            print(f"        Issues: {r['issues']}")
    
    # Model Performance Assessment
    print_header("🧠 ML MODEL PERFORMANCE ASSESSMENT")
    
    crop_test = results[0] if results else None
    fert_test = results[1] if len(results) > 1 else None
    
    if crop_test:
        print(f"\n  CROP MODEL (Naive Bayes):")
        if "rice" in [k.lower() for k in crop_test.get("matched_keywords", [])]:
            print(f"     ✅ Correctly predicted RICE for optimal conditions")
            print(f"     Model appears to be working correctly")
        else:
            print(f"     ⚠️ Did not predict expected crop (rice)")
            print(f"     May indicate model issues or different interpretation")
    
    if fert_test:
        print(f"\n  FERTILIZER MODEL (XGBoost):")
        fert_matched = [k.lower() for k in fert_test.get("matched_keywords", [])]
        if any(f in fert_matched for f in ["urea", "dap", "npk"]):
            print(f"     ✅ Predicted reasonable fertilizer")
            print(f"     Model appears to be working correctly")
        else:
            print(f"     ⚠️ Did not predict expected fertilizer")
            print(f"     May indicate model issues or need for recalibration")
    
    return results


if __name__ == "__main__":
    print("\n🚀 Starting Deep Quality Tests...\n")
    run_quality_suite()
    print("\n✅ Quality test suite complete!\n")
