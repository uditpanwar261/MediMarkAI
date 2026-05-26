# MediMark AI — Gunicorn Config
# Optimised for Render free tier (512MB RAM, shared CPU)

import os
import multiprocessing

# Render injects PORT env var
bind    = f"0.0.0.0:{os.getenv('PORT', '5000')}"
backlog = 512

# Render free tier: 512MB RAM — keep workers low
workers          = int(os.getenv('GUNICORN_WORKERS', '2'))
worker_class     = 'sync'
threads          = 1
timeout          = 120        # AI inference can take time
keepalive        = 5
max_requests     = 500
max_requests_jitter = 50

# Logging
loglevel        = 'info'
accesslog       = '-'
errorlog        = '-'
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(D)sµs'

proc_name = 'medimark_ai'

def on_starting(server):
    server.log.info("MediMark AI starting on port %s ...", os.getenv('PORT', '5000'))
