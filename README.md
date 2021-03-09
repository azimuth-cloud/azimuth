# jasmin-cloud

The `jasmin-cloud` project provides an API for administration of tenancies in
the JASMIN Cloud.

## Documentation

Documentation for `jasmin-cloud` can be found on the [project wiki](https://github.com/cedadev/jasmin-cloud/wiki).

## Quickstart guide

First of all, follow instructions at https://github.com/stackhpc/jasmin-cloud-ui#build-instructions to setup the frontend.

Then place the following inside `/etc/nginx/sites-enabled/default` and `service nginx restart`.

    server {
        listen 80 default_server;
        listen [::]:80 default_server;

        root /var/www/html;

        index index.html index.htm index.nginx-debian.html;

        server_name _;

        location / {
            root /home/ubuntu/jasmin-cloud-ui/dist;
            try_files $uri /index.html;
        }

        location /api {
            proxy_pass http://127.0.0.1:8000/api;
            sub_filter "http://127.0.0.1:8000" $http_host;
            sub_filter_once off;
        }

        location /static {
            proxy_pass http://127.0.0.1:8000/static;
            sub_filter "http://127.0.0.1:8000" $http_host;
            sub_filter_once off;
        }
    }

Finally, start the API server:

    virtualenv venv
    source venv/bin/activate
    pip install -r requirements.txt
    cp jasmin_cloud_site/settings{-local.py,}.py
    vi jasmin_cloud_site/settings.py
    python manage.py runserver
