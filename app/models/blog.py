"""
Blog models for posts and categories.
"""
import json
from datetime import datetime, timezone
from extensions import db


class BlogCategory(db.Model):
    __tablename__ = 'blog_category'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)
    slug = db.Column(db.String(120), nullable=False, unique=True, index=True)
    color = db.Column(db.String(7), default='#3B82F6')  # Hex color code
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<BlogCategory {self.name}>'


class BlogPost(db.Model):
    __tablename__ = 'blog_post'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(250), nullable=False, unique=True, index=True)
    content = db.Column(db.Text, nullable=False)
    summary = db.Column(db.Text)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('blog_category.id'), nullable=True)

    # Status and visibility
    status = db.Column(db.String(20), default='draft')  # draft, published, archived
    is_featured = db.Column(db.Boolean, default=False)
    published_at = db.Column(db.DateTime, nullable=True)

    # Content metadata
    banner_image = db.Column(db.Text)  # URL of banner image
    images = db.Column(db.Text)  # JSON array of image URLs
    tags = db.Column(db.Text)    # JSON array of tags

    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    author = db.relationship('User', backref=db.backref('blog_posts', lazy=True))
    category = db.relationship('BlogCategory', backref=db.backref('posts', lazy=True))

    def get_images(self):
        """Get images as a list"""
        if self.images:
            return json.loads(self.images)
        return []

    def set_images(self, images):
        """Set images from a list"""
        if images:
            self.images = json.dumps(images)
        else:
            self.images = None

    def get_tags(self):
        """Get tags as a list"""
        if self.tags:
            return json.loads(self.tags)
        return []

    def set_tags(self, tags):
        """Set tags from a list"""
        if tags:
            self.tags = json.dumps(tags)
        else:
            self.tags = None

    def __repr__(self):
        return f'<BlogPost {self.title}>'
