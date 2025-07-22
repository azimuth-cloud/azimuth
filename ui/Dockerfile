FROM node:14 AS build

# Install the dependencies separately using only the required files
# This allows better use of the build cache
COPY package.json yarn.lock /application/
RUN cd /application && \
    yarn install --frozen-lockfile --network-timeout 3600000 && \
    cd /

# Build the application
COPY . /application
RUN cd /application && \
    yarn build


# This intermediate image is used to fetch the GPG key for the NGINX repo
# without polluting the runtime image with GPG packages
FROM ubuntu:24.04 AS nginx-gpg-key

ENV NGINX_GPG_KEY="2FD21310B49F6B46"

RUN apt-get update && \
    apt-get install -y gnupg2 && \
    rm -rf /var/lib/apt/lists/*

RUN gpg2 --keyserver hkp://keyserver.ubuntu.com:80 --keyserver-options timeout=10 --recv-keys "$NGINX_GPG_KEY" && \
    gpg2 --export "$NGINX_GPG_KEY" > /usr/share/keyrings/nginx-archive-keyring.gpg


FROM ubuntu:24.04

# Copy the GPG key from the intermediate container
COPY --from=nginx-gpg-key /usr/share/keyrings/nginx-archive-keyring.gpg /usr/share/keyrings/

# Install NGINX from the official repository
#
# We make changes to the Nginx config related to running as a non-root user and
# running with a read-only root filesystem
#
#   1. Precreate required directories and allow the nginx user to use them
#      When running with a RO filesystem, we will mount writable directories over them
#   2. Remove the user from the config file as it produces a warning when running as non-root
#   3. Use a subdirectory of /var/run for the pid file that is writable by the nginx user
#      When running with a RO filesystem we will mount a writable directory over it,
#      but we don't want to make all of /var/run writable
RUN echo "Target NGINX version: ${NGINX_VERSION}"
RUN apt-get update && \
    apt-get install --no-install-recommends --no-install-suggests -y ca-certificates tini && \
    echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] https://nginx.org/packages/mainline/ubuntu/ noble nginx" \
      > /etc/apt/sources.list.d/nginx.list && \
    apt-get update && \
    apt-get install --no-install-recommends --no-install-suggests -y "nginx=${NGINX_VERSION}*" && \
    rm -rf /var/lib/apt/lists/* && \
    ln -sf /dev/stdout /var/log/nginx/access.log && \
    ln -sf /dev/stderr /var/log/nginx/error.log && \
    sed -i '/^user /d' /etc/nginx/nginx.conf && \
    sed -i 's/\/run\/nginx.pid/\/var\/run\/nginx\/nginx.pid/' /etc/nginx/nginx.conf && \
    mkdir -p /var/cache/nginx /var/run/nginx && \
    chown nginx:nginx /var/cache/nginx /var/run/nginx

# Copy the dist folder from the build stage
COPY --from=build /application/dist/ /var/www
# Install the Nginx configuration
COPY ./etc/nginx/conf.d/default.conf /etc/nginx/conf.d/

# The Nginx user has UID 999
USER 999
ENTRYPOINT ["tini", "-g", "--"]
CMD ["nginx", "-g", "daemon off;"]
