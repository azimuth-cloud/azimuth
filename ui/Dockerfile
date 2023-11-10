##
## Build stage
##
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


##
## Runtime stage
##
FROM nginx

# Install Tini
RUN apt-get update && \
    apt-get dist-upgrade && \
    apt-get install -y tini && \
    rm -rf /var/lib/apt/lists/*

# Make changes to the Nginx config related to running as a non-root user and
# running with a read-only root filesystem
#
#   1. Precreate required directories and allow the nginx user to use them
#      When running with a RO filesystem, we will mount writable directories over them
#   2. Remove the user from the config file as it produces a warning when running as non-root
#   3. Use a subdirectory of /var/run for the pid file that is writable by the nginx user
#      When running with a RO filesystem we will mount a writable directory over it,
#      but we don't want to make all of /var/run writable
RUN sed -i '/^user /d' /etc/nginx/nginx.conf && \
    sed -i 's/\/var\/run/\/var\/run\/nginx/' /etc/nginx/nginx.conf && \
    mkdir -p /var/run/nginx && \
    chown nginx:nginx /var/cache/nginx && \
    chown nginx:nginx /var/run/nginx

# Copy the dist folder from the build stage
COPY --from=build /application/dist/ /var/www
# Install the Nginx configuration
COPY ./etc/nginx/conf.d/default.conf /etc/nginx/conf.d/

# The Nginx user has UID 101
USER 101
ENTRYPOINT ["tini", "-g", "--", "/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
