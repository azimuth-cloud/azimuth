# azimuth  <!-- omit in toc -->

Azimuth provides a self-service portal for managing cloud resources, with a focus on simplifying
the use of cloud for high-performance computing (HPC) and artificial intelligence (AI) use cases.

It is currently capable of targeting [OpenStack](https://www.openstack.org/) clouds.

## Contents  <!-- omit in toc -->

- [Introduction](#introduction)
- [Timeline](#timeline)
- [Architecture](#architecture)
- [Deploying Azimuth](#deploying-azimuth)
- [Setting up a local development environment](#setting-up-a-local-development-environment)

## Introduction

Azimuth was originally developed for the [JASMIN Cloud](https://jasmin.ac.uk/) as a simplified
version of the [OpenStack Horizon](https://docs.openstack.org/horizon/latest/) dashboard, with the
aim of reducing complexity for less technical users.

It has since grown to offer additional functionality with a continued focus on simplicity for
scientific use cases, including the ability to provision complex, multi-machine appliances
(e.g. [Slurm](https://slurm.schedmd.com/) clusters) via a user-friendly interface (referred
to as Cluster-as-a-Service, or CaaS). It can also provision servers with authenticated web consoles
and web-based remote desktops without consuming floating IPs or requiring SSH keys using the
[Zenith](https://github.com/stackhpc/zenith) application proxy.

Key features of Azimuth include:

  * Supports multiple Keystone authentication methods:
    * Username and password, e.g. for LDAP integration.
    * [Keystone federation](https://docs.openstack.org/keystone/latest/admin/federation/introduction.html)
      for integration with existing [OpenID Connect](https://openid.net/connect/) or 
      [SAML 2.0](http://docs.oasis-open.org/security/saml/Post2.0/sstc-saml-tech-overview-2.0.html)
      identity providers.
  * Simplified interface for managing OpenStack resources:
    * Automatic detection of networking, with auto-provisioning of networks and routers if required.
    * Create, update and delete machines with automatic network detection.
    * Create, delete and attach volumes.
    * Allocate, attach and detach floating IPs.
    * Configure instance-specific security group rules.
  * Application proxy using Zenith:
    * Zenith uses SSH tunnels to expose services running behind NAT or a firewall to the internet
      using operator-controlled, random domains.
      * Exposed services do not need to be directly accessible to the internet.
      * Exposed services do not consume a floating IP.
    * Zenith supports an auth callout for proxied services, which Azimuth uses to secure proxied services.
    * Used by Azimuth to provide:
      * Authenticated web consoles for VMs using [Apache Guacamole](https://guacamole.apache.org/).
      * Web-based dashboards for clusters provisioned using the Kubernetes and Cluster-as-a-Service systems.
  * Kubernetes-as-a-Service
    * Operators configure a set of supported templates defining available Kubernetes versions,
      networking configurations, custom addons etc.
    * Uses [Cluster API](https://cluster-api.sigs.k8s.io/) to provision Kubernetes clusters.
    * Supports Kubernetes version upgrades with minimal downtime using rolling node replacement.
    * Supports auto-healing clusters that automatically identify and replace unhealthy nodes.
    * Supports multiple node groups, including auto-scaling node groups.
    * Transparently configures clusters so that they can make use of GPUs and accelerated networking (e.g. SR-IOV).
    * Installs and configures addons for monitoring, logging and application provisioning.
  * Cluster-as-a-Service (CaaS)
    * Operators provide a catalog of appliances that can be deployed via the Azimuth portal.
    * Appliances are Ansible playbooks that provision and configure infrastructure.
    * Ansible calls out to either [Terraform](https://www.terraform.io/) (recommended) or
      [OpenStack Heat](https://docs.openstack.org/heat/latest/) to provision infrastructure.
    * Uses [AWX](https://github.com/ansible/awx), the open-source version of
      [Ansible Tower](https://docs.ansible.com/ansible-tower/), to manage Ansible playbook execution
      and [Consul](https://www.consul.io/) to store Terraform state.
      
## Timeline

This section shows a timeline of the significant events in the development of Azimuth:

  * **Autumn 2015**: Development begins on the JASMIN Cloud Portal, targetting JASMIN's VMware cloud.
  * **Spring 2016**: JASMIN Cloud Portal goes into production.
  * **Early 2017**: JASMIN Cloud plans to move to OpenStack, cloud portal v2 development begins.
  * **Summer 2017**: JASMIN's OpenStack cloud goes into production, with the JASMIN Cloud Portal v2.
  * **Spring 2019**: Work begins on JASMIN Cluster-as-a-Service with [StackHPC](https://www.stackhpc.com/).
    * Initial work presented at [UKRI Cloud Workshop](https://cloud.ac.uk/workshops/feb2019/).
  * **Summer 2019**: JASMIN Cluster-as-a-Service beta roll out.
  * **Spring 2020**: JASMIN Cluster-as-a-Service adopted by customers, e.g. the
    [ESA Climate Change Initiative Knowledge Exchange](https://climate.esa.int/en/) project.
    * Production system presented at [UKRI Cloud Workshop](https://cloud.ac.uk/workshops/mar2020/).
  * **Summer 2020**: Production rollout of JASMIN Cluster-as-a-Service.
  * **Spring 2021**: StackHPC fork JASMIN Cloud Portal to develop it for [IRIS](https://www.iris.ac.uk/).
  * **Summer 2021**: [Zenith application proxy](https://github.com/stackhpc/zenith) developed and used
    to provide web consoles in Azimuth.
  * **November 2021**: StackHPC fork detached and rebranded to Azimuth.
  * **December 2021**: StackHPC Slurm appliance integrated into Cluster-as-a-Service.
  * **January 2022**: Native Kubernetes support added using Cluster API.
  * **February 2022**: Support for exposing services in Kubernetes using Zenith.
  * **March 2022**: Support for exposing services in Cluster-as-a-Service appliances using Zenith.

## Architecture

Azimuth consists of a [Python](https://www.python.org/) backend providing a REST API (different
to the OpenStack API) and a Javascript frontend written in [React](https://reactjs.org/).

At it's core, Azimuth is just an OpenStack client. When a user authenticates with Azimuth, it
negotiates with [Keystone](https://docs.openstack.org/keystone/latest/) (using either
username/password or federation) to obtain a token which is stored in a cookie in the user's
browser. Azimuth then uses this token to talk to the OpenStack API on behalf of the user when
the user submits requests to the Azimuth API via the Azimuth UI.

![Azimuth Core Architecture Diagram](./docs/architecture-core.png?raw=true)

When the Zenith application proxy and Cluster-as-a-Service (CaaS) subsystems are enabled, this
picture becomes more complicated - see [Azimuth Architecture](./docs/architecture.md) for more
details.

## Deploying Azimuth

Although it is not required for the core functionality, deploying to
[Kubernetes](https://kubernetes.io/) using [Helm](https://helm.sh/) is the only officially
supported and maintained deployment mechanism. Kubernetes is also required for some of the
optional functionality, e.g. the Zenith application proxy.

This documentation assumes that you already have a Kubernetes cluster available for your
Azimuth deployment that has an
[Ingress Controller](https://kubernetes.io/docs/concepts/services-networking/ingress-controllers/)
installed. If you intend to use the Zenith application proxy, this must be the
[NGINX Ingress Controller](https://kubernetes.github.io/ingress-nginx/) specifically - see
the [Zenith Deployment prerequisites](https://github.com/stackhpc/zenith/blob/main/docs/server.md#prerequisites).

The following is a minimal Helm values file to deploy the core Azimuth portal locally using
[Minikube](https://minikube.sigs.k8s.io/docs/) (tested on Mac OSX with the Docker driver):

> **NOTE**
>
> This configuration will only work if the target OpenStack cloud uses username/password
> authentication.

```yaml
# values.yaml

ingress:
  # Use a nip.io domain pointing to localhost
  host: azimuth.127-0-0-1.nip.io
  # Disable TLS
  tls:
    enabled: false

provider:
  openstack:
    # Point Azimuth at the Keystone URL for the target OpenStack cloud
    authUrl: https://openstack.example-cloud.org:5000/v3
```

Then to deploy Azimuth into Minikube:

```sh
# Make sure your Minikube cluster is running
minikube start
# Make sure that the ingress controller is enabled
minikube addons enable ingress

# Install the Azimuth Helm repository
helm repo add azimuth https://stackhpc.github.io/azimuth
helm repo update

# Get the latest version of the master branch
VN="$(helm search repo azimuth --devel --versions | grep master | head -n 1 | awk '{ print $2; }')"

# Install Azimuth
helm upgrade azimuth azimuth/azimuth --version $VN -i -f values.yaml

# Expose the ingress resource using minikube tunnel
minikube tunnel
```

Azimuth should then be available at `http://azimuth.127-0-0-1.nip.io`.

For more detail on deploying and configuring Azimuth, e.g. configuring TLS, the Zenith application
proxy and Cluster-as-a-Service, see [Deploying and configuring Azimuth](./docs/deploy-configure.md).

## Setting up a local development environment

See [Setting up a local development environment](./docs/local-development.md).
