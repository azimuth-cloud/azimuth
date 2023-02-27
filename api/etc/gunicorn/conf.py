# Default settings for gunicorn
# Also allows for overriding with environment variables

import multiprocessing
import os

# Configure the bind address
_host = os.environ.get("GUNICORN_HOST", "0.0.0.0")
_port = os.environ.get("GUNICORN_PORT", "8080")
bind = os.environ.get("GUNICORN_BIND", "{}:{}".format(_host, _port))

# Configure the workers and threads
cores = multiprocessing.cpu_count()
# Because we are an I/O bound application, we use more threads per worker than usual
# The total number of threads is 4 * number of cores
# We aim for one worker per core, however we must have a minimum of 2 workers
# This is because if we don't and the only worker _is_ doing CPU work then no other requests get served
# So if we have only 1 core available, we must use 2 workers with 2 threads per worker
workers = int(os.environ.get("GUNICORN_WORKERS", str(max(cores, 2))))
threads = int(os.environ.get("GUNICORN_THREADS", str(int((4 * cores) / workers))))
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
