"""
Airtable Service for Pizza Grants and Club Management
"""
import os
import json
import logging
import requests
import urllib.parse
import secrets
import string
from datetime import datetime, timezone

# This will be properly initialized when imported by the app
app = None
db = None
User = None
Club = None
filter_profanity_comprehensive = None


def init_service(flask_app, database, user_model, club_model, profanity_filter):
    """Initialize the service with app context and dependencies"""
    global app, db, User, Club, filter_profanity_comprehensive
    app = flask_app
    db = database
    User = user_model
    Club = club_model
    filter_profanity_comprehensive = profanity_filter


class AirtableService:
    def __init__(self):
        self.api_token = os.environ.get('AIRTABLE_TOKEN')
        self.base_id = os.environ.get('AIRTABLE_BASE_ID', 'appSnnIu0BhjI3E1p')
        self.table_name = os.environ.get('AIRTABLE_TABLE_NAME', 'Grants')
        # New club management base
        self.clubs_base_id = os.environ.get('AIRTABLE_CLUBS_BASE_ID', 'appSUAc40CDu6bDAp')
        self.clubs_table_id = os.environ.get('AIRTABLE_CLUBS_TABLE_ID', 'tbl5saCV1f7ZWjsn0')
        self.clubs_table_name = os.environ.get('AIRTABLE_CLUBS_TABLE_NAME', 'Clubs Dashboard')
        # Email verification table
        self.email_verification_table_name = 'Dashboard Email Verification'
        self.headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json'
        }
        encoded_table_name = urllib.parse.quote(self.table_name)
        self.base_url = f'https://api.airtable.com/v0/{self.base_id}/{encoded_table_name}'

        # Club management URLs - use table ID for direct access
        self.clubs_base_url = f'https://api.airtable.com/v0/{self.clubs_base_id}/{self.clubs_table_id}'
        # Email verification URL
        self.email_verification_url = f'https://api.airtable.com/v0/{self.clubs_base_id}/{urllib.parse.quote(self.email_verification_table_name)}'

    def _validate_airtable_url(self, url):
        """Validate that URL is a legitimate Airtable API URL to prevent SSRF"""
        try:
            parsed = urllib.parse.urlparse(url)
            return (parsed.scheme in ['https'] and
                   parsed.hostname == 'api.airtable.com' and
                   parsed.path.startswith('/v0/'))
        except:
            return False

    def _safe_request(self, method, url, **kwargs):
        """Make a safe HTTP request with URL validation and timeout"""
        if not self._validate_airtable_url(url):
            raise ValueError(f"Invalid Airtable URL: {url}")

        # Add timeout to prevent hanging requests - longer for email operations
        kwargs.setdefault('timeout', 60)

        if method.upper() == 'GET':
            return requests.get(url, **kwargs)
        elif method.upper() == 'POST':
            return requests.post(url, **kwargs)
        elif method.upper() == 'PATCH':
            return requests.patch(url, **kwargs)
        elif method.upper() == 'DELETE':
            return requests.delete(url, **kwargs)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

    def _check_school_variations(self, club_name, venue):
        """Check for common school name variations"""
        # Remove common words that might cause mismatches
        common_words = ['high', 'school', 'college', 'university', 'academy', 'the', 'of', 'at']

        # Extract main words from both names
        club_words = [word for word in club_name.split() if word not in common_words and len(word) > 2]
        venue_words = [word for word in venue.split() if word not in common_words and len(word) > 2]

        # Check if any significant words match
        for club_word in club_words:
            for venue_word in venue_words:
                if (club_word in venue_word or venue_word in club_word or
                    # Check for common abbreviations
                    (club_word.startswith(venue_word[:3]) and len(venue_word) > 3) or
                    (venue_word.startswith(club_word[:3]) and len(club_word) > 3)):
                    return True

        return False

    def verify_club_leader(self, email, club_name):
        if not self.api_token:
            app.logger.error("Airtable API token not configured")
            return False

        if not self.clubs_base_id or not self.clubs_table_name:
            app.logger.error("Airtable clubs base ID or table name not configured")
            return False

        # Validate email format to prevent injection
        if not email or '@' not in email or len(email) < 3:
            app.logger.error("Invalid email format for verification")
            return False

        # Escape email for safe use in formula - prevent wildcard matching
        escaped_email = email.replace('"', '""').replace("'", "''")

        # Validate email contains proper domain
        if email.count('@') != 1:
            app.logger.error("Invalid email format - multiple @ symbols")
            return False

        try:
            # Use exact email matching instead of FIND to prevent wildcard abuse
            email_filter_params = {
                'filterByFormula': f'{{Current Leaders\' Emails}} = "{escaped_email}"'
            }

            app.logger.info(f"Verifying club leader: email={email}, club={club_name}")
            app.logger.debug(f"Airtable URL: {self.clubs_base_url}")
            app.logger.debug(f"Email filter formula: {email_filter_params['filterByFormula']}")

            # Validate the URL to prevent SSRF
            parsed_url = urllib.parse.urlparse(self.clubs_base_url)
            if parsed_url.hostname not in ['api.airtable.com']:
                app.logger.error(f"Invalid Airtable URL hostname: {parsed_url.hostname}")
                return False

            response = self._safe_request('GET', self.clubs_base_url, headers=self.headers, params=email_filter_params)

            app.logger.info(f"Airtable response status: {response.status_code}")
            app.logger.debug(f"Airtable response headers: {dict(response.headers)}")
            app.logger.debug(f"Airtable response content length: {len(response.content) if response.content else 0}")

            if response.status_code == 200:
                try:
                    data = response.json()
                    app.logger.debug(f"Airtable response data keys: {list(data.keys()) if data else 'None'}")
                    records = data.get('records', [])
                    app.logger.info(f"Found {len(records)} records with email {email}")
                    if records:
                        app.logger.debug(f"First record fields: {list(records[0].get('fields', {}).keys()) if records else 'None'}")
                except ValueError as json_error:
                    app.logger.error(f"Failed to parse Airtable JSON response: {json_error}")
                    app.logger.error(f"Raw response content: {response.text[:500]}...")
                    return False

                if len(records) == 0:
                    app.logger.info("No records found with that email address")
                    return False

                # Check if any of the records match the club name (case-insensitive partial match)
                club_name_lower = club_name.lower().strip()

                # Log all available club names for debugging
                club_names = [record.get('fields', {}).get('Club Name', '') for record in records]
                app.logger.info(f"Available club names for {email}: {club_names}")
                app.logger.debug(f"Full record data for debugging: {[record.get('fields', {}) for record in records]}")

                for record in records:
                    fields = record.get('fields', {})
                    venue = fields.get('Club Name', '').lower().strip()
                    app.logger.debug(f"Checking club name: '{venue}' against requested club name: '{club_name_lower}'")

                    # Try multiple matching strategies with more flexible matching
                    if (club_name_lower in venue or
                        venue.find(club_name_lower) >= 0 or
                        # Check if club name words are in venue
                        any(word.strip() in venue for word in club_name_lower.split() if len(word.strip()) > 2) or
                        # Check if venue words are in club name
                        any(word.strip() in club_name_lower for word in venue.split() if len(word.strip()) > 2) or
                        # Check for common school/high school variations
                        self._check_school_variations(club_name_lower, venue)):
                        app.logger.info(f"Found matching club: {fields.get('Club Name', '')}")
                        return True

                app.logger.info(f"No club name match found for '{club_name}' in available clubs: {club_names}")
                return False

            elif response.status_code == 403:
                app.logger.error(f"Airtable 403 Forbidden - check API token permissions. Response: {response.text}")
                return False
            elif response.status_code == 404:
                app.logger.error(f"Airtable 404 Not Found - check base ID and table name. Response: {response.text}")
                return False
            else:
                app.logger.error(f"Airtable API error {response.status_code}: {response.text}")
                return False

        except Exception as e:
            app.logger.error(f"Exception during Airtable verification: {str(e)}")
            return False

    def log_pizza_grant(self, submission_data):
        if not self.api_token:
            app.logger.error("Airtable API token not configured")
            return None

        try:
            hours = float(submission_data.get('project_hours', 0))

            # New detailed earning structure: $5 per hour, capped at $20
            # Must be in-person meeting and have 3+ members to redeem
            grant_amount = min(hours * 5, 20)  # $5/hour, max $20

            # Round down to nearest dollar for clean amounts
            grant_amount = int(grant_amount)

            # Ensure minimum requirements are met for any grant
            if grant_amount > 0:
                # Check if club meets requirements (will be validated on submission)
                is_in_person = submission_data.get('is_in_person_meeting', False)
                club_member_count = submission_data.get('club_member_count', 0)

                if not is_in_person:
                    grant_amount = 0
                    app.logger.info(f"Grant denied: Not an in-person meeting")
                elif club_member_count < 3:
                    grant_amount = 0
                    app.logger.info(f"Grant denied: Club has {club_member_count} members, need 3+")
                else:
                    app.logger.info(f"Grant approved: ${grant_amount} for {hours} hours (in-person meeting, {club_member_count} members)")

            # Use YSWS Project Submission table fields - updated field names to match actual table
            project_table_name = urllib.parse.quote('YSWS Project Submission')
            project_url = f'https://api.airtable.com/v0/{self.base_id}/{project_table_name}'

            fields = {
                'Code URL': submission_data.get('github_url', ''),
                'Playable URL': submission_data.get('live_url', ''),
                'First Name': submission_data.get('first_name', ''),
                'Last Name': submission_data.get('last_name', ''),
                'Email': submission_data.get('email', ''),
                'Age': submission_data.get('age', ''),
                'Status': 'Pending',
                'Decision Reason': '',
                'How did you hear about this?': 'Through Club Leader',
                'What are we doing well?': submission_data.get('doing_well', ''),
                'How can we improve?': submission_data.get('improve', ''),
                'Screenshot': [{'url': submission_data.get('screenshot_url', '')}] if submission_data.get('screenshot_url') else [],
                'Description': submission_data.get('project_description', ''),
                'GitHub Username': submission_data.get('github_username', ''),
                'Address (Line 1)': submission_data.get('address_1', ''),
                'Address (Line 2)': submission_data.get('address_2', ''),
                'City': submission_data.get('city', ''),
                'State / Province': submission_data.get('state', ''),
                'Country': submission_data.get('country', ''),
                'ZIP / Postal Code': submission_data.get('zip', ''),
                'Birthday': submission_data.get('birthday', ''),
                'Hackatime Project': submission_data.get('project_name', ''),
                'Hours': float(hours),
                'Grant Amount': float(grant_amount),
                'Club Name': submission_data.get('club_name', ''),
                'Leader Email': submission_data.get('leader_email', ''),
                'In-Person Meeting': 'Yes' if submission_data.get('is_in_person_meeting', False) else 'No',
                'Club Member Count': str(submission_data.get('club_member_count', 0)),
                'Meeting Requirements Met': 'Yes' if (submission_data.get('is_in_person_meeting', False) and submission_data.get('club_member_count', 0) >= 3) else 'No'
            }

            # Debug log submission data
            app.logger.debug(f"Club name in submission_data: '{submission_data.get('club_name', 'NOT_FOUND')}'")
            app.logger.debug(f"Leader email in submission_data: '{submission_data.get('leader_email', 'NOT_FOUND')}'")

            # Remove empty fields to avoid validation issues
            fields_before_filter = fields.copy()
            fields = {k: v for k, v in fields.items() if v not in [None, '', []]}

            # Log which fields were filtered out
            filtered_out = set(fields_before_filter.keys()) - set(fields.keys())
            if filtered_out:
                app.logger.debug(f"Fields filtered out due to empty values: {filtered_out}")

            payload = {'records': [{'fields': fields}]}

            app.logger.info(f"Submitting to Airtable: {project_url}")
            app.logger.debug(f"Airtable payload fields: {list(fields.keys())}")
            app.logger.info(f"Screenshot field value: {fields.get('Screenshot', 'NOT_FOUND')}")
            app.logger.debug(f"Full payload: {payload}")

            response = requests.post(project_url, headers=self.headers, json=payload)

            app.logger.info(f"Airtable response status: {response.status_code}")
            if response.status_code not in [200, 201]:
                app.logger.error(f"Airtable submission failed: {response.text}")
                return None

            app.logger.info("Successfully submitted to Airtable")
            return response.json()

        except Exception as e:
            app.logger.error(f"Exception in log_pizza_grant: {str(e)}")
            return None

    def submit_pizza_grant(self, grant_data):
        """Submit pizza grant to Grants table"""
        if not self.api_token:
            return None

        # Use Grants table instead
        grants_table_name = urllib.parse.quote('Grants')
        grants_url = f'https://api.airtable.com/v0/{self.base_id}/{grants_table_name}'

        fields = {
            'Club': grant_data.get('club_name', ''),
            'Email': grant_data.get('contact_email', ''),
            'Status': 'In progress',
            'Grant Amount': float(grant_data.get('grant_amount', 0)),
            'Grant Type': 'Pizza Card',
            'Address': grant_data.get('club_address', ''),
            'Order ID': grant_data.get('order_id', '')
        }

        payload = {'records': [{'fields': fields}]}

        try:
            response = requests.post(grants_url, headers=self.headers, json=payload)
            app.logger.debug(f"Airtable response status: {response.status_code}")
            app.logger.debug(f"Airtable response body: {response.text}")
            if response.status_code in [200, 201]:
                return response.json()
            else:
                app.logger.error(f"Airtable error: {response.text}")
                return None
        except Exception as e:
            app.logger.error(f"Exception submitting to Airtable: {str(e)}")
            return None

    def submit_purchase_request(self, purchase_data):
        """Submit purchase request to Grant Fulfillment table"""
        if not self.api_token:
            return None

        # Use Grant Fulfillment table
        fulfillment_table_name = urllib.parse.quote('Grant Fulfillment')
        fulfillment_url = f'https://api.airtable.com/v0/{self.base_id}/{fulfillment_table_name}'

        fields = {
            'Leader First Name': purchase_data.get('leader_first_name', ''),
            'Leader Last Name': purchase_data.get('leader_last_name', ''),
            'Leader Email': purchase_data.get('leader_email', ''),
            'Purchase Type': purchase_data.get('purchase_type', ''),
            'Purchase Description': purchase_data.get('description', ''),
            'Purchase Reason': purchase_data.get('reason', ''),
            'Fulfillment Method': purchase_data.get('fulfillment_method', ''),
            'Status': 'Pending',
            'Club Name': purchase_data.get('club_name', ''),
            'Amount': str(purchase_data.get('amount', 0))
        }

        payload = {'records': [{'fields': fields}]}

        try:
            response = requests.post(fulfillment_url, headers=self.headers, json=payload)
            app.logger.debug(f"Airtable Grant Fulfillment response status: {response.status_code}")
            app.logger.debug(f"Airtable Grant Fulfillment response body: {response.text}")
            if response.status_code in [200, 201]:
                return response.json()
            else:
                app.logger.error(f"Airtable Grant Fulfillment error: {response.text}")
                return None
        except Exception as e:
            app.logger.error(f"Exception submitting to Airtable Grant Fulfillment: {str(e)}")
            return None

    def get_pizza_grant_submissions(self):
        if not self.api_token:
            return []

        try:
            # Use YSWS Project Submission table
            project_table_name = urllib.parse.quote('YSWS Project Submission')
            project_url = f'https://api.airtable.com/v0/{self.base_id}/{project_table_name}'

            response = requests.get(project_url, headers=self.headers)
            if response.status_code == 200:
                data = response.json()
                records = data.get('records', [])

                submissions = []
                for record in records:
                    fields = record.get('fields', {})
                    submissions.append({
                        'id': record['id'],
                        'project_name': fields.get('Hackatime Project', ''),
                        'first_name': fields.get('First Name', ''),
                        'last_name': fields.get('Last Name', ''),
                        'email': fields.get('Email', ''),
                        'club_name': fields.get('Club Name', fields.get('Hack Club', '')),
                        'description': fields.get('Description', ''),
                        'github_url': fields.get('Code URL', ''),
                        'live_url': fields.get('Playable URL', ''),
                        'doing_well': fields.get('What are we doing well?', ''),
                        'improve': fields.get('How can we improve?', ''),
                        'address_1': fields.get('Address (Line 1)', ''),
                        'city': fields.get('City', ''),
                        'state': fields.get('State / Province', ''),
                        'zip': fields.get('ZIP / Postal Code', ''),
                        'country': fields.get('Country', ''),
                        'hours': fields.get('Hours', 0),
                        'grant_amount': fields.get('Grant Amount Override') or fields.get('Grant Amount', ''),
                        'status': fields.get('Status', fields.get('Grant Status', fields.get('Review Status', 'Pending'))),
                        'created_time': record.get('createdTime', '')
                    })

                return submissions
            else:
                app.logger.error(f"Failed to fetch submissions: {response.status_code} - {response.text}")
                return []
        except Exception as e:
            app.logger.error(f"Error fetching pizza grant submissions: {str(e)}")
            return []

    def get_submission_by_id(self, submission_id):
        if not self.api_token:
            return None

        try:
            # Use YSWS Project Submission table
            project_table_name = urllib.parse.quote('YSWS Project Submission')
            project_url = f'https://api.airtable.com/v0/{self.base_id}/{project_table_name}'
            url = f"{project_url}/{submission_id}"

            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                data = response.json()
                fields = data.get('fields', {})
                return {
                    'id': data['id'],
                    'project_name': fields.get('Hackatime Project', ''),
                    'hours': fields.get('Hours', 0),
                    'status': 'Submitted'
                }
            return None
        except Exception as e:
            app.logger.error(f"Error fetching submission {submission_id}: {str(e)}")
            return None

    def update_submission_status(self, submission_id, action):
        if not self.api_token:
            return False

        try:
            # Use YSWS Project Submission table
            project_table_name = urllib.parse.quote('YSWS Project Submission')
            project_url = f'https://api.airtable.com/v0/{self.base_id}/{project_table_name}'
            url = f"{project_url}/{submission_id}"

            # Map action to status
            status = 'Approved' if action == 'approve' else 'Rejected'

            # First, try to get the current record to see what fields exist
            get_response = requests.get(url, headers=self.headers)
            if get_response.status_code == 200:
                current_record = get_response.json()
                fields = current_record.get('fields', {})
                app.logger.info(f"Current record fields: {list(fields.keys())}")

            # Try different status field names one by one
            possible_status_fields = ['Status', 'Grant Status', 'Review Status', 'Approval Status']

            for field_name in possible_status_fields:
                update_data = {
                    'fields': {
                        field_name: status
                    }
                }

                response = requests.patch(url, headers=self.headers, json=update_data)

                if response.status_code == 200:
                    app.logger.info(f"Submission {submission_id} status updated to {status} using field '{field_name}'")
                    return True
                else:
                    app.logger.debug(f"Failed to update with field '{field_name}': {response.status_code} - {response.text}")

            # If no field worked, log the error and return False
            app.logger.error(f"Failed to update submission status with any field name. Last response: {response.status_code} - {response.text}")
            return False
        except Exception as e:
            app.logger.error(f"Error updating submission status: {str(e)}")
            return False

    def delete_submission(self, submission_id):
        if not self.api_token:
            return False

        try:
            # Use YSWS Project Submission table
            project_table_name = urllib.parse.quote('YSWS Project Submission')
            project_url = f'https://api.airtable.com/v0/{self.base_id}/{project_table_name}'
            url = f"{project_url}/{submission_id}"

            response = requests.delete(url, headers=self.headers)
            return response.status_code == 200
        except Exception as e:
            app.logger.error(f"Error deleting submission: {str(e)}")
            return False

    def get_all_clubs_from_airtable(self):
        """Fetch all clubs from Airtable"""
        if not self.api_token:
            app.logger.error("Cannot fetch clubs from Airtable: API token not configured")
            return []

        try:
            app.logger.info("Starting to fetch all clubs from Airtable")
            app.logger.debug(f"Using Airtable URL: {self.clubs_base_url}")
            all_records = []
            offset = None
            page_count = 0

            while True:
                page_count += 1
                params = {}
                if offset:
                    params['offset'] = offset

                app.logger.debug(f"Fetching page {page_count} with offset: {offset}")
                response = requests.get(self.clubs_base_url, headers=self.headers, params=params)
                app.logger.debug(f"Page {page_count} response status: {response.status_code}")

                if response.status_code != 200:
                    app.logger.error(f"Airtable API error on page {page_count}: {response.status_code} - {response.text}")
                    app.logger.error(f"Request headers: {self.headers}")
                    app.logger.error(f"Request params: {params}")
                    break

                try:
                    data = response.json()
                    page_records = data.get('records', [])
                    all_records.extend(page_records)
                    app.logger.debug(f"Page {page_count}: Retrieved {len(page_records)} records, total so far: {len(all_records)}")

                    offset = data.get('offset')
                    if not offset:
                        app.logger.info(f"Completed fetching all clubs from Airtable. Total records: {len(all_records)}")
                        break
                except ValueError as json_error:
                    app.logger.error(f"Failed to parse Airtable JSON response on page {page_count}: {json_error}")
                    app.logger.error(f"Raw response content: {response.text[:500]}...")
                    break

            clubs = []
            app.logger.debug(f"Processing {len(all_records)} Airtable records into club data")
            for i, record in enumerate(all_records):
                fields = record.get('fields', {})
                app.logger.debug(f"Processing record {i+1}/{len(all_records)}: ID={record.get('id')}, Fields keys: {list(fields.keys())}")

                # Extract club information from Airtable fields
                club_data = {
                    'airtable_id': record['id'],
                    'name': fields.get('Club Name', '').strip(),
                    'leader_email': fields.get("Current Leaders' Emails", '').split(',')[0].strip() if fields.get("Current Leaders' Emails") else '',
                    'location': fields.get('Location', '').strip(),
                    'description': fields.get('Description', '').strip(),
                    'status': fields.get('Status', '').strip(),
                    'meeting_day': fields.get('Meeting Day', '').strip(),
                    'meeting_time': fields.get('Meeting Time', '').strip(),
                    'website': fields.get('Website', '').strip(),
                    'slack_channel': fields.get('Slack Channel', '').strip(),
                    'github': fields.get('GitHub', '').strip(),
                    'latitude': fields.get('Latitude'),
                    'longitude': fields.get('Longitude'),
                    'country': fields.get('Country', '').strip(),
                    'region': fields.get('Region', '').strip(),
                    'timezone': fields.get('Timezone', '').strip(),
                    'primary_leader': fields.get('Primary Leader', '').strip(),
                    'co_leaders': fields.get('Co-Leaders', '').strip(),
                    'meeting_notes': fields.get('Meeting Notes', '').strip(),
                    'club_applications_link': fields.get('Club Applications Link', '').strip(),
                }

                # Only include clubs with valid names and leader emails
                if club_data['name'] and club_data['leader_email']:
                    clubs.append(club_data)
                    app.logger.debug(f"Added valid club: {club_data['name']} ({club_data['leader_email']})")
                else:
                    app.logger.debug(f"Skipped invalid club record - Name: '{club_data['name']}', Email: '{club_data['leader_email']}'")

            app.logger.info(f"Successfully processed {len(clubs)} valid clubs from {len(all_records)} Airtable records")
            return clubs

        except Exception as e:
            app.logger.error(f"Error fetching clubs from Airtable: {str(e)}")
            return []

    def sync_club_with_airtable(self, club_id, airtable_data):
        """Sync a specific club with Airtable data"""
        try:
            app.logger.info(f"Starting sync for club ID {club_id} with Airtable data")
            app.logger.debug(f"Airtable data keys: {list(airtable_data.keys()) if airtable_data else 'None'}")

            club = Club.query.get(club_id)
            if not club:
                app.logger.error(f"Club with ID {club_id} not found in database")
                return False

            app.logger.debug(f"Found club: {club.name} (current location: {club.location})")

            # Update club fields with Airtable data
            if 'name' in airtable_data and airtable_data['name']:
                filtered_name = filter_profanity_comprehensive(airtable_data['name'])
                club.name = filtered_name
            else:
                club.name = club.name
            club.location = airtable_data.get('location', club.location)
            if 'description' in airtable_data and airtable_data['description']:
                filtered_description = filter_profanity_comprehensive(airtable_data['description'])
                club.description = filtered_description
            else:
                club.description = club.description

            # Store additional Airtable metadata as JSON in a new field
            club.airtable_data = json.dumps({
                'airtable_id': airtable_data.get('airtable_id'),
                'status': airtable_data.get('status'),
                'meeting_day': airtable_data.get('meeting_day'),
                'meeting_time': airtable_data.get('meeting_time'),
                'website': airtable_data.get('website'),
                'slack_channel': airtable_data.get('slack_channel'),
                'github': airtable_data.get('github'),
                'latitude': airtable_data.get('latitude'),
                'longitude': airtable_data.get('longitude'),
                'country': airtable_data.get('country'),
                'region': airtable_data.get('region'),
                'timezone': airtable_data.get('timezone'),
                'primary_leader': airtable_data.get('primary_leader'),
                'co_leaders': airtable_data.get('co_leaders'),
                'meeting_notes': airtable_data.get('meeting_notes'),
                'club_applications_link': airtable_data.get('club_applications_link'),
            })

            club.updated_at = datetime.now(timezone.utc)
            app.logger.debug(f"Updated club fields for {club.name}")

            db.session.commit()
            app.logger.info(f"Successfully synced club {club_id} ({club.name}) with Airtable data")
            return True

        except Exception as e:
            app.logger.error(f"Error syncing club {club_id} with Airtable: {str(e)}")
            app.logger.error(f"Exception type: {type(e).__name__}")
            app.logger.error(f"Exception details: {str(e)}")
            db.session.rollback()
            return False

    def create_club_from_airtable(self, airtable_data):
        """Create a new club from Airtable data"""
        try:
            app.logger.info(f"Creating new club from Airtable data")
            app.logger.debug(f"Airtable data: {airtable_data}")

            # Find or create leader by email
            leader_email = airtable_data.get('leader_email')
            if not leader_email:
                app.logger.error("Cannot create club: no leader email provided in Airtable data")
                return None

            app.logger.debug(f"Looking for leader with email: {leader_email}")

            leader = User.query.filter_by(email=leader_email).first()
            if not leader:
                # Create a placeholder leader account
                username = leader_email.split('@')[0]
                # Ensure username is unique
                counter = 1
                original_username = username
                while User.query.filter_by(username=username).first():
                    username = f"{original_username}{counter}"
                    counter += 1

                leader = User(
                    username=username,
                    email=leader_email,
                    first_name=airtable_data.get('primary_leader', '').split(' ')[0] if airtable_data.get('primary_leader') else '',
                    last_name=' '.join(airtable_data.get('primary_leader', '').split(' ')[1:]) if airtable_data.get('primary_leader') else ''
                )
                leader.set_password(secrets.token_urlsafe(16))  # Random password
                db.session.add(leader)
                db.session.flush()

            # Create club
            filtered_name = filter_profanity_comprehensive(airtable_data.get('name'))

            # Check for duplicate club names
            existing_club = Club.query.filter_by(name=filtered_name).first()
            if existing_club:
                app.logger.warning(f"Skipping club creation from Airtable - duplicate name: {filtered_name}")
                return None

            default_desc = f"Official {filtered_name} Hack Club"
            club_desc = airtable_data.get('description', default_desc)
            filtered_description = filter_profanity_comprehensive(club_desc)
            club = Club(
                name=filtered_name,
                description=filtered_description,
                location=airtable_data.get('location'),
                leader_id=leader.id,
                airtable_data=json.dumps({
                    'airtable_id': airtable_data.get('airtable_id'),
                    'status': airtable_data.get('status'),
                    'meeting_day': airtable_data.get('meeting_day'),
                    'meeting_time': airtable_data.get('meeting_time'),
                    'website': airtable_data.get('website'),
                    'slack_channel': airtable_data.get('slack_channel'),
                    'github': airtable_data.get('github'),
                    'latitude': airtable_data.get('latitude'),
                    'longitude': airtable_data.get('longitude'),
                    'country': airtable_data.get('country'),
                    'region': airtable_data.get('region'),
                    'timezone': airtable_data.get('timezone'),
                    'primary_leader': airtable_data.get('primary_leader'),
                    'co_leaders': airtable_data.get('co_leaders'),
                    'meeting_notes': airtable_data.get('meeting_notes'),
                    'club_applications_link': airtable_data.get('club_applications_link'),
                })
            )
            club.generate_join_code()

            db.session.add(club)
            db.session.commit()

            app.logger.info(f"Successfully created club '{club.name}' from Airtable data (ID: {club.id})")
            return club

        except Exception as e:
            app.logger.error(f"Error creating club from Airtable data: {str(e)}")
            app.logger.error(f"Exception type: {type(e).__name__}")
            app.logger.error(f"Airtable data that caused error: {airtable_data}")
            db.session.rollback()
            return None

    def update_club_in_airtable(self, airtable_record_id, fields):
        """Update a specific club record in Airtable"""
        if not self.api_token or not airtable_record_id:
            return False

        try:
            update_url = f"{self.clubs_base_url}/{airtable_record_id}"
            payload = {'fields': fields}

            response = requests.patch(update_url, headers=self.headers, json=payload)

            if response.status_code == 200:
                return True
            else:
                app.logger.error(f"Airtable update error: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            app.logger.error(f"Error updating Airtable record: {str(e)}")
            return False

    def send_email_verification(self, email):
        """Send email verification code to Airtable for automation with retry logic"""
        if not self.api_token:
            app.logger.error("Airtable API token not configured for email verification")
            return None

        # Generate 5-digit verification code
        verification_code = ''.join(secrets.choice(string.digits) for _ in range(5))

        # Retry logic for network timeouts
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                # First, check if there's an existing pending verification for this email
                existing_params = {
                    'filterByFormula': f'AND({{Email}} = "{email}", {{Status}} = "Pending")'
                }

                existing_response = self._safe_request('GET', self.email_verification_url, headers=self.headers, params=existing_params, timeout=90)

                if existing_response.status_code == 200:
                    existing_data = existing_response.json()
                    existing_records = existing_data.get('records', [])

                    # Update existing pending record instead of creating new one
                    if existing_records:
                        record_id = existing_records[0]['id']
                        update_url = f"{self.email_verification_url}/{record_id}"

                        payload = {
                            'fields': {
                                'Code': verification_code,
                                'Status': 'Pending'
                            }
                        }

                        response = self._safe_request('PATCH', update_url, headers=self.headers, json=payload, timeout=90)
                    else:
                        # Create new verification record
                        payload = {
                            'records': [{
                                'fields': {
                                    'Email': email,
                                    'Code': verification_code,
                                    'Status': 'Pending'
                                }
                            }]
                        }

                        response = self._safe_request('POST', self.email_verification_url, headers=self.headers, json=payload, timeout=90)
                else:
                    # Create new verification record if we can't check existing
                    payload = {
                        'records': [{
                            'fields': {
                                'Email': email,
                                'Code': verification_code,
                                'Status': 'Pending'
                            }
                        }]
                    }

                    response = self._safe_request('POST', self.email_verification_url, headers=self.headers, json=payload, timeout=90)

                if response.status_code in [200, 201]:
                    app.logger.info(f"Email verification code sent for {email}")
                    return verification_code
                else:
                    app.logger.error(f"Failed to send email verification: {response.status_code} - {response.text}")
                    return None

            except requests.exceptions.ReadTimeout as e:
                retry_count += 1
                app.logger.warning(f"Email verification timeout, attempt {retry_count}/{max_retries}: {str(e)}")
                if retry_count >= max_retries:
                    app.logger.error(f"Email verification failed after {max_retries} attempts due to timeout")
                    return None
                # Wait before retrying
                import time
                time.sleep(2 ** retry_count)  # Exponential backoff

            except Exception as e:
                app.logger.error(f"Exception sending email verification: {str(e)}")
                return None

        return None

    def verify_email_code(self, email, code):
        """Verify the email verification code"""
        if not self.api_token:
            app.logger.error("Airtable API token not configured for email verification")
            return False

        try:
            # Find the verification record
            filter_params = {
                'filterByFormula': f'AND({{Email}} = "{email}", {{Code}} = "{code}", {{Status}} = "Pending")'
            }

            response = self._safe_request('GET', self.email_verification_url, headers=self.headers, params=filter_params, timeout=90)

            if response.status_code == 200:
                data = response.json()
                records = data.get('records', [])

                if records:
                    # Mark as verified
                    record_id = records[0]['id']
                    update_url = f"{self.email_verification_url}/{record_id}"

                    payload = {
                        'fields': {
                            'Status': 'Verified'
                        }
                    }

                    update_response = self._safe_request('PATCH', update_url, headers=self.headers, json=payload, timeout=90)

                    if update_response.status_code == 200:
                        app.logger.info(f"Email verification successful for {email}")
                        return True
                    else:
                        app.logger.error(f"Failed to update verification status: {update_response.status_code}")
                        return False
                else:
                    app.logger.warning(f"No pending verification found for {email} with code {code}")
                    return False
            else:
                app.logger.error(f"Error checking verification code: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            app.logger.error(f"Exception verifying email code: {str(e)}")
            return False

    def check_email_code(self, email, code):
        """Check if email verification code is valid without marking as verified"""
        if not self.api_token:
            app.logger.error("Airtable API token not configured for email verification")
            return False

        try:
            # Find the verification record
            filter_params = {
                'filterByFormula': f'AND({{Email}} = "{email}", {{Code}} = "{code}", {{Status}} = "Pending")'
            }

            response = self._safe_request('GET', self.email_verification_url, headers=self.headers, params=filter_params, timeout=90)

            if response.status_code == 200:
                data = response.json()
                records = data.get('records', [])

                if records:
                    app.logger.info(f"Email verification code check successful for {email}")
                    return True
                else:
                    app.logger.warning(f"No pending verification found for {email} with code {code}")
                    return False
            else:
                app.logger.error(f"Error checking verification code: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            app.logger.error(f"Exception checking email code: {str(e)}")
            return False

    def sync_all_clubs_with_airtable(self):
        """Sync all clubs with Airtable data"""
        try:
            airtable_clubs = self.get_all_clubs_from_airtable()

            created_count = 0
            updated_count = 0

            for airtable_club in airtable_clubs:
                # Try to find existing club by leader email
                leader_email = airtable_club.get('leader_email')
                if not leader_email:
                    continue

                leader = User.query.filter_by(email=leader_email).first()
                existing_club = None

                if leader:
                    existing_club = Club.query.filter_by(leader_id=leader.id).first()

                if existing_club:
                    # Update existing club
                    if self.sync_club_with_airtable(existing_club.id, airtable_club):
                        updated_count += 1
                else:
                    # Create new club
                    new_club = self.create_club_from_airtable(airtable_club)
                    if new_club:
                        created_count += 1

            return {
                'success': True,
                'created': created_count,
                'updated': updated_count,
                'total_airtable_clubs': len(airtable_clubs)
            }

        except Exception as e:
            app.logger.error(f"Error syncing all clubs with Airtable: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def submit_project_data(self, submission_data):
        """Submit project submission data to Airtable"""
        if not self.api_token:
            app.logger.error("AIRTABLE: API token not configured")
            return None

        try:
            # Use YSWS Project Submission table
            project_table_name = urllib.parse.quote('YSWS Project Submission')
            project_url = f'https://api.airtable.com/v0/{self.base_id}/{project_table_name}'

            app.logger.info(f"AIRTABLE: Submitting to URL: {project_url}")

            fields = {
                'Address (Line 1)': submission_data.get('address_1', ''),
                'Birthday': submission_data.get('birthday', ''),
                'City': submission_data.get('city', ''),
                'Club Name': submission_data.get('club_name', ''),
                'Code URL': submission_data.get('github_url', ''),
                'Country': submission_data.get('country', ''),
                'Description': submission_data.get('project_description', ''),
                'Email': submission_data.get('email', ''),
                'First Name': submission_data.get('first_name', ''),
                'GitHub Username': submission_data.get('github_username', ''),
                'Hackatime Project': submission_data.get('project_name', ''),
                'Hours': float(str(submission_data.get('project_hours', '0')).strip()),
                'How can we improve?': submission_data.get('improve', ''),
                'How did you hear about this?': 'Through Club Leader Dashboard',
                'Last Name': submission_data.get('last_name', ''),
                'Leader Email': submission_data.get('leader_email', ''),
                'Playable URL': submission_data.get('live_url', ''),
                'State / Province': submission_data.get('state', ''),
                'Status': 'Pending',
                'What are we doing well?': submission_data.get('doing_well', ''),
                'ZIP / Postal Code': submission_data.get('zip', '')
            }

            # Remove empty fields to avoid validation issues
            fields = {k: v for k, v in fields.items() if v not in [None, '', []]}

            app.logger.info(f"AIRTABLE: Submitting fields: {list(fields.keys())}")
            app.logger.info(f"AIRTABLE: Project name: {fields.get('Hackatime Project', 'NOT_FOUND')}")
            app.logger.info(f"AIRTABLE: Hours: {fields.get('Hours', 'NOT_FOUND')}")

            payload = {'records': [{'fields': fields}]}

            response = self._safe_request('POST', project_url, headers=self.headers, json=payload)

            app.logger.info(f"AIRTABLE: Response status: {response.status_code}")
            if response.status_code not in [200, 201]:
                app.logger.error(f"AIRTABLE: Submission failed: {response.text}")
                return None

            result = response.json()
            app.logger.info(f"AIRTABLE: Successfully submitted project! Record ID: {result.get('records', [{}])[0].get('id', 'UNKNOWN')}")
            return result

        except Exception as e:
            app.logger.error(f"AIRTABLE: Exception in submit_project_data: {str(e)}")
            return None

    def get_ysws_project_submissions(self):
        """Get all YSWS project submissions from Airtable"""
        if not self.api_token:
            app.logger.error("AIRTABLE: API token not configured")
            return []

        try:
            project_table_name = urllib.parse.quote('YSWS Project Submission')
            project_url = f'https://api.airtable.com/v0/{self.base_id}/{project_table_name}'

            all_records = []
            offset = None

            while True:
                params = {}
                if offset:
                    params['offset'] = offset

                response = self._safe_request('GET', project_url, headers=self.headers, params=params)

                if response.status_code != 200:
                    app.logger.error(f"AIRTABLE: Failed to fetch project submissions: {response.text}")
                    break

                data = response.json()
                records = data.get('records', [])
                all_records.extend(records)

                offset = data.get('offset')
                if not offset:
                    break

            # Transform records to a more usable format
            submissions = []
            for record in all_records:
                fields = record.get('fields', {})
                submission = {
                    'id': record.get('id'),
                    'firstName': fields.get('First Name', ''),
                    'lastName': fields.get('Last Name', ''),
                    'email': fields.get('Email', ''),
                    'age': fields.get('Age', ''),
                    'codeUrl': fields.get('Code URL', ''),
                    'playableUrl': fields.get('Playable URL', ''),
                    'description': fields.get('Description', ''),
                    'githubUsername': fields.get('GitHub Username', ''),
                    'addressLine1': fields.get('Address (Line 1)', ''),
                    'addressLine2': fields.get('Address (Line 2)', ''),
                    'city': fields.get('City', ''),
                    'country': fields.get('Country', ''),
                    'zipCode': fields.get('ZIP / Postal Code', ''),
                    'birthday': fields.get('Birthday', ''),
                    'hackatimeProject': fields.get('Hackatime Project', ''),
                    'hours': fields.get('Hours', ''),
                    'grantAmount': fields.get('Grant Amount Override') or fields.get('Grant Amount', ''),
                    'clubName': fields.get('Club Name', ''),
                    'leaderEmail': fields.get('Leader Email', ''),
                    'status': fields.get('Status', 'Pending'),
                    'autoReviewStatus': fields.get('Auto Review Status', ''),
                    'decisionReason': fields.get('Decision Reason', ''),
                    'howDidYouHear': fields.get('How did you hear about this?', ''),
                    'whatAreWeDoingWell': fields.get('What are we doing well?', ''),
                    'howCanWeImprove': fields.get('How can we improve?', ''),
                    'screenshot': fields.get('Screenshot', ''),
                    'grantOverrideReason': fields.get('Grant Override Reason', ''),
                    'createdTime': record.get('createdTime', '')
                }

                # Handle screenshot attachment if it's an array
                if isinstance(submission['screenshot'], list) and len(submission['screenshot']) > 0:
                    submission['screenshot'] = submission['screenshot'][0].get('url', '')
                elif not isinstance(submission['screenshot'], str):
                    submission['screenshot'] = ''

                submissions.append(submission)

            app.logger.info(f"AIRTABLE: Fetched {len(submissions)} project submissions")
            return submissions

        except Exception as e:
            app.logger.error(f"AIRTABLE: Exception in get_ysws_project_submissions: {str(e)}")
            return []

    def update_ysws_project_submission(self, record_id, fields):
        """Update a YSWS project submission in Airtable"""
        if not self.api_token or not record_id:
            app.logger.error("AIRTABLE: API token not configured or no record ID provided")
            return False

        try:
            project_table_name = urllib.parse.quote('YSWS Project Submission')
            update_url = f'https://api.airtable.com/v0/{self.base_id}/{project_table_name}/{record_id}'

            # Only include fields that we're allowed to update
            allowed_fields = {
                'Status', 'Decision Reason', 'Grant Amount Override', 'Auto Review Status', 'Grant Override Reason'
            }

            update_fields = {k: v for k, v in fields.items() if k in allowed_fields}

            payload = {'fields': update_fields}

            response = self._safe_request('PATCH', update_url, headers=self.headers, json=payload)

            if response.status_code == 200:
                app.logger.info(f"AIRTABLE: Successfully updated project submission {record_id}")
                return True
            else:
                app.logger.error(f"AIRTABLE: Failed to update project submission: {response.text}")
                return False

        except Exception as e:
            app.logger.error(f"AIRTABLE: Exception in update_ysws_project_submission: {str(e)}")
            return False

    def delete_ysws_project_submission(self, record_id):
        """Delete a YSWS project submission from Airtable"""
        if not self.api_token or not record_id:
            app.logger.error("AIRTABLE: API token not configured or no record ID provided")
            return False

        try:
            project_table_name = urllib.parse.quote('YSWS Project Submission')
            delete_url = f'https://api.airtable.com/v0/{self.base_id}/{project_table_name}/{record_id}'

            response = self._safe_request('DELETE', delete_url, headers=self.headers)

            if response.status_code == 200:
                app.logger.info(f"AIRTABLE: Successfully deleted project submission {record_id}")
                return True
            else:
                app.logger.error(f"AIRTABLE: Failed to delete project submission: {response.text}")
                return False

        except Exception as e:
            app.logger.error(f"AIRTABLE: Exception in delete_ysws_project_submission: {str(e)}")
            return False

    def submit_order(self, order_data):
        """Submit order to Orders table"""
        if not self.api_token:
            return None

        # Use Orders table in the shop base
        shop_base_id = 'app7OFpfZceddfK17'
        orders_table_name = urllib.parse.quote('Orders')
        orders_url = f'https://api.airtable.com/v0/{shop_base_id}/{orders_table_name}'

        fields = {
            'Club Name': order_data.get('club_name', ''),
            'Leader First Name': order_data.get('leader_first_name', ''),
            'Leader Last Name': order_data.get('leader_last_name', ''),
            'Leader Email': order_data.get('leader_email', ''),
            'Club Member Amount': order_data.get('club_member_amount', 0),
            'Product(s)': order_data.get('products', ''),
            'Total Estimated Cost': order_data.get('total_estimated_cost', 0),
            'Delivery Address Line 1': order_data.get('delivery_address_line_1', ''),
            'Delivery Address Line 2': order_data.get('delivery_address_line_2', ''),
            'City': order_data.get('delivery_city', ''),
            'Delivery ZIP/Postal Code': order_data.get('delivery_zip', ''),
            'Delivery State/Area': order_data.get('delivery_state', ''),
            'Delivery Country': order_data.get('delivery_country', ''),
            'Special Notes': order_data.get('special_notes', ''),
            'Usage Reason': order_data.get('usage_reason', ''),
            'Order Sources': order_data.get('order_sources', []),
            'Shipment Status': 'Pending'
        }

        payload = {'records': [{'fields': fields}]}

        try:
            response = requests.post(orders_url, headers=self.headers, json=payload)
            app.logger.debug(f"Airtable Orders response status: {response.status_code}")
            app.logger.debug(f"Airtable Orders response body: {response.text}")
            if response.status_code in [200, 201]:
                return response.json()
            else:
                app.logger.error(f"Airtable Orders error: {response.text}")
                return None
        except Exception as e:
            app.logger.error(f"Exception submitting to Airtable Orders: {str(e)}")
            return None

    def get_orders_for_club(self, club_name):
        """Get all orders for a specific club"""
        if not self.api_token:
            return []

        shop_base_id = 'app7OFpfZceddfK17'
        orders_table_name = urllib.parse.quote('Orders')
        orders_url = f'https://api.airtable.com/v0/{shop_base_id}/{orders_table_name}'

        try:
            # Filter by club name
            params = {
                'filterByFormula': f"{{Club Name}} = '{club_name}'"
            }

            response = requests.get(orders_url, headers=self.headers, params=params)
            if response.status_code == 200:
                data = response.json()
                records = data.get('records', [])

                orders = []
                for record in records:
                    fields = record.get('fields', {})
                    orders.append({
                        'id': record['id'],
                        'club_name': fields.get('Club Name', ''),
                        'leader_first_name': fields.get('Leader First Name', ''),
                        'leader_last_name': fields.get('Leader Last Name', ''),
                        'leader_email': fields.get('Leader Email', ''),
                        'club_member_amount': fields.get('Club Member Amount', 0),
                        'products': fields.get('Product(s)', ''),
                        'total_estimated_cost': fields.get('Total Estimated Cost', 0),
                        'delivery_address_line_1': fields.get('Delivery Address Line 1', ''),
                        'delivery_address_line_2': fields.get('Delivery Address Line 2', ''),
                        'delivery_city': fields.get('City', ''),
                        'delivery_zip': fields.get('Delivery ZIP/Postal Code', ''),
                        'delivery_state': fields.get('Delivery State/Area', ''),
                        'delivery_country': fields.get('Delivery Country', ''),
                        'special_notes': fields.get('Special Notes', ''),
                        'usage_reason': fields.get('Usage Reason', ''),
                        'order_sources': fields.get('Order Sources', []),
                        'shipment_status': fields.get('Shipment Status', 'Pending'),
                        'created_time': record.get('createdTime', '')
                    })

                return orders
            else:
                app.logger.error(f"Failed to fetch orders: {response.status_code} - {response.text}")
                return []
        except Exception as e:
            app.logger.error(f"Error fetching orders for club {club_name}: {str(e)}")
            return []

    def get_all_orders(self):
        """Get all orders for admin review"""
        if not self.api_token:
            return []

        shop_base_id = 'app7OFpfZceddfK17'
        orders_table_name = urllib.parse.quote('Orders')
        orders_url = f'https://api.airtable.com/v0/{shop_base_id}/{orders_table_name}'

        try:
            all_orders = []
            offset = None

            while True:
                params = {}
                if offset:
                    params['offset'] = offset

                response = requests.get(orders_url, headers=self.headers, params=params)
                if response.status_code == 200:
                    data = response.json()
                    records = data.get('records', [])

                    for record in records:
                        fields = record.get('fields', {})
                        all_orders.append({
                            'id': record['id'],
                            'club_name': fields.get('Club Name', ''),
                            'leader_first_name': fields.get('Leader First Name', ''),
                            'leader_last_name': fields.get('Leader Last Name', ''),
                            'leader_email': fields.get('Leader Email', ''),
                            'club_member_amount': fields.get('Club Member Amount', 0),
                            'products': fields.get('Product(s)', ''),
                            'total_estimated_cost': fields.get('Total Estimated Cost', 0),
                            'delivery_address_line_1': fields.get('Delivery Address Line 1', ''),
                            'delivery_address_line_2': fields.get('Delivery Address Line 2', ''),
                            'delivery_city': fields.get('City', ''),
                            'delivery_zip': fields.get('Delivery ZIP/Postal Code', ''),
                            'delivery_state': fields.get('Delivery State/Area', ''),
                            'delivery_country': fields.get('Delivery Country', ''),
                            'special_notes': fields.get('Special Notes', ''),
                            'usage_reason': fields.get('Usage Reason', ''),
                            'order_sources': fields.get('Order Sources', []),
                            'shipment_status': fields.get('Shipment Status', 'Pending'),
                            'reviewer_reason': fields.get('Reviewer Reason', ''),
                            'created_time': record.get('createdTime', '')
                        })

                    offset = data.get('offset')
                    if not offset:
                        break
                else:
                    app.logger.error(f"Failed to fetch all orders: {response.status_code} - {response.text}")
                    break

            return all_orders
        except Exception as e:
            app.logger.error(f"Error fetching all orders: {str(e)}")
            return []

    def update_order_status(self, order_id, status, reviewer_reason):
        """Update order status and reviewer reason"""
        if not self.api_token:
            return False

        shop_base_id = 'app7OFpfZceddfK17'
        orders_table_name = urllib.parse.quote('Orders')
        update_url = f'https://api.airtable.com/v0/{shop_base_id}/{orders_table_name}/{order_id}'

        fields = {
            'Shipment Status': status,
            'Reviewer Reason': reviewer_reason
        }

        payload = {'fields': fields}

        try:
            response = requests.patch(update_url, headers=self.headers, json=payload)
            app.logger.debug(f"Airtable order update response status: {response.status_code}")
            app.logger.debug(f"Airtable order update response body: {response.text}")
            if response.status_code == 200:
                return response.json()
            else:
                app.logger.error(f"Airtable order update error: {response.text}")
                return False
        except Exception as e:
            app.logger.error(f"Exception updating order status: {str(e)}")
            return False

    def delete_order(self, order_id):
        """Delete an order record"""
        if not self.api_token:
            return False

        shop_base_id = 'app7OFpfZceddfK17'
        orders_table_name = urllib.parse.quote('Orders')
        delete_url = f'https://api.airtable.com/v0/{shop_base_id}/{orders_table_name}/{order_id}'

        try:
            response = requests.delete(delete_url, headers=self.headers)
            app.logger.debug(f"Airtable order delete response status: {response.status_code}")
            app.logger.debug(f"Airtable order delete response body: {response.text}")
            if response.status_code == 200:
                return response.json()
            else:
                app.logger.error(f"Airtable order delete error: {response.text}")
                return False
        except Exception as e:
            app.logger.error(f"Exception deleting order: {str(e)}")
            return False

    def log_gallery_post(self, post_title, description, photos, club_name, author_username):
        """Log gallery post to Airtable Gallery table"""
        if not self.api_token:
            app.logger.error("AIRTABLE: API token not configured for gallery logging")
            return False

        try:
            gallery_base_id = 'app7OFpfZceddfK17'  # Base ID provided by user
            gallery_table_name = urllib.parse.quote('Gallary')  # Table name provided by user (note the spelling)
            gallery_url = f'https://api.airtable.com/v0/{gallery_base_id}/{gallery_table_name}'

            # Format photos as comma-separated string (imgurl1, imgurl2, etc)
            photos_formatted = ', '.join(photos) if photos else ''

            fields = {
                'Post Title': post_title,
                'Description': description,
                'Photos': photos_formatted,
                'Club Name': club_name
            }

            payload = {'fields': fields}

            app.logger.info(f"AIRTABLE: Logging gallery post to {gallery_url}")
            app.logger.debug(f"AIRTABLE: Gallery post payload: {payload}")

            response = self._safe_request('POST', gallery_url, headers=self.headers, json=payload)

            app.logger.info(f"AIRTABLE: Gallery post response status: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                app.logger.info(f"AIRTABLE: Successfully logged gallery post! Record ID: {result.get('id', 'UNKNOWN')}")
                return True
            else:
                app.logger.error(f"AIRTABLE: Gallery post logging failed: {response.text}")
                return False

        except Exception as e:
            app.logger.error(f"AIRTABLE: Exception in log_gallery_post: {str(e)}")
            return False


# Create singleton instance
airtable_service = AirtableService()
