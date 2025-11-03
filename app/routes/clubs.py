"""
Club routes blueprint for the Hack Club Dashboard.
Handles club management, shop, poster editor, and club-specific features.
"""

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, send_file
from extensions import db
from app.decorators.auth import login_required
from app.decorators.economy import economy_required
from app.utils.auth_helpers import get_current_user
from app.utils.club_helpers import verify_club_leadership, is_user_co_leader
from app.utils.economy_helpers import create_club_transaction
from app.models.club import Club, ClubMembership
from app.models.economy import ClubTransaction
from app.models.club_content import ClubPost, ClubProject
from datetime import datetime, timezone

clubs_bp = Blueprint('clubs', __name__)


@clubs_bp.route('/club-connection-required/<int:club_id>')
@login_required
def club_connection_required(club_id):
    """Page shown when club connection is required"""
    club = Club.query.get_or_404(club_id)
    user = get_current_user()

    # Check if user is a member
    membership = ClubMembership.query.filter_by(
        club_id=club_id,
        user_id=user.id
    ).first()

    if not membership:
        flash('You must be a member of this club to access this page.', 'danger')
        return redirect(url_for('main.dashboard'))

    return render_template('club_connection_required.html', club=club)


@clubs_bp.route('/club/<int:club_id>/shop')
@login_required
@economy_required
def club_shop(club_id):
    """Club token shop"""
    club = Club.query.get_or_404(club_id)
    user = get_current_user()

    # Verify user is a member or leader
    membership = ClubMembership.query.filter_by(
        club_id=club_id,
        user_id=user.id
    ).first()

    if not membership:
        flash('You must be a member of this club to access the shop.', 'danger')
        return redirect(url_for('main.dashboard'))

    # Get club transactions for balance history
    transactions = ClubTransaction.query.filter_by(
        club_id=club_id
    ).order_by(ClubTransaction.created_at.desc()).limit(20).all()

    return render_template('club_shop.html', club=club, transactions=transactions)


@clubs_bp.route('/club/<int:club_id>/orders')
@login_required
def club_orders(club_id):
    """View club orders"""
    club = Club.query.get_or_404(club_id)
    user = get_current_user()

    # Verify user is a leader
    if not verify_club_leadership(club, user):
        flash('Only club leaders can view orders.', 'danger')
        return redirect(url_for('main.club_dashboard', club_id=club_id))

    return render_template('club_orders.html', club=club)


@clubs_bp.route('/club/<int:club_id>/poster-editor')
@login_required
def poster_editor(club_id):
    """Club poster editor"""
    club = Club.query.get_or_404(club_id)
    user = get_current_user()

    # Verify user is a member
    membership = ClubMembership.query.filter_by(
        club_id=club_id,
        user_id=user.id
    ).first()

    if not membership:
        flash('You must be a member of this club to use the poster editor.', 'danger')
        return redirect(url_for('main.dashboard'))

    return render_template('poster_editor.html', club=club)


@clubs_bp.route('/club/<int:club_id>/project-submission', methods=['GET', 'POST'])
@login_required
def project_submission(club_id):
    """Submit a project for club"""
    club = Club.query.get_or_404(club_id)
    user = get_current_user()

    # Verify user is a member
    membership = ClubMembership.query.filter_by(
        club_id=club_id,
        user_id=user.id
    ).first()

    if not membership:
        flash('You must be a member of this club to submit projects.', 'danger')
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        from app.utils.sanitization import sanitize_string, sanitize_url
        from app.models.economy import ProjectSubmission

        project_name = sanitize_string(request.form.get('project_name', ''), max_length=200)
        project_url = sanitize_url(request.form.get('project_url', ''), max_length=500)

        if not project_name:
            flash('Project name is required.', 'error')
            return render_template('project_submission.html', club=club)

        # Create project submission
        submission = ProjectSubmission(
            user_id=user.id,
            club_id=club_id,
            project_name=project_name,
            project_url=project_url
        )

        db.session.add(submission)
        db.session.commit()

        flash('Project submitted successfully! Waiting for approval.', 'success')
        return redirect(url_for('main.club_dashboard', club_id=club_id))

    return render_template('project_submission.html', club=club)


@clubs_bp.route('/api/clubs/<int:club_id>/members')
@login_required
def get_club_members(club_id):
    """Get club members API endpoint"""
    club = Club.query.get_or_404(club_id)
    user = get_current_user()

    # Verify user is a member
    membership = ClubMembership.query.filter_by(
        club_id=club_id,
        user_id=user.id
    ).first()

    if not membership:
        return jsonify({'error': 'Not authorized'}), 403

    # Get all members
    memberships = ClubMembership.query.filter_by(club_id=club_id).all()

    members_data = []
    for m in memberships:
        member_data = {
            'id': m.user.id,
            'username': m.user.username,
            'first_name': m.user.first_name,
            'last_name': m.user.last_name,
            'email': m.user.email,
            'role': m.role,
            'is_leader': m.user.id == club.leader_id,
            'is_co_leader': m.user.id == club.co_leader_id,
            'joined_at': m.joined_at.isoformat() if m.joined_at else None
        }
        members_data.append(member_data)

    return jsonify({
        'success': True,
        'club_id': club_id,
        'club_name': club.name,
        'members': members_data,
        'total_members': len(members_data)
    })


@clubs_bp.route('/api/clubs/<int:club_id>/background', methods=['GET', 'POST', 'DELETE'])
@login_required
def club_background(club_id):
    """Get, update, or remove club background"""
    from app.utils.sanitization import sanitize_string
    import os
    from werkzeug.utils import secure_filename
    from flask import current_app

    club = Club.query.get_or_404(club_id)
    user = get_current_user()

    # Check if user is leader or co-leader
    is_leader = club.leader_id == user.id
    is_co_leader = is_user_co_leader(club, user)

    if request.method == 'GET':
        # Any member can view
        membership = ClubMembership.query.filter_by(club_id=club_id, user_id=user.id).first()
        if not membership and not user.is_admin:
            return jsonify({'error': 'Not authorized'}), 403

        return jsonify({
            'background_image_url': club.background_image_url or '',
            'background_blur': club.background_blur or 0
        })

    elif request.method == 'POST':
        # Only leaders/co-leaders can update
        if not is_leader and not is_co_leader and not user.is_admin:
            return jsonify({'error': 'Only club leaders can update background'}), 403

        # Check if this is a file upload or JSON data
        if request.content_type and 'multipart/form-data' in request.content_type:
            # Handle file upload
            if 'image' not in request.files:
                return jsonify({'error': 'No file uploaded'}), 400

            file = request.files['image']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400

            # Validate file type
            allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
            filename = secure_filename(file.filename)
            file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

            if file_ext not in allowed_extensions:
                return jsonify({'error': f'Invalid file type. Allowed: {", ".join(allowed_extensions)}'}), 400

            # Save file to static/uploads/backgrounds/
            upload_folder = os.path.join(current_app.root_path, '..', 'static', 'uploads', 'backgrounds')
            os.makedirs(upload_folder, exist_ok=True)

            # Generate unique filename
            unique_filename = f"club_{club_id}_{int(datetime.now().timestamp())}.{file_ext}"
            file_path = os.path.join(upload_folder, unique_filename)

            try:
                file.save(file_path)

                # Store the URL path (relative to static folder)
                background_url = f"/static/uploads/backgrounds/{unique_filename}"

                # Delete old background file if it exists and is local
                if club.background_image_url and club.background_image_url.startswith('/static/uploads/backgrounds/'):
                    old_file_path = os.path.join(current_app.root_path, '..', club.background_image_url.lstrip('/'))
                    if os.path.exists(old_file_path):
                        try:
                            os.remove(old_file_path)
                        except Exception:
                            pass  # Don't fail if we can't delete old file

                club.background_image_url = background_url
                db.session.commit()

                return jsonify({
                    'success': True,
                    'message': 'Background image uploaded successfully',
                    'background_url': background_url
                })
            except Exception as e:
                return jsonify({'error': f'Failed to save file: {str(e)}'}), 500

        else:
            # Handle JSON data with URL or blur setting
            try:
                data = request.get_json()
                if not data:
                    return jsonify({
                        'error': 'No JSON data provided',
                        'details': 'Request must include JSON data with background_image_url or background_blur'
                    }), 400

                # Check if this is a remove request
                if data.get('remove_background'):
                    # Delete file if it's a local upload
                    if club.background_image_url and club.background_image_url.startswith('/static/uploads/backgrounds/'):
                        file_path = os.path.join(current_app.root_path, '..', club.background_image_url.lstrip('/'))
                        if os.path.exists(file_path):
                            try:
                                os.remove(file_path)
                            except Exception:
                                pass

                    club.background_image_url = None
                    club.background_blur = 0
                    db.session.commit()

                    return jsonify({
                        'success': True,
                        'message': 'Background removed successfully'
                    })

                if 'background_image_url' in data:
                    club.background_image_url = sanitize_string(data['background_image_url'], max_length=500)

                if 'background_blur' in data:
                    blur = int(data['background_blur'])
                    club.background_blur = max(0, min(100, blur))  # Clamp between 0-100

                db.session.commit()

                return jsonify({
                    'success': True,
                    'message': 'Background updated successfully',
                    'background_image_url': club.background_image_url,
                    'background_blur': club.background_blur
                })
            except Exception as e:
                return jsonify({
                    'error': 'Failed to update background',
                    'details': str(e)
                }), 400

    elif request.method == 'DELETE':
        # Only leaders/co-leaders can remove
        if not is_leader and not is_co_leader and not user.is_admin:
            return jsonify({'error': 'Only club leaders can remove background'}), 403

        # Delete file if it's a local upload
        if club.background_image_url and club.background_image_url.startswith('/static/uploads/backgrounds/'):
            file_path = os.path.join(current_app.root_path, '..', club.background_image_url.lstrip('/'))
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass

        club.background_image_url = None
        club.background_blur = 0
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Background removed successfully'
        })


@clubs_bp.route('/api/clubs/<int:club_id>/update-email', methods=['POST'])
@login_required
def update_club_email(club_id):
    """Update club email"""
    from app.utils.sanitization import sanitize_string
    from app.models.user import create_audit_log

    club = Club.query.get_or_404(club_id)
    user = get_current_user()

    # Check if user is leader or co-leader
    is_leader = club.leader_id == user.id
    is_co_leader = is_user_co_leader(club, user)

    if not is_leader and not is_co_leader and not user.is_admin:
        return jsonify({'error': 'Only club leaders can update email'}), 403

    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'error': 'No JSON data provided',
                'details': 'Request must include JSON data with an email field'
            }), 400

        new_email = data.get('email', '').strip()

        if not new_email:
            return jsonify({
                'error': 'Email is required',
                'details': 'Please provide an email address'
            }), 400

        # Validate email format
        if '@' not in new_email or '.' not in new_email.split('@')[-1]:
            return jsonify({
                'error': 'Invalid email format',
                'details': 'Please provide a valid email address'
            }), 400

        # Sanitize the email
        new_email = sanitize_string(new_email, max_length=120)

        old_email = club.email
        club.email = new_email
        db.session.commit()

        create_audit_log(
            action_type='club_email_update',
            description=f'Club {club.name} email updated from {old_email} to {new_email}',
            user=user,
            target_type='club',
            target_id=club_id,
            category='club'
        )

        return jsonify({
            'success': True,
            'message': 'Email updated successfully',
            'email': new_email
        })
    except Exception as e:
        return jsonify({
            'error': 'Failed to update email',
            'details': str(e)
        }), 400


@clubs_bp.route('/api/club/<int:club_id>/orders', methods=['GET'])
@login_required
def get_club_orders(club_id):
    """Get orders for a club from Airtable"""
    from app.services.airtable import AirtableService

    club = Club.query.get_or_404(club_id)
    user = get_current_user()

    # Verify user is a leader or co-leader
    is_leader = club.leader_id == user.id
    is_co_leader = is_user_co_leader(club, user)

    if not is_leader and not is_co_leader and not user.is_admin:
        return jsonify({'error': 'Not authorized'}), 403

    try:
        # Get orders from Airtable
        airtable_service = AirtableService()
        orders = airtable_service.get_orders_for_club(club.name)

        return jsonify({
            'success': True,
            'club_id': club_id,
            'club_name': club.name,
            'orders': orders,
            'total_orders': len(orders)
        })
    except Exception as e:
        return jsonify({
            'error': 'Failed to fetch orders',
            'orders': [],
            'total_orders': 0
        }), 200


@clubs_bp.route('/api/club/<int:club_id>/cosmetics', methods=['GET'])
@login_required
def get_club_cosmetics(club_id):
    """Get available cosmetics for a club"""
    from app.models.club import ClubCosmetic, MemberCosmetic

    club = Club.query.get_or_404(club_id)
    user = get_current_user()

    # Verify user is a member
    membership = ClubMembership.query.filter_by(club_id=club_id, user_id=user.id).first()
    if not membership and not user.is_admin:
        return jsonify({'error': 'Not authorized'}), 403

    # Get all available cosmetics
    cosmetics = ClubCosmetic.query.filter_by(is_active=True).all()

    cosmetics_data = []
    for cosmetic in cosmetics:
        # Check if club owns this cosmetic
        owned = MemberCosmetic.query.filter_by(
            club_id=club_id,
            cosmetic_id=cosmetic.id
        ).first() is not None

        cosmetics_data.append({
            'id': cosmetic.id,
            'name': cosmetic.name,
            'description': cosmetic.description,
            'cosmetic_type': cosmetic.cosmetic_type,
            'price': cosmetic.price,
            'image_url': cosmetic.image_url,
            'owned': owned
        })

    return jsonify({
        'success': True,
        'cosmetics': cosmetics_data
    })


@clubs_bp.route('/api/club/<int:club_id>/cosmetics/purchase', methods=['POST'])
@login_required
def purchase_cosmetic(club_id):
    """Purchase a cosmetic for the club"""
    from app.models.club import ClubCosmetic, MemberCosmetic
    from app.models.user import create_audit_log

    club = Club.query.get_or_404(club_id)
    user = get_current_user()

    # Only leaders can purchase cosmetics
    if club.leader_id != user.id and not user.is_admin:
        return jsonify({'error': 'Only club leaders can purchase cosmetics'}), 403

    data = request.get_json()
    cosmetic_id = data.get('cosmetic_id')

    if not cosmetic_id:
        return jsonify({'error': 'cosmetic_id is required'}), 400

    cosmetic = ClubCosmetic.query.get_or_404(cosmetic_id)

    # Check if already owned
    existing = MemberCosmetic.query.filter_by(
        club_id=club_id,
        cosmetic_id=cosmetic_id
    ).first()

    if existing:
        return jsonify({'error': 'Cosmetic already owned'}), 400

    # Check if club has enough tokens
    if club.tokens < cosmetic.price:
        return jsonify({'error': 'Insufficient tokens'}), 400

    # Deduct tokens
    club.tokens -= cosmetic.price

    # Grant cosmetic
    member_cosmetic = MemberCosmetic(
        club_id=club_id,
        cosmetic_id=cosmetic_id
    )
    db.session.add(member_cosmetic)

    # Create transaction
    create_club_transaction(
        club_id=club_id,
        transaction_type='debit',
        amount=cosmetic.price,
        description=f'Purchased cosmetic: {cosmetic.name}',
        user_id=user.id,
        reference_type='cosmetic_purchase',
        reference_id=cosmetic_id,
        created_by=user.id
    )

    db.session.commit()

    create_audit_log(
        action_type='cosmetic_purchase',
        description=f'Club {club.name} purchased cosmetic {cosmetic.name}',
        user=user,
        target_type='cosmetic',
        target_id=cosmetic_id,
        category='club'
    )

    return jsonify({
        'success': True,
        'message': 'Cosmetic purchased successfully',
        'remaining_tokens': club.tokens
    })


@clubs_bp.route('/api/club/<int:club_id>/shop-items', methods=['GET'])
@login_required
def get_club_shop_items(club_id):
    """Get shop items available for purchase from Airtable"""
    import requests
    import os

    club = Club.query.get_or_404(club_id)
    user = get_current_user()

    # Verify user is a member or leader
    is_leader = club.leader_id == user.id
    is_co_leader = is_user_co_leader(club, user)

    if not is_leader and not is_co_leader and not user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        # Fetch shop items from Airtable
        shop_base_id = os.environ.get('AIRTABLE_SHOP_BASE_ID', 'app7OFpfZceddfK17')
        shop_table_name = 'Shop%20Items'
        shop_url = f'https://api.airtable.com/v0/{shop_base_id}/{shop_table_name}'

        airtable_token = os.environ.get('AIRTABLE_TOKEN')
        headers = {
            'Authorization': f'Bearer {airtable_token}',
            'Content-Type': 'application/json'
        }

        # Get all records
        response = requests.get(shop_url, headers=headers)

        if response.status_code != 200:
            return jsonify({'error': 'Failed to fetch shop items', 'items': []}), 200

        data = response.json()
        all_records = data.get('records', [])

        # Get disabled items
        disabled_items_url = f"{shop_url}?filterByFormula=NOT({{Enabled}})"
        disabled_response = requests.get(disabled_items_url, headers=headers)

        disabled_record_ids = set()
        if disabled_response.status_code == 200:
            disabled_data = disabled_response.json()
            disabled_records = disabled_data.get('records', [])
            disabled_record_ids = {record['id'] for record in disabled_records}

        items = []
        for record in all_records:
            fields = record.get('fields', {})
            record_id = record['id']

            is_disabled = record_id in disabled_record_ids

            # Extract image URL
            picture_url = None
            if 'Picture' in fields and fields['Picture']:
                if isinstance(fields['Picture'], list) and len(fields['Picture']) > 0:
                    picture_url = fields['Picture'][0].get('url', '')
                elif isinstance(fields['Picture'], str):
                    picture_url = fields['Picture']

            item = {
                'id': record_id,
                'name': fields.get('Item', ''),
                'url': fields.get('Item URL', ''),
                'picture': picture_url,
                'price': fields.get('Rough Total Price', 0),
                'description': fields.get('Description', ''),
                'starred': bool(fields.get('Starred', False)),
                'enabled': not is_disabled,
                'limited': bool(fields.get('Limited', False)),
                'source': fields.get('Source', 'Warehouse')
            }

            # Only include enabled items with required fields
            if item['name'] and item['price'] and item['enabled']:
                items.append(item)

        return jsonify({
            'success': True,
            'items': items,
            'club_tokens': club.tokens
        })

    except Exception as e:
        return jsonify({'error': 'Failed to fetch shop items', 'items': []}), 200


@clubs_bp.route('/api/clubs/<int:club_id>/project-submission', methods=['POST'])
@login_required
def submit_club_project(club_id):
    """Submit a project for the club"""
    from app.models.economy import ProjectSubmission
    from app.models.user import create_audit_log
    from app.utils.sanitization import sanitize_string

    club = Club.query.get_or_404(club_id)
    user = get_current_user()

    # Verify user is a member
    membership = ClubMembership.query.filter_by(club_id=club_id, user_id=user.id).first()
    if not membership:
        return jsonify({'error': 'Not authorized'}), 403

    data = request.get_json()

    name = sanitize_string(data.get('name', ''), max_length=200)
    description = sanitize_string(data.get('description', ''), max_length=2000)
    url = sanitize_string(data.get('url', ''), max_length=500)
    github_url = sanitize_string(data.get('github_url', ''), max_length=500)

    if not name or not url:
        return jsonify({'error': 'Name and URL are required'}), 400

    # Create project submission
    project = ProjectSubmission(
        name=name,
        description=description,
        url=url,
        github_url=github_url,
        club_id=club_id,
        user_id=user.id
    )
    db.session.add(project)
    db.session.commit()

    create_audit_log(
        action_type='project_submission',
        description=f'User {user.username} submitted project "{name}" for club {club.name}',
        user=user,
        target_type='project',
        target_id=project.id,
        category='club'
    )

    return jsonify({
        'success': True,
        'message': 'Project submitted for review',
        'project_id': project.id
    })


@clubs_bp.route('/api/clubs/<int:club_id>/members/<int:user_id>', methods=['DELETE'])
@login_required
def remove_club_member(club_id, user_id):
    """Remove a member from the club or allow member to leave"""
    from app.models.user import create_audit_log

    current_user = get_current_user()
    club = Club.query.get_or_404(club_id)

    # Allow members to remove themselves (leave club)
    is_removing_self = (current_user.id == user_id)

    if is_removing_self:
        # Prevent leader from leaving their own club
        if user_id == club.leader_id:
            return jsonify({'error': 'Club leaders cannot leave their club. Transfer leadership first.'}), 400

        # Prevent co-leaders from leaving (they need to be demoted first)
        co_leader_membership = ClubMembership.query.filter_by(
            club_id=club_id,
            user_id=user_id,
            role='co-leader'
        ).first()
        if co_leader_membership:
            return jsonify({'error': 'Co-leaders cannot leave. Ask the leader to demote you first.'}), 400
    else:
        # Only leaders/co-leaders can remove OTHER members
        is_leader = club.leader_id == current_user.id
        is_co_leader = is_user_co_leader(club, current_user)

        if not is_leader and not is_co_leader and not current_user.is_admin:
            return jsonify({'error': 'Unauthorized: Only club leaders and co-leaders can remove members'}), 403

        # Prevent removing the main leader
        if user_id == club.leader_id:
            return jsonify({'error': 'Cannot remove club leader'}), 400

        # Prevent removing co-leader
        if hasattr(club, 'co_leader_id') and user_id == club.co_leader_id:
            return jsonify({'error': 'Cannot remove co-leader'}), 400

    # Verify the target user is actually a member
    membership = ClubMembership.query.filter_by(club_id=club_id, user_id=user_id).first()
    if not membership:
        return jsonify({'error': 'User is not a member of this club'}), 404

    try:
        db.session.delete(membership)
        db.session.commit()

        if is_removing_self:
            create_audit_log(
                action_type='member_left',
                description=f'User {current_user.username} left club {club.name}',
                user=current_user,
                target_type='club',
                target_id=club_id,
                category='club'
            )
            return jsonify({'success': True, 'message': 'You have left the club successfully'})
        else:
            target_user = membership.user
            create_audit_log(
                action_type='member_removed',
                description=f'User {current_user.username} removed member {target_user.username} from club {club.name}',
                user=current_user,
                target_type='club',
                target_id=club_id,
                category='club'
            )
            return jsonify({'success': True, 'message': 'Member removed successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to remove member'}), 500


@clubs_bp.route('/api/clubs/<int:club_id>/co-leader', methods=['POST', 'DELETE'])
@login_required
def manage_co_leader(club_id):
    """Make a user co-leader or remove co-leader status"""
    from app.models.user import create_audit_log, User
    from app.services.airtable import AirtableService

    current_user = get_current_user()
    club = Club.query.get_or_404(club_id)

    # Only the actual leader can manage co-leaders
    if club.leader_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Unauthorized: Only club leaders can manage co-leaders'}), 403

    data = request.get_json(silent=True) or {}
    airtable_service = AirtableService()

    # Check if this is an email verification step
    if 'step' in data and data['step'] == 'verify_email':
        verification_code = data.get('verification_code', '').strip()

        if not verification_code:
            return jsonify({'error': 'Verification code is required'}), 400

        # Verify the email code
        is_code_valid = airtable_service.verify_email_code(club.leader.email, verification_code)

        if is_code_valid:
            return jsonify({
                'success': True,
                'message': 'Email verification successful! You can now manage co-leaders.',
                'email_verified': True
            })
        else:
            return jsonify({'error': 'Invalid or expired verification code. Please check your email or request a new code.'}), 400

    # Check if this is a request to send verification code
    if 'step' in data and data['step'] == 'send_verification':
        verification_code = airtable_service.send_email_verification(club.leader.email)

        if verification_code:
            return jsonify({
                'success': True,
                'message': 'Verification code sent to your email. Please check your inbox.',
                'verification_sent': True
            })
        else:
            return jsonify({'error': 'Failed to send verification code. Please try again.'}), 500

    if request.method == 'DELETE':
        # Remove co-leader
        user_id = data.get('user_id')
        if not user_id:
            return jsonify({'error': 'User ID is required'}), 400

        # Check for recent email verification in Airtable
        email_verified = airtable_service.check_recent_verification(club.leader.email)
        if not email_verified:
            return jsonify({
                'error': 'Email verification required for this action. Please verify your email first.',
                'requires_verification': True,
                'verification_email': club.leader.email
            }), 403

        # Find the co-leader membership record
        membership = ClubMembership.query.filter_by(club_id=club_id, user_id=user_id, role='co-leader').first()
        if not membership:
            # Provide more helpful error message
            user = User.query.get(user_id)
            if not user:
                return jsonify({'error': 'User not found'}), 404

            # Check if user is a member at all
            any_membership = ClubMembership.query.filter_by(club_id=club_id, user_id=user_id).first()
            if not any_membership:
                return jsonify({'error': f'User {user.username} is not a member of this club'}), 400
            else:
                return jsonify({'error': f'User {user.username} is not a co-leader (current role: {any_membership.role})'}), 400

        try:
            # Update membership role back to member
            membership.role = 'member'
            db.session.commit()

            create_audit_log(
                action_type='co_leader_removed',
                description=f'User {membership.user.username} removed as co-leader from club {club.name}',
                user=current_user,
                target_type='club',
                target_id=club_id,
                category='club'
            )

            return jsonify({'success': True, 'message': 'Co-leader removed successfully'})

        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'Failed to remove co-leader: {str(e)}'}), 500

    else:
        # POST method - Make user co-leader
        user_id = data.get('user_id')

        if not user_id:
            return jsonify({'error': 'User ID is required'}), 400

        # Check for recent email verification in Airtable
        email_verified = airtable_service.check_recent_verification(club.leader.email)
        if not email_verified:
            return jsonify({
                'error': 'Email verification required for this action. Please verify your email first.',
                'requires_verification': True,
                'verification_email': club.leader.email
            }), 403

        # Check if user is a member of the club
        membership = ClubMembership.query.filter_by(club_id=club_id, user_id=user_id).first()
        if not membership and user_id != club.leader_id:
            return jsonify({'error': 'User is not a member of this club'}), 404

        # Check if user is already the leader
        if user_id == club.leader_id:
            return jsonify({'error': 'User is already the club leader'}), 400

        # Check if user is already a co-leader
        existing_co_leader_membership = ClubMembership.query.filter_by(
            club_id=club_id, user_id=user_id, role='co-leader'
        ).first()
        if existing_co_leader_membership:
            return jsonify({'error': 'User is already a co-leader'}), 400

        # Make user co-leader
        try:
            # Update membership role if user is a member
            if membership:
                membership.role = 'co-leader'
            else:
                # Create a new membership record with co-leader role
                new_membership = ClubMembership(
                    user_id=user_id,
                    club_id=club_id,
                    role='co-leader'
                )
                db.session.add(new_membership)

            db.session.commit()

            from app.models.user import User
            promoted_user = User.query.get(user_id)

            create_audit_log(
                action_type='co_leader_added',
                description=f'User {promoted_user.username} promoted to co-leader in club {club.name}',
                user=current_user,
                target_type='club',
                target_id=club_id,
                category='club'
            )

            return jsonify({'success': True, 'message': 'User promoted to co-leader successfully'})

        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'Failed to promote user: {str(e)}'}), 500


@clubs_bp.route('/api/clubs/<int:club_id>/remove-co-leader', methods=['POST'])
@login_required
def remove_co_leader_legacy(club_id):
    """Remove co-leader (legacy route for backwards compatibility)"""
    from app.models.user import create_audit_log, User
    from app.services.airtable import AirtableService

    current_user = get_current_user()
    club = Club.query.get_or_404(club_id)

    # Only the actual leader can remove co-leaders
    if club.leader_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Unauthorized: Only club leaders can remove co-leaders'}), 403

    data = request.get_json(silent=True) or {}
    airtable_service = AirtableService()

    # Check if this is an email verification step
    if 'step' in data and data['step'] == 'verify_email':
        verification_code = data.get('verification_code', '').strip()

        if not verification_code:
            return jsonify({'error': 'Verification code is required'}), 400

        # Verify the email code
        is_code_valid = airtable_service.verify_email_code(club.leader.email, verification_code)

        if is_code_valid:
            return jsonify({
                'success': True,
                'message': 'Email verification successful! You can now remove co-leaders.',
                'email_verified': True
            })
        else:
            return jsonify({'error': 'Invalid or expired verification code. Please check your email or request a new code.'}), 400

    # Check if this is a request to send verification code
    if 'step' in data and data['step'] == 'send_verification':
        verification_code = airtable_service.send_email_verification(club.leader.email)

        if verification_code:
            return jsonify({
                'success': True,
                'message': 'Verification code sent to your email. Please check your inbox.',
                'verification_sent': True
            })
        else:
            return jsonify({'error': 'Failed to send verification code. Please try again.'}), 500

    user_id = data.get('user_id')
    if not user_id:
        return jsonify({'error': 'User ID is required'}), 400

    # Check for recent email verification in Airtable
    email_verified = airtable_service.check_recent_verification(club.leader.email)
    if not email_verified:
        return jsonify({
            'error': 'Email verification required for this action. Please verify your email first.',
            'requires_verification': True,
            'verification_email': club.leader.email
        }), 403

    # Find the co-leader membership record
    membership = ClubMembership.query.filter_by(club_id=club_id, user_id=user_id, role='co-leader').first()
    if not membership:
        # Provide more helpful error message
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        any_membership = ClubMembership.query.filter_by(club_id=club_id, user_id=user_id).first()
        if not any_membership:
            return jsonify({'error': f'User {user.username} is not a member of this club'}), 400
        else:
            return jsonify({'error': f'User {user.username} is not a co-leader (current role: {any_membership.role})'}), 400

    try:
        # Update membership role back to member
        membership.role = 'member'
        db.session.commit()

        create_audit_log(
            action_type='co_leader_removed',
            description=f'User {membership.user.username} removed as co-leader from club {club.name}',
            user=current_user,
            target_type='club',
            target_id=club_id,
            category='club'
        )

        return jsonify({'success': True, 'message': 'Co-leader removed successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to remove co-leader: {str(e)}'}), 500


@clubs_bp.route('/api/clubs/<int:club_id>/join-code', methods=['POST'])
@login_required
def generate_club_join_code(club_id):
    """Generate a new join code for the club"""
    from app.models.user import create_audit_log

    current_user = get_current_user()
    club = Club.query.get_or_404(club_id)

    is_leader = club.leader_id == current_user.id
    is_co_leader = is_user_co_leader(club, current_user)

    if not is_leader and not is_co_leader and not current_user.is_admin:
        return jsonify({'error': 'Only leaders and co-leaders can generate join codes'}), 403

    # Generate new join code using the Club model's method
    club.generate_join_code()
    db.session.commit()

    create_audit_log(
        action_type='join_code_generated',
        description=f'New join code generated for club {club.name}',
        user=current_user,
        target_type='club',
        target_id=club_id,
        category='club'
    )

    return jsonify({
        'success': True,
        'join_code': club.join_code,
        'message': 'Join code generated successfully'
    })


@clubs_bp.route('/api/clubs/<int:club_id>/settings', methods=['PUT'])
@login_required
def update_club_settings(club_id):
    """Update club settings (name, description, location)"""
    from app.models.user import create_audit_log

    current_user = get_current_user()
    club = Club.query.get_or_404(club_id)

    is_leader = club.leader_id == current_user.id
    is_co_leader = is_user_co_leader(club, current_user)

    if not is_leader and not is_co_leader and not current_user.is_admin:
        return jsonify({'error': 'Only leaders and co-leaders can update club settings'}), 403

    data = request.get_json()

    # Update club settings
    if 'name' in data:
        club.name = data['name'].strip()
    if 'description' in data:
        club.description = data['description'].strip() if data['description'] else None
    if 'location' in data:
        club.location = data['location'].strip() if data['location'] else None

    club.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    create_audit_log(
        action_type='club_settings_updated',
        description=f'Updated settings for club {club.name}',
        user=current_user,
        target_type='club',
        target_id=club_id,
        category='club'
    )

    return jsonify({
        'success': True,
        'message': 'Club settings updated successfully',
        'club': {
            'name': club.name,
            'description': club.description,
            'location': club.location
        }
    })


@clubs_bp.route('/api/clubs/<int:club_id>/transfer-leadership', methods=['POST'])
@login_required
def transfer_leadership(club_id):
    """Transfer club leadership to another member"""
    from app.models.user import create_audit_log, User

    current_user = get_current_user()
    club = Club.query.get_or_404(club_id)

    # Only the current leader can transfer leadership
    if club.leader_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Only the club leader can transfer leadership'}), 403

    data = request.get_json()
    step = data.get('step')

    # Handle email verification steps (no-op for now, return success)
    if step == 'send_verification':
        return jsonify({
            'success': True,
            'message': 'Verification code sent to your email'
        })

    if step == 'verify_email':
        return jsonify({
            'success': True,
            'email_verified': True
        })

    # Handle actual leadership transfer
    new_leader_id = data.get('new_leader_id')
    confirmation_text = data.get('confirmation_text', '')

    if not new_leader_id:
        return jsonify({'error': 'New leader ID is required'}), 400

    if confirmation_text.upper() != 'TRANSFER':
        return jsonify({'error': 'Confirmation text must be "TRANSFER"'}), 400

    # Get the new leader
    new_leader = User.query.get(new_leader_id)
    if not new_leader:
        return jsonify({'error': 'New leader not found'}), 404

    # Check if new leader is a member of the club
    membership = ClubMembership.query.filter_by(
        club_id=club_id,
        user_id=new_leader_id
    ).first()

    if not membership:
        return jsonify({'error': 'New leader must be a member of the club'}), 400

    # Transfer leadership
    old_leader_id = club.leader_id
    club.leader_id = new_leader_id

    # Update memberships: remove new leader from members, add old leader as member
    if membership:
        db.session.delete(membership)

    # Add old leader as regular member
    old_membership = ClubMembership(
        club_id=club_id,
        user_id=old_leader_id,
        role='member',
        joined_at=datetime.now(timezone.utc)
    )
    db.session.add(old_membership)
    db.session.commit()

    create_audit_log(
        action_type='leadership_transferred',
        description=f'Leadership transferred from {current_user.username} to {new_leader.username}',
        user=current_user,
        target_type='club',
        target_id=club_id,
        category='club'
    )

    return jsonify({
        'success': True,
        'message': 'Leadership transferred successfully',
        'new_leader': {
            'id': new_leader.id,
            'username': new_leader.username
        }
    })


@clubs_bp.route('/api/clubs/<int:club_id>/transactions', methods=['GET'])
@login_required
def get_club_transactions(club_id):
    """Get all transactions for a club"""
    from app.models.economy import ClubTransaction

    current_user = get_current_user()
    club = Club.query.get_or_404(club_id)

    # Check if user is a member or admin
    is_leader = club.leader_id == current_user.id
    is_co_leader = is_user_co_leader(club, current_user)
    is_member = ClubMembership.query.filter_by(
        club_id=club_id,
        user_id=current_user.id
    ).first() is not None

    if not is_leader and not is_co_leader and not is_member and not current_user.is_admin:
        return jsonify({'error': 'You do not have access to this club'}), 403

    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    transaction_type = request.args.get('type', '')
    date_range = request.args.get('date_range', '')

    # Build query for club transactions (exclude piggy bank transactions)
    query = ClubTransaction.query.filter(
        ClubTransaction.club_id == club_id,
        ~ClubTransaction.transaction_type.in_(['piggy_bank_credit', 'piggy_bank_debit'])
    )

    # Apply type filter
    if transaction_type == 'credit':
        query = query.filter(ClubTransaction.amount > 0)
    elif transaction_type == 'debit':
        query = query.filter(ClubTransaction.amount < 0)
    elif transaction_type == 'grant':
        query = query.filter(ClubTransaction.transaction_type == 'grant')
    elif transaction_type == 'purchase':
        query = query.filter(ClubTransaction.transaction_type == 'purchase')

    # Apply date range filter
    if date_range:
        from datetime import timedelta
        now = datetime.now(timezone.utc)

        if date_range == 'today':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            query = query.filter(ClubTransaction.created_at >= start_date)
        elif date_range == 'week':
            start_date = now - timedelta(days=7)
            query = query.filter(ClubTransaction.created_at >= start_date)
        elif date_range == 'month':
            start_date = now - timedelta(days=30)
            query = query.filter(ClubTransaction.created_at >= start_date)
        elif date_range == 'quarter':
            start_date = now - timedelta(days=90)
            query = query.filter(ClubTransaction.created_at >= start_date)

    # Order by most recent first
    query = query.order_by(ClubTransaction.created_at.desc())

    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    transactions = []
    for transaction in pagination.items:
        transactions.append({
            'id': transaction.id,
            'transaction_type': transaction.transaction_type,
            'amount': transaction.amount,
            'description': transaction.description,
            'balance_after': transaction.balance_after,
            'reference_id': transaction.reference_id,
            'reference_type': transaction.reference_type,
            'created_at': transaction.created_at.isoformat(),
            'user_id': transaction.user_id
        })

    return jsonify({
        'transactions': transactions,
        'club': {
            'id': club.id,
            'name': club.name,
            'balance': club.tokens
        },
        'pagination': {
            'page': pagination.page,
            'per_page': pagination.per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_prev': pagination.has_prev,
            'has_next': pagination.has_next
        }
    })


@clubs_bp.route('/api/clubs/<int:club_id>/piggy-bank/transactions', methods=['GET'])
@login_required
def get_piggy_bank_transactions(club_id):
    """Get piggy bank transactions for a club"""
    from app.models.economy import ClubTransaction

    current_user = get_current_user()
    club = Club.query.get_or_404(club_id)

    # Check if user is a member or admin
    is_leader = club.leader_id == current_user.id
    is_co_leader = is_user_co_leader(club, current_user)
    is_member = ClubMembership.query.filter_by(
        club_id=club_id,
        user_id=current_user.id
    ).first() is not None

    if not is_leader and not is_co_leader and not is_member and not current_user.is_admin:
        return jsonify({'error': 'You do not have access to this club'}), 403

    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    transaction_type = request.args.get('type', '')

    # Build query for piggy bank transactions
    query = ClubTransaction.query.filter(
        ClubTransaction.club_id == club_id,
        ClubTransaction.transaction_type.in_(['piggy_bank_credit', 'piggy_bank_debit'])
    )

    # Apply type filter if specified
    if transaction_type:
        query = query.filter(ClubTransaction.transaction_type == transaction_type)

    # Order by most recent first
    query = query.order_by(ClubTransaction.created_at.desc())

    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    transactions = []
    for transaction in pagination.items:
        transactions.append({
            'id': transaction.id,
            'transaction_type': transaction.transaction_type,
            'amount': transaction.amount,
            'description': transaction.description,
            'balance_after': transaction.balance_after,
            'reference_id': transaction.reference_id,
            'reference_type': transaction.reference_type,
            'created_at': transaction.created_at.isoformat(),
            'user_id': transaction.user_id
        })

    return jsonify({
        'transactions': transactions,
        'club': {
            'id': club.id,
            'name': club.name,
            'piggy_bank_balance': club.piggy_bank_tokens
        },
        'pagination': {
            'page': pagination.page,
            'per_page': pagination.per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_prev': pagination.has_prev,
            'has_next': pagination.has_next
        }
    })
