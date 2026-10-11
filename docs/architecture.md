# Azimuth Architecture  <!-- omit in toc -->

This document describes the architecture of Azimuth in detail, including the integration with
the [Zenith application proxy](https://github.com/azimuth-cloud/zenith),
[Kubernetes](https://kubernetes.io/) support using [Cluster API](https://cluster-api.sigs.k8s.io/)
and the Cluster-as-a-Service (CaaS) subsystem.

Azimuth consists of a [Python](https://www.python.org/) backend providing a REST API (different
to the OpenStack API) and a Javascript frontend written in [React](https://reactjs.org/).
It is possible to deploy Azimuth without Zenith, Kubernetes and CaaS support, in which case
it is just a regular OpenStack client presenting a simplified interface for provisioning servers
and volumes while hiding the details of the underlying networking from the user.

When Zenith, Kubernetes and CaaS support are enabled for a fully-featured Azimuth deployment
there are many more components involved with complex interactions, which this document describes
in more detail.

> **NOTE**
>
> Before reading this document, please make sure you are familiar with the
> [Zenith Architecture](https://github.com/azimuth-cloud/zenith/blob/main/docs/architecture.md).
>
> This document treats Zenith as a black box, focusing on Azimuth's integration points.

## Contents  <!-- omit in toc -->

- [Architecture Diagram](#architecture-diagram)
- [Network discovery and auto-creation](#network-discovery-and-auto-creation)
- [Kubernetes](#kubernetes)
- [Cluster-as-a-Service (CaaS)](#cluster-as-a-service-caas)
- [Zenith integrations](#zenith-integrations)
  - [Authentication of proxied services](#authentication-of-proxied-services)
  - [Integration with Kubernetes](#integration-with-kubernetes)
  - [Integration with Cluster-as-a-Service (CaaS)](#integration-with-cluster-as-a-service-caas)

## Architecture Diagram

This diagram shows the components in the Azimuth Architecture. Components are colour-coded
to show which subsystem they belong to:

  * **Azimuth core component**: The component is composed of custom Azimuth code.
  * **App Proxy component**: The component is only deployed when the application proxy is enabled.
  * **Cluster-as-a-Service (CaaS) component**: The component is deployed when CaaS is enabled.
  * **Kubernetes component**: The component is part of the Kubernetes cluster.
  * **OpenStack component**: The component is part of the target OpenStack cloud.

![Azimuth Architecture Diagram](./architecture-full.png)

## Network discovery and auto-creation

Azimuth does not expose any networking configuration to end users - instead it attempts to discover
the networks that it should be using, and is capable of creating the required networking components
if they are not present in an OpenStack project.

Azimuth has knowledge of two networks:

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

## Kubernetes

Coming soon!

## Cluster-as-a-Service (CaaS)

Coming soon!

## Zenith integrations

Azimuth optionally integrates with the [Zenith proxy](https://github.com/azimuth-cloud/zenith).
When enabled, Azimuth will use Zenith to provide authenticated access to platform services
such as web-based consoles + desktops, monitoring dashboards and Jupyter Notebooks without
the need to consume a floating IP.

Azimuth integrates with Zenith in two places, which are shown as "External components" in the
[Zenith architecture diagram](https://github.com/azimuth-cloud/zenith/blob/main/docs/architecture.md#architecture-diagram):

  * **External auth service**: Azimuth provides authentication and authorization for proxied
    services by implementing Zenith's authentication callout.
  * **Broker**: Azimuth acts as a broker for Zenith registrar tokens, and is responsible for
    reserving subdomains and communicating the tokens to Zenith clients.

### Authentication of proxied services

Azimuth provides authentication and authorization for Zenith services that is based on whether
the user can authenticate with OpenStack and which projects they have access to.

The authentication relies on a cookie in the user's browser that must be available to
both the Azimuth API and the Zenith proxy. Due to cookie security rules, this means that
the Azimuth API/UI and Zenith services must share a common base/parent domain, e.g.
the Azimuth portal at `portal.apps.example-cloud.org` with the Zenith services being
`subdomain1.apps.example-cloud.org`, `subdomain2.apps.example-cloud.org`, ... In this case,
the cookie would be set with the domain `.apps.example-cloud.org`.

Zenith allows external auth services to respect additional headers that can be specified by
Zenith clients using the `auth_params` option (see the
[Zenith client docs](https://github.com/azimuth-cloud/zenith/blob/main/docs/client.md) for more
information). Zenith imposes no contraints on these headers - they are just forwarded to the
external auth service as specified by the client as headers with the prefix `X-Auth-`.

If no `auth_params` are specified for a service, Azimuth will ensure that the user can
authenticate with the target OpenStack cloud but will not impose any project-level authorization
before allowing a request to proceed to the service.

To enforce project-level authorization for a service, clients can specify
`auth_params.tenancy-id`, which should be set to the ID of an OpenStack project. When called to
verify an incoming request for the service, Azimuth will receive the project ID as the
`X-Auth-Tenancy-Id` header and will verify that the authenticated user belongs to the specified
project before allowing the request to proceed.

The flow when an unauthenticated user tries to access an authenticated Zenith service is:

  1. Unauthenticated user attempts to access a Zenith service (no cookie set).
  1. The Zenith proxy calls out to Azimuth to verify the request.
  1. Azimuth responds that the user is unauthenticated.
  1. The Zenith proxy redirects the user to the Azimuth sign-in page.
  1. Azimuth negotiates with Keystone to obtain an OpenStack token for the user.
  1. Azimuth places the token into a cookie for the base/parent domain.
  1. Azimuth redirects the user back to the Zenith service (this time with a cookie set).
  1. The Zenith proxy calls out to Azimuth to verify the request.
  1. Azimuth reads the token from the cookie and checks that it is still valid.
  1. If the service specified `auth_params.tenancy-id`, Azimuth checks that the user
     belongs to the specified project.
  1. Azimuth responds to the Zenith proxy that the request can proceed.
  1. The request is forwarded to the proxied service down the Zenith tunnel.

### Integration with Kubernetes

Coming soon!

### Integration with Cluster-as-a-Service (CaaS)

Coming soon!
