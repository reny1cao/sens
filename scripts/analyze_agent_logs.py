#!/usr/bin/env python3
"""Script to analyze agent logs and show notes progression."""

import json
import re
import sys


def extract_agent_notes(log_file):
    """Extract and display agent notes progression from logs."""
    notes_updates = []
    current_iteration = 0

    with open(log_file, "r") as f:
        for line in f:
            # Extract iteration
            iteration_match = re.search(r"iteration\[0m=\[35m(\d+)", line)
            if iteration_match:
                current_iteration = int(iteration_match.group(1))

            # Extract notes updates
            if "agent_notes_updated" in line and "new_info" in line:
                new_info_match = re.search(r"new_info\[0m=\[35m\'([^\']+)\'", line)
                if new_info_match:
                    new_info = new_info_match.group(1)
                    notes_updates.append(
                        {"iteration": current_iteration, "update": new_info}
                    )

            # Extract reflection learnings
            if "agent_reflection_complete" in line and "learnings" in line:
                learnings_match = re.search(r"learnings\[0m=\[35m\'([^\']+)\'", line)
                if learnings_match:
                    learnings = learnings_match.group(1)
                    if learnings:
                        notes_updates.append(
                            {"iteration": current_iteration, "reflection": learnings}
                        )

    # Display results
    print("=== AGENT NOTES PROGRESSION ===\n")

    for item in notes_updates:
        if "update" in item:
            print(f"Iteration {item['iteration']} - NOTES UPDATE:")
            print(f"  {item['update']}")
            print()
        elif "reflection" in item:
            print(f"Iteration {item['iteration']} - REFLECTION:")
            print(f"  {item['reflection']}")
            print()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        extract_agent_notes(sys.argv[1])
    else:
        print("Usage: python analyze_agent_logs.py <logfile>")
        print("Example: python analyze_agent_logs.py agent_output.log")
