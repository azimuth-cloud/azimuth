# Deploying and configuring Azimuth  <!-- omit in toc -->

The only supported deployment mechanism for Azimuth is to use [Helm](https://helm.sh/) to
deploy on a [Kubernetes](https://kubernetes.io/) cluster.

This document describes the most commonly used configuration options, which will be sufficient
for the vast majority of cases. For more advanced configuration requirements, see the
[values.yaml for the Helm chart](../chart/values.yaml).

Make sure you are familiar with the [Azimuth Architecture](./architecture.md) before
continuing with this document.

## Contents  <!-- omit in toc -->

- [Prerequisites](#prerequisites)
- [Installing and upgrading Azimuth](#installing-and-upgrading-azimuth)
- [Configuring the target cloud](#configuring-the-target-cloud)
  - [Enabling federated authentication](#enabling-federated-authentication)
  - [Networking configuration](#networking-configuration)
- [Configuring ingress (no Zenith)](#configuring-ingress-no-zenith)
  - [Specifying the portal domain](#specifying-the-portal-domain)
  - [Specifying the ingress class](#specifying-the-ingress-class)
  - [Transport Layer Security (TLS)](#transport-layer-security-tls)
    - [Automating certificates with cert-manager](#automating-certificates-with-cert-manager)
    - [Using a pre-existing certificate](#using-a-pre-existing-certificate)
- [Enabling the Zenith application proxy](#enabling-the-zenith-application-proxy)
  - [Configuring ingress](#configuring-ingress)
  - [Configuring Zenith](#configuring-zenith)
- [Enabling Cluster-as-a-Service (CaaS)](#enabling-cluster-as-a-service-caas)
  - [Accessing the AWX UI](#accessing-the-awx-ui)
  - [Configuring available appliances](#configuring-available-appliances)
  - [Customising the AWX operator deployment](#customising-the-awx-operator-deployment)
  - [Customising the AWX deployment](#customising-the-awx-deployment)
- [Using non-standard images](#using-non-standard-images)
- [Managing resource consumption](#managing-resource-consumption)
- [Customising the Consul deployment](#customising-the-consul-deployment)

## Prerequisites

This documentation assumes that you are already familiar with Helm and Kubernetes, and
have a Kubernetes cluster available for your Azimuth deployment that has an 
[Ingress Controller](https://kubernetes.io/docs/concepts/services-networking/ingress-controllers/)
installed (specifically the
[NGINX Ingress Controller](https://kubernetes.github.io/ingress-nginx/) if Zenith is enabled).

A DNS entry must exist for the domain that Azimuth will use, and that DNS entry should point
to the Kubernetes Ingress Controller - Azimuth does not manage this for you. If the Zenith
application proxy is enabled, the DNS entry must be a wildcard DNS entry that gives Azimuth
and Zenith control of an entire subdomain where both the Azimuth portal interface and
proxied services will be exposed (see
[Enabling the Zenith application proxy](#enabling-the-zenith-application-proxy)).

If you wish to use [cert-manager](https://cert-manager.io/) to automatically request and
renew TLS certificates for Azimuth (and Zenith) services, it must be installed before you deploy
Azimuth. You will also need to [configure an issuer](https://cert-manager.io/docs/configuration/)
for Azimuth to consume - Azimuth will not manage this for you.

In their default configurations, Consul and AWX both assume that you have a default
[Storage Class](https://kubernetes.io/docs/concepts/storage/storage-classes/) configured
on your Kubernetes cluster that they can use for data volumes. If this is not the case,
or if you have multiple storage classes available and need to specify a particular one,
you will need to customise the [AWX](#customising-the-awx-deployment) and 
[Consul](#customising-the-consul-deployment) deployments accordingly.

## Installing and upgrading Azimuth

First, you will need to create a Helm values file for your Azimuth deployment, using
the options described in this document. Once you have this, Azimuth can be deployed using
the following commands:

```bash
# Install the Azimuth Helm repository
helm repo add azimuth https://stackhpc.github.io/azimuth

# Check for available versions
# Usually, the latest tag or latest commit to master should be used
helm search repo azimuth --devel --versions

# Install Azimuth using configuration from "values.yaml"
# Azimuth uses a post-install/upgrade job to configure AWX, so we use a long timeout
# to ensure that job has sufficient time to complete
helm upgrade azimuth azimuth/azimuth --version ${version} -i -f values.yaml --timeout 60m
```

To change the configuration of your Azimuth deployment, modify your `values.yaml` and re-run
the `helm upgrade` command. To upgrade Azimuth, re-run the `helm upgrade` command specifying
the version that you wish to upgrade to. In both cases, the update should happen with near-zero
downtime as most of the components are capable of performing a rolling upgrade and those that
aren't will become available quickly after an update.

## Configuring the target cloud

The main piece of configuration required by Azimuth is the connection information for the
target OpenStack cloud. Azimuth connects to OpenStack as the authenticated user, so it does
not need any credentials to be issued for it.

Azimuth uses the
[Keystone Service Catalog](https://docs.openstack.org/keystone/latest/contributor/service-catalog.html)
to discover the endpoints for OpenStack services, so only needs to be told where to find the
Keystone v3 endpoint:

```yaml
provider:
  openstack:
    authUrl: https://openstack.example-cloud.org:5000/v3
```

Azimuth does not currently have support for specifying a custom CA for verifying TLS. If the
target cloud uses a TLS certificate that is not verifiable using the operating-system default
trustroots, TLS verification must be disabled:

```yaml
provider:
  openstack:
    verifySsl: false
```

If you use a domain other than `default`, you will also need to tell Azimuth the name of the
domain to use when authenticating:

```yaml
provider:
  openstack:
    domain: my-domain
```

### Enabling federated authentication

By default, the password authenticator is enabled, and this requires no additional configuration.

If the target cloud consumes identities from an external provider via
[Keystone federation](https://docs.openstack.org/keystone/latest/admin/federation/introduction.html),
then Azimuth can be configured to obtain an OpenStack token from Keystone using the same flow
that Horizon uses. To enable this, additional configuration is required for both Azimuth and Keystone
on the target cloud.

In your Azimuth configuration, enable the `openstack-federation` authenticator and tell
it the Keystone federation URL for the identity provider you want to use:

```yaml
authenticator:
  type: openstack-federation
  openstackFederation:
    federationUrl: https://openstack.example-cloud.org:5000/v3/auth/OS-FEDERATION/websso/<provider>
```

The Keystone configuration of the target cloud must also be modified to add Azimuth as a
[trusted dashboard](https://docs.openstack.org/keystone/latest/admin/federation/configure_federation.html#add-a-trusted-dashboard-websso),
otherwise it will be unable to retrieve a token via the federation flow. When configuring Azimuth as a
trusted dashboard, you must specify the URL that will receive token data - for an Azimuth deployment,
this URL is `https://[portal domain]/auth/complete/`, where the portal domain depends on the options
set in your Helm values file as described elsewhere in this document.

### Networking configuration

Azimuth uses
[Neutron resource tags](https://docs.openstack.org/neutron/latest/contributor/internals/tag.html)
to discover the networks it should use, and the tags it looks for are `portal-internal` and
`portal-external` for the internal and external networks respectively. These tags must be applied
by the cloud operator.

If it cannot find a tagged internal network, the default behaviour is for Azimuth to create an
internal network to use (and the corresponding router to attach it to the external network).

The discovery and auto-creation process is described in detail in
[Network discovery and auto-creation](./architecture.md#network-discovery-and-auto-creation).

To disable the auto-creation of internal networks, use the following:

```yaml
provider:
  openstack:
    createInternalNet: false
```

The CIDR of the auto-created subnet can also be changed, although it is the same for every project:

```yaml
provider:
  openstack:
    internalNetCidr: 10.0.3.0/24  # Defaults to 192.168.3.0/24
```

## Configuring ingress (no Zenith)

> **IMPORTANT**
>
> This section only applies when the Zenith application proxy is **not** enabled.
>
> When Zenith is enabled, the ingress configuration is slightly more complex as Azimuth must
> share a common parent domain with the Zenith services. This is discussed in detail
> [below](#configuring-ingress).

Azimuth uses [Ingress resources](https://kubernetes.io/docs/concepts/services-networking/ingress/)
to expose the API and UI outside the cluster, even when Zenith is not enabled.

### Specifying the portal domain

The domain at which the Azimuth portal will be exposed is required, and is specified as
follows:

```yaml
ingress:
  host: azimuth.example-cloud.org
```

As discussed in [Prerequisites](#prerequisites), there must be a DNS entry for this domain
pointing at the Kubernetes Ingress Controller.

### Specifying the ingress class

Azimuth must be told what
[IngressClass](https://kubernetes.io/docs/concepts/services-networking/ingress/#ingress-class)
to use for the `Ingress` resources that it creates. This is specified with the following:

```yaml
ingress:
  className: public
```

The default value is `nginx`, which is the name of the ingress class created when the
NGINX Ingress Controller is installed with the official Helm chart using the default
values. You can see the ingress classes available on your cluster using
`kubectl get ingressclass` (most will only have one).

### Transport Layer Security (TLS)

TLS for Azimuth can be configured by either:

#### Automating certificates with cert-manager

When cert-manager is installed and an issuer is configured, it is possible to specify annotations
for the portal `Ingress` resource. These annotations instruct cert-manager to dynamically request
a TLS certificate for the portal domain and to renew it when it gets close to expiring.

To configure annotations for the portal `Ingress` resource, use the following:

```yaml
ingress:
  annotations:
    cert-manager.io/cluster-issuer: name-of-issuer
```

In particular, this mechanism can be used to consume certificates issued by Let's Encrypt using
the [HTTP-01 challenge type](https://letsencrypt.org/docs/challenge-types/#http-01-challenge).

#### Using a pre-existing certificate

If you have a pre-existing TLS certificate issued for the portal domain, you must first create
a TLS secret in Kubernetes containing the certificate and private key. The certificate file
must include the *full certificate chain* in order, with the most specific certificate at the
top and the root CA at the bottom:

```sh
kubectl create secret tls azimuth-tls --cert=path/to/cert/file --key=path/to/key/file
```

Then configure Azimuth to use that secret for the portal `Ingress` resource:

```yaml
ingress:
  tls:
    secretName: azimuth-tls
```

> **WARNING**
>
> It is your responsibility to check for the expiry of the certificate and renew it when required.

## Enabling the Zenith application proxy

> Please ensure that you are familiar with the
> [Zenith Architecture](https://github.com/stackhpc/zenith/blob/main/docs/architecture.md)
> before continuing with this section.

As discussed in [Azimuth Architecture](./architecture.md), the Azimuth API and Zenith services
must share a base/parent domain in order for the Zenith auth callout to Azimuth to work. As such,
there must be a **wildcard** DNS entry for that base domain that points at the Kubernetes Ingress
Controller, and Azimuth/Zenith must be allowed to use any subdomain beneath that.

To enable the Zenith app proxy, use the following:

```yaml
tags:
  apps: true
```

### Configuring ingress

In order to share ingress configuration between Azimuth and Zenith and avoid duplication, we use
`global.ingress` instead of `ingress` (which we used for the non-Zenith case).

The base domain is specified instead of the full portal domain, and is picked up by both Azimuth
and Zenith:

```yaml
global:
  ingress:
    baseDomain: apps.example-cloud.org
```

The portal will be available at `portal.apps.example-cloud.org`, the Zenith registrar at
`registrar.apps.example-cloud.org` and the Zenith services at `subdomain1.apps.example-cloud.org`,
`subdomain2.apps.example-cloud.org`, ...

Similar to the [non-Zenith case](#specifying-the-ingress-class), Azimuth and Zenith must be told
what ingress class to use using `global.ingress`:

```yaml
global:
  ingress:
    className: public  # Defaults to nginx
```

TLS configuration also is very similar to the [non-Zenith case](#transport-layer-security-tls),
except that:

  * If using a pre-existing certificate, it must be a **wildcard** certificate for the Azimuth/Zenith
    base domain rather than for the Azimuth portal domain only.
  * The configuration should be set under `global.ingress.tls` rather than `ingress.tls`.

For example:

```yaml
global:
  ingress:
    tls:
      # Specify the name of a secret containing a wildcard certificate
      secretName: azimuth-wildcard-tls
      # Or specify annotations to be added to all ingress resources, including those created
      # by Zenith for proxied services
      annotations:
        cert-manager.io/cluster-issuer: name-of-issuer
```

> **WARNING**
>
> When using cert-manager annotations, a separate TLS certificate will be issued for each
> service proxied by Zenith. If there are a large number of proxied services, this will cause
> cert-manager to request a large number of certificates which may cause problems if the certificate
> issuer imposes rate limits.
>
> In particular, Let's Encrypt applies a [rate limit](https://letsencrypt.org/docs/rate-limits/)
> of 50 certificates per week per *Registered Domain*. This means that even if Azimuth/Zenith has
> been given `apps.example-cloud.org`, the limit would apply to the whole of `example-cloud.org`.
>
> For this reason a secret containing a wildcard certificate is preferred, despite the lack of
> automation. If you use a
> [supported DNS provider](https://cert-manager.io/docs/configuration/acme/dns01/#supported-dns01-providers),
> it is possible to use [cert-manager Certificate resources](https://cert-manager.io/docs/usage/certificate/)
> to automatically provision such a secret, however this is beyond the scope of this documentation.

### Configuring Zenith

Zenith is configured using the Zenith Helm chart, and all the options for the Zenith chart
can be set under the `zenith` key when deploying Azimuth. The options are discussed in detail at
[Deploying and configuring a Zenith server](https://github.com/stackhpc/zenith/blob/main/docs/server.md#using-a-loadbalancer-service).

In particular, a signing key must be set for the Zenith registrar:

```yaml
zenith:
  registrar:
    config:
      # This should be a long, random string - at least 32 bytes (256 bits) is recommended
      # A suitable token can be generated using "openssl rand -hex 32"
      subdomainTokenSigningKey: c2c0431de2ab6e4920ab97f343d3c1169139c595529522a16a6827be1c2f96f0
```

The Zenith SSHD service must also be configured in a way that allows the Azimuth chart to infer
the SSHD host and port. Azimuth needs to know these values so that they can be passed to clients.

If using a `LoadBalancer` service for Zenith SSHD, you **must** use a pre-allocated IP address:

```yaml
zenith:
  sshd:
    service:
      type: LoadBalancer
      loadBalancerIP: xxx.xxx.xxx.xxx
```

Similarly, if using `NodePort` service for Zenith SSHD you **must** specify a fixed port:

```yaml
zenith:
  sshd:
    service:
      type: NodePort
      nodePort: 32222
```

## Enabling Cluster-as-a-Service (CaaS)

To enable the Cluster-as-a-Service subsystem, just set:

```yaml
tags:
  clusters: true
```

The Azimuth Helm chart will handle all the plumbing that is required to connect Azimuth
and AWX.

### Accessing the AWX UI

In order to debug issues or to make changes to the Projects and Job Templates, it is often
useful to access the AWX UI.

With the default configuration the AWX UI is not exposed outside of the Kubernetes cluster,
but it can be accessed using
[Kubernetes Port Forwarding](https://kubernetes.io/docs/tasks/access-application-cluster/port-forward-access-application-cluster/).

First, you must retrieve the generated admin password:

```sh
kubectl -n azimuth get secret azimuth-awx-admin-password -o go-template='{{ .data.password | base64decode }}'
```

Then set up the forwarded port to the Azimuth UI service:

```sh
kubectl port-forward svc/azimuth-awx-service 8080:80
```

The AWX UI will now be available at `http://localhost:8080`, and you can sign in with the
username `admin` and the password from above.

It is also possible to configure AWX so that it provisions an `Ingress` resource for the
AWX UI - see [Customising the AWX deployment](#customising-the-awx-deployment) below.

### Configuring available appliances

As discussed in [Azimuth Architecture](./architecture.md), the appliances exposed to end users
via the Azimuth UI correspond to Job Templates in AWX, where Job Templates correspond to playbooks
in Projects and Projects are essentially Git repositories containing Ansible playbooks.

It is entirely possible to configure the available appliances using only the AWX UI, and in
many cases this will be the preferred approach. However if you prefer to specify the available
appliances using an "infrastructure-as-code" approach, the Azimuth Helm chart allows you to
specify a set of default projects that it will ensure are present after every deployment.

For example, the following will make the
[StackHPC Slurm appliance](https://github.com/stackhpc/caas-slurm-appliance) available in
your Azimuth deployment:

```yaml
clusterEngine:
  awx:
    defaultProjects:
      - # The name of the project
        name: StackHPC Slurm Appliance
        # The git repository where the playbooks live
        gitUrl: https://github.com/stackhpc/caas-slurm-appliance.git
        # The version of the git repository to use
        gitVersion: main
        # The URL prefix for UI metadata
        #   Each playbook is expected to have a file {metadataRoot}/{playbook name}.yml
        metadataRoot: https://raw.githubusercontent.com/stackhpc/caas-slurm-appliance/main/ui-meta
        # The playbooks within the repository to create Job Templates for
        playbooks: [slurm-infra.yml]
        # Extra vars to associate with the playbooks when creating Job Templates
        #   These are fed into the playbook executions for the Job Template
        #   The keys are the playbooks, with the special key "__ALL__" applying for all playbooks
        extraVars:
          __ALL__:
            # The StackHPC Slurm appliance needs to be told the ID of a CentOS 8 image to use
            cluster_image: 9ab38ae7-61ee-4de7-aa95-138c7b4b916f
        # A custom execution environment, if required
        #   See https://weiyentan.github.io/2021/creating-execution-environments/
        #   Most appliances will not require this as they can install what they need using
        #   collection and role dependencies
        #   This is only required if specific OS or Python dependencies are required
        executionEnvironment:
          image: ghcr.io/stackhpc/caas-ee:main
```

### Customising the AWX operator deployment

The [AWX operator](https://github.com/ansible/awx-operator) is installed using a
[Helm chart](https://github.com/stackhpc/awx-operator-helm) developed and maintained by StackHPC.
The deployment can be customised by setting values under the `awx-operator` key.

The available options are documented
[here](https://github.com/stackhpc/awx-operator-helm/blob/main/values.yaml). The vast majority
of deployments will never need to change anything.

### Customising the AWX deployment

As discussed in [Azimuth Architecture](./architecture.md), AWX is deployed using the
[AWX operator](https://github.com/ansible/awx-operator) by creating an instance of the `AWX`
custom resource.

The default options will be sufficient for the vast majority of deployments, however the
`spec` of the `AWX` instance can be configured using the `awx.spec` field. For example,
to enable an `Ingress` resource for the AWX UI, the following configuration can be used
to specify the hostname, and also to specify cert-manager annotations for an automatic
TLS certificate:

```yaml
awx:
  spec:
    ingress_type: ingress
    hostname: awx.example-cloud.org
    ingress_annotations: |
      cert-manager.io/cluster-issuer: name-of-issuer
    # Note that we specify the secret name, even though it doesn't exist until
    # cert-manager creates it
    ingress_tls_secret: azimuth-awx-tls
```

For a full list of available options, see the
[AWX operator documentation](https://github.com/ansible/awx-operator).

## Using non-standard images

It is possible to specify different images for the Azimuth components, for example if the
images are mirrored into an internal registry in order to provide an air-gapped system or
for security scanning:

```yaml
api:
  image:
    repository: internal.repo/azimuth/azimuth-api
    # The tag defaults to the appVersion of the chart
    tag: <valid tag>

ui:
  image:
    repository: internal.repo/azimuth/azimuth-ui
    # The tag defaults to the appVersion of the chart
    tag: <valid tag>
```

You may also wish to change the images used for Zenith, AWX and Consul - see the relevant
documentation for details.

## Managing resource consumption

In a production environment, it is important to constrain the resources available to each
container in order to prevent a rogue container starving other workloads on the cluster,
or even taking down a node.

In Kubernetes, this is done using
[resource requests and limits](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/).
These can be set for the Azimuth components using the Helm chart (the following values
are just an example and not a recommendation!):

```yaml
api:
  resources:
    requests:
      cpu: 500m
      memory: 128Mi
    limits:
      cpu: 1000m
      memory: 1Gi

ui:
  resources:
    requests:
      cpu: 500m
      memory: 128Mi
    limits:
      cpu: 1000m
      memory: 1Gi
```

Depending which optional features are enabled, you may also want to customise the resources for
the Zenith, AWX and Consul components. These can be configured under the `zenith`, `awx-operator`,
`awx` and `consul` keys - see the relevant documentation for details.

Alternatively, you can use the
[Vertical Pod Autoscaler](https://github.com/kubernetes/autoscaler/tree/master/vertical-pod-autoscaler)
to set these values automatically based on observed usage.

## Customising the Consul deployment

When either the Zenith application proxy or Cluster-as-a-Service subsystems are enabled,
[Consul](https://www.consul.io/) is installed automatically as a dependency of Azimuth using the
[official Consul Helm chart](https://www.consul.io/docs/k8s/installation/install#helm-chart-installation).
The default setup of Consul will be sufficient in almost all cases, however the values
for the Consul deployment can be customised if required by adding configuration under
the `consul` key in your Helm values file. The available options for the Consul Helm chart
(there are many!) are [documented on the Consul website](https://www.consul.io/docs/k8s/helm).

The most common change required for Consul is to reduce the number of replicas used for the
Consul server in order to get it to start, e.g. on a single node cluster:

```yaml
consul:
  server:
    replicas: 1
```

If your
[Kubernetes network plugin](https://kubernetes.io/docs/concepts/extend-kubernetes/compute-storage-net/network-plugins/)
does not support `hostPort`, you may also need to configure the Consul agents to use the host
networking:

```yaml
consul:
  client:
    dnsPolicy: ClusterFirstWithHostNet
    hostNetwork: true
```
