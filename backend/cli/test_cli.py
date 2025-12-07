"""
CLI Module Validation Tests

Quick tests to verify CLI module structure and imports.
Run with: python cli/test_cli.py
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_imports():
    """Test that all CLI modules can be imported."""
    print("Testing CLI module imports...")

    try:
        import cli
        print("✅ cli package imported")

        from cli import enrich
        print("✅ cli.enrich imported")

        from cli import formatters
        print("✅ cli.formatters imported")

        from cli import staging
        print("✅ cli.staging imported")

        from cli.staging import StagingMode, OutreachChannel, parse_channels
        print("✅ cli.staging classes imported")

        from cli.enrich import InputType, detect_input_type, parse_input
        print("✅ cli.enrich classes imported")

        print("\n✅ All imports successful!")
        return True

    except Exception as e:
        print(f"\n❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_input_detection():
    """Test input type auto-detection."""
    print("\nTesting input type detection...")

    from cli.enrich import detect_input_type, InputType

    tests = [
        ("https://acme-hvac.com", InputType.URL),
        ("http://example.com", InputType.URL),
        ("www.example.com", InputType.URL),
        ("https://linkedin.com/company/acme", InputType.LINKEDIN),
        ("lead_abc123", InputType.CLOSE_ID),
        ("John Smith, Acme HVAC", InputType.PERSON),
        ("John Smith at Acme HVAC", InputType.PERSON),
        ("Acme HVAC", InputType.NAME),
    ]

    passed = 0
    failed = 0

    for input_text, expected_type in tests:
        detected = detect_input_type(input_text)
        if detected == expected_type:
            print(f"✅ '{input_text}' → {detected.value}")
            passed += 1
        else:
            print(f"❌ '{input_text}' → {detected.value} (expected {expected_type.value})")
            failed += 1

    print(f"\nPassed: {passed}/{len(tests)}")
    return failed == 0


def test_channel_parsing():
    """Test channel parsing."""
    print("\nTesting channel parsing...")

    from cli.staging import parse_channels

    tests = [
        ("email", ["email"]),
        ("email,sms", ["email", "sms"]),
        ("email,sms,linkedin", ["email", "sms", "linkedin"]),
        ("all", ["email", "sms", "linkedin", "call"]),
        ("", []),
    ]

    passed = 0
    failed = 0

    for input_str, expected in tests:
        result = parse_channels(input_str)
        if result == expected:
            print(f"✅ '{input_str}' → {result}")
            passed += 1
        else:
            print(f"❌ '{input_str}' → {result} (expected {expected})")
            failed += 1

    print(f"\nPassed: {passed}/{len(tests)}")
    return failed == 0


def test_input_parsing():
    """Test input parsing."""
    print("\nTesting input parsing...")

    from cli.enrich import parse_input, InputType

    tests = [
        (
            "https://acme-hvac.com",
            InputType.URL,
            {"domain": "acme-hvac.com"}
        ),
        (
            "https://www.example.com/page",
            InputType.URL,
            {"domain": "example.com"}
        ),
        (
            "lead_abc123",
            InputType.CLOSE_ID,
            {"close_lead_id": "lead_abc123"}
        ),
        (
            "John Smith, Acme HVAC",
            InputType.PERSON,
            {"person_name": "John Smith", "company_name": "Acme HVAC"}
        ),
        (
            "Acme HVAC Corporation",
            InputType.NAME,
            {"company_name": "Acme HVAC Corporation"}
        ),
    ]

    passed = 0
    failed = 0

    for input_text, input_type, expected_fields in tests:
        result = parse_input(input_text, input_type)

        # Check expected fields
        all_match = True
        for key, expected_value in expected_fields.items():
            if result.get(key) != expected_value:
                all_match = False
                print(f"❌ '{input_text}' field '{key}': got '{result.get(key)}', expected '{expected_value}'")

        if all_match:
            print(f"✅ '{input_text}' parsed correctly")
            passed += 1
        else:
            failed += 1

    print(f"\nPassed: {passed}/{len(tests)}")
    return failed == 0


def main():
    """Run all tests."""
    print("=" * 60)
    print("CLI Module Validation Tests")
    print("=" * 60)

    tests = [
        test_imports,
        test_input_detection,
        test_channel_parsing,
        test_input_parsing,
    ]

    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"\n❌ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)

        print("\n" + "-" * 60)

    # Summary
    passed = sum(results)
    total = len(results)

    print("\n" + "=" * 60)
    print(f"SUMMARY: {passed}/{total} test suites passed")
    print("=" * 60)

    if passed == total:
        print("\n✅ All tests passed! CLI module is ready to use.")
        return 0
    else:
        print(f"\n❌ {total - passed} test suite(s) failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
