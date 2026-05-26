# MediMark AI — Gunicorn Config for Render

import os

bind    = f"0.0.0.0:{os.getenv('PORT', '10000')}"
workers = int(os.getenv('WEB_CONCURRENCY', '1'))
threads = 1
timeout = 120
keepalive = 5
max_requests = 500
max_requests_jitter = 50
loglevel   = 'info'
accesslog  = '-'
errorlog   = '-'
proc_name  = 'medimark_ai'


def on_starting(server):
    """Create tables and seed data on first startup."""
    import subprocess, sys
    server.log.info("Running db-init...")
    subprocess.run(
        [sys.executable, '-m', 'flask', '--app', 'manage', 'db-init'],
        check=False
    )
    server.log.info("Running seed...")
    subprocess.run(
        [sys.executable, '-m', 'flask', '--app', 'manage', 'seed'],
        check=False
    )
    server.log.info("MediMark AI startup complete.")
