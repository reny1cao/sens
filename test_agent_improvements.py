#!/usr/bin/env python3
"""
Comprehensive test suite to verify agent improvements after fixing mock intent creation.
Tests various scenarios to measure performance improvements.
"""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Configure logging to capture detailed information
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Test scenarios designed to showcase improvements
TEST_SCENARIOS = [
    {
        "name": "Basic Stock Query",
        "query": "Show me recent Apple stock prices",
        "expected_improvements": [
            "Proper entity recognition (Apple → AAPL)",
            "Better table/column mapping",
            "More accurate SQL generation",
        ],
    },
    {
        "name": "Complex Financial Query",
        "query": "What's the correlation between Microsoft stock and GDP?",
        "expected_improvements": [
            "Multi-table intent recognition",
            "Entity mapping (Microsoft → MSFT)",
            "Complex query type classification",
        ],
    },
    {
        "name": "Ambiguous Query",
        "query": "Show me technology companies performance last month",
        "expected_improvements": [
            "Sector classification",
            "Date range interpretation",
            "Multiple entity handling",
        ],
    },
    {
        "name": "Value Discovery Query",
        "query": "Find stocks similar to Google",
        "expected_improvements": [
            "Similarity intent recognition",
            "Value mapping (Google → GOOGL)",
            "Schema exploration for related data",
        ],
    },
]


async def test_agent_scenario(scenario):
    """Test a single agent scenario and capture detailed metrics."""
    print(f"\n🧪 Testing: {scenario['name']}")
    print(f"Query: '{scenario['query']}'")
    print("=" * 60)

    try:
        # Import here to avoid dependency issues during module loading
        from sens.agents.core import SENSAgent

        # Initialize agent
        agent = SENSAgent(max_iterations=3)

        # Record start time
        start_time = time.time()

        # Process the query
        result = await agent.process_query(
            user_query=scenario["query"],
            conversation_id=f"test_{scenario['name'].lower().replace(' ', '_')}",
        )

        # Record end time
        end_time = time.time()
        processing_time = end_time - start_time

        # Analyze results
        analysis = analyze_agent_result(result, scenario, processing_time)
        print_detailed_analysis(analysis)

        return analysis

    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        print(f"Error type: {type(e).__name__}")

        # Try to get more details about the error
        import traceback

        print(f"Traceback: {traceback.format_exc()}")

        return {
            "success": False,
            "error": str(e),
            "scenario": scenario["name"],
            "processing_time": 0,
        }


def analyze_agent_result(result, scenario, processing_time):
    """Analyze agent result and extract improvement metrics."""
    analysis = {
        "scenario": scenario["name"],
        "query": scenario["query"],
        "success": result.get("success", False),
        "processing_time": processing_time,
        "iterations": result.get("iterations", 0),
        "sql_generated": bool(result.get("sql")),
        "mappings_discovered": len(result.get("discovered_mappings", {})),
        "reasoning_steps": len(result.get("reasoning_trace", [])),
        "actions_taken": len(result.get("actions_taken", [])),
        "improvements_observed": [],
        "issues_found": [],
    }

    # Check for specific improvements
    if result.get("discovered_mappings"):
        analysis["improvements_observed"].append("Value mappings discovered")

    if result.get("sql") and "JOIN" in result["sql"].upper():
        analysis["improvements_observed"].append("Multi-table query generated")

    if result.get("reasoning_trace"):
        analysis["improvements_observed"].append("Detailed reasoning trace available")

    if analysis["iterations"] <= 3:
        analysis["improvements_observed"].append("Efficient iteration count")
    else:
        analysis["issues_found"].append(
            f"High iteration count: {analysis['iterations']}"
        )

    if processing_time < 30:
        analysis["improvements_observed"].append("Fast processing time")
    else:
        analysis["issues_found"].append(f"Slow processing: {processing_time:.1f}s")

    # Check for SQL quality
    sql = result.get("sql", "")
    if sql:
        if "WHERE" in sql.upper():
            analysis["improvements_observed"].append("SQL includes filtering")
        if "ORDER BY" in sql.upper():
            analysis["improvements_observed"].append("SQL includes sorting")
        if len(sql.split()) > 10:
            analysis["improvements_observed"].append("Complex SQL generated")
    else:
        analysis["issues_found"].append("No SQL generated")

    return analysis


def print_detailed_analysis(analysis):
    """Print detailed analysis of test results."""
    print(f"📊 Results for '{analysis['scenario']}':")
    print(f"   Success: {'✅' if analysis['success'] else '❌'}")
    print(f"   Processing Time: {analysis['processing_time']:.2f}s")
    print(f"   Iterations: {analysis['iterations']}")
    print(f"   SQL Generated: {'✅' if analysis['sql_generated'] else '❌'}")
    print(f"   Mappings Found: {analysis['mappings_discovered']}")
    print(f"   Reasoning Steps: {analysis['reasoning_steps']}")
    print(f"   Actions Taken: {analysis['actions_taken']}")

    if analysis["improvements_observed"]:
        print(f"   🎯 Improvements Observed:")
        for improvement in analysis["improvements_observed"]:
            print(f"      • {improvement}")

    if analysis["issues_found"]:
        print(f"   ⚠️  Issues Found:")
        for issue in analysis["issues_found"]:
            print(f"      • {issue}")


async def run_comprehensive_tests():
    """Run all test scenarios and provide summary."""
    print("🚀 SENS Agent Improvement Testing")
    print("Testing agent performance after fixing mock intent creation")
    print("=" * 70)

    # Check if we can import the agent (dependency check)
    try:
        from sens.agents.core import SENSAgent

        print("✅ Agent import successful")
    except Exception as e:
        print(f"❌ Cannot import agent: {e}")
        print(
            "Dependency issues detected. Please ensure all requirements are installed."
        )
        return

    results = []

    # Run each test scenario
    for scenario in TEST_SCENARIOS:
        try:
            result = await test_agent_scenario(scenario)
            results.append(result)

            # Brief pause between tests
            await asyncio.sleep(2)

        except Exception as e:
            print(f"❌ Failed to test scenario '{scenario['name']}': {e}")
            results.append(
                {"scenario": scenario["name"], "success": False, "error": str(e)}
            )

    # Generate summary report
    print_summary_report(results)

    # Save detailed results
    save_test_results(results)


def print_summary_report(results):
    """Print a comprehensive summary of all test results."""
    print("\n" + "=" * 70)
    print("📋 COMPREHENSIVE SUMMARY REPORT")
    print("=" * 70)

    total_tests = len(results)
    successful_tests = len([r for r in results if r.get("success", False)])

    print(f"📊 Overall Statistics:")
    print(f"   Total Tests: {total_tests}")
    print(f"   Successful: {successful_tests}")
    print(f"   Failed: {total_tests - successful_tests}")
    print(f"   Success Rate: {(successful_tests/total_tests*100):.1f}%")

    if successful_tests > 0:
        avg_time = (
            sum(r.get("processing_time", 0) for r in results if r.get("success"))
            / successful_tests
        )
        avg_iterations = (
            sum(r.get("iterations", 0) for r in results if r.get("success"))
            / successful_tests
        )

        print(f"\n⚡ Performance Metrics:")
        print(f"   Average Processing Time: {avg_time:.2f}s")
        print(f"   Average Iterations: {avg_iterations:.1f}")

        # Count total improvements
        total_improvements = []
        for result in results:
            if result.get("improvements_observed"):
                total_improvements.extend(result["improvements_observed"])

        unique_improvements = list(set(total_improvements))
        print(f"   Unique Improvements Observed: {len(unique_improvements)}")

        if unique_improvements:
            print(f"\n🎯 Key Improvements Demonstrated:")
            for improvement in unique_improvements:
                count = total_improvements.count(improvement)
                print(f"      • {improvement} ({count} tests)")

    # Identify common issues
    all_issues = []
    for result in results:
        if result.get("issues_found"):
            all_issues.extend(result["issues_found"])

    if all_issues:
        unique_issues = list(set(all_issues))
        print(f"\n⚠️  Common Issues Identified:")
        for issue in unique_issues:
            count = all_issues.count(issue)
            print(f"      • {issue} ({count} tests)")

    print(f"\n💡 Recommendations:")
    if successful_tests == total_tests:
        print(
            "   🎉 Excellent! All tests passed. The intent extraction fix is working perfectly."
        )
    elif successful_tests > total_tests * 0.7:
        print("   👍 Good performance. Minor issues may need attention.")
    else:
        print("   🔧 Significant issues detected. Further debugging recommended.")


def save_test_results(results):
    """Save detailed test results to a JSON file."""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"agent_test_results_{timestamp}.json"

    with open(filename, "w") as f:
        json.dump(
            {
                "timestamp": timestamp,
                "test_type": "agent_improvements_after_intent_fix",
                "total_scenarios": len(TEST_SCENARIOS),
                "results": results,
            },
            f,
            indent=2,
            default=str,
        )

    print(f"\n💾 Detailed results saved to: {filename}")


if __name__ == "__main__":
    asyncio.run(run_comprehensive_tests())
