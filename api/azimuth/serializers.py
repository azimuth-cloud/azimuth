"""
Django REST framework serializers for objects from the :py:mod:`~.cloud.dto` package.
"""
import collections
import datetime
import dataclasses
import ipaddress

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives.serialization import load_ssh_public_key

from django.urls import reverse

from rest_framework import serializers

import jsonschema

import easysemver

from .cluster_api import dto as capi_dto
from .cluster_engine import dto as clusters_dto, errors as clusters_errors
from .provider import dto, errors
from .scheduling import dto as scheduling_dto
from .settings import cloud_settings


def make_dto_serializer(dto_class, exclude = []):
    """
    Returns a new serializer class for the given DTO class.

    This just produces a ``ReadOnlyField`` for each field of the DTO class
    that is not in ``exclude``.

    Args:
        dto_class: The DTO class to build a serializer for.
        exclude: A list of field names to exclude.

    Returns:
        A subclass of ``rest_framework.serializers.Serializer``.
    """
    if dataclasses.is_dataclass(dto_class):
        fields = [f.name for f in dataclasses.fields(dto_class)]
    else:
        fields = dto_class._fields
    return type(
        dto_class.__name__ + "Serializer",
        (serializers.Serializer, ),
        {
            name: serializers.ReadOnlyField()
            for name in fields
            if name not in exclude
        }
    )


# Regex for matching valid IDs
ID_REGEX = "^[-a-zA-Z0-9_.]+$"


Ref = collections.namedtuple("Ref", ["id"])


class RefSerializer(serializers.Serializer):
    id = serializers.ReadOnlyField()

    def to_representation(self, obj):
        # If the object is falsey, the representation is None
        if not obj:
            return None
        # If the given object is a scalar, convert it to a ref first
        if not hasattr(obj, "id"):
            obj = Ref(obj)
        result = super().to_representation(obj)
        # If the info to build a link is in the context, add it
        request = self.context.get("request")
        tenant = self.context.get("tenant")
        if request and tenant:
            result.setdefault("links", {})["self"] = self.get_self_link(
                request,
                tenant,
                obj.id
            )
        return result

    def get_self_link(self, request, tenant, id):
        """
        Returns the self link for a ref.
        """
        raise NotImplementedError


class SSHKeyUpdateSerializer(serializers.Serializer):
    """
    Serializer for updating an SSH public key.
    """
    #: The new SSH public key
    ssh_public_key = serializers.CharField(write_only = True)

    def validate_ssh_public_key(self, value):
        # Try to load the public key using cryptography
        try:
            public_key = load_ssh_public_key(value.encode())
        except (ValueError, UnsupportedAlgorithm):
            raise serializers.ValidationError(["Not a valid SSH public key."])
        # Now we know it is a valid SSH key, we know how to get the type as a string
        key_type = value.split()[0]
        # Test whether the key type is an allowed key type
        if key_type not in cloud_settings.SSH_ALLOWED_KEY_TYPES:
            message = "Keys of type '{}' are not permitted.".format(key_type)
            raise serializers.ValidationError([message])
        # If the key is an RSA key, check the minimum size
        if key_type == "ssh-rsa" and public_key.key_size < cloud_settings.SSH_RSA_MIN_BITS:
            message = "RSA keys must have a minimum of {} bits ({} given).".format(
                cloud_settings.SSH_RSA_MIN_BITS,
                public_key.key_size
            )
            raise serializers.ValidationError([message])
        # The key is valid! Hooray!
        return value


class TenancySerializer(make_dto_serializer(dto.Tenancy)):
    def to_representation(self, obj):
        result = super().to_representation(obj)
        # If the info to build a link is in the context, add it
        request = self.context.get("request")
        if request:
            result.setdefault("links", {}).update({
                "quotas": request.build_absolute_uri(
                    reverse("azimuth:quotas", kwargs = {
                        "tenant": obj.id,
                    })
                ),
                "identity_provider": request.build_absolute_uri(
                    reverse("azimuth:identity_provider", kwargs = {
                        "tenant": obj.id,
                    })
                ),
                "images": request.build_absolute_uri(
                    reverse("azimuth:images", kwargs = {
                        "tenant": obj.id,
                    })
                ),
                "sizes": request.build_absolute_uri(
                    reverse("azimuth:sizes", kwargs = {
                        "tenant": obj.id,
                    })
                ),
                "volumes": request.build_absolute_uri(
                    reverse("azimuth:volumes", kwargs = {
                        "tenant": obj.id,
                    })
                ),
                "external_ips": request.build_absolute_uri(
                    reverse("azimuth:external_ips", kwargs = {
                        "tenant": obj.id,
                    })
                ),
                "machines": request.build_absolute_uri(
                    reverse("azimuth:machines", kwargs = {
                        "tenant": obj.id,
                    })
                ),
                "kubernetes_cluster_templates": request.build_absolute_uri(
                    reverse("azimuth:kubernetes_cluster_templates", kwargs = {
                        "tenant": obj.id,
                    })
                ),
                "kubernetes_clusters": request.build_absolute_uri(
                    reverse("azimuth:kubernetes_clusters", kwargs = {
                        "tenant": obj.id,
                    })
                ),
                "kubernetes_app_templates": request.build_absolute_uri(
                    reverse("azimuth:kubernetes_app_templates", kwargs = {
                        "tenant": obj.id,
                    })
                ),
                "kubernetes_apps": request.build_absolute_uri(
                    reverse("azimuth:kubernetes_apps", kwargs = {
                        "tenant": obj.id,
                    })
                ),
                "cluster_types": request.build_absolute_uri(
                    reverse("azimuth:cluster_types", kwargs = {
                        "tenant": obj.id,
                    })
                ),
                "clusters": request.build_absolute_uri(
                    reverse("azimuth:clusters", kwargs = {
                        "tenant": obj.id,
                    })
                ),
            })
        if cloud_settings.METRICS.TENANT_METRICS_URL_TEMPLATE:
            result.setdefault("links", {}).update({
                "metrics": cloud_settings.METRICS.TENANT_METRICS_URL_TEMPLATE.format(
                    tenant_id = obj.id
                ),
            })
        return result


QuotaSerializer = make_dto_serializer(dto.Quota)


class ImageRefSerializer(RefSerializer):
    def get_self_link(self, request, tenant, id):
        return request.build_absolute_uri(
            reverse("azimuth:image_details", kwargs = {
                "tenant": tenant,
                "image": id,
            })
        )


class ImageSerializer(
    ImageRefSerializer,
    make_dto_serializer(dto.Image, exclude = ["metadata"])
):
    nat_allowed = serializers.SerializerMethodField()

    def get_nat_allowed(self, obj):
        # The value in the metadata will be a string 1 or 0
        # If the metadata is not present, NAT is allowed
        return obj.metadata.get("nat_allowed", "1") == "1"


class SizeRefSerializer(RefSerializer):
    def get_self_link(self, request, tenant, id):
        return request.build_absolute_uri(
            reverse("azimuth:size_details", kwargs = {
                "tenant": tenant,
                "size": id,
            })
        )


SizeSerializer = type(
    "SizeSerializer",
    (SizeRefSerializer, make_dto_serializer(dto.Size)),
    {}
)


class VolumeRefSerializer(RefSerializer):
    def get_self_link(self, request, tenant, id):
        return request.build_absolute_uri(
            reverse("azimuth:volume_details", kwargs = {
                "tenant": tenant,
                "volume": id,
            })
        )


class MachineRefSerializer(RefSerializer):
    def get_self_link(self, request, tenant, id):
        return request.build_absolute_uri(
            reverse("azimuth:machine_details", kwargs = {
                "tenant": tenant,
                "machine": id,
            })
        )


class VolumeSerializer(
    VolumeRefSerializer,
    make_dto_serializer(dto.Volume, exclude = ["status", "machine_id"])
):
    status = serializers.ReadOnlyField(source = "status.name")
    machine = MachineRefSerializer(
        source = "machine_id",
        read_only = True,
        allow_null = True
    )


class CreateVolumeSerializer(serializers.Serializer):
    name = serializers.RegexField("^[A-Za-z0-9._-]+$", write_only = True)
    size = serializers.IntegerField(write_only = True, min_value = 1)


class UpdateVolumeSerializer(serializers.Serializer):
    machine_id = serializers.RegexField(ID_REGEX, write_only = True, allow_null = True)


class MachineStatusSerializer(make_dto_serializer(dto.MachineStatus)):
    type = serializers.ReadOnlyField(source = "type.name")


class MachineSerializer(
    MachineRefSerializer,
    make_dto_serializer(dto.Machine, exclude = [
        "image_id",
        "size_id",
        "attached_volume_ids",
        "metadata"
    ])
):
    image = ImageRefSerializer(source = "image_id", read_only = True)
    size = SizeRefSerializer(source = "size_id", read_only = True)
    status = MachineStatusSerializer(read_only = True)
    attached_volumes = VolumeRefSerializer(
        source = "attached_volume_ids",
        many = True,
        read_only = True
    )

    # Specific values derived from DTO metadata
    nat_allowed = serializers.SerializerMethodField()

    def get_nat_allowed(self, obj):
        # The value in the metadata will be a string 1 or 0
        # If the metadata is not present, NAT is allowed
        return obj.metadata.get("nat_allowed", "1") == "1"

    def to_representation(self, obj):
        result = super().to_representation(obj)
        # If the info to build a link is in the context, add it
        request = self.context.get("request")
        tenant = self.context.get("tenant")
        if request and tenant:
            result.setdefault("links", {}).update({
                "logs": request.build_absolute_uri(
                    reverse("azimuth:machine_logs", kwargs = {
                        "tenant": tenant,
                        "machine": obj.id,
                    })
                ),
                "start": request.build_absolute_uri(
                    reverse("azimuth:machine_start", kwargs = {
                        "tenant": tenant,
                        "machine": obj.id,
                    })
                ),
                "stop": request.build_absolute_uri(
                    reverse("azimuth:machine_stop", kwargs = {
                        "tenant": tenant,
                        "machine": obj.id,
                    })
                ),
                "restart": request.build_absolute_uri(
                    reverse("azimuth:machine_restart", kwargs = {
                        "tenant": tenant,
                        "machine": obj.id,
                    })
                ),
                "firewall_rules": request.build_absolute_uri(
                    reverse("azimuth:machine_firewall_rules", kwargs = {
                        "tenant": tenant,
                        "machine": obj.id,
                    })
                ),
            })
        return result


class CreateMachineSerializer(serializers.Serializer):
    name = serializers.RegexField("^[A-Za-z0-9.-]+$", write_only = True)
    image_id = serializers.RegexField(ID_REGEX, write_only = True)
    size_id = serializers.RegexField(ID_REGEX, write_only = True)


class FirewallRuleSerializer(
    make_dto_serializer(dto.FirewallRule, exclude = ["direction", "protocol"])
):
    direction = serializers.ReadOnlyField(source = "direction.name")
    protocol = serializers.ReadOnlyField(source = "protocol.name")



class FirewallGroupSerializer(
    make_dto_serializer(dto.FirewallGroup, exclude = ["rules"])
):
    rules = FirewallRuleSerializer(many = True, read_only = True)


class CreateFirewallRuleSerializer(serializers.Serializer):
    direction = serializers.ChoiceField(
        choices = [d.name for d in dto.FirewallRuleDirection],
        write_only = True
    )
    protocol = serializers.ChoiceField(
        choices = [p.name for p in dto.FirewallRuleProtocol],
        write_only = True
    )
    port = serializers.IntegerField(
        allow_null = True,
        min_value = 1,
        max_value = 65535,
        write_only = True
    )
    remote_cidr = serializers.CharField(
        allow_blank = True,
        allow_null = True,
        write_only = True
    )

    def validate_direction(self, value):
        """
        Converts a string direction into an enum member.
        """
        return dto.FirewallRuleDirection[value]

    def validate_protocol(self, value):
        """
        Converts a string protocol into an enum member.
        """
        return dto.FirewallRuleProtocol[value]

    def validate_remote_cidr(self, value):
        """
        Check that the given value is a valid CIDR.
        """
        if value:
            try:
                _ = ipaddress.IPv4Network(value)
            except (ipaddress.AddressValueError, ipaddress.NetmaskValueError):
                raise serializers.ValidationError(["Not a valid IPv4 CIDR."])
            return value
        else:
            return None


class ExternalIPSerializer(make_dto_serializer(dto.ExternalIp)):
    machine = MachineRefSerializer(
        source = "machine_id",
        read_only = True,
        allow_null = True
    )
    machine_id = serializers.RegexField(ID_REGEX, write_only = True, allow_null = True)

    def to_representation(self, obj):
        result = super().to_representation(obj)
        # If the info to build a link is in the context, add it
        request = self.context.get("request")
        tenant = self.context.get("tenant")
        if request and tenant:
            result.setdefault("links", {})["self"] = request.build_absolute_uri(
                reverse("azimuth:external_ip_details", kwargs = {
                    "tenant": tenant,
                    "ip": obj.id,
                })
            )
        return result
    

ProjectedQuotaSerializer = make_dto_serializer(scheduling_dto.ProjectedQuota)


class PlatformScheduleSerializer(serializers.Serializer):
    end_time = serializers.DateTimeField(default_timezone = datetime.timezone.utc)

    def validate_end_time(self, value):
        # Ensure that the end time is in the future
        now = datetime.datetime.now(tz = datetime.timezone.utc)
        if value <= now:
            raise serializers.ValidationError("End time cannot be in the past.")
        # Ensure that the end time is UTC
        return value.astimezone(datetime.timezone.utc)

    def to_internal_value(self, data):
        data = super().to_internal_value(data)
        return scheduling_dto.PlatformSchedule(**data)


ClusterParameterSerializer = make_dto_serializer(clusters_dto.ClusterParameter)


class ClusterTypeSerializer(
    make_dto_serializer(clusters_dto.ClusterType, exclude = ["services"])
):
    parameters = ClusterParameterSerializer(many = True, read_only = True)

    def to_representation(self, obj):
        result = super().to_representation(obj)
        # If the info to build a link is in the context, add it
        request = self.context.get("request")
        tenant = self.context.get("tenant")
        if request and tenant:
            result.setdefault("links", {})["self"] = request.build_absolute_uri(
                reverse("azimuth:cluster_type_details", kwargs = {
                    "tenant": tenant,
                    "cluster_type": obj.name,
                })
            )
        return result


class ClusterSerializer(
    make_dto_serializer(
        clusters_dto.Cluster,
        exclude = ["status", "services", "schedule"]
    )
):
    status = serializers.ReadOnlyField(source = "status.name")
    services = serializers.SerializerMethodField()
    schedule = PlatformScheduleSerializer()

    def get_services(self, obj):
        request = self.context.get("request")
        tenant = self.context.get("tenant")
        services = []
        for service_dto in obj.services:
            service_obj = dataclasses.asdict(service_dto)
            service_obj["url"] = request.build_absolute_uri(
                reverse("azimuth:cluster_service", kwargs = {
                    "tenant": tenant,
                    "cluster": obj.id,
                    "service": service_dto.name,
                })
            )
            services.append(service_obj)
        return services

    def to_representation(self, obj):
        result = super().to_representation(obj)
        # If the info to build a link is in the context, add it
        request = self.context.get("request")
        tenant = self.context.get("tenant")
        if request and tenant:
            result.setdefault("links", {}).update({
                "self": request.build_absolute_uri(
                    reverse("azimuth:cluster_details", kwargs = {
                        "tenant": tenant,
                        "cluster": obj.id,
                    })
                ),
                "patch": request.build_absolute_uri(
                    reverse("azimuth:cluster_patch", kwargs = {
                        "tenant": tenant,
                        "cluster": obj.id,
                    })
                ),
            })
        return result


class CreateClusterSerializer(serializers.Serializer):
    name = serializers.RegexField("^[a-z0-9-]+$", write_only = True)
    cluster_type = serializers.RegexField(ID_REGEX, write_only = True)
    parameter_values = serializers.JSONField(write_only = True)
    schedule = PlatformScheduleSerializer(write_only = True, allow_null = True, default = None)

    def validate_cluster_type(self, value):
        # Find the cluster type
        # Convert not found errors into validation errors
        cluster_manager = self.context["cluster_manager"]
        try:
            return cluster_manager.find_cluster_type(value)
        except clusters_errors.ObjectNotFoundError as exc:
            raise serializers.ValidationError(str(exc))

    def validate_schedule(self, value):
        if self.context.get("validate_schedule", True):
            if cloud_settings.SCHEDULING.ENABLED and not value:
                raise serializers.ValidationError("This field is required.")
            elif not cloud_settings.SCHEDULING.ENABLED and value:
                raise serializers.ValidationError("Scheduling is not supported.")
        return value

    def validate(self, data):
        # Force a validation of the parameter values for the cluster type
        # Convert the provider error into a DRF ValidationError
        cluster_manager = self.context["cluster_manager"]
        try:
            data["parameter_values"] = cluster_manager.validate_cluster_params(
                data["cluster_type"],
                data["parameter_values"]
            )
        except clusters_errors.ValidationError as exc:
            raise serializers.ValidationError({ "parameter_values": exc.errors })
        return data


class UpdateClusterSerializer(serializers.Serializer):
    parameter_values = serializers.JSONField(write_only = True)

    def validate(self, data):
        # Force a validation of the parameter values against the cluster
        # type for the cluster
        # Convert the provider error into a DRF ValidationError
        cluster_manager = self.context["cluster_manager"]
        cluster_type = self.context.get("cluster_type", self.instance.cluster_type)
        try:
            data["parameter_values"] = cluster_manager.validate_cluster_params(
                cluster_type,
                data["parameter_values"],
                self.instance.parameter_values
            )
        except clusters_errors.ValidationError as exc:
            raise serializers.ValidationError({ "parameter_values": exc.errors })
        return data


class KubernetesClusterTemplateRefSerializer(RefSerializer):
    def get_self_link(self, request, tenant, id):
        return request.build_absolute_uri(
            reverse("azimuth:kubernetes_cluster_template_details", kwargs = {
                "tenant": tenant,
                "template": id,
            })
        )


KubernetesClusterTemplateSerializer = type(
    "KubernetesClusterTemplateSerializer",
    (
        KubernetesClusterTemplateRefSerializer,
        make_dto_serializer(capi_dto.ClusterTemplate)
    ),
    {}
)


class KubernetesClusterNodeGroupSerializer(
    make_dto_serializer(capi_dto.NodeGroup, exclude = ["machine_size_id"])
):
    machine_size = SizeRefSerializer(source = "machine_size_id", read_only = True)


class KubernetesClusterNodeSerializer(
    make_dto_serializer(capi_dto.Node, exclude = ["size_id"])
):
    size = SizeRefSerializer(source = "size_id", read_only = True)


class KubernetesClusterAddonSerializer(make_dto_serializer(capi_dto.Addon)):
    pass


class KubernetesClusterRefSerializer(RefSerializer):
    def get_self_link(self, request, tenant, id):
        return request.build_absolute_uri(
            reverse("azimuth:kubernetes_cluster_details", kwargs = {
                "tenant": tenant,
                "cluster": id,
            })
        )


class KubernetesClusterSerializer(
    KubernetesClusterRefSerializer,
    make_dto_serializer(
        capi_dto.Cluster,
        exclude = [
            "template_id",
            "control_plane_size_id",
            "node_groups",
            "nodes",
            "addons",
            "services",
            "schedule",
        ]
    )
):
    template = KubernetesClusterTemplateRefSerializer(source = "template_id", read_only = True)
    control_plane_size = SizeRefSerializer(source = "control_plane_size_id", read_only = True)
    node_groups = KubernetesClusterNodeGroupSerializer(many = True, read_only = True)
    nodes = KubernetesClusterNodeSerializer(many = True, read_only = True)
    addons = KubernetesClusterAddonSerializer(many = True, read_only = True)
    services = serializers.SerializerMethodField()
    schedule = PlatformScheduleSerializer()

    def get_services(self, obj):
        request = self.context.get("request")
        tenant = self.context.get("tenant")
        services = []
        for service_dto in obj.services:
            service_obj = dataclasses.asdict(service_dto)
            service_obj["url"] = request.build_absolute_uri(
                reverse("azimuth:kubernetes_cluster_service", kwargs = {
                    "tenant": tenant,
                    "cluster": obj.id,
                    "service": service_dto.name,
                })
            )
            services.append(service_obj)
        return services

    def to_representation(self, obj):
        result = super().to_representation(obj)
        # If the info to build a link is in the context, add it
        request = self.context.get("request")
        tenant = self.context.get("tenant")
        if request and tenant:
            result.setdefault("links", {}).update({
                "kubeconfig": request.build_absolute_uri(
                    reverse(
                        "azimuth:kubernetes_cluster_generate_kubeconfig",
                        kwargs = {
                            "tenant": tenant,
                            "cluster": obj.id,
                        }
                    )
                ),
            })
        return result


class NodeGroupSpecSerializer(serializers.Serializer):
    name = serializers.RegexField("^[a-z][a-z0-9-]+[a-z0-9]$")
    machine_size = serializers.RegexField(ID_REGEX)
    autoscale = serializers.BooleanField(default = False)
    count = serializers.IntegerField(required = False, allow_null = True, min_value = 0)
    # Currently, we don't support autoscaling groups that go to zero
    min_count = serializers.IntegerField(required = False, allow_null = True, min_value = 1)
    max_count = serializers.IntegerField(required = False, allow_null = True, min_value = 1)

    def validate_machine_size(self, value):
        session = self.context["session"]
        try:
            return session.find_size(value)
        except errors.ObjectNotFoundError as exc:
            raise serializers.ValidationError(str(exc))

    def validate(self, data):
        errors = {}
        if data["autoscale"]:
            min_count = data.get("min_count")
            if min_count is None:
                errors["min_count"] = "Required for an autoscaling node group."
            max_count = data.get("max_count")
            if max_count is None:
                errors["max_count"] = "Required for an autoscaling node group."
            if min_count and max_count and max_count < min_count:
                errors["max_count"] = "Must be greater than or equal to the minimum count."
        else:
            if data.get("count") is None:
                errors["count"] = "Required for a non-autoscaling node group."
        if errors:
            raise serializers.ValidationError(errors)
        return data


class KubernetesClusterValidationMixin:
    def validate(self, data):
        # If ingress is being enabled, an IP must be specified and that IP must be free
        if (
            # Ingress is being enabled by the change
            data.get("ingress_enabled", False) and
            # Ingress is not currently enabled
            not getattr(self.instance, "ingress_enabled", False)
        ):
            ip_address = data.get("ingress_controller_load_balancer_ip")
            # No ingress controller IP is given
            if not ip_address:
                raise serializers.ValidationError({
                    "ingress_controller_load_balancer_ip": "Required when ingress is enabled.",
                })
            # The given IP is not free
            session = self.context["session"]
            try:
                ip = session.find_external_ip_by_ip_address(ip_address)
            except errors.ObjectNotFoundError as exc:
                raise serializers.ValidationError({
                    "ingress_controller_load_balancer_ip": str(exc),
                })
            else:
                if ip.machine_id:
                    raise serializers.ValidationError({
                        "ingress_controller_load_balancer_ip": (
                            f"{ip_address} is already associated with "
                            "another platform or machine."
                        )
                    })

        # OCCM does not respect changes to the ingress loadbalancer IP, so disallow it
        if(
            # Ingress is currently enabled
            getattr(self.instance, "ingress_enabled", False) and
            # Ingress will still be enabled after the changes
            data.get("ingress_enabled", True) and
            # The ingress IP is being changed
            "ingress_controller_load_balancer_ip" in data and
            data["ingress_controller_load_balancer_ip"] != self.instance.ingress_controller_load_balancer_ip
        ):
            raise serializers.ValidationError({
                "ingress_controller_load_balancer_ip": (
                    "Changing the IP address of the load balancer is not supported."
                ),
            })

        # The size of the metrics volume is not permitted to decrease
        if (
            # The metrics volume size is present and needs validating
            data.get("monitoring_metrics_volume_size") and
            # The monitoring is currently enabled
            getattr(self.instance, "monitoring_enabled", False) and
            # The monitoring will still be enabled after the changes are applied
            data.get("monitoring_enabled", True) and
            # The new volume size is less than the previous volume size
            data["monitoring_metrics_volume_size"] < self.instance.monitoring_metrics_volume_size
        ):
            raise serializers.ValidationError({
                "monitoring_metrics_volume_size": (
                    "Decreasing the size of the metrics volume is not permitted."
                ),
            })

        # Similar for the logs volume
        if (
            data.get("monitoring_logs_volume_size") and
            getattr(self.instance, "monitoring_enabled", False) and
            data.get("monitoring_enabled", True) and
            data["monitoring_logs_volume_size"] < self.instance.monitoring_logs_volume_size
        ):
            raise serializers.ValidationError({
                "monitoring_logs_volume_size": (
                    "Decreasing the size of the logs volume is not permitted."
                ),
            })

        # The data is good
        return data

    def validate_template(self, value):
        capi_session = self.context["capi_session"]
        try:
            template = capi_session.find_cluster_template(value)
        except errors.ObjectNotFoundError as exc:
            raise serializers.ValidationError(str(exc))
        # When picking a new template, it must not be deprecated
        if template.deprecated:
            raise serializers.ValidationError("Selected template is deprecated.")
        return template

    def validate_control_plane_size(self, value):
        session = self.context["session"]
        try:
            return session.find_size(value)
        except errors.ObjectNotFoundError as exc:
            raise serializers.ValidationError(str(exc))

    def validate_node_groups(self, value):
        # There must be at least one worker node, or the cluster will not deploy
        min_worker_count = 0
        for ng in value:
            min_worker_count += ng["min_count"] if ng["autoscale"] else ng["count"]
        if min_worker_count < 1:
            raise serializers.ValidationError("There must be at least one worker node.")
        return value


class CreateKubernetesClusterSerializer(
    KubernetesClusterValidationMixin,
    serializers.Serializer
):
    name = serializers.RegexField("^[a-z][a-z0-9-]+[a-z0-9]$")
    template = serializers.RegexField("^[a-z0-9-]+$")
    control_plane_size = serializers.RegexField(ID_REGEX)
    node_groups = NodeGroupSpecSerializer(many = True)
    autohealing_enabled = serializers.BooleanField(default = True)
    dashboard_enabled = serializers.BooleanField(default = False)
    ingress_enabled = serializers.BooleanField(default = False)
    ingress_controller_load_balancer_ip = serializers.IPAddressField(
        protocol = "IPv4",
        allow_null = True,
        default = None
    )
    monitoring_enabled = serializers.BooleanField(default = False)
    monitoring_metrics_volume_size = serializers.IntegerField(
        min_value = 1,
        default = 10
    )
    monitoring_logs_volume_size = serializers.IntegerField(
        min_value = 1,
        default = 10
    )
    schedule = PlatformScheduleSerializer(allow_null = True, default = None)

    def validate_schedule(self, value):
        if self.context.get("validate_schedule", True):
            if cloud_settings.SCHEDULING.ENABLED and not value:
                raise serializers.ValidationError("This field is required.")
            elif not cloud_settings.SCHEDULING.ENABLED and value:
                raise serializers.ValidationError("Scheduling is not supported.")
        return value


class UpdateKubernetesClusterSerializer(
    KubernetesClusterValidationMixin,
    serializers.Serializer
):
    template = serializers.RegexField("^[a-z0-9-]+$", required = False)
    control_plane_size = serializers.RegexField(ID_REGEX, required = False)
    node_groups = NodeGroupSpecSerializer(many = True, required = False)
    autohealing_enabled = serializers.BooleanField(required = False)
    dashboard_enabled = serializers.BooleanField(required = False)
    ingress_enabled = serializers.BooleanField(required = False)
    ingress_controller_load_balancer_ip = serializers.IPAddressField(
        protocol = "IPv4",
        allow_null = True,
        required = False
    )
    monitoring_enabled = serializers.BooleanField(required = False)
    monitoring_metrics_volume_size = serializers.IntegerField(
        required = False,
        min_value = 1
    )
    monitoring_logs_volume_size = serializers.IntegerField(
        required = False,
        min_value = 1
    )

    def validate(self, data):
        if "template" in data and len(data) > 1:
            raise serializers.ValidationError("If template is given, no other fields are permitted.")
        return super().validate(data)

    def validate_template(self, value):
        capi_session = self.context["capi_session"]
        current_template = capi_session.find_cluster_template(self.instance.template_id)
        current_version = easysemver.Version(current_template.kubernetes_version)
        next_template = super().validate_template(value)
        next_version = easysemver.Version(next_template.kubernetes_version)
        # The template is not permitted to be a downgrade
        if next_version < current_version:
            raise serializers.ValidationError("Downgrading is not supported.")
        # Prevent the major version from changing
        # TODO(mkjpryor) change this if Kubernetes 2.x is ever released and upgrade is allowed
        if next_version.major != current_version.major:
            raise serializers.ValidationError("Upgrading to a new major version is not supported.")
        # The template can only be bumped by one minor version
        if next_version.minor > current_version.minor.increment():
            raise serializers.ValidationError("Upgrading by more than one minor version is not supported.")
        # Make sure that the new template is within one minor version of the oldest node
        # NOTE(mkjpryor) this is stricter than the official Kubernetes skew policy, which
        #                allows kubelet to be up to three minor versions old, but enforcing
        #                the stricter constraint here reduces the risk of races in the
        #                control plane when multiple upgrades are applied without waiting
        #                for the previous one to finish
        oldest_kubelet_version = min(
            easysemver.Version(node.kubelet_version)
            for node in self.instance.nodes
            if node.kubelet_version
        )
        if next_version.minor > oldest_kubelet_version.minor.increment():
            raise serializers.ValidationError(
                "Upgrading to more than one minor version newer than "
                "the oldest node is not supported."
            )
        return next_template


class KubernetesAppTemplateRefSerializer(RefSerializer):
    def get_self_link(self, request, tenant, id):
        return request.build_absolute_uri(
            reverse("azimuth:kubernetes_app_template_details", kwargs = {
                "tenant": tenant,
                "template": id,
            })
        )


KubernetesAppTemplateVersionSerializer = type(
    "KubernetesAppTemplateVersionSerializer",
    (make_dto_serializer(capi_dto.Version), ),
    {}
)


class KubernetesAppTemplateSerializer(
    KubernetesAppTemplateRefSerializer,
    make_dto_serializer(capi_dto.AppTemplate, exclude = ["chart", "default_values"])
):
    versions = KubernetesAppTemplateVersionSerializer(many = True)


class KubernetesAppSerializer(
    make_dto_serializer(
        capi_dto.App,
        exclude = [
            "template_id",
            "kubernetes_cluster_id",
            "services",
        ]
    )
):
    template = KubernetesAppTemplateRefSerializer(source = "template_id", read_only = True)
    kubernetes_cluster = KubernetesClusterRefSerializer(
        source = "kubernetes_cluster_id",
        read_only = True
    )
    services = serializers.SerializerMethodField()

    def get_services(self, obj):
        request = self.context.get("request")
        tenant = self.context.get("tenant")
        services = []
        for service_dto in obj.services:
            service_obj = dataclasses.asdict(service_dto)
            service_obj["url"] = request.build_absolute_uri(
                reverse("azimuth:kubernetes_app_service", kwargs = {
                    "tenant": tenant,
                    "app": obj.id,
                    "service": service_dto.name,
                })
            )
            services.append(service_obj)
        return services

    def to_representation(self, obj):
        result = super().to_representation(obj)
        # If the info to build a link is in the context, add it
        request = self.context.get("request")
        tenant = self.context.get("tenant")
        if request and tenant:
            result.setdefault("links", {}).update({
                "self": request.build_absolute_uri(
                    reverse("azimuth:kubernetes_app_details", kwargs = {
                        "tenant": tenant,
                        "app": obj.id,
                    })
                ),
            })
        return result


def get_full_values(app_template, user_values):
    """
    Given the app template and user values, return the values to be validated once
    any default values in the app template have been merged.
    """
    def mergeconcat2(defaults, overrides):
        if isinstance(defaults, dict) and isinstance(overrides, dict):
            merged = dict(defaults)
            for key, value in overrides.items():
                if key in defaults:
                    merged[key] = mergeconcat2(defaults[key], value)
                else:
                    merged[key] = value
            return merged
        elif isinstance(defaults, (list, tuple)) and isinstance(overrides, (list, tuple)):
            merged = list(defaults)
            merged.extend(overrides)
            return merged
        else:
            return overrides if overrides is not None else defaults
    return mergeconcat2(app_template.default_values, user_values)


class CreateKubernetesAppSerializer(serializers.Serializer):
    name = serializers.RegexField("^[a-z][a-z0-9-]+[a-z0-9]$", write_only = True)
    template = serializers.RegexField("^[a-z0-9-]+$", write_only = True)
    kubernetes_cluster = serializers.RegexField("^[a-z0-9-]+$", write_only = True)
    values = serializers.JSONField(write_only = True)

    def validate_template(self, value):
        capi_session = self.context["capi_session"]
        try:
            return capi_session.find_app_template(value)
        except errors.ObjectNotFoundError as exc:
            raise serializers.ValidationError(str(exc))

    def validate_kubernetes_cluster(self, value):
        capi_session = self.context["capi_session"]
        try:
            return capi_session.find_cluster(value)
        except errors.ObjectNotFoundError as exc:
            raise serializers.ValidationError(str(exc))

    def validate(self, data):
        # Use the JSON schema defined by the template to validate the values
        # For create, we use the most recent version
        if "template" in data and "values" in data:
            values = get_full_values(data["template"], data["values"] or {})
            schema = data["template"].versions[0].values_schema
            try:
                jsonschema.validate(values, schema)
            except jsonschema.ValidationError as exc:
                path = "/" + "/".join(exc.absolute_path)
                raise serializers.ValidationError({ "values": { path: exc.message }})
            else:
                data["values"] = values
        return data


class UpdateKubernetesAppSerializer(serializers.Serializer):
    version = serializers.RegexField("^[a-zA-Z0-9+.-]+$", write_only = True)
    values = serializers.JSONField(write_only = True)

    def validate_version(self, value):
        app_template = self.context["app_template"]
        # Get the index of the new version in the versions
        try:
            new_version_idx = next(
                idx
                for idx, version in enumerate(app_template.versions)
                if version.name == value
            )
        except StopIteration:
            raise serializers.ValidationError(f"Version \"{value}\" is not valid")
        # We want to make sure that the new version is at least as new as the current
        app = self.context["app"]
        try:
            current_version_idx = next(
                idx
                for idx, version in enumerate(app_template.versions)
                if version.name == app.version
            )
        except StopIteration:
            # If the current version is not in the list, any version is good
            pass
        else:
            # Versions are ordered from the latest to the oldest
            # So the new version must be closer to the front of the list than current
            if new_version_idx > current_version_idx:
                raise serializers.ValidationError("Downgrading an app is not supported")
        # Return the new version
        return app_template.versions[new_version_idx]

    def validate(self, data):
        # Use the JSON schema defined by the version to validate the values
        if "version" in data and "values" in data:
            values = get_full_values(self.context["app_template"], data["values"] or {})
            schema = data["version"].values_schema
            try:
                jsonschema.validate(values, schema)
            except jsonschema.ValidationError as exc:
                path = "/" + "/".join(exc.absolute_path)
                raise serializers.ValidationError({ "values": { path: exc.message }})
            else:
                data["values"] = values
        return data
