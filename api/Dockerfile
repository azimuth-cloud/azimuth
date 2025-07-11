FROM ubuntu:24.04 AS python-builder

RUN apt-get update && \
    apt-get install -y git python3 python3-venv && \
    rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /venv && \
    /venv/bin/pip install -U pip setuptools

COPY requirements.txt /app/requirements.txt
RUN  /venv/bin/pip install --requirement /app/requirements.txt

# Django fails to load templates if this is installed the "regular" way
# If we use an editable mode install then it works
COPY . /app
RUN /venv/bin/pip install -e /app


FROM ubuntu:24.04

# Don't buffer stdout and stderr as it breaks realtime logging
ENV PYTHONUNBUFFERED 1

# Make httpx and requests use the system trust roots
# By default, this means we use the roots baked into the image
ENV SSL_CERT_FILE /etc/ssl/certs/ca-certificates.crt
ENV REQUESTS_CA_BUNDLE /etc/ssl/certs/ca-certificates.crt

# Create the user that will be used to run the app
ENV APP_UID 1001
ENV APP_GID 1001
ENV APP_USER app
ENV APP_GROUP app
RUN groupadd --gid $APP_GID $APP_GROUP && \
    useradd \
      --no-create-home \
      --no-user-group \
      --gid $APP_GID \
      --shell /sbin/nologin \
      --uid $APP_UID \
      $APP_USER

RUN apt-get update && \
    apt-get install --no-install-recommends --no-install-suggests -y ca-certificates python3 && \
    rm -rf /var/lib/apt/lists/*

COPY --from=python-builder /venv /venv
COPY --from=python-builder /app /app

# Install Gunicorn config
COPY ./etc/gunicorn /etc/gunicorn

# Install application configuration using flexi-settings
ENV DJANGO_SETTINGS_MODULE flexi_settings.settings
ENV DJANGO_FLEXI_SETTINGS_ROOT /etc/azimuth/settings.py
COPY ./etc/azimuth /etc/azimuth
RUN mkdir -p /etc/azimuth/settings.d

# Collect the static files
RUN /venv/bin/django-admin collectstatic

# By default, serve the app on port 8080 using the app user
EXPOSE 8080
USER $APP_UID
CMD ["/venv/bin/gunicorn", "--config", "/etc/gunicorn/conf.py", "azimuth_site.wsgi:application"]
