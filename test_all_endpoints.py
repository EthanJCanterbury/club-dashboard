#!/usr/bin/env python3
"""
Comprehensive endpoint testing script for Hack Club Dashboard.
Tests all major routes and API endpoints to identify broken functionality.
"""

import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from extensions import db
from app.models.user import User
from flask import url_for

def test_endpoint(client, endpoint, method='GET', data=None, auth_user=None, expected_status=None):
    """Test a single endpoint and return results"""
    headers = {}

    # Set up authentication if user provided
    if auth_user:
        with client.session_transaction() as sess:
            sess['user_id'] = auth_user.id
            sess['logged_in'] = True

    try:
        if method == 'GET':
            response = client.get(endpoint, headers=headers)
        elif method == 'POST':
            response = client.post(endpoint, json=data, headers=headers)
        elif method == 'PUT':
            response = client.put(endpoint, json=data, headers=headers)
        elif method == 'DELETE':
            response = client.delete(endpoint, headers=headers)

        status = response.status_code
        success = True if not expected_status else (status == expected_status)

        return {
            'endpoint': endpoint,
            'method': method,
            'status': status,
            'success': success,
            'error': None if success else f"Expected {expected_status}, got {status}",
            'data': response.get_json() if response.is_json else None
        }
    except Exception as e:
        return {
            'endpoint': endpoint,
            'method': method,
            'status': None,
            'success': False,
            'error': str(e),
            'data': None
        }

def main():
    """Run comprehensive endpoint tests"""
    app = create_app()

    with app.app_context():
        # Get test users
        admin_user = User.query.filter_by(email='ethan@hackclub.com').first()
        regular_user = User.query.filter(User.email != 'ethan@hackclub.com').first()

        if not admin_user:
            print("ERROR: Admin user not found")
            return

        if not regular_user:
            print("ERROR: Regular test user not found")
            return

        # Find a club that the regular user belongs to
        from app.models.club import ClubMembership
        membership = ClubMembership.query.filter_by(user_id=regular_user.id).first()
        test_club_id = membership.club_id if membership else 171

        print(f"Testing with admin user: {admin_user.username} ({admin_user.email})")
        print(f"Testing with regular user: {regular_user.username} ({regular_user.email})")
        print(f"Testing with club ID: {test_club_id}")
        print()

        print("=" * 80)
        print("HACK CLUB DASHBOARD - COMPREHENSIVE ENDPOINT TESTING")
        print("=" * 80)
        print()

        client = app.test_client()
        results = []

        # Test categories
        tests = {
            "Public Routes": [
                ('/', 'GET', None, None, 200),
                ('/login', 'GET', None, None, 200),
            ],
            "User Dashboard (Regular User)": [
                ('/dashboard', 'GET', None, regular_user, 200),
            ],
            "Club Routes (Regular User)": [
                (f'/club-dashboard/{test_club_id}', 'GET', None, regular_user, 200),
                (f'/club/{test_club_id}/shop', 'GET', None, regular_user, 200),
            ],
            "Club API Endpoints (Regular User)": [
                (f'/api/clubs/{test_club_id}/posts', 'GET', None, regular_user, 200),
                (f'/api/clubs/{test_club_id}/meetings', 'GET', None, regular_user, 200),
                (f'/api/clubs/{test_club_id}/assignments', 'GET', None, regular_user, 200),
                (f'/api/clubs/{test_club_id}/members', 'GET', None, regular_user, 200),
                (f'/api/clubs/{test_club_id}/transactions', 'GET', None, regular_user, 200),
                (f'/api/club/{test_club_id}/quests', 'GET', None, regular_user, 200),
                (f'/api/club/{test_club_id}/chat/messages', 'GET', None, regular_user, 200),
            ],
            "Admin Routes (Admin User)": [
                ('/admin/dashboard', 'GET', None, admin_user, 200),
                ('/admin/users', 'GET', None, admin_user, 200),
            ],
            "Admin Routes (Regular User - Should Fail)": [
                ('/admin/dashboard', 'GET', None, regular_user, [302, 403]),
                ('/admin/users', 'GET', None, regular_user, [302, 403]),
            ],
        }

        for category, test_cases in tests.items():
            print(f"\n{category}")
            print("-" * 80)

            for test_case in test_cases:
                endpoint, method, data, user, expected = test_case
                result = test_endpoint(client, endpoint, method, data, user, expected)

                # Handle multiple acceptable status codes
                if isinstance(expected, list):
                    result['success'] = result['status'] in expected
                    if not result['success']:
                        result['error'] = f"Expected one of {expected}, got {result['status']}"

                results.append(result)

                status_icon = "✓" if result['success'] else "✗"
                status_color = "\033[92m" if result['success'] else "\033[91m"
                reset_color = "\033[0m"

                print(f"  {status_color}{status_icon}{reset_color} {method:6s} {endpoint:50s} [{result['status']}]")

                if not result['success'] and result['error']:
                    print(f"     Error: {result['error']}")
                if result['data'] and 'error' in result['data']:
                    print(f"     Response: {result['data']['error']}")

        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)

        total = len(results)
        passed = sum(1 for r in results if r['success'])
        failed = total - passed

        print(f"Total Tests: {total}")
        print(f"Passed: \033[92m{passed}\033[0m")
        print(f"Failed: \033[91m{failed}\033[0m")
        print(f"Success Rate: {(passed/total*100):.1f}%")

        if failed > 0:
            print("\n" + "=" * 80)
            print("FAILED TESTS")
            print("=" * 80)
            for result in results:
                if not result['success']:
                    print(f"\n✗ {result['method']} {result['endpoint']}")
                    print(f"  Status: {result['status']}")
                    print(f"  Error: {result['error']}")
                    if result['data'] and 'error' in result['data']:
                        print(f"  Response: {result['data']}")

if __name__ == '__main__':
    main()
