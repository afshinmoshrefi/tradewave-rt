"""Pull + digest + publish Anne-Marie's morning video briefing.

Usage: .venv/bin/python pull_briefing.py [--force]
Run manually each trading morning for now; becomes a timer once trusted.
"""
import sys

from app import create_app

app = create_app()
with app.app_context():
    post, status = __import__("app.briefing", fromlist=["publish_briefing"]) \
        .publish_briefing(force="--force" in sys.argv)
    print(f"status: {status}")
    if post:
        print(f"post id={post.id} title={post.title!r}")
        print()
        print(post.body)
