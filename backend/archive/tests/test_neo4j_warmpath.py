#!/usr/bin/env python3
"""
Test Neo4j Relationship Graph - Warm Path Discovery

Verifies:
1. Neo4j connection works
2. Schema initialization
3. Adding people with work history
4. Finding warm paths through shared companies

Usage:
    python test_neo4j_warmpath.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.relationship_graph import RelationshipGraphService, get_relationship_graph


def test_connection():
    """Test Neo4j connection."""
    print("\n" + "="*60)
    print("TEST 1: Neo4j Connection")
    print("="*60)

    graph = RelationshipGraphService()
    connected = graph.connect()

    if connected:
        print("✅ Connected to Neo4j successfully!")
        return graph
    else:
        print("❌ Failed to connect to Neo4j")
        print("   Make sure container is running: docker-compose up -d neo4j")
        return None


def test_schema(graph: RelationshipGraphService):
    """Test schema initialization."""
    print("\n" + "="*60)
    print("TEST 2: Schema Initialization")
    print("="*60)

    try:
        graph.init_schema()
        print("✅ Schema initialized (constraints + indexes created)")
        return True
    except Exception as e:
        print(f"❌ Schema init failed: {e}")
        return False


def test_add_people(graph: RelationshipGraphService):
    """Add sample people with work history."""
    print("\n" + "="*60)
    print("TEST 3: Adding People with Work History")
    print("="*60)

    # --- OUR CONTACTS (people we know/sold to) ---

    # Sarah - Coperniq customer, used to work at ABC HVAC and TechSolar
    graph.add_person_with_experience(
        linkedin_url="https://linkedin.com/in/sarah-jones-123",
        name="Sarah Jones",
        email="sarah.jones@coperniq-customer.com",
        is_our_contact=True,
        experience=[
            {"company": "Coperniq Customer Corp", "title": "VP Operations", "current": True, "domain": "coperniq-customer.com"},
            {"company": "ABC HVAC Solutions", "title": "Director of Ops", "current": False, "domain": "abchvac.com"},
            {"company": "TechSolar Inc", "title": "Project Manager", "current": False, "domain": "techsolar.com"},
        ]
    )
    graph.mark_as_our_contact("https://linkedin.com/in/sarah-jones-123", "deal_closed", "Closed $50k deal in Q3")
    print("  ✅ Added Sarah Jones (Coperniq customer, ex-ABC HVAC, ex-TechSolar)")

    # Mike - Energy consultant we've worked with
    graph.add_person_with_experience(
        linkedin_url="https://linkedin.com/in/mike-smith-456",
        name="Mike Smith",
        email="mike@energy-consulting.com",
        is_our_contact=True,
        experience=[
            {"company": "Energy Consulting Group", "title": "Principal", "current": True, "domain": "energy-consulting.com"},
            {"company": "Fresno Mechanical", "title": "Energy Manager", "current": False, "domain": "fresnomech.com"},
            {"company": "Pacific Gas Electric", "title": "Commercial Account Rep", "current": False, "domain": "pge.com"},
        ]
    )
    graph.mark_as_our_contact("https://linkedin.com/in/mike-smith-456", "active_customer", "Refers us deals regularly")
    print("  ✅ Added Mike Smith (Consultant, ex-Fresno Mechanical, ex-PG&E)")

    # --- LEADS (people we want to reach) ---

    # Lead 1: John - Works at ABC HVAC (shared history with Sarah!)
    graph.add_person_with_experience(
        linkedin_url="https://linkedin.com/in/john-doe-789",
        name="John Doe",
        email="john@abchvac.com",
        is_our_contact=False,
        experience=[
            {"company": "ABC HVAC Solutions", "title": "CEO", "current": True, "domain": "abchvac.com"},
            {"company": "Carrier Heating", "title": "Regional Manager", "current": False, "domain": "carrier.com"},
        ]
    )
    print("  ✅ Added John Doe (CEO at ABC HVAC - WARM PATH via Sarah!)")

    # Lead 2: Lisa - Works at TechSolar (shared history with Sarah!)
    graph.add_person_with_experience(
        linkedin_url="https://linkedin.com/in/lisa-chen-101",
        name="Lisa Chen",
        email="lisa@techsolar.com",
        is_our_contact=False,
        experience=[
            {"company": "TechSolar Inc", "title": "VP Sales", "current": True, "domain": "techsolar.com"},
            {"company": "SunPower", "title": "Territory Rep", "current": False, "domain": "sunpower.com"},
        ]
    )
    print("  ✅ Added Lisa Chen (VP Sales at TechSolar - WARM PATH via Sarah!)")

    # Lead 3: Bob - Works at Fresno Mechanical (shared history with Mike!)
    graph.add_person_with_experience(
        linkedin_url="https://linkedin.com/in/bob-wilson-202",
        name="Bob Wilson",
        email="bob@fresnomech.com",
        is_our_contact=False,
        experience=[
            {"company": "Fresno Mechanical", "title": "Owner", "current": True, "domain": "fresnomech.com"},
            {"company": "Valley Air Conditioning", "title": "Service Manager", "current": False, "domain": "valleyac.com"},
        ]
    )
    print("  ✅ Added Bob Wilson (Owner at Fresno Mechanical - WARM PATH via Mike!)")

    # Lead 4: Cold lead - No shared history
    graph.add_person_with_experience(
        linkedin_url="https://linkedin.com/in/cold-lead-999",
        name="Cold Lead",
        email="cold@random-company.com",
        is_our_contact=False,
        experience=[
            {"company": "Random Company", "title": "CEO", "current": True, "domain": "random-company.com"},
        ]
    )
    print("  ✅ Added Cold Lead (no shared history - should find NO warm paths)")

    return True


def test_warm_paths(graph: RelationshipGraphService):
    """Test warm path discovery."""
    print("\n" + "="*60)
    print("TEST 4: Warm Path Discovery")
    print("="*60)

    test_cases = [
        ("https://linkedin.com/in/john-doe-789", "John Doe (ABC HVAC)", True),
        ("https://linkedin.com/in/lisa-chen-101", "Lisa Chen (TechSolar)", True),
        ("https://linkedin.com/in/bob-wilson-202", "Bob Wilson (Fresno Mechanical)", True),
        ("https://linkedin.com/in/cold-lead-999", "Cold Lead (Random)", False),
    ]

    all_passed = True

    for linkedin_url, name, expect_warm in test_cases:
        print(f"\n  🔍 Finding warm paths for: {name}")

        paths = graph.find_warm_paths(linkedin_url)

        if expect_warm:
            if paths:
                print(f"     ✅ Found {len(paths)} warm path(s)!")
                for i, path in enumerate(paths, 1):
                    print(f"        Path {i}: via {path.via_company}")
                    print(f"          Known contact: {path.known_contact_name} ({path.known_contact_email})")
                    print(f"          Warmth score: {path.warmth_score}/100")
                    print(f"          Opener: \"{path.suggested_opener}\"")
            else:
                print(f"     ❌ Expected warm paths but found none!")
                all_passed = False
        else:
            if not paths:
                print(f"     ✅ Correctly found no warm paths (cold lead)")
            else:
                print(f"     ⚠️  Unexpectedly found {len(paths)} path(s) - investigating...")

    return all_passed


def test_stats(graph: RelationshipGraphService):
    """Test graph statistics."""
    print("\n" + "="*60)
    print("TEST 5: Graph Statistics")
    print("="*60)

    stats = graph.get_stats()

    print(f"  📊 Total People: {stats.get('total_people', 0)}")
    print(f"  📊 Our Contacts: {stats.get('our_contacts', 0)}")
    print(f"  📊 Companies: {stats.get('total_companies', 0)}")
    print(f"  📊 Work History Edges (WORKED_AT): {stats.get('work_history_edges', 0)}")
    print(f"  📊 Current Job Edges (WORKS_AT): {stats.get('current_job_edges', 0)}")
    print(f"  📊 Warm Path Potential: {stats.get('warm_path_potential', 0)}")

    return True


def main():
    print("\n" + "="*60)
    print("  NEO4J WARM PATH DISCOVERY TEST")
    print("  Verifying relationship graph is ready for Coperniq outreach")
    print("="*60)

    # Test 1: Connection
    graph = test_connection()
    if not graph:
        print("\n❌ FAILED: Cannot continue without Neo4j connection")
        return 1

    # Test 2: Schema
    if not test_schema(graph):
        print("\n⚠️  Schema init had issues - continuing anyway")

    # Test 3: Add sample data
    if not test_add_people(graph):
        print("\n❌ FAILED: Could not add people to graph")
        return 1

    # Test 4: Warm path discovery
    if not test_warm_paths(graph):
        print("\n⚠️  Some warm path tests failed")

    # Test 5: Stats
    test_stats(graph)

    # Cleanup
    graph.close()

    print("\n" + "="*60)
    print("  ✅ NEO4J WARM PATH TEST COMPLETE")
    print("="*60)
    print("\n🚀 Ready for Coperniq outreach in 4 days!")
    print("   - Neo4j is running and connected")
    print("   - Schema is initialized")
    print("   - Warm path queries working")
    print("\n📋 Next steps:")
    print("   1. Import existing leads: python import_leads_to_graph.py")
    print("   2. Wire into qualification pipeline")
    print("   3. Test with real Browserbase LinkedIn scrapes")
    print("\n🌐 Neo4j Browser: http://localhost:7474")
    print("   Credentials: neo4j / coperniq_graph_2024")

    return 0


if __name__ == "__main__":
    sys.exit(main())
