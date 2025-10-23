"""
Economy helper utilities for the Hack Club Dashboard.
Contains functions for managing club transactions, quests, and token systems.
"""

from datetime import datetime, timedelta
from flask import current_app
from extensions import db
from app.models.club import Club
from app.models.economy import ClubTransaction, WeeklyQuest, ClubQuestProgress


def create_club_transaction(club_id, transaction_type, amount, description,
                            user_id=None, reference_id=None, reference_type=None,
                            created_by=None):
    """
    Create a new club transaction and update the club balance.

    Args:
        club_id: ID of the club
        transaction_type: Type of transaction ('credit', 'debit', 'grant', etc.)
        amount: Amount in tokens (positive for credits, negative for debits)
        description: Description of the transaction
        user_id: Optional ID of the user who triggered the transaction
        reference_id: Optional reference to related record
        reference_type: Optional type of reference ('project', 'shop_order', etc.)
        created_by: Optional ID of admin who created the transaction

    Returns:
        Tuple of (success: bool, result: ClubTransaction or error message)
    """
    try:
        # Use SELECT FOR UPDATE to lock the club record and prevent race conditions
        club = Club.query.filter_by(id=club_id).with_for_update().first()
        if not club:
            return False, "Club not found"

        # For debit transactions, check if sufficient balance exists
        if amount < 0 and club.tokens + amount < 0:
            return False, f"Insufficient balance. Current: {club.tokens} tokens, Required: {abs(amount)} tokens"

        # Update club balance atomically
        club.tokens += amount
        # Keep balance field in sync (convert tokens to USD)
        club.balance = club.tokens / 100.0

        # Create transaction record
        transaction = ClubTransaction(
            club_id=club_id,
            user_id=user_id,
            transaction_type=transaction_type,
            amount=amount,
            description=description,
            balance_after=club.tokens,
            reference_id=reference_id,
            reference_type=reference_type,
            created_by=created_by
        )

        db.session.add(transaction)
        db.session.commit()

        return True, transaction
    except Exception as e:
        db.session.rollback()
        return False, str(e)


def get_current_week_start():
    """
    Get the start of the current week (Monday).

    Returns:
        datetime.date: The date of the current week's Monday
    """
    today = datetime.now().date()
    days_since_monday = today.weekday()
    week_start = today - timedelta(days=days_since_monday)
    return week_start


def update_quest_progress(club_id, quest_type, increment=1):
    """
    Update quest progress for a club and automatically award tokens on completion.

    Args:
        club_id: ID of the club
        quest_type: Type of quest ('gallery_post', 'member_projects', etc.)
        increment: Amount to increment progress by (default: 1)

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        week_start = get_current_week_start()

        # Find the quest by type
        quest = WeeklyQuest.query.filter_by(quest_type=quest_type, is_active=True).first()
        if not quest:
            return False, "Quest not found"

        # Set target based on quest type
        target = 1 if quest_type == 'gallery_post' else 5

        # Get or create quest progress record
        progress_record = ClubQuestProgress.query.filter_by(
            club_id=club_id,
            quest_id=quest.id,
            week_start=week_start
        ).first()

        if not progress_record:
            progress_record = ClubQuestProgress(
                club_id=club_id,
                quest_id=quest.id,
                week_start=week_start,
                progress=0,
                target=target,
                completed=False,
                reward_claimed=False
            )
            db.session.add(progress_record)

        # Update progress
        progress_record.progress += increment
        progress_record.updated_at = datetime.utcnow()

        # Check if quest is completed
        if progress_record.progress >= target and not progress_record.completed:
            progress_record.completed = True
            progress_record.completed_at = datetime.utcnow()

            # Get club with lock to check piggy bank balance
            club = Club.query.filter_by(id=club_id).with_for_update().first()
            if not club:
                current_app.logger.error(f"Club {club_id} not found when completing quest")
                return False, "Club not found"

            # Check if piggy bank has enough tokens
            if club.piggy_bank_tokens >= quest.reward_tokens:
                # Transfer tokens from piggy bank to regular balance
                club.piggy_bank_tokens -= quest.reward_tokens

                # Award tokens to regular balance
                success, transaction = create_club_transaction(
                    club_id=club_id,
                    transaction_type='credit',
                    amount=quest.reward_tokens,
                    description=f'Weekly quest reward: {quest.name} (transferred from piggy bank)',
                    reference_type='weekly_quest',
                    reference_id=str(quest.id),
                    created_by=None
                )

                if success:
                    # Create piggy bank debit transaction record
                    try:
                        piggy_success, piggy_transaction = create_club_transaction(
                            club_id=club_id,
                            transaction_type='piggy_bank_debit',
                            amount=-quest.reward_tokens,
                            description=f'Piggy bank deduction for quest reward: {quest.name}',
                            reference_type='weekly_quest',
                            reference_id=str(quest.id),
                            created_by=None
                        )
                        if piggy_success:
                            progress_record.reward_claimed = True
                            current_app.logger.info(
                                f"Club {club_id} completed quest {quest.name} and received "
                                f"{quest.reward_tokens} tokens from piggy bank "
                                f"(remaining piggy bank: {club.piggy_bank_tokens})"
                            )
                        else:
                            current_app.logger.error(
                                f"Failed to record piggy bank debit transaction: {piggy_transaction}"
                            )
                            # Still mark as claimed since the main transaction succeeded
                            progress_record.reward_claimed = True
                    except Exception as piggy_error:
                        current_app.logger.error(f"Error recording piggy bank transaction: {str(piggy_error)}")
                        # Still mark as claimed since the main transaction succeeded
                        progress_record.reward_claimed = True
                else:
                    # Restore piggy bank tokens if main transaction failed
                    club.piggy_bank_tokens += quest.reward_tokens
                    current_app.logger.error(f"Failed to award quest tokens: {transaction}")
            else:
                # Not enough tokens in piggy bank - don't award anything
                current_app.logger.warning(
                    f"Club {club_id} completed quest {quest.name} but piggy bank has "
                    f"insufficient tokens ({club.piggy_bank_tokens} < {quest.reward_tokens}). "
                    f"No reward given."
                )
                # Still mark as completed but not rewarded
                progress_record.reward_claimed = False

        db.session.commit()
        return True, "Quest progress updated"

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating quest progress: {str(e)}")
        return False, str(e)
