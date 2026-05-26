# MediMark AI — Gunicorn Config for Render free tier
import os

# Render sets PORT automatically
bind    = f"0.0.0.0:{os.getenv('PORT', '10000')}"
workers = int(os.getenv('WEB_CONCURRENCY', '1'))
threads = 1
timeout = 120
keepalive = 5
max_requests = 500
max_requests_jitter = 50
loglevel  = 'info'
accesslog = '-'
errorlog  = '-'
proc_name = 'medimark_ai'
