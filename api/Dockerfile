FROM python:3.9

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

# Install gunicorn as the WSGI server, whitenoise to handle static files and
# django-flexi-settings for smart handling of settings
RUN pip install --no-cache-dir \
      'gunicorn==20.1.0' \
      'whitenoise==5.3.0' \
      'git+https://github.com/stackhpc/django-flexi-settings.git@079359cc1e2d380a15ae6149ebffbcdae8094276#egg=django_flexi_settings'

# Install Gunicorn config
COPY ./etc/gunicorn /etc/gunicorn

# Install dependencies
# Doing this separately by copying only the requirements file enables better use of the build cache
COPY ./requirements.txt /application/
RUN pip install --no-deps --requirement /application/requirements.txt

# Install the application itself
COPY . /application
RUN pip install --no-deps -e /application

# Install application configuration using flexi-settings
ENV DJANGO_SETTINGS_MODULE flexi_settings.settings
ENV DJANGO_FLEXI_SETTINGS_ROOT /etc/azimuth/settings.py
COPY ./etc/azimuth /etc/azimuth
RUN mkdir -p /etc/azimuth/settings.d

# Collect the static files
RUN django-admin collectstatic

# Install the scripts
COPY ./bin /usr/local/bin

# By default, serve the app on port 8080 using the app user
EXPOSE 8080
USER $APP_UID
ENTRYPOINT ["tini", "-g", "--", "azimuth-entrypoint"]
CMD ["gunicorn", "--config", "/etc/gunicorn/conf.py", "azimuth_site.wsgi:application"]
