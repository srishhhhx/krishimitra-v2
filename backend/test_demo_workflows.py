#!/usr/bin/env python3
"""
Demo Workflow Test Suite - 18 Agentic Workflows

Tests all demo-ready workflows with expected routing and behavior validation.
Run 5 at a time with delays to respect API limits.

Run: python test_demo_workflows.py [phase_number]
  phase_number: 1-6 (default: 1)
"""

import sys
import os
import time
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.orchestrator import orchestrator

# ============================================================================
# DEMO WORKFLOWS DEFINITION
# ============================================================================

WORKFLOWS = {
    # Phase 1: Single Agent (W1-W4)
    1: [
        {
            "id": "W1",
            "name": "Weather Query",
            "query": "What's the weather in Bangalore?",
            "expected_agents": ["weather_agent"],
            "validate_keywords": ["temperature", "humidity", "bangalore"],
            "category": "single"
        },
        {
            "id": "W2",
            "name": "RAG Knowledge Query",
            "query": "How do I prevent rice blast disease?",
            "expected_agents": ["general_rag_agent"],
            "validate_keywords": ["disease", "prevention", "treatment", "fungicide"],
            "category": "single"
        },
        {
            "id": "W3",
            "name": "Direct Crop with Parameters",
            "query": "What crop for N=90 P=45 K=50 temp=28 humidity=70 pH=6.5 rainfall=150?",
            "expected_agents": ["crop_agent"],
            "validate_keywords": ["crop", "confidence", "recommended"],
            "category": "single"
        },
        {
            "id": "W4",
            "name": "Cultivation Practice",
            "query": "What is SRI method for rice cultivation?",
            "expected_agents": ["general_rag_agent"],
            "validate_keywords": ["sri", "rice", "seedling", "method"],
            "category": "single"
        }
    ],
    
    # Phase 2: Two-Agent Chains (W5-W8)
    2: [
        {
            "id": "W5",
            "name": "Location to Crop Chain",
            "query": "What crop should I grow in Pune?",
            "expected_agents": ["weather_agent", "crop_agent"],
            "validate_keywords": ["pune", "temperature", "crop", "recommended"],
            "category": "chain"
        },
        {
            "id": "W6",
            "name": "Crop Variety Query",
            "query": "Recommend a rice variety for black soil in monsoon",
            "expected_agents": ["general_rag_agent"],  # Fixed: Variety queries go to RAG
            "validate_keywords": ["rice", "variety", "soil"],
            "category": "chain"
        },
        {
            "id": "W7",
            "name": "Disease Symptoms Query",
            "query": "My tomato leaves have yellow spots, what's the problem?",
            "expected_agents": ["general_rag_agent"],  # Fixed: Text disease queries go to RAG
            "validate_keywords": ["tomato", "yellow", "disease", "deficiency"],
            "category": "chain"
        },
        {
            "id": "W8",
            "name": "Fertilizer with Known Crop",
            "query": "What fertilizer should I use for wheat on loamy soil?",
            "expected_agents": ["fertilizer_agent"],
            "validate_keywords": ["fertilizer", "wheat", "npk"],
            "category": "chain"
        }
    ],
    
    # Phase 3: Three-Agent Chains (W9-W11)
    3: [
        {
            "id": "W9",
            "name": "Full Recommendation Pipeline",
            "query": "What crop and fertilizer for Tamil Nadu this season?",
            "expected_agents": ["weather_agent", "crop_agent", "fertilizer_agent"],
            "validate_keywords": ["tamil", "temperature", "crop", "fertilizer"],
            "category": "chain"
        },
        {
            "id": "W10",
            "name": "Location + Crop + Cultivation",
            "query": "Best practices for growing rice in Kerala?",
            "expected_agents": ["weather_agent", "crop_agent"],  # May include RAG
            "validate_keywords": ["kerala", "rice", "practice"],
            "category": "chain"
        },
        {
            "id": "W11",
            "name": "Disease Chain with Context",
            "query": "I'm growing cotton in Maharashtra, seeing pest damage. Help?",
            "expected_agents": ["weather_agent", "general_rag_agent"],
            "validate_keywords": ["cotton", "pest", "maharashtra"],
            "category": "chain"
        }
    ],
    
    # Phase 4: Clarification Flows (W12-W14)
    4: [
        {
            "id": "W12",
            "name": "Missing Location Clarification",
            "query": "What crop should I grow?",
            "expected_behavior": "clarification",
            "validate_keywords": ["location", "soil", "where", "what"],
            "category": "clarification"
        },
        {
            "id": "W13",
            "name": "Missing Crop for Fertilizer",
            "query": "What fertilizer should I use?",
            "expected_behavior": "clarification",
            "validate_keywords": ["crop", "soil", "what", "which"],
            "category": "clarification"
        },
        {
            "id": "W14",
            "name": "Ambiguous Query",
            "query": "Help with my wheat",
            "expected_behavior": "clarification",
            "validate_keywords": ["planting", "disease", "fertilizer", "help", "looking"],
            "category": "clarification"
        }
    ],
    
    # Phase 5: Multi-Turn Context (W15-W17)
    5: [
        {
            "id": "W15",
            "name": "Context Carryover - Location",
            "turns": [
                {"query": "I'm farming in Punjab", "store_session": True},
                {"query": "What crop should I grow?", "use_session": True}
            ],
            "expected_behavior": "uses Punjab from previous turn",
            "validate_keywords": ["punjab", "crop", "recommended"],
            "category": "multi-turn"
        },
        {
            "id": "W16",
            "name": "Context Carryover - Crop Follow-up",
            "turns": [
                {"query": "Recommend a crop for Karnataka", "store_session": True},
                {"query": "What fertilizer for this?", "use_session": True}
            ],
            "expected_behavior": "uses crop from previous turn",
            "validate_keywords": ["fertilizer"],
            "category": "multi-turn"
        },
        {
            "id": "W17",
            "name": "Progressive Information Gathering",
            "turns": [
                {"query": "I need farming advice", "store_session": True},
                {"query": "Maharashtra", "use_session": True},
                {"query": "Crops", "use_session": True}
            ],
            "expected_behavior": "builds context across turns",
            "validate_keywords": ["maharashtra", "crop"],
            "category": "multi-turn"
        }
    ],
    
    # Phase 6: Flagship Demo (W18)
    6: [
        {
            "id": "W18",
            "name": "Full Agentic Demo",
            "query": "I have 5 acres in Andhra Pradesh with red soil. Monsoon is starting. What should I plant and how much fertilizer? Also common pests to watch for.",
            "expected_agents": ["weather_agent", "crop_agent", "fertilizer_agent", "general_rag_agent"],
            "validate_keywords": ["andhra", "crop", "fertilizer", "pest", "monsoon"],
            "category": "flagship"
        }
    ]
}


def print_header(text: str, char: str = "="):
    print(f"\n{char * 80}")
    print(f"  {text}")
    print(f"{char * 80}")


def check_routing(actual_agents: list, expected_agents: list) -> str:
    """Check if routing matches expected agents"""
    if set(expected_agents).issubset(set(actual_agents)):
        return "✅ CORRECT"
    elif any(agent in actual_agents for agent in expected_agents):
        return "⚠️ PARTIAL"
    else:
        return "❌ WRONG"


def check_keywords(response: str, keywords: list) -> tuple:
    """Check if response contains expected keywords"""
    response_lower = response.lower()
    matched = [k for k in keywords if k.lower() in response_lower]
    missed = [k for k in keywords if k.lower() not in response_lower]
    return matched, missed


def run_single_turn_test(workflow: dict) -> dict:
    """Run a single-turn workflow test"""
    print(f"\n{'─' * 80}")
    print(f"  {workflow['id']}: {workflow['name']}")
    print(f"{'─' * 80}")
    print(f"📝 Query: {workflow['query']}")
    print(f"📊 Expected: {workflow.get('expected_agents', workflow.get('expected_behavior'))}")
    
    try:
        start = time.time()
        result = orchestrator.run(
            query=workflow['query'],
            user_context={},
            images=None,
            session_id=None
        )
        latency = (time.time() - start) * 1000
        
        agents = result.get("executed_agents", [])
        response = result.get("final_response", result.get("answer", ""))
        session_id = result.get("session_id", "")
        
        # Check routing
        expected = workflow.get("expected_agents", [])
        routing_status = check_routing(agents, expected) if expected else "N/A"
        
        # Check keywords
        keywords = workflow.get("validate_keywords", [])
        matched, missed = check_keywords(response, keywords)
        keyword_pct = (len(matched) / len(keywords) * 100) if keywords else 0
        
        print(f"\n⚡ Agents: {agents}")
        print(f"🔀 Routing: {routing_status}")
        print(f"⏱️  Latency: {latency:.0f}ms")
        print(f"✓ Keywords: {matched} ({keyword_pct:.0f}%)")
        print(f"✗ Missing: {missed}")
        print(f"\n📝 Response Preview:\n{response[:400]}...")
        
        return {
            "id": workflow["id"],
            "name": workflow["name"],
            "passed": routing_status == "✅ CORRECT" and keyword_pct >= 50,
            "routing": routing_status,
            "agents": agents,
            "latency": latency,
            "keyword_pct": keyword_pct,
            "session_id": session_id
        }
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return {
            "id": workflow["id"],
            "name": workflow["name"],
            "passed": False,
            "routing": "ERROR",
            "agents": [],
            "latency": 0,
            "keyword_pct": 0,
            "error": str(e)
        }


def run_multi_turn_test(workflow: dict) -> dict:
    """Run a multi-turn workflow test"""
    print(f"\n{'─' * 80}")
    print(f"  {workflow['id']}: {workflow['name']}")
    print(f"{'─' * 80}")
    
    session_id = None
    final_response = ""
    final_agents = []
    
    for i, turn in enumerate(workflow["turns"], 1):
        print(f"\n🔄 Turn {i}: {turn['query']}")
        
        try:
            result = orchestrator.run(
                query=turn["query"],
                user_context={},
                images=None,
                session_id=session_id if turn.get("use_session") else None
            )
            
            if turn.get("store_session"):
                session_id = result.get("session_id", "")
                print(f"   💾 Session stored: {session_id[:20]}...")
            
            agents = result.get("executed_agents", [])
            response = result.get("final_response", result.get("answer", ""))
            final_response = response
            final_agents = agents
            
            print(f"   ⚡ Agents: {agents}")
            print(f"   📝 Response: {response[:150]}...")
            
            time.sleep(3)  # Small delay between turns
            
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            return {"id": workflow["id"], "passed": False, "error": str(e)}
    
    # Check keywords in final response
    keywords = workflow.get("validate_keywords", [])
    matched, missed = check_keywords(final_response, keywords)
    keyword_pct = (len(matched) / len(keywords) * 100) if keywords else 0
    
    print(f"\n✓ Final Keywords: {matched} ({keyword_pct:.0f}%)")
    
    return {
        "id": workflow["id"],
        "name": workflow["name"],
        "passed": keyword_pct >= 50,
        "agents": final_agents,
        "keyword_pct": keyword_pct
    }


def run_phase(phase: int):
    """Run all workflows in a phase"""
    workflows = WORKFLOWS.get(phase, [])
    
    if not workflows:
        print(f"❌ Invalid phase: {phase}. Valid phases: 1-6")
        return
    
    phase_names = {
        1: "Single Agent Reliability",
        2: "Two-Agent Chains",
        3: "Three-Agent Chains",
        4: "Clarification Flows",
        5: "Multi-Turn Context",
        6: "Flagship Demo"
    }
    
    print_header(f"🔬 PHASE {phase}: {phase_names[phase]}")
    print(f"Testing {len(workflows)} workflows with 8s delays...")
    
    results = []
    
    for i, workflow in enumerate(workflows, 1):
        if workflow.get("turns"):  # Multi-turn
            result = run_multi_turn_test(workflow)
        else:  # Single-turn
            result = run_single_turn_test(workflow)
        
        results.append(result)
        
        if i < len(workflows):
            print(f"\n⏳ Waiting 8s...")
            time.sleep(8)
    
    # Summary
    print_header(f"📊 PHASE {phase} RESULTS")
    
    passed = sum(1 for r in results if r.get("passed"))
    print(f"\n  Passed: {passed}/{len(results)}")
    
    for r in results:
        status = "✅" if r.get("passed") else "❌"
        print(f"  {status} {r['id']}: {r['name']} - {r.get('routing', 'N/A')}, Keywords: {r.get('keyword_pct', 0):.0f}%")
    
    return results


if __name__ == "__main__":
    phase = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    print(f"\n🚀 Running Demo Workflow Tests - Phase {phase}\n")
    run_phase(phase)
    print("\n✅ Test complete!\n")
