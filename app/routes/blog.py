"""
Blog routes blueprint for the Hack Club Dashboard.
Handles blog posts viewing, creation, editing, and deletion.
"""

from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from datetime import datetime, timezone
from extensions import db
from app.decorators.auth import login_required, admin_required
from app.utils.auth_helpers import get_current_user
from app.utils.sanitization import sanitize_string
from app.utils.formatting import markdown_to_html
from app.models.blog import BlogPost, BlogCategory
from app.models.user import User

blog_bp = Blueprint('blog', __name__)


@blog_bp.route('/blog')
def blog_index():
    """List all blog posts"""
    # Get published posts only (unless admin)
    user = get_current_user()

    if user and user.is_admin:
        posts = BlogPost.query.order_by(BlogPost.published_at.desc()).all()
    else:
        posts = BlogPost.query.filter_by(
            is_published=True
        ).order_by(BlogPost.published_at.desc()).all()

    categories = BlogCategory.query.all()

    return render_template('blog/index.html', posts=posts, categories=categories)


@blog_bp.route('/blog/<slug>')
def blog_post(slug):
    """View a single blog post"""
    post = BlogPost.query.filter_by(slug=slug).first_or_404()

    # Check if post is published (unless admin)
    user = get_current_user()
    if not post.is_published and (not user or not user.is_admin):
        abort(404)

    # Convert markdown content to HTML
    if post.content:
        post.html_content = markdown_to_html(post.content)

    return render_template('blog/post.html', post=post)


@blog_bp.route('/blog/create', methods=['GET', 'POST'])
@login_required
@admin_required
def blog_create():
    """Create a new blog post"""
    user = get_current_user()

    if request.method == 'POST':
        title = sanitize_string(request.form.get('title', ''), max_length=200)
        slug = sanitize_string(request.form.get('slug', ''), max_length=200)
        content = request.form.get('content', '')
        excerpt = sanitize_string(request.form.get('excerpt', ''), max_length=500)
        category_id = request.form.get('category_id')
        is_published = request.form.get('is_published') == 'on'

        if not title or not slug or not content:
            flash('Title, slug, and content are required.', 'error')
            return render_template('blog/create.html', categories=BlogCategory.query.all())

        # Check if slug already exists
        if BlogPost.query.filter_by(slug=slug).first():
            flash('A post with this slug already exists.', 'error')
            return render_template('blog/create.html', categories=BlogCategory.query.all())

        # Create new post
        post = BlogPost(
            title=title,
            slug=slug,
            content=content,
            excerpt=excerpt,
            author_id=user.id,
            category_id=category_id if category_id else None,
            is_published=is_published,
            published_at=datetime.now(timezone.utc) if is_published else None
        )

        db.session.add(post)
        db.session.commit()

        flash('Blog post created successfully!', 'success')
        return redirect(url_for('blog.blog_post', slug=post.slug))

    categories = BlogCategory.query.all()
    return render_template('blog/create.html', categories=categories)


@blog_bp.route('/blog/<slug>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def blog_edit(slug):
    """Edit a blog post"""
    post = BlogPost.query.filter_by(slug=slug).first_or_404()

    if request.method == 'POST':
        post.title = sanitize_string(request.form.get('title', ''), max_length=200)
        new_slug = sanitize_string(request.form.get('slug', ''), max_length=200)
        post.content = request.form.get('content', '')
        post.excerpt = sanitize_string(request.form.get('excerpt', ''), max_length=500)
        category_id = request.form.get('category_id')
        is_published = request.form.get('is_published') == 'on'

        if not post.title or not new_slug or not post.content:
            flash('Title, slug, and content are required.', 'error')
            return render_template('blog/edit.html', post=post, categories=BlogCategory.query.all())

        # Check if slug changed and is unique
        if new_slug != post.slug:
            if BlogPost.query.filter_by(slug=new_slug).first():
                flash('A post with this slug already exists.', 'error')
                return render_template('blog/edit.html', post=post, categories=BlogCategory.query.all())
            post.slug = new_slug

        post.category_id = category_id if category_id else None

        # Update published status
        if is_published and not post.is_published:
            post.is_published = True
            post.published_at = datetime.now(timezone.utc)
        elif not is_published and post.is_published:
            post.is_published = False
            post.published_at = None

        post.updated_at = datetime.now(timezone.utc)

        db.session.commit()

        flash('Blog post updated successfully!', 'success')
        return redirect(url_for('blog.blog_post', slug=post.slug))

    categories = BlogCategory.query.all()
    return render_template('blog/edit.html', post=post, categories=categories)


@blog_bp.route('/blog/<slug>/delete', methods=['POST'])
@login_required
@admin_required
def blog_delete(slug):
    """Delete a blog post"""
    post = BlogPost.query.filter_by(slug=slug).first_or_404()

    db.session.delete(post)
    db.session.commit()

    flash('Blog post deleted successfully.', 'success')
    return redirect(url_for('blog.blog_index'))
