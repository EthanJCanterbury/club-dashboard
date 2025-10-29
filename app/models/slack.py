"""
Slack integration models for club channels.
"""
from datetime import datetime, timezone
from extensions import db


class ClubSlackSettings(db.Model):
    __tablename__ = 'club_slack_settings'

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id'), nullable=False)
    channel_id = db.Column(db.String(255))
    channel_name = db.Column(db.String(255))
    is_public = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    club = db.relationship('Club', backref=db.backref('slack_settings', uselist=False, cascade='all, delete-orphan'))

    def to_dict(self):
        return {
            'id': self.id,
            'club_id': self.club_id,
            'channel_id': self.channel_id,
            'channel_name': self.channel_name,
            'is_public': self.is_public,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
