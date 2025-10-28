#!/usr/bin/env python3
"""
COMPREHENSIVE endpoint testing - Tests EVERYTHING
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from extensions import db
from app.models.user import User
import json

def test_endpoint(client, endpoint, method='GET', data=None, user=None, expected_status=None, description=""):
    """Test a single endpoint"""
    if user:
        with client.session_transaction() as sess:
            sess['user_id'] = user.id
            sess['logged_in'] = True

    try:
        if method == 'GET':
            response = client.get(endpoint)
        elif method == 'POST':
            response = client.post(endpoint, json=data)

        status = response.status_code

        # Check if response is JSON
        try:
            json_data = response.get_json()
        except:
            json_data = None

        success = status == expected_status if expected_status else status < 400

        return {
            'endpoint': endpoint,
            'method': method,
            'status': status,
            'success': success,
            'description': description,
            'error': None if success else f"Expected {expected_status}, got {status}",
            'data': json_data
        }
    except Exception as e:
        return {
            'endpoint': endpoint,
            'method': method,
            'status': None,
            'success': False,
            'description': description,
            'error': str(e),
            'data': None
        }

def main():
    app = create_app()

    with app.app_context():
        # Get users
        admin_user = User.query.filter_by(email='ethan@hackclub.com').first()
        regular_user = User.query.filter(User.email != 'ethan@hackclub.com').first()

        if not admin_user:
            print("ERROR: Admin user not found")
            return

        if not regular_user:
            print("ERROR: No regular users found")
            return

        print("="*100)
        print("COMPREHENSIVE ENDPOINT TESTING - TESTING EVERYTHING")
        print("="*100)
        print(f"Admin: {admin_user.username} ({admin_user.email})")
        print(f"Regular: {regular_user.username} ({regular_user.email})")
        print("="*100)

        client = app.test_client()
        results = []

        # TEST CATEGORIES
        test_suites = {
            "PUBLIC ROUTES": [
                ('/', 'GET', None, None, None, "Homepage"),
                ('/login', 'GET', None, None, 200, "Login page"),
                ('/signup', 'GET', None, None, 200, "Signup page"),
            ],

            "AUTHENTICATED USER ROUTES": [
                ('/dashboard', 'GET', None, regular_user, 200, "User dashboard"),
                ('/gallery', 'GET', None, regular_user, 200, "Gallery"),
                ('/leaderboard', 'GET', None, regular_user, 200, "Leaderboard"),
            ],

            "ADMIN DASHBOARD ROUTES": [
                ('/admin/dashboard', 'GET', None, admin_user, 200, "Admin dashboard"),
                ('/admin/users', 'GET', None, admin_user, 200, "Admin users page"),
            ],

            "ADMIN API - USERS": [
                ('/api/admin/users?page=1&per_page=10', 'GET', None, admin_user, 200, "Get users list"),
                ('/api/admin/users?page=1&per_page=10&sort=created_at-desc', 'GET', None, admin_user, 200, "Get users sorted"),
                ('/api/admin/users?page=2&per_page=10', 'GET', None, admin_user, 200, "Get users page 2"),
            ],

            "ADMIN API - CLUBS": [
                ('/api/admin/clubs?page=1&per_page=10', 'GET', None, admin_user, 200, "Get clubs list"),
                ('/api/admin/clubs?page=1&per_page=20', 'GET', None, admin_user, 200, "Get clubs with different page size"),
            ],

            "ADMIN API - RBAC": [
                ('/api/admin/rbac/roles', 'GET', None, admin_user, 200, "Get all roles"),
                ('/api/admin/rbac/permissions', 'GET', None, admin_user, 200, "Get all permissions"),
            ],

            "ADMIN API - API KEYS & OAUTH": [
                ('/api/admin/apikeys', 'GET', None, admin_user, 200, "Get API keys"),
                ('/api/admin/oauthapps', 'GET', None, admin_user, 200, "Get OAuth apps"),
            ],

            "ADMIN API - AUDIT & ACTIVITY": [
                ('/api/admin/audit-logs?page=1&per_page=50', 'GET', None, admin_user, 200, "Get audit logs"),
                ('/api/admin/audit-logs?page=1&per_page=50&sort=desc', 'GET', None, admin_user, 200, "Get audit logs sorted"),
                ('/api/admin/activity?page=1&per_page=50', 'GET', None, admin_user, 200, "Get activity"),
            ],

            "ADMIN API - SETTINGS & STATS": [
                ('/api/admin/settings', 'GET', None, admin_user, 200, "Get system settings"),
                ('/api/admin/stats', 'GET', None, admin_user, 200, "Get system stats"),
            ],

            "USER API ENDPOINTS (OAuth - Expected to fail without token)": [
                ('/api/user/clubs', 'GET', None, regular_user, 401, "Get user's clubs (OAuth required)"),
            ],

            "ADMIN PERMISSION CHECKS (Regular User Should Fail)": [
                ('/admin/dashboard', 'GET', None, regular_user, 302, "Regular user blocked from admin"),
                ('/api/admin/users', 'GET', None, regular_user, 302, "Regular user blocked from users API"),
                ('/api/admin/clubs', 'GET', None, regular_user, 302, "Regular user blocked from clubs API"),
            ],
        }

        total_tests = sum(len(tests) for tests in test_suites.values())
        test_num = 0

        for suite_name, tests in test_suites.items():
            print(f"\n{'='*100}")
            print(f"{suite_name}")
            print('='*100)

            for test_case in tests:
                test_num += 1
                endpoint, method, data, user, expected, description = test_case

                print(f"\n[{test_num}/{total_tests}] {description}")
                print(f"  Endpoint: {method} {endpoint}")

                result = test_endpoint(client, endpoint, method, data, user, expected, description)
                results.append(result)

                if result['success']:
                    print(f"  ✅ SUCCESS - Status {result['status']}")
                    # Show data summary if available
                    if result['data']:
                        if isinstance(result['data'], dict):
                            keys = list(result['data'].keys())
                            print(f"  📦 Response keys: {keys}")
                            # Show counts for list responses
                            for key in ['users', 'clubs', 'roles', 'permissions', 'logs']:
                                if key in result['data']:
                                    if isinstance(result['data'][key], list):
                                        print(f"  📊 {key}: {len(result['data'][key])} items")
                                    elif isinstance(result['data'][key], dict):
                                        print(f"  📊 {key}: {len(result['data'][key])} categories")
                else:
                    print(f"  ❌ FAILED - Status {result['status']}")
                    print(f"  💥 Error: {result['error']}")
                    if result['data'] and 'error' in result['data']:
                        print(f"  💬 Message: {result['data']['error']}")

        # SUMMARY
        print("\n" + "="*100)
        print("FINAL SUMMARY")
        print("="*100)

        passed = sum(1 for r in results if r['success'])
        failed = total_tests - passed

        print(f"\nTotal Tests: {total_tests}")
        print(f"✅ Passed: {passed} ({passed/total_tests*100:.1f}%)")
        print(f"❌ Failed: {failed} ({failed/total_tests*100:.1f}%)")

        if failed > 0:
            print("\n" + "="*100)
            print("FAILED TESTS DETAILS")
            print("="*100)
            for result in results:
                if not result['success']:
                    print(f"\n❌ {result['description']}")
                    print(f"   {result['method']} {result['endpoint']}")
                    print(f"   Status: {result['status']}")
                    print(f"   Error: {result['error']}")
                    if result['data']:
                        print(f"   Response: {json.dumps(result['data'], indent=2)}")

        print("\n" + "="*100)
        if failed == 0:
            print("🎉 ALL TESTS PASSED! EVERYTHING IS WORKING!")
        else:
            print(f"⚠️  {failed} TESTS FAILED - SEE DETAILS ABOVE")
        print("="*100)

if __name__ == '__main__':
    main()
