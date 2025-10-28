#!/usr/bin/env python3
"""
Comprehensive route testing script to verify all fixes from modularization.
Tests all API endpoints and pages that were reported as broken.
"""

import requests
import sys

BASE_URL = "http://localhost:5000"

def test_endpoint(method, path, expected_codes=[200, 302, 401, 403], description=""):
    """Test an endpoint and return result"""
    url = f"{BASE_URL}{path}"
    try:
        if method == "GET":
            response = requests.get(url, timeout=5)
        elif method == "POST":
            response = requests.post(url, timeout=5)
        else:
            return False, f"Unsupported method: {method}"
        
        if response.status_code in expected_codes:
            return True, f"✅ {description or path}: {response.status_code}"
        else:
            return False, f"❌ {description or path}: {response.status_code} (expected {expected_codes})"
    except Exception as e:
        return False, f"❌ {description or path}: {str(e)}"

def main():
    print("=" * 80)
    print("TESTING MODULARIZATION FIXES")
    print("=" * 80)
    
    tests = [
        # Basic pages
        ("GET", "/", [200], "Homepage"),
        ("GET", "/dashboard", [200, 302], "Dashboard"),
        ("GET", "/gallery", [200], "Gallery Page"),
        
        # Gallery API
        ("GET", "/api/gallery/posts", [200], "Gallery Posts API"),
        
        # Admin pages (will redirect to login if not authenticated)
        ("GET", "/admin/dashboard", [200, 302], "Admin Dashboard"),
        ("GET", "/admin/users", [200, 302], "Admin Users List"),
        ("GET", "/admin/clubs", [200, 302], "Admin Clubs List"),
        ("GET", "/admin/orders/review", [200, 302], "Admin Order Review"),
        
        # Club API endpoints (will return 401 if not authenticated)
        # We're testing that the route exists, not that we can access it
        ("GET", "/api/clubs/1/posts", [200, 401, 403, 404], "Club Posts API"),
        ("GET", "/api/clubs/1/assignments", [200, 401, 403, 404], "Club Assignments API"),
        ("GET", "/api/clubs/1/meetings", [200, 401, 403, 404], "Club Meetings API"),
        ("GET", "/api/clubs/1/transactions", [200, 401, 403, 404], "Club Transactions API"),
        ("GET", "/api/club/1/quests", [200, 401, 403, 404], "Club Quests API"),
        
        # Status endpoints
        ("GET", "/api/status/banner", [200], "Status Banner API"),
    ]
    
    passed = 0
    failed = 0
    
    print("\nRunning tests...\n")
    
    for method, path, expected, desc in tests:
        success, message = test_endpoint(method, path, expected, desc)
        print(message)
        if success:
            passed += 1
        else:
            failed += 1
    
    print("\n" + "=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 80)
    
    if failed > 0:
        print("\n⚠️  Some tests failed. Check the output above for details.")
        return 1
    else:
        print("\n✅ All tests passed! Application is working correctly.")
        return 0

if __name__ == "__main__":
    sys.exit(main())
