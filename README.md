<p align="center">
    <img src="./branding/azimuth-logo-blue-text.png" height="120" />
</p>

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
scientific use cases, including the ability to provision complex platforms via a user-friendly
interface. The platforms range from single-machine workstations with web-based remote console
and desktop access to entire [Slurm](https://slurm.schedmd.com/) clusters and platforms such
as [JupyterHub](https://jupyter.org/hub) that run on [Kubernetes](https://kubernetes.io/) clusters.

Services are exposed to users without consuming floating IPs or requiring SSH keys using the
[Zenith](https://github.com/stackhpc/zenith) application proxy.

Here, you can see Stig Telfer (CEO) and Matt Pryor (Senior Tech Lead and Azimuth project lead) from
[StackHPC](https://www.stackhpc.com/) presenting on Azimuth at the
[OpenInfra Summit in Berlin in 2022](https://openinfra.dev/summit/berlin-2022):

[![Azimuth - self service cloud platforms for reducing time to science](https://img.youtube.com/vi/FRbpI7ZsvMw/0.jpg)](https://www.youtube.com/watch?v=FRbpI7ZsvMw)

Key features of Azimuth include:

  * Supports multiple Keystone authentication methods simultaneously:
    * Username and password, e.g. for LDAP integration.
    * [Keystone federation](https://docs.openstack.org/keystone/latest/admin/federation/introduction.html)
      for integration with existing [OpenID Connect](https://openid.net/connect/) or 
      [SAML 2.0](http://docs.oasis-open.org/security/saml/Post2.0/sstc-saml-tech-overview-2.0.html)
      identity providers.
    * [Application credentials](https://docs.openstack.org/keystone/latest/user/application_credentials.html)
      to allowing the distribution of easily-revokable credentials, e.g. for training, or for integrating
      with clouds that use federation but implementing the required trust is not possible.
  * On-demand Platforms
    * Kubernetes-as-a-Service and Kubernetes-based platforms
      * Operators provide a curated set of templates defining available Kubernetes versions,
        networking configurations, custom addons etc.
      * Uses [Cluster API](https://cluster-api.sigs.k8s.io/) to provision Kubernetes clusters.
      * Supports Kubernetes version upgrades with minimal downtime using rolling node replacement.
      * Supports auto-healing clusters that automatically identify and replace unhealthy nodes.
      * Supports multiple node groups, including auto-scaling node groups.
      * Supports clusters that can utilise GPUs and accelerated networking (e.g. SR-IOV).
      * Installs and configures addons for monitoring + logging, system dashboards and ingress.
      * Provides an application dashboard for deploying Kubernetes-based platforms.
    * Cluster-as-a-Service (CaaS)
      * Operators provide a curated catalog of appliances.
      * Appliances are Ansible playbooks that provision and configure infrastructure.
        * Ansible calls out to [Terraform](https://www.terraform.io/) to provision infrastructure.
      * Uses [AWX](https://github.com/ansible/awx), the open-source version of
        [Ansible Tower](https://docs.ansible.com/ansible-tower/), to manage Ansible playbook execution
        and [Consul](https://www.consul.io/) to store Terraform state.
  * Application proxy using Zenith:
    * Zenith uses SSH tunnels to expose services running behind NAT or a firewall to the internet
      using operator-controlled, random domains.
      * Exposed services do not need to be directly accessible to the internet.
      * Exposed services do not consume a floating IP.
    * Zenith supports an auth callout for proxied services, which Azimuth uses to secure proxied services.
    * Used by Azimuth to provide access to platforms, e.g.:
      * Web-based console / desktop access using [Apache Guacamole](https://guacamole.apache.org/)
      * Monitoring and system dashboards
      * Platform-specific interfaces such as [Jupyter Notebooks](https://jupyter.org/) and
        [Open OnDemand](https://openondemand.org/)
  * Simplified interface for managing basic OpenStack resources:
    * Automatic detection of networking, with auto-provisioning of networks and routers if required.
    * Create, update and delete machines with automatic network detection.
    * Create, delete and attach volumes.
    * Allocate, attach and detach floating IPs.
    * Configure instance-specific security group rules.
      
## Timeline

This section shows a timeline of the significant events in the development of Azimuth:

  * **Autumn 2015**: Development begins on the JASMIN Cloud Portal, targetting JASMIN's VMware cloud.
  * **Spring 2016**: JASMIN Cloud Portal goes into production.
  * **Early 2017**: JASMIN Cloud plans to move to OpenStack, cloud portal v2 development begins.
  * **Summer 2017**: JASMIN's OpenStack cloud goes into production, with the JASMIN Cloud Portal v2.
  * **Spring 2019**: Work begins on JASMIN Cluster-as-a-Service (CaaS) with [StackHPC](https://www.stackhpc.com/).
    * Initial work presented at [UKRI Cloud Workshop](https://cloud.ac.uk/workshops/feb2019/).
  * **Summer 2019**: JASMIN CaaS beta roll out.
  * **Spring 2020**: JASMIN CaaS in use by customers, e.g. the
    [ESA Climate Change Initiative Knowledge Exchange](https://climate.esa.int/en/) project.
    * Production system presented at [UKRI Cloud Workshop](https://cloud.ac.uk/workshops/mar2020/).
  * **Summer 2020**: Production rollout of JASMIN CaaS.
  * **Spring 2021**: StackHPC fork JASMIN Cloud Portal to develop it for [IRIS](https://www.iris.ac.uk/).
  * **Summer 2021**: [Zenith application proxy](https://github.com/stackhpc/zenith) developed and used
    to provide web consoles in Azimuth.
  * **November 2021**: StackHPC fork detached and rebranded to Azimuth.
  * **December 2021**: StackHPC Slurm appliance integrated into CaaS.
  * **January 2022**: Native Kubernetes support added using Cluster API (previously supported by JASMIN as a CaaS appliance).
  * **February 2022**: Support for exposing services in Kubernetes using Zenith.
  * **March 2022**: Support for exposing services in CaaS appliances using Zenith.
  * **June 2022**: Unified platforms interface for Kubernetes and CaaS.

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

Although Azimuth itself is a simple Python + React application that is deployed onto a
Kubernetes cluster using [Helm](https://helm.sh/), a fully functional Azimuth deployment
is much more complex and has many dependencies:

  * A Kubernetes cluster.
  * Persistent storage for Kubernetes configured as a
    [Storage Class](https://kubernetes.io/docs/concepts/storage/storage-classes/).
  * The [NGINX Ingress Controller](https://kubernetes.github.io/ingress-nginx/) for exposing
    services in Kubernetes.
  * AWX for executing Cluster-as-a-Service jobs.
  * Cluster API operators + custom Kubernetes operator for Kubernetes support.
  * Zenith application proxy with authentication callout wired into Azimuth.
  * Consul for Zenith service discovery and Terraform state for CaaS.

To manage this complexity, we use [Ansible](https://www.ansible.com/) to deploy Azimuth
and all of it's dependencies. See the
[Azimuth Deployment Documentation](https://stackhpc.github.io/azimuth-config/) for
more details.

## Setting up a local development environment

See [Setting up a local development environment](./docs/local-development.md).
