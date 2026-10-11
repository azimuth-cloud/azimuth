# Build args which are used in FROM statements must come before
# All FROM statements in the dockerfile.
ARG FINAL_IMAGE_TAG=nonroot

############################
## INSTALL AND BUILD APP ###
############################
FROM ghcr.io/astral-sh/uv:trixie AS build
# Note: distro should match final image stage to ensure build compat. trixie=debian13
# Non-slim version required for git.

# These env vars setup UV for a docker installation as opposed to
# the defaults which are optimised for local development.
# https://docs.astral.sh/uv/guides/integration/docker/#optimizations
# https://docs.astral.sh/uv/reference/environment/
ENV UV_NO_DEV=1 \
    UV_NO_EDITABLE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_FROZEN=1 \
    UV_CACHE_DIR=/uv-cache/ \
    UV_PYTHON_INSTALL_DIR=/python \
    UV_PYTHON_INSTALL_BIN=0 \
    UV_PYTHON_PREFERENCE=only-managed

WORKDIR /app-source

### INSTALL PINNED PYTHON ###
# https://docs.astral.sh/uv/guides/install-python/
COPY .python-version /app-source
RUN uv python install \
    && chmod -R ugo=rX /python

### INSTALL PROJECT INTO VENV ###
# uv sync --active makes uv (re)create the currently
# active venv and install into it.
ENV VIRTUAL_ENV=/app

### INSTALL PINNED DEPENDENCIES ###
# --frozen makes uv install the versions which are pinned in uv.lock
# Installing the dependencies first optimizes caching so if the app
# changes but not the deps there is no need to rebuild this.
COPY uv.lock pyproject.toml /app-source
RUN --mount=type=cache,target=/uv-cache/ \
    uv sync --active \
            --frozen \
            --no-install-project \
    && chmod -R ugo=rX /app

### INSTALL THE PROJECT ###
# Then install the app.
COPY . /app-source
RUN --mount=type=cache,target=/uv-cache/ \
    uv sync --active \
            --frozen \
    && chmod -R ugo=rX /app

### INSTALL CONFIG ###
COPY ./api/etc/gunicorn /etc/gunicorn
COPY ./api/etc/azimuth /etc/azimuth
RUN chmod -R ugo=rX /etc/azimuth \
    && chmod -R ugo=rX /etc/gunicorn

### PERFORM SETUP TASKS ###
# Collect the static files into /var/azimuth
ENV DJANGO_SETTINGS_MODULE=flexi_settings.settings \
    DJANGO_FLEXI_SETTINGS_ROOT=/etc/azimuth/settings.py
RUN /app/bin/django-admin collectstatic \
    && chmod -R ugo=rX /var/azimuth

###########################
### COMPILE FINAL IMAGE ###
###########################
FROM gcr.io/distroless/cc-debian13:$FINAL_IMAGE_TAG AS final
# $FINAL_IMAGE_TAG is a build arg defined at the top.
# In the final build this should be "nonroot".
# For debugging, debug-nonroot
# Note: distro should match build stage trixie=debian13

### COPY IN APP ###
# Files copied in must have their modes set so the nonroot user may read them.
# You cannot do it here, chmod does not exist, and the docker flag doesn't work with podman yet.
# Should be ordered the same as the stages are created above, to allow the parallel build to keep up.
COPY --from=build /python /python
COPY --from=build /app /app
COPY --from=build /etc/gunicorn /etc/gunicorn
COPY --from=build /etc/azimuth /etc/azimuth
COPY --from=build /var/azimuth /var/azimuth

### SETUP APPLICATION RUNTIME ###
# Install application configuration using flexi-settings
ENV DJANGO_SETTINGS_MODULE=flexi_settings.settings \
    DJANGO_FLEXI_SETTINGS_ROOT=/etc/azimuth/settings.py
# By default, serve the app on port 8080
EXPOSE 8080
CMD ["/app/bin/gunicorn", "--config", "/etc/gunicorn/conf.py", "azimuth_site.wsgi:application"]
