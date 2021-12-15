# Azimuth Architecture  <!-- omit in toc -->

This document describes the architecture of Azimuth in detail, including the integration with
the [Zenith application proxy](https://github.com/stackhpc/zenith) and the Cluster-as-a-Service
subsystem.

Azimuth consists of a [Python](https://www.python.org/) backend providing a REST API (different
to the OpenStack API) and a Javascript frontend written in [React](https://reactjs.org/). The
primary function of Azimuth is as a regular OpenStack client, presenting a simplified interface
for provisioning servers and volumes and making the networking as easy and transparent as possible.

The application proxy and Cluster-as-a-Service subsystems provide additional functionality
above and beyond that provided by OpenStack, such as secure web consoles and the ability to
provision complex, multi-machine appliances.

> **NOTE**
>
> Before reading this document, please make sure you are familiar with the
> [Zenith Architecture](https://github.com/stackhpc/zenith/blob/main/docs/architecture.md).
>
> This document treats Zenith as a black box, focusing on Azimuth's integration points.

## Contents  <!-- omit in toc -->

- [Architecture Diagram](#architecture-diagram)
- [Network discovery and auto-creation](#network-discovery-and-auto-creation)
- [Zenith integration](#zenith-integration)
  - [Authentication of proxied services](#authentication-of-proxied-services)
  - [Web console support](#web-console-support)
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

## Zenith integration

Azimuth optionally integrates with the [Zenith proxy](https://github.com/stackhpc/zenith).
Currently, Zenith is used to provide access to authenticated web consoles for provisioned servers
without the need to consume a floating IP, but many more integrations are planned in the near
future.

Azimuth integrates with Zenith in two places, which are shown as "External components" in the
[Zenith architecture diagram](https://github.com/stackhpc/zenith/blob/main/docs/architecture.md#architecture-diagram):

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
[Zenith client docs](https://github.com/stackhpc/zenith/blob/main/docs/client.md) for more
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

### Web console support

When Zenith is enabled, a user can optionally request that a machine is provisioned with a web
console using [Apache Guacamole](https://guacamole.apache.org/). The web console is installed
and configured using the `console` playbook from the
[stackhpc.azimuth_tools Ansible collection](https://github.com/stackhpc/ansible-collection-azimuth-tools),
and uses [Podman](https://podman.io/) to run Guacamole and the Zenith client as containers.

Please see the [Zenith client docs](https://github.com/stackhpc/zenith/blob/main/docs/client.md)
for details on the Zenith client commands and options.

When the web console is enabled for a server, the following steps are executed to establish
the web console and corresponding Zenith tunnel:

  1. Azimuth calls out to the Zenith registrar on its admin interface (which is internal to
     the cluster) to reserve a domain and receives a token in return.
  1. Azimuth places the token, the allocated subdomain and connection information for the Zenith
     registrar and SSHD services in the
     [instance metadata](https://docs.openstack.org/nova/latest/user/metadata.html).
  1. Azimuth also sets the
     [instance user data](https://docs.openstack.org/nova/latest/user/metadata.html#user-data)
     to a script that invokes the `stackhpc.azimuth_tools.console` playbook.
  1. The playbook installs and configures Guacamole.
  1. The playbook reads the Zenith token from the metadata service and runs `zenith-client init`
     to generate a new SSH keypair and register the public key.
  1. The playbook runs `zenith-client connect` using the registered SSH keypair. It passes
     the OpenStack project ID from the instance metadata as an auth parameter (see above).
  1. Traffic can now flow via the secure Zenith tunnel to Guacamole, with authentication
     and TLS termination provided by the Zenith proxy.

When a user accesses the web console for a server in the Azimuth UI, the API will fetch the
instance from OpenStack, extract the subdomain from the instance metadata and redirect the
user to the web console for that server.

It is important to note that this does **not** require the server running Guacamole to be
accessible from outside the project or to have any inbound firewall rules at all. Even if
the server was assigned a floating IP, Guacamole is not bound to a public interface so would
still not be directly accessible.

In fact, Guacamole and the Zenith client run in a Podman pod (similar to a Kubernetes pod)
which has an isolated network context, and so are not even bound to the host's loopback
interface - they are only bound to the pod's isolated interface.

## Cluster-as-a-Service (CaaS) subsystem

### Custom AWX credentials

### Use of Terraform for provisioning

### Customising the parameter form for an appliance
