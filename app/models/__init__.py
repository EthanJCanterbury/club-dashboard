"""
Database models for the Hack Club Dashboard application.
All models are imported here for easy access and to ensure proper SQLAlchemy relationships.
"""

# Import all models so SQLAlchemy can track relationships
from app.models.user import User, Role, Permission, RolePermission, UserRole, AuditLog
from app.models.auth import APIKey, OAuthApplication, OAuthToken, OAuthAuthorizationCode
from app.models.club import Club, ClubMembership, ClubCosmetic, MemberCosmetic
from app.models.club_content import ClubPost, ClubAssignment, ClubMeeting, ClubResource, ClubProject
from app.models.chat import ClubChatMessage
from app.models.attendance import AttendanceSession, AttendanceRecord, AttendanceGuest
from app.models.economy import ClubTransaction, ProjectSubmission, WeeklyQuest, ClubQuestProgress, LeaderboardExclusion
from app.models.gallery import GalleryPost
from app.models.system import SystemSettings, StatusIncident, StatusUpdate
from app.models.shop import ShopItem, Order

# Import helper functions
from app.models.user import create_audit_log, initialize_rbac_system, migrate_existing_users_to_rbac
from app.models.economy import create_club_transaction, get_current_week_start, update_quest_progress

__all__ = [
    # User models
    'User', 'Role', 'Permission', 'RolePermission', 'UserRole', 'AuditLog',
    # Auth models
    'APIKey', 'OAuthApplication', 'OAuthToken', 'OAuthAuthorizationCode',
    # Club models
    'Club', 'ClubMembership', 'ClubCosmetic', 'MemberCosmetic',
    # Club content models
    'ClubPost', 'ClubAssignment', 'ClubMeeting', 'ClubResource', 'ClubProject',
    # Chat models
    'ClubChatMessage',
    # Attendance models
    'AttendanceSession', 'AttendanceRecord', 'AttendanceGuest',
    # Economy models
    'ClubTransaction', 'ProjectSubmission', 'WeeklyQuest', 'ClubQuestProgress', 'LeaderboardExclusion',
    # Gallery models
    'GalleryPost',
    # System models
    'SystemSettings', 'StatusIncident', 'StatusUpdate',
    # Shop models
    'ShopItem', 'Order',
    # Helper functions
    'create_audit_log', 'initialize_rbac_system', 'migrate_existing_users_to_rbac',
    'create_club_transaction', 'get_current_week_start', 'update_quest_progress',
]
