#!/usr/bin/env python3
"""
Test script for Personalized Outreach Campaigns System

Tests all components of Task 4:
- Campaign creation
- Message generation with 3 variants
- Channel-specific formatting
- A/B testing framework
- Analytics and performance tracking
"""
import asyncio
import httpx
import json
from datetime import datetime
from typing import Dict, Any


BASE_URL = "http://localhost:8001"
API_PREFIX = "/api/v1"


class CampaignTester:
    """Test suite for campaign system"""

    def __init__(self):
        self.client = httpx.AsyncClient(base_url=BASE_URL, timeout=30.0)
        self.campaign_id = None
        self.message_ids = []

    async def test_create_campaign(self):
        """Test 4.1: Create campaign with configuration"""
        print("\n" + "="*80)
        print("TEST 1: Create Campaign")
        print("="*80)

        payload = {
            "name": f"Test Campaign {datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "channel": "email",
            "description": "Automated test campaign for outreach system",
            "target_audience": {
                "industry": "Software",
                "company_size": "50-200 employees"
            },
            "min_qualification_score": 70.0
        }

        response = await self.client.post(f"{API_PREFIX}/campaigns/create", json=payload)

        if response.status_code == 201:
            data = response.json()
            self.campaign_id = data["id"]
            print(f"✅ Campaign created successfully!")
            print(f"   - ID: {data['id']}")
            print(f"   - Name: {data['name']}")
            print(f"   - Channel: {data['channel']}")
            print(f"   - Status: {data['status']}")
            return True
        else:
            print(f"❌ Campaign creation failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    async def test_generate_messages(self):
        """Test 4.2-4.4: Generate messages with 3 variants"""
        print("\n" + "="*80)
        print("TEST 2: Generate Message Variants")
        print("="*80)

        if not self.campaign_id:
            print("❌ Skipping: No campaign created")
            return False

        # First, check if we have any leads
        leads_response = await self.client.get(f"{API_PREFIX}/leads/")
        leads = leads_response.json()

        if not leads or len(leads) == 0:
            print("❌ No leads available for message generation")
            print("   Creating test lead first...")

            # Create a test lead
            test_lead = {
                "company_name": "Test Corp",
                "company_website": "https://testcorp.com",
                "company_size": "100-200 employees",
                "industry": "Software",
                "contact_name": "John Doe",
                "contact_email": "john@testcorp.com",
                "contact_title": "VP of Sales",
                "notes": "High-value prospect for AI sales automation"
            }

            lead_response = await self.client.post(f"{API_PREFIX}/leads/qualify", json=test_lead)
            if lead_response.status_code == 201:
                lead = lead_response.json()
                lead_ids = [lead["id"]]
                print(f"✅ Test lead created (ID: {lead['id']})")
            else:
                print(f"❌ Failed to create test lead: {lead_response.status_code}")
                return False
        else:
            # Use first 3 leads
            lead_ids = [lead["id"] for lead in leads[:3]]
            print(f"   Using {len(lead_ids)} existing leads")

        # Generate messages
        payload = {
            "lead_ids": lead_ids,
            "custom_context": "Mention our ultra-fast AI inference and cost savings"
        }

        response = await self.client.post(
            f"{API_PREFIX}/campaigns/{self.campaign_id}/generate-messages",
            json=payload
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Messages generated successfully!")
            print(f"   - Messages: {data['messages_generated']}")
            print(f"   - Total cost: ${data['total_cost_usd']:.6f}")
            print(f"   - Avg latency: {data['average_latency_ms']}ms")

            # Store message IDs for later tests
            self.message_ids = [msg["id"] for msg in data["messages"]]

            # Display first message variants
            if data["messages"]:
                first_msg = data["messages"][0]
                print(f"\n   Message ID {first_msg['id']} Variants:")
                for i, variant in enumerate(first_msg["variants"]):
                    print(f"\n   Variant {i} ({variant['tone']}):")
                    if variant.get("subject"):
                        print(f"      Subject: {variant['subject'][:60]}...")
                    print(f"      Body: {variant['body'][:150]}...")

            return True
        else:
            print(f"❌ Message generation failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    async def test_list_messages(self):
        """Test listing campaign messages"""
        print("\n" + "="*80)
        print("TEST 3: List Campaign Messages")
        print("="*80)

        if not self.campaign_id:
            print("❌ Skipping: No campaign created")
            return False

        response = await self.client.get(
            f"{API_PREFIX}/campaigns/{self.campaign_id}/messages?limit=10"
        )

        if response.status_code == 200:
            messages = response.json()
            print(f"✅ Listed {len(messages)} messages")
            for msg in messages[:3]:
                print(f"   - Message {msg['id']}: Lead {msg['lead_id']}, Status: {msg['status']}")
            return True
        else:
            print(f"❌ Failed to list messages: {response.status_code}")
            return False

    async def test_get_message_variants(self):
        """Test 4.2: Get all 3 variants for a message"""
        print("\n" + "="*80)
        print("TEST 4: Get Message Variants")
        print("="*80)

        if not self.message_ids:
            print("❌ Skipping: No messages generated")
            return False

        message_id = self.message_ids[0]
        response = await self.client.get(f"{API_PREFIX}/messages/{message_id}/variants")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Retrieved variants for message {message_id}")
            print(f"   - Selected variant: {data['selected_variant']}")
            print(f"   - Total variants: {len(data['variants'])}")

            for i, variant in enumerate(data['variants']):
                print(f"\n   Variant {i} ({variant['tone']}):")
                if variant.get('subject'):
                    print(f"      Subject: {variant['subject']}")
                print(f"      Body preview: {variant['body'][:100]}...")

            return True
        else:
            print(f"❌ Failed to get variants: {response.status_code}")
            return False

    async def test_update_message_status(self):
        """Test 4.5: Update message status for A/B testing tracking"""
        print("\n" + "="*80)
        print("TEST 5: Update Message Status (A/B Testing)")
        print("="*80)

        if not self.message_ids:
            print("❌ Skipping: No messages generated")
            return False

        # Simulate message lifecycle: sent -> delivered -> opened -> clicked -> replied
        statuses = ["sent", "delivered", "opened", "clicked", "replied"]
        message_id = self.message_ids[0]

        for status in statuses:
            payload = {
                "status": status,
                "channel_data": {
                    "email_id": f"msg_{message_id}_{status}",
                    "provider": "test_provider"
                }
            }

            response = await self.client.put(
                f"{API_PREFIX}/messages/{message_id}/status",
                json=payload
            )

            if response.status_code == 200:
                print(f"   ✅ Updated to '{status}'")
            else:
                print(f"   ❌ Failed to update to '{status}': {response.status_code}")
                return False

        print(f"✅ Message lifecycle simulation complete")
        return True

    async def test_campaign_analytics(self):
        """Test 4.5: Get campaign analytics with A/B test results"""
        print("\n" + "="*80)
        print("TEST 6: Campaign Analytics & A/B Testing")
        print("="*80)

        if not self.campaign_id:
            print("❌ Skipping: No campaign created")
            return False

        response = await self.client.get(f"{API_PREFIX}/campaigns/{self.campaign_id}/analytics")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Analytics retrieved successfully!")
            print(f"\n   Campaign: {data['name']}")
            print(f"   Status: {data['status']}")
            print(f"   Channel: {data['channel']}")

            perf = data['performance']
            print(f"\n   Performance Metrics:")
            print(f"      Total Messages: {perf['total_messages']}")
            print(f"      Sent: {perf['sent']}")
            print(f"      Delivered: {perf['delivered']}")
            print(f"      Opened: {perf['opened']}")
            print(f"      Clicked: {perf['clicked']}")
            print(f"      Replied: {perf['replied']}")
            print(f"      Open Rate: {perf['open_rate']}%")
            print(f"      Click Rate: {perf['click_rate']}%")
            print(f"      Reply Rate: {perf['reply_rate']}%")

            cost = data['cost']
            print(f"\n   Cost Analysis:")
            print(f"      Total: ${cost['total_usd']:.6f}")
            print(f"      Per Message: ${cost['cost_per_message']:.6f}")
            if cost['cost_per_reply'] > 0:
                print(f"      Per Reply: ${cost['cost_per_reply']:.6f}")

            ab = data['ab_testing']
            print(f"\n   A/B Testing Results:")
            print(f"      Winning Variant: {ab['winning_variant']}")
            for variant in ab['variants']:
                print(f"\n      Variant {variant['variant_number']} ({variant['tone']}):")
                print(f"         Sent: {variant['sent']}")
                print(f"         Open Rate: {variant['open_rate']}%")
                print(f"         Click Rate: {variant['click_rate']}%")
                print(f"         Reply Rate: {variant['reply_rate']}%")

            return True
        else:
            print(f"❌ Failed to get analytics: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    async def test_send_campaign(self):
        """Test campaign activation"""
        print("\n" + "="*80)
        print("TEST 7: Send Campaign (Activation)")
        print("="*80)

        if not self.campaign_id:
            print("❌ Skipping: No campaign created")
            return False

        response = await self.client.post(f"{API_PREFIX}/campaigns/{self.campaign_id}/send")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Campaign activated!")
            print(f"   - Status: {data['campaign_status']}")
            print(f"   - Total Messages: {data['total_messages']}")
            print(f"   - Note: {data['note']}")
            return True
        else:
            print(f"❌ Campaign activation failed: {response.status_code}")
            return False

    async def run_all_tests(self):
        """Run complete test suite"""
        print("\n" + "="*80)
        print("PERSONALIZED OUTREACH CAMPAIGNS - TEST SUITE")
        print("="*80)
        print(f"Testing against: {BASE_URL}")
        print(f"Timestamp: {datetime.now().isoformat()}")

        results = {
            "Create Campaign": await self.test_create_campaign(),
            "Generate Messages": await self.test_generate_messages(),
            "List Messages": await self.test_list_messages(),
            "Get Variants": await self.test_get_message_variants(),
            "Update Status": await self.test_update_message_status(),
            "Analytics": await self.test_campaign_analytics(),
            "Send Campaign": await self.test_send_campaign()
        }

        # Summary
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)

        passed = sum(1 for v in results.values() if v)
        total = len(results)

        for test_name, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status} - {test_name}")

        print(f"\nTotal: {passed}/{total} tests passed")
        print(f"Success Rate: {(passed/total)*100:.1f}%")

        if passed == total:
            print("\n🎉 All tests passed! Campaign system is fully functional.")
        else:
            print(f"\n⚠️  {total - passed} test(s) failed. Check logs above.")

        await self.client.aclose()

        return passed == total


async def main():
    """Main test runner"""
    tester = CampaignTester()
    success = await tester.run_all_tests()
    exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
