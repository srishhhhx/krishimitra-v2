#!/usr/bin/env python3
"""
Interactive Test Script for Crop Agent

This script provides a dedicated interactive interface to test the Crop Agent
in isolation, allowing for detailed inspection of its parameter extraction,
default logic, and model recommendations.

Features:
- Focused testing of the CropAgent
- Detailed breakdown of extracted vs. defaulted parameters
- Debug mode for inspecting raw agent output
- Example queries for various scenarios

Usage:
    python test_crop_agent_interactive.py

Commands:
    - Type your query and press Enter
    - 'help' - Show example queries
    - 'debug' - Toggle debug mode (shows raw collected_findings)
    - 'quit' or 'exit' - Exit the program
"""

import sys
import asyncio
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

# Load .env file from the same directory as the script
dotenv_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=dotenv_path)

from agents.crop_agent import CropAgent
from services.generation import GenerationService
from schemas.agents import AgentState
from core.logging import get_logger

# Setup logging
logger = get_logger(__name__)

# ANSI color codes for beautiful output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    DIM = '\033[2m'

# Emoji for visual appeal
EMOJI = {
    'crop': '🌱',
    'thinking': '🧠',
    'success': '✅',
    'error': '❌',
    'params': '🔧',
    'debug': '🐞',
}

def print_banner():
    """Print welcome banner"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}")
    print(f"  {EMOJI['crop']} KrishiMitra - Crop Agent Interactive Test")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}\n")
    print(f"{Colors.OKCYAN}This tool allows for focused testing of the Crop Agent.{Colors.ENDC}\n")
    print(f"{Colors.DIM}Type 'help' for examples, 'debug' for details, 'quit' to exit.{Colors.ENDC}\n")

def print_help():
    """Print comprehensive help with examples for the Crop Agent"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}")
    print(f"  EXAMPLE CROP AGENT QUERIES")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}\n")

    examples = {
        "Full Parameters": "N=90 P=42 K=43 temperature=20.8 humidity=82 ph=6.5 rainfall=202",
        "Partial Parameters": "I have sandy soil with high nitrogen and the temperature is around 30C.",
        "Location-based": "What crop should I grow in Punjab?",
        "Vague Query": "What's the best crop for my farm?",
        "User Preference": "I want to grow rice in black soil.",
        "Hindi Query": "मेरी मिट्टी में नाइट्रोजन अधिक है, कौन सी फसल उगानी चाहिए?",
    }

    for category, example in examples.items():
        print(f"{Colors.BOLD}{category}:{Colors.ENDC}")
        print(f"  {Colors.OKGREEN}• {example}{Colors.ENDC}\n")

def print_separator():
    """Print separator line"""
    print(f"{Colors.OKBLUE}{'─'*70}{Colors.ENDC}")

def format_result(result: Dict[str, Any], show_debug: bool = False):
    """Format and print comprehensive result from the agent"""
    print_separator()

    finding = result.get("collected_findings", {}).get("crop_agent", {})
    status = finding.get("status")
    data = finding.get("data", {})

    if status == "success":
        print(f"\n{Colors.BOLD}{Colors.HEADER}RECOMMENDATION{Colors.ENDC}\n")
        
        recommended_crop = data.get('recommended_crop', 'N/A').title()
        confidence = data.get('confidence_percentage', 0)
        
        print(f"  {EMOJI['crop']} {Colors.BOLD}Recommended Crop: {Colors.OKGREEN}{recommended_crop}{Colors.ENDC}")
        print(f"     {Colors.DIM}Confidence: {confidence:.1f}%{Colors.ENDC}\n")

        alternatives = data.get("alternatives", [])
        if alternatives:
            print(f"  {Colors.BOLD}Alternative Crops:{Colors.ENDC}")
            for alt in alternatives[:3]:
                alt_crop = alt.get("crop", "N/A").title()
                alt_conf = alt.get("confidence_percentage", 0)
                print(f"     {Colors.DIM}• {alt_crop} ({alt_conf:.1f}%){Colors.ENDC}")
            print()

        print(f"  {EMOJI['params']} {Colors.BOLD}Parameters Used:{Colors.ENDC}")
        input_params = data.get("input_parameters", {})
        defaults_used = data.get("defaults_applied", [])
        
        for key, value in input_params.items():
            is_default = " (default)" if key.upper() in defaults_used or key in defaults_used else ""
            print(f"     {Colors.DIM}• {key.title()}: {value}{Colors.WARNING}{is_default}{Colors.ENDC}")
        
    elif status == "error":
        print(f"\n{Colors.BOLD}{Colors.FAIL}ERROR{Colors.ENDC}\n")
        error_msg = finding.get("error", "Unknown error")
        print(f"  {EMOJI['error']} {error_msg}")
    
    else:
        print(f"\n{Colors.BOLD}{Colors.WARNING}UNKNOWN RESPONSE{Colors.ENDC}\n")
        print(f"  Received unexpected status: {status}")

    if show_debug:
        print(f"\n{Colors.BOLD}{Colors.WARNING}{EMOJI['debug']} DEBUG INFORMATION{Colors.ENDC}")
        import json
        print(json.dumps(finding, indent=2))

    print()
    print_separator()
    print()


async def test_query(agent: CropAgent, query: str, show_debug: bool = False):
    """Test a single query against the Crop Agent"""
    try:
        print(f"{Colors.DIM}Processing query...{Colors.ENDC}\n")

        # Create a basic state for the agent
        initial_state: AgentState = {
            "user_query": query,
            "user_context": {},
            "collected_findings": {},
            "clarification_state": {},
            "executed_agents": [],
        }

        # Run the agent
        final_state = await agent.run(initial_state)

        # Format and print the result
        format_result(final_state, show_debug=show_debug)

    except Exception as e:
        print(f"{Colors.FAIL}{Colors.BOLD}An unexpected error occurred: {e}{Colors.ENDC}")
        if show_debug:
            import traceback
            traceback.print_exc()

async def main():
    """Main interactive loop"""
    print_banner()

    # Initialize GenerationService and CropAgent
    try:
        print(f"{Colors.OKCYAN}Initializing services...{Colors.ENDC}")
        generation_service = GenerationService()
        crop_agent = CropAgent(generation_service=generation_service)
        health = crop_agent.health_check()
        if health.get("status") != "healthy":
            raise RuntimeError(f"Crop Agent is not healthy: {health.get('details')}")
        print(f"{Colors.OKGREEN}{EMOJI['success']} Crop Agent is ready!{Colors.ENDC}\n")
    except Exception as e:
        print(f"{Colors.FAIL}Failed to initialize agent: {e}{Colors.ENDC}")
        return

    show_debug = False
    while True:
        try:
            query = input(f"{Colors.BOLD}Your crop query:{Colors.ENDC} ").strip()

            if not query:
                continue
            
            if query.lower() in ['quit', 'exit', 'q']:
                print(f"\n{Colors.OKCYAN}Goodbye!{Colors.ENDC}\n")
                break

            elif query.lower() == 'help':
                print_help()
                continue
            
            elif query.lower() == 'debug':
                show_debug = not show_debug
                status = "enabled" if show_debug else "disabled"
                print(f"{Colors.WARNING}Debug mode {status}{Colors.ENDC}\n")
                continue

            # Process the query with the agent
            await test_query(crop_agent, query, show_debug)

        except KeyboardInterrupt:
            print(f"\n\n{Colors.OKCYAN}Interrupted. Type 'quit' to exit.{Colors.ENDC}\n")
        except Exception as e:
            print(f"{Colors.FAIL}Error in main loop: {e}{Colors.ENDC}\n")
            if show_debug:
                import traceback
                traceback.print_exc()

if __name__ == "__main__":
    # Setup asyncio event loop
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting.")
