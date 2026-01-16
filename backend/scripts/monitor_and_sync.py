#!/usr/bin/env python3
"""
Monitor webhooks and sync phone data to dim_contacts.
Run this after webhooks have had time to arrive (2+ hours).
"""
import httpx
import os
import json
from datetime import datetime, timezone
from pathlib import Path

# Load env
env_file = Path('/Users/tmk/tk_projects/sales-agent/backend/.env')
for line in env_file.read_text().splitlines():
    if '=' in line and not line.startswith('#'):
        key, val = line.split('=', 1)
        os.environ[key.strip()] = val.strip()

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_KEY')
APOLLO_API_KEY = os.environ.get('APOLLO_API_KEY')

headers = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json'
}

def fetch_all(table, params=None):
    all_data = []
    offset = 0
    limit = 1000
    while True:
        p = {'select': '*', 'limit': str(limit), 'offset': str(offset)}
        if params:
            p.update(params)
        response = httpx.get(f'{SUPABASE_URL}/rest/v1/{table}', params=p, headers=headers, timeout=60.0)
        batch = response.json()
        if not batch:
            break
        all_data.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return all_data

def main():
    print("="*70)
    print(f"PHONE SYNC & AUDIT - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*70)
    
    # Get phone reveals
    reveals = fetch_all('fact_enrichments', {'method': 'eq.apollo_phone_reveal'})
    print(f"Phone reveals in fact_enrichments: {len(reveals)}")
    
    # Extract unique phones
    phone_data = {}
    for r in reveals:
        try:
            data = json.loads(r['error_message'])
            apollo_id = data.get('apollo_person_id')
            phone = data.get('best_phone')
            if apollo_id and phone:
                phone_data[apollo_id] = phone
        except:
            continue
    
    print(f"Unique Apollo IDs with phones: {len(phone_data)}")
    
    # Get contacts
    contacts = fetch_all('dim_contacts', {'email': 'not.is.null'})
    email_to_contact = {c['email'].lower(): c for c in contacts if c.get('email')}
    print(f"Contacts with email: {len(email_to_contact)}")
    
    # Sync phones
    synced = 0
    already_had = 0
    
    for apollo_id, phone in list(phone_data.items()):
        try:
            response = httpx.get(
                f'https://api.apollo.io/api/v1/people/{apollo_id}',
                headers={'x-api-key': APOLLO_API_KEY},
                timeout=10.0
            )
            
            if response.status_code == 200:
                person = response.json().get('person', {})
                email = person.get('email', '').lower()
                
                if email and email in email_to_contact:
                    contact = email_to_contact[email]
                    
                    if contact.get('phone'):
                        already_had += 1
                        continue
                    
                    update_response = httpx.patch(
                        f'{SUPABASE_URL}/rest/v1/dim_contacts',
                        params={'contact_id': f"eq.{contact['contact_id']}"},
                        json={
                            'phone': phone,
                            'phone_verified': True,
                            'updated_at': datetime.now(timezone.utc).isoformat()
                        },
                        headers={**headers, 'Prefer': 'return=representation'},
                        timeout=10.0
                    )
                    
                    if update_response.status_code == 200:
                        synced += 1
                        if synced <= 50:
                            print(f"✓ {contact['first_name']} {contact['last_name']}: {phone}")
        except:
            continue
    
    print(f"\n{'='*70}")
    print(f"SYNC COMPLETE")
    print(f"{'='*70}")
    print(f"New phones synced: {synced}")
    print(f"Already had phone: {already_had}")
    
    # Final counts
    response = httpx.get(
        f'{SUPABASE_URL}/rest/v1/dim_contacts',
        params={'select': 'count', 'is_atl': 'eq.true', 'phone': 'not.is.null', 'email': 'not.is.null'},
        headers={**headers, 'Prefer': 'count=exact'},
        timeout=30.0
    )
    total_ready = response.headers.get('content-range', '0').split('/')[-1]
    print(f"\nTotal ATLs ready (email+phone): {total_ready}")

if __name__ == '__main__':
    main()
