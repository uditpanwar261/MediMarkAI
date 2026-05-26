# MediMark AI — Gunicorn Production Config
# Usage: gunicorn -c gunicorn.conf.py app:app

import multiprocessing
import os

# ── Binding ───────────────────────────────────────────────────
bind    = f"0.0.0.0:{os.getenv('PORT', '5000')}"
backlog = 2048

# ── Workers ───────────────────────────────────────────────────
# 2-4 x number of CPUs recommended for IO-bound Flask apps
workers          = int(os.getenv('GUNICORN_WORKERS',
                                  min(4, (multiprocessing.cpu_count() * 2) + 1)))
worker_class     = 'sync'
worker_connections = 1000
threads          = 2
timeout          = 120          # Important for AI inference (can be slow)
keepalive        = 5
max_requests     = 1000         # Restart workers periodically to avoid memory leaks
max_requests_jitter = 50

# ── Logging ───────────────────────────────────────────────────
loglevel        = os.getenv('LOG_LEVEL', 'info')
accesslog       = '-'           # stdout
errorlog        = '-'           # stderr
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s %(D)sµs'

# ── Process naming ────────────────────────────────────────────
proc_name = 'medimark_ai'

# ── Security ──────────────────────────────────────────────────
limit_request_line   = 4094
limit_request_fields = 100

# ── Hooks ─────────────────────────────────────────────────────
def on_starting(server):
    server.log.info("MediMark AI starting …")

def worker_exit(server, worker):
    server.log.info("Worker %s exiting", worker.pid)
