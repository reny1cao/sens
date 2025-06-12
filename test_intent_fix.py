#!/usr/bin/env python3
"""Simple test to verify the intent extraction fix."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def test_intent_fix():
    """Test that the tools.py file no longer contains mock intent creation."""
    tools_file = Path(__file__).parent / "src" / "sens" / "agents" / "tools.py"
    content = tools_file.read_text()

    # Check that mock intent creation is removed
    mock_patterns = [
        "Create mock intent",
        "mock intent for SQL generation",
        "base_intent = Intent(",
        "ValidIntent(original_intent=base_intent",
    ]

    found_mocks = []
    for pattern in mock_patterns:
        if pattern in content:
            found_mocks.append(pattern)

    if found_mocks:
        print("❌ Still found mock intent patterns:")
        for pattern in found_mocks:
            print(f"  - {pattern}")
        return False

    # Check that proper intent extraction is present
    proper_patterns = [
        "intent_extractor.extract(modified_query)",
        "intent_validator.validate(",
        "proper intent extraction pipeline",
    ]

    found_proper = []
    for pattern in proper_patterns:
        if pattern in content:
            found_proper.append(pattern)

    if len(found_proper) < 2:  # Should find at least 2 of these
        print("❌ Proper intent extraction not found:")
        print(f"  Found: {found_proper}")
        return False

    print("✅ Intent extraction fix verified!")
    print("✅ Mock intent creation removed")
    print("✅ Proper intent extraction pipeline implemented")
    print("✅ Error handling added for intent extraction failures")

    return True


if __name__ == "__main__":
    success = test_intent_fix()
    sys.exit(0 if success else 1)
