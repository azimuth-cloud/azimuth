# Azimuth Architecture  <!-- omit in toc -->

This document describes the architecture of Azimuth in detail, including the integration with
the [Zenith application proxy](https://github.com/stackhpc/zenith) and the Cluster-as-a-Service
subsystem.

Azimuth consists of a [Python](https://www.python.org/) backend providing a REST API (different
to the OpenStack API) and a Javascript frontend written in [React](https://reactjs.org/). The
primary function of Azimuth is to be an OpenStack client, providing a simplified interface for
creating servers and volumes and making the networking as transparent as possible.

The application proxy and Cluster-as-a-Service subsystems provide additional functionality
above and beyond that provided by OpenStack, such as secure web consoles and the ability to
provision complex, multi-machine appliances.

> **NOTE**
>
> Before reading this document, please make sure you are familiar with the
> [Zenith Architecture](https://github.com/stackhpc/azimuth/blob/master/docs/architecture.md).
>
> This document treats Zenith as a black box, focusing on Azimuth's integration points.

## Contents  <!-- omit in toc -->

- [Architecture Diagram](#architecture-diagram)
- [Network discovery and auto-creation](#network-discovery-and-auto-creation)
- [Zenith integration](#zenith-integration)
  - [Authentication of proxied services](#authentication-of-proxied-services)
  - [Acquiring and distributing registrar tokens](#acquiring-and-distributing-registrar-tokens)
- [Cluster-as-a-Service (CaaS) subsystem](#cluster-as-a-service-caas-subsystem)
  - [Custom AWX credentials](#custom-awx-credentials)
  - [Use of Terraform for provisioning](#use-of-terraform-for-provisioning)
  - [Customising the parameter form for an appliance](#customising-the-parameter-form-for-an-appliance)

## Architecture Diagram

This diagram shows the components in the Azimuth Architecture. Components are colour-coded
to show which subsystem they belong to:

  * **Azimuth core component**: The component is composed of custom Azimuth code.
  * **App Proxy component**: The component is only deployed when the application proxy is enabled.
  * **Cluster-as-a-Service (CaaS) component**: The component is deployed when CaaS is enabled.
  * **Kubernetes component**: The component is part of the Kubernetes cluster.
  * **OpenStack component**: The component is part of the target OpenStack cloud.

![Zenith Architecture Diagram](./architecture-full.png)

## Network discovery and auto-creation

Azimuth does not expose any networking configuration to end users - instead it attempts to discover
the networks that it should be using, and is capable of creating the required networking components
if they are not present in an OpenStack project.

Azimuth only has a concept of two networks:

  * An "internal" network, typically a project-specific VXLAN.
  * An "external" network (external in the Neutron sense), that provides access from outside
    of the OpenStack project. This is typically a provider network shared between projects
    that connects to the internet.

Azimuth uses
[Neutron resource tags](https://docs.openstack.org/neutron/latest/contributor/internals/tag.html)
to discover the networks it should use, and the tags it looks for are `portal-internal` and
`portal-external` for the internal and external networks respectively.

If there is no network with the `portal-external` tag available in a project, then Azimuth looks
for networks with the `router:external` property. If there is **exactly one** such network it
will use that, otherwise it will raise a configuration error. If there are multiple external
networks, one must be tagged for use by the portal.

If there is no network with the `portal-internal` tag available in a project, then Azimuth will
create one and tag it. If it can detect an external network, it will also create a router
connecting the newly-created internal network and the external network.

This "auto-create" behaviour for the internal network can be disabled, in which case not finding
a tagged internal network will raise a configuration error.

## Zenith integration

### Authentication of proxied services

### Acquiring and distributing registrar tokens

## Cluster-as-a-Service (CaaS) subsystem

### Custom AWX credentials

### Use of Terraform for provisioning

### Customising the parameter form for an appliance
