<p align="center">
    <img src="./branding/azimuth-logo-blue-text.png" height="120" />
</p>

# Azimuth Portal

This repository contains the portal component of Azimuth: its Django REST API, React UI and Helm chart.
The portal provides a web interface for managing cloud resources and platforms in an Azimuth deployment.

See the [Azimuth organization overview](https://github.com/azimuth-cloud) for an introduction to the project, its architecture, other components and history.

## Repository contents

| Directory | Contents |
| --- | --- |
| [api](./api) | Django REST API for authentication, cloud resources and platform management. |
| [ui](./ui) | React web interface that calls the API. |
| [chart](./chart) | Helm chart for deploying the portal on Kubernetes. |

In an OpenStack deployment, the API manages cloud resources on behalf of the logged-in user.
It also creates and updates Kubernetes resources for the platform operators to reconcile.

## Setting up a local development environment

The [local development guide](./docs/local-development.md) covers API tests and UI builds.
(These can be run locally without a cloud account)
To work against a running deployment, follow the [OpenStack and Tilt development workflow](https://azimuth-config.readthedocs.io/en/stable/developing/).

## Deploying the portal

The [portal Helm chart](./chart) is one part of an Azimuth deployment.
Follow the [deployment documentation](https://azimuth-config.readthedocs.io/en/stable/) to configure it alongside the other Azimuth components.
Portal configuration options are listed in [chart/values.yaml](./chart/values.yaml).

## Contributing

Documentation fixes, bug reports and code changes are welcome.
See [CONTRIBUTING.md](./CONTRIBUTING.md) for local checks, PR guidance and CI limitations.
