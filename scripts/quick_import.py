#!/usr/bin/env python3
"""
Quick Start Script - Import CSV and start server if needed

This script will:
1. Check if server is running
2. Start server if needed (optional)
3. Import the CSV file
4. Verify import
"""
import subprocess
import time
import requests
import sys
from pathlib import Path

def check_server():
    """Check if server is running"""
    try:
        response = requests.get("http://localhost:8001/api/health", timeout=2)
        return response.status_code == 200
    except:
        return False

def start_server():
    """Start the server in background"""
    print("🚀 Starting FastAPI server...")
    script_path = Path(__file__).parent.parent / "start_server.py"
    subprocess.Popen([sys.executable, str(script_path)], 
                     stdout=subprocess.DEVNULL, 
                     stderr=subprocess.DEVNULL)
    print("   Waiting for server to start...")
    
    # Wait up to 30 seconds for server to start
    for i in range(30):
        if check_server():
            print("   ✅ Server is running!")
            return True
        time.sleep(1)
    
    print("   ⚠️  Server may not have started. Check manually:")
    print("   python3 start_server.py")
    return False

def import_csv(file_path):
    """Import CSV file"""
    from scripts.import_csv import import_csv as do_import
    return do_import(file_path)

if __name__ == "__main__":
    csv_file = Path("companies_ready_to_import.csv")
    
    if not csv_file.exists():
        print(f"❌ CSV file not found: {csv_file}")
        print("   Run: python3 scripts/transform_dealer_csv.py")
        sys.exit(1)
    
    # Check server
    if not check_server():
        print("⚠️  Server is not running")
        response = input("   Start server automatically? (y/n): ").strip().lower()
        if response == 'y':
            if not start_server():
                print("\n❌ Could not start server. Please start manually:")
                print("   python3 start_server.py")
                sys.exit(1)
        else:
            print("\n⚠️  Please start the server manually:")
            print("   python3 start_server.py")
            print("\nThen run this script again to import.")
            sys.exit(1)
    
    # Import CSV
    print(f"\n📤 Importing {csv_file}...")
    success = import_csv(str(csv_file))
    
    if success:
        print("\n✅ Import complete! Check results above.")
        print("\nNext steps:")
        print("  1. View leads: curl http://localhost:8001/api/leads/")
        print("  2. Test agents: python3 agent_cli.py")
        print("  3. Enrich contacts: python3 scripts/batch_enrich_companies.py")
    else:
        sys.exit(1)

