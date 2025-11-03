"""
Authentication models for API Keys and OAuth.
Includes APIKey, OAuthApplication, OAuthToken, and OAuthAuthorizationCode models.
"""
import json
import secrets
from datetime import datetime, timedelta, timezone
from extensions import db


class APIKey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_used_at = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    rate_limit = db.Column(db.Integer, default=1000)  # requests per hour
    scopes = db.Column(db.Text)  # JSON array of allowed scopes

    user = db.relationship('User', backref=db.backref('api_keys', cascade='all, delete-orphan'))

    def generate_key(self):
        self.key = secrets.token_urlsafe(48)

    def get_scopes(self):
        try:
            return json.loads(self.scopes) if self.scopes else []
        except:
            return []

    def set_scopes(self, scopes_list):
        self.scopes = json.dumps(scopes_list)


class OAuthApplication(db.Model):
    __tablename__ = 'o_auth_application'

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    client_secret = db.Column(db.String(128), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    redirect_uris = db.Column(db.Text)  # JSON array of allowed redirect URIs
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = db.Column(db.Boolean, default=True)
    scopes = db.Column(db.Text)  # JSON array of allowed scopes
    requires_identity_verification = db.Column(db.Boolean, default=False)

    # Relationships
    tokens = db.relationship(
        'OAuthToken',
        primaryjoin='OAuthApplication.id == OAuthToken.application_id',
        back_populates='application',
        cascade='all, delete-orphan'
    )
    authorization_codes = db.relationship(
        'OAuthAuthorizationCode',
        primaryjoin='OAuthApplication.id == OAuthAuthorizationCode.application_id',
        back_populates='application',
        cascade='all, delete-orphan'
    )

    user = db.relationship('User', backref=db.backref('oauth_applications', cascade='all, delete-orphan'))

    def generate_credentials(self):
        self.client_id = secrets.token_urlsafe(32)
        self.client_secret = secrets.token_urlsafe(64)

    def get_redirect_uris(self):
        try:
            return json.loads(self.redirect_uris) if self.redirect_uris else []
        except:
            return []

    def set_redirect_uris(self, uris_list):
        self.redirect_uris = json.dumps(uris_list)

    def get_scopes(self):
        try:
            return json.loads(self.scopes) if self.scopes else []
        except:
            return []

    def set_scopes(self, scopes_list):
        self.scopes = json.dumps(scopes_list)


class OAuthToken(db.Model):
    __tablename__ = 'o_auth_token'

    id = db.Column(db.Integer, primary_key=True)
    access_token = db.Column(db.String(128), unique=True, nullable=False, index=True)
    refresh_token = db.Column(db.String(128), unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    application_id = db.Column(db.Integer, db.ForeignKey('o_auth_application.id'), nullable=False)
    scopes = db.Column(db.Text)  # JSON array of granted scopes
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = db.Column(db.Boolean, default=True)

    user = db.relationship('User', backref=db.backref('oauth_tokens', cascade='all, delete-orphan'))
    application = db.relationship('OAuthApplication', back_populates='tokens', foreign_keys=[application_id])

    def generate_tokens(self):
        self.access_token = secrets.token_urlsafe(48)
        self.refresh_token = secrets.token_urlsafe(48)
        self.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    def get_scopes(self):
        try:
            return json.loads(self.scopes) if self.scopes else []
        except:
            return []

    def set_scopes(self, scopes_list):
        self.scopes = json.dumps(scopes_list)


class OAuthAuthorizationCode(db.Model):
    __tablename__ = 'o_auth_authorization_code'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(128), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    application_id = db.Column(db.Integer, db.ForeignKey('o_auth_application.id'), nullable=False)
    redirect_uri = db.Column(db.String(500), nullable=False)
    scopes = db.Column(db.Text)  # JSON array of requested scopes
    state = db.Column(db.String(500))
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref=db.backref('oauth_authorization_codes', cascade='all, delete-orphan'))
    application = db.relationship('OAuthApplication', back_populates='authorization_codes', foreign_keys=[application_id])

    def generate_code(self):
        self.code = secrets.token_urlsafe(32)
        self.expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    def get_scopes(self):
        try:
            return json.loads(self.scopes) if self.scopes else []
        except:
            return []

    def set_scopes(self, scopes_list):
        self.scopes = json.dumps(scopes_list)
