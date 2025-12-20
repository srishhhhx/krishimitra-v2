"""
RAG Evaluation Script for Krishi Mitra
Sends queries from CSV to the RAG endpoint and tracks results
"""

import requests
import time
import csv
import json
from datetime import datetime
from typing import List, Dict, Any

# --- Configuration ---
BASE_URL = "http://127.0.0.1:8000"
LOGIN_URL = f"{BASE_URL}/auth/login"
RAG_URL = f"{BASE_URL}/api/v1/rag/query"

# !! IMPORTANT: Fill these in with your test user credentials !!
# You need to create a test user first via signup endpoint or frontend
TEST_EMAIL = "test@example.com"  # Change this to your test user email
TEST_PASSWORD = "testpassword123"  # Change this to your test user password

# Path to your CSV file with queries
CSV_FILE = "testquries.csv"

# Output file for results
OUTPUT_FILE = f"evaluation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

# -------------------------


def load_queries_from_csv(csv_path: str) -> List[Dict[str, str]]:
    """Load queries from CSV file."""
    queries = []
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("Query"):  # Skip empty rows
                    queries.append(
                        {"query": row["Query"], "type": row.get("Type", "Unknown")}
                    )
        print(f"✓ Loaded {len(queries)} queries from {csv_path}")
        return queries
    except FileNotFoundError:
        print(f"✗ Error: CSV file '{csv_path}' not found")
        return []
    except Exception as e:
        print(f"✗ Error loading CSV: {e}")
        return []


def get_auth_token() -> str:
    """Logs in to the API and returns a JWT access token."""
    print(f"\n🔐 Attempting to log in as {TEST_EMAIL}...")
    try:
        response = requests.post(
            LOGIN_URL,
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()

        token = response.json().get("access_token")
        if not token:
            print("✗ Error: 'access_token' not found in login response.")
            return None

        print("✓ Login successful. Token received.")
        return token
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print("✗ Login failed: Invalid credentials")
            print(
                "   Please create a test user first or update TEST_EMAIL and TEST_PASSWORD"
            )
        else:
            print(f"✗ Login failed: HTTP {e.response.status_code}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"✗ Login failed: {e}")
        print("   Make sure the backend server is running on http://127.0.0.1:8000")
        return None


def run_rag_queries(token: str, queries: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Loops through queries and sends each to the RAG endpoint."""
    if not token:
        print("✗ No auth token, cannot run queries.")
        return []

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    total_queries = len(queries)
    results = []

    print(f"\n🚀 Starting to send {total_queries} queries to RAG endpoint...")
    print("=" * 80)

    for i, query_data in enumerate(queries):
        query_text = query_data["query"]
        query_type = query_data["type"]

        payload = {"query": query_text, "top_k": 5}

        try:
            print(f"\n[{i + 1}/{total_queries}] Type: {query_type}")
            print(f"Query: {query_text[:80]}{'...' if len(query_text) > 80 else ''}")

            start_time = time.time()
            response = requests.post(RAG_URL, headers=headers, json=payload)
            response.raise_for_status()
            response_time = (time.time() - start_time) * 1000

            result_data = response.json()

            # Store result
            result = {
                "query_number": i + 1,
                "query": query_text,
                "type": query_type,
                "status": "success",
                "http_status": response.status_code,
                "response_time_ms": round(response_time, 2),
                "answer": result_data.get("answer", ""),
                "sources": result_data.get("sources", []),
                "num_chunks_retrieved": len(result_data.get("retrieved_chunks", [])),
                "backend_latency_ms": result_data.get("latency_ms", 0),
            }
            results.append(result)

            print(f"✓ Success (HTTP {response.status_code})")
            print(f"  Response time: {round(response_time, 2)}ms")
            print(f"  Answer preview: {result_data.get('answer', '')[:100]}...")

        except requests.exceptions.HTTPError as e:
            error_detail = "Unknown error"
            try:
                error_detail = e.response.json().get("detail", str(e))
            except:
                error_detail = e.response.text if e.response.text else str(e)

            print(f"✗ FAILED (HTTP {e.response.status_code})")
            print(f"  Error: {error_detail[:200]}")
            result = {
                "query_number": i + 1,
                "query": query_text,
                "type": query_type,
                "status": "failed",
                "http_status": e.response.status_code,
                "error": str(e),
                "error_detail": error_detail,
            }
            results.append(result)

        except requests.exceptions.RequestException as e:
            print(f"✗ FAILED: {e}")
            result = {
                "query_number": i + 1,
                "query": query_text,
                "type": query_type,
                "status": "failed",
                "error": str(e),
            }
            results.append(result)

        # Be nice to your server
        if i < total_queries - 1:
            time.sleep(5)

    print("\n" + "=" * 80)
    print(f"✓ All {total_queries} queries completed.")
    return results


def save_results(results: List[Dict[str, Any]], output_file: str):
    """Save results to JSON file."""
    try:
        summary = {
            "total_queries": len(results),
            "successful": len([r for r in results if r["status"] == "success"]),
            "failed": len([r for r in results if r["status"] == "failed"]),
            "by_type": {},
        }

        # Count by type
        for result in results:
            query_type = result.get("type", "Unknown")
            if query_type not in summary["by_type"]:
                summary["by_type"][query_type] = {
                    "total": 0,
                    "successful": 0,
                    "failed": 0,
                }
            summary["by_type"][query_type]["total"] += 1
            if result["status"] == "success":
                summary["by_type"][query_type]["successful"] += 1
            else:
                summary["by_type"][query_type]["failed"] += 1

        # Calculate average response time
        successful_results = [r for r in results if r["status"] == "success"]
        if successful_results:
            avg_response_time = sum(
                r.get("response_time_ms", 0) for r in successful_results
            ) / len(successful_results)
            summary["avg_response_time_ms"] = round(avg_response_time, 2)

        output_data = {
            "timestamp": datetime.now().isoformat(),
            "summary": summary,
            "results": results,
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Results saved to: {output_file}")
        print("\n📊 Summary:")
        print(f"  Total queries: {summary['total_queries']}")
        print(f"  Successful: {summary['successful']}")
        print(f"  Failed: {summary['failed']}")
        if "avg_response_time_ms" in summary:
            print(f"  Avg response time: {summary['avg_response_time_ms']}ms")
        print("\n  By type:")
        for qtype, stats in summary["by_type"].items():
            print(f"    {qtype}: {stats['successful']}/{stats['total']} successful")

    except Exception as e:
        print(f"✗ Error saving results: {e}")


def main():
    """Main execution function."""
    print("=" * 80)
    print("🌾 Krishi Mitra RAG Evaluation Script")
    print("=" * 80)

    # Load queries from CSV
    queries = load_queries_from_csv(CSV_FILE)
    if not queries:
        print("\n✗ No queries to process. Exiting.")
        return

    # Get authentication token
    access_token = get_auth_token()
    if not access_token:
        print("\n✗ Authentication failed. Exiting.")
        return

    # Run queries
    results = run_rag_queries(access_token, queries)

    # Save results
    if results:
        save_results(results, OUTPUT_FILE)

    print("\n" + "=" * 80)
    print("✓ Evaluation complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
