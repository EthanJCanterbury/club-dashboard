"""
Chat routes blueprint for the Hack Club Dashboard.
Handles club chat messaging and image uploads.
"""

from flask import Blueprint, jsonify, request
from datetime import datetime, timezone
from extensions import db, limiter
from app.decorators.auth import login_required
from app.utils.auth_helpers import get_current_user
from app.utils.sanitization import sanitize_string
from app.utils.security import validate_input_with_security, get_real_ip, log_security_event
from app.models.club import Club, ClubMembership
from app.models.chat import ClubChatMessage
from app.models.user import User

chat_bp = Blueprint('chat', __name__)


@chat_bp.route('/api/club/<int:club_id>/chat/messages', methods=['GET', 'POST'])
@login_required
@limiter.limit("60 per minute")
def chat_messages(club_id):
    """Get or post chat messages for a club"""
    user = get_current_user()
    club = Club.query.get_or_404(club_id)

    # Verify user is a member
    membership = ClubMembership.query.filter_by(
        club_id=club_id,
        user_id=user.id
    ).first()

    if not membership:
        return jsonify({'error': 'Not authorized'}), 403

    if request.method == 'GET':
        # Get messages
        limit = request.args.get('limit', 50, type=int)
        limit = min(limit, 100)  # Max 100 messages

        before_id = request.args.get('before', type=int)

        query = ClubChatMessage.query.filter_by(club_id=club_id)

        if before_id:
            query = query.filter(ClubChatMessage.id < before_id)

        messages = query.order_by(
            ClubChatMessage.created_at.desc()
        ).limit(limit).all()

        # Reverse to get chronological order
        messages.reverse()

        messages_data = []
        for msg in messages:
            messages_data.append({
                'id': msg.id,
                'user_id': msg.user_id,
                'username': msg.user.username,
                'first_name': msg.user.first_name,
                'last_name': msg.user.last_name,
                'message': msg.message,
                'image_url': msg.image_url,
                'created_at': msg.created_at.isoformat() if msg.created_at else None
            })

        return jsonify({
            'success': True,
            'messages': messages_data,
            'club_id': club_id,
            'club_name': club.name
        })

    elif request.method == 'POST':
        # Post a new message
        data = request.get_json()
        message_text = data.get('message', '').strip()
        image_url = data.get('image_url', '').strip()

        if not message_text and not image_url:
            return jsonify({'error': 'Message or image required'}), 400

        # Validate message content
        if message_text:
            # Use security validation
            is_valid, validated_message = validate_input_with_security(
                message_text,
                field_name='chat_message',
                user=user,
                max_length=2000
            )

            if not is_valid:
                return jsonify({'error': validated_message}), 400

            message_text = validated_message

        # Create message
        chat_message = ClubChatMessage(
            club_id=club_id,
            user_id=user.id,
            message=message_text,
            image_url=image_url
        )

        db.session.add(chat_message)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': {
                'id': chat_message.id,
                'user_id': chat_message.user_id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'message': chat_message.message,
                'image_url': chat_message.image_url,
                'created_at': chat_message.created_at.isoformat() if chat_message.created_at else None
            }
        }), 201


@chat_bp.route('/api/club/<int:club_id>/chat/messages/<int:message_id>', methods=['PUT', 'DELETE'])
@login_required
@limiter.limit("30 per minute")
def chat_message_operations(club_id, message_id):
    """Edit or delete a chat message"""
    user = get_current_user()
    club = Club.query.get_or_404(club_id)

    # Verify user is a member
    membership = ClubMembership.query.filter_by(
        club_id=club_id,
        user_id=user.id
    ).first()

    if not membership:
        return jsonify({'error': 'Not authorized'}), 403

    # Get the message
    message = ClubChatMessage.query.filter_by(
        id=message_id,
        club_id=club_id
    ).first_or_404()

    # Verify user owns the message or is a leader
    is_leader = (user.id == club.leader_id or user.id == club.co_leader_id)
    if message.user_id != user.id and not is_leader and not user.is_admin:
        return jsonify({'error': 'Not authorized to modify this message'}), 403

    if request.method == 'PUT':
        # Edit message
        data = request.get_json()
        new_message_text = data.get('message', '').strip()

        if not new_message_text:
            return jsonify({'error': 'Message text required'}), 400

        # Validate message content
        is_valid, validated_message = validate_input_with_security(
            new_message_text,
            field_name='chat_message',
            user=user,
            max_length=2000
        )

        if not is_valid:
            return jsonify({'error': validated_message}), 400

        message.message = validated_message

        db.session.commit()

        return jsonify({
            'success': True,
            'message': {
                'id': message.id,
                'message': message.message,
                'created_at': message.created_at.isoformat() if message.created_at else None
            }
        })

    elif request.method == 'DELETE':
        # Delete message
        db.session.delete(message)
        db.session.commit()

        # Log deletion
        log_security_event(
            'CHAT_MESSAGE_DELETED',
            f'User {user.username} deleted message {message_id} in club {club_id}',
            user_id=user.id,
            ip_address=get_real_ip()
        )

        return jsonify({
            'success': True,
            'message': 'Message deleted'
        })


@chat_bp.route('/api/club/<int:club_id>/chat/upload-image', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def upload_chat_image(club_id):
    """Upload an image for chat"""
    user = get_current_user()
    club = Club.query.get_or_404(club_id)

    # Verify user is a member
    membership = ClubMembership.query.filter_by(
        club_id=club_id,
        user_id=user.id
    ).first()

    if not membership:
        return jsonify({'error': 'Not authorized'}), 403

    # Check if file was uploaded
    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400

    file = request.files['image']

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    # Validate file type
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    if not ('.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
        return jsonify({'error': 'Invalid file type. Allowed: PNG, JPG, GIF, WEBP'}), 400

    # TODO: Implement actual file upload to cloud storage (S3, Cloudinary, etc.)
    # For now, return a placeholder
    image_url = f'https://placeholder.example.com/chat-image-{club_id}-{user.id}.jpg'

    return jsonify({
        'success': True,
        'image_url': image_url
    })
