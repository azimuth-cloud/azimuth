FROM ubuntu:jammy as build-image

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install --no-install-recommends python3.10-venv git curl -y && \
    rm -rf /var/lib/apt/lists/*

# build into a venv we can copy across
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY ./requirements.txt /application/
RUN pip install -U pip setuptools
RUN pip install --no-deps --requirement /application/requirements.txt

COPY . /application
RUN pip install --no-deps /application

# Install the scripts
COPY ./bin /opt/venv/bin

#
# Now the image we run with
#
FROM ubuntu:jammy as run-image

# Add just python tini and some ca-certs
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install --no-install-recommends python3 tini ca-certificates -y && \
    rm -rf /var/lib/apt/lists/*

# Copy accross the venv
COPY --from=build-image /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

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
    apt-get install -y tini && \
    rm -rf /var/lib/apt/lists/*

# Don't buffer stdout and stderr as it breaks realtime logging
ENV PYTHONUNBUFFERED 1

# Install Gunicorn config
COPY ./etc/gunicorn /etc/gunicorn

# Install application configuration using flexi-settings
ENV DJANGO_SETTINGS_MODULE flexi_settings.settings
ENV DJANGO_FLEXI_SETTINGS_ROOT /etc/azimuth/settings.py
COPY ./etc/azimuth /etc/azimuth
RUN mkdir -p /etc/azimuth/settings.d

# Collect the static files
RUN django-admin collectstatic

# By default, serve the app on port 8080 using the app user
EXPOSE 8080
USER $APP_UID
ENTRYPOINT ["tini", "-g", "--", "azimuth-entrypoint"]
CMD ["gunicorn", "--config", "/etc/gunicorn/conf.py", "azimuth_site.wsgi:application"]
