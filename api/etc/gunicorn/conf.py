# Default settings for gunicorn
# Also allows for overriding with environment variables

import multiprocessing
import os

# Configure the bind address
_host = os.environ.get("GUNICORN_HOST", "0.0.0.0")
_port = os.environ.get("GUNICORN_PORT", "8080")
bind = os.environ.get("GUNICORN_BIND", "{}:{}".format(_host, _port))

# Configure the workers
# Default to a worker per core with two threads per worker
cores = multiprocessing.cpu_count()
workers = int(os.environ.get("GUNICORN_WORKERS", str(cores)))
threads = int(os.environ.get("GUNICORN_THREADS", "2"))
worker_class = os.environ.get("GUNICORN_WORKER_CLASS", "gthread")

# Configure logging
loglevel = os.environ.get("GUNICORN_LOGLEVEL", "info")
errorlog = "-"
# Access logging on by default
if os.environ.get("GUNICORN_ACCESSLOG", "1") in {"1", "yes", "on", "true"}:
    accesslog = "-"
else:
    accesslog = None
# Use the value of the remote ip header in the access log format
access_log_format = "%({x-forwarded-for}i)s %(l)s %(u)s %(t)s \"%(r)s\" %(s)s %(b)s \"%(f)s\" \"%(a)s\""
