"""
Django REST framework serializers for objects from the :py:mod:`~.cloud.dto` package.
"""

import collections
import dataclasses
import ipaddress

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives.serialization import load_ssh_public_key

from django.urls import reverse

from rest_framework import serializers

from .cluster_api import dto as capi_dto, errors as capi_errors
from .provider import dto, errors
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
    name = serializers.CharField(write_only = True)
    size = serializers.IntegerField(write_only = True, min_value = 1)


class UpdateVolumeSerializer(serializers.Serializer):
    machine_id = serializers.UUIDField(write_only = True, allow_null = True)


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
    web_console_enabled = serializers.SerializerMethodField()

    def get_nat_allowed(self, obj):
        # The value in the metadata will be a string 1 or 0
        # If the metadata is not present, NAT is allowed
        return obj.metadata.get("nat_allowed", "1") == "1"

    def get_web_console_enabled(self, obj):
        # The value in the metadata will be a string 1 or 0
        # If the metadata is not present, the web console is not enabled
        return obj.metadata.get("web_console_enabled", "0") == "1"

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
                "console": request.build_absolute_uri(
                    reverse("azimuth:machine_console", kwargs = {
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
    name = serializers.CharField(write_only = True)
    image_id = serializers.UUIDField(write_only = True)
    size_id = serializers.RegexField("^[a-z0-9-]+$", write_only = True)
    web_console_enabled = serializers.BooleanField(default = False, write_only = True)
    desktop_enabled = serializers.BooleanField(default = False, write_only = True)


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
    machine_id = serializers.UUIDField(write_only = True, allow_null = True)

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


ClusterParameterSerializer = make_dto_serializer(dto.ClusterParameter)


class ClusterTypeSerializer(make_dto_serializer(dto.ClusterType)):
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


class ClusterSerializer(make_dto_serializer(dto.Cluster)):
    status = serializers.ReadOnlyField(source = "status.name")

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
    name = serializers.CharField(write_only = True)
    cluster_type = serializers.CharField(write_only = True)
    parameter_values = serializers.JSONField(write_only = True)

    def validate_cluster_type(self, value):
        # Find the cluster type
        # Convert not found errors into validation errors
        session = self.context["session"]
        try:
            return session.find_cluster_type(value)
        except errors.ObjectNotFoundError as exc:
            raise serializers.ValidationError(str(exc))

    def validate(self, data):
        # Force a validation of the parameter values for the cluster type
        # Convert the provider error into a DRF ValidationError
        session = self.context["session"]
        try:
            data["parameter_values"] = session.validate_cluster_params(
                data["cluster_type"],
                data["parameter_values"]
            )
        except errors.ValidationError as exc:
            raise serializers.ValidationError({ "parameter_values": exc.errors })
        return data


class UpdateClusterSerializer(serializers.Serializer):
    parameter_values = serializers.JSONField(write_only = True)

    def validate(self, data):
        # Force a validation of the parameter values against the cluster
        # type for the cluster
        # Convert the provider error into a DRF ValidationError
        session = self.context["session"]
        cluster = self.context["cluster"]
        try:
            data["parameter_values"] = session.validate_cluster_params(
                cluster.cluster_type,
                data["parameter_values"],
                cluster.parameter_values
            )
        except errors.ValidationError as exc:
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


class KubernetesClusterNodeSerializer(make_dto_serializer(capi_dto.Node)):
    pass


class KubernetesClusterSerializer(
    make_dto_serializer(
        capi_dto.Cluster,
        exclude = [
            "template_id",
            "control_plane_size_id",
            "node_groups",
            "nodes",
        ]
    )
):
    template = KubernetesClusterTemplateRefSerializer(source = "template_id", read_only = True)
    control_plane_size = SizeRefSerializer(source = "control_plane_size_id", read_only = True)
    node_groups = KubernetesClusterNodeGroupSerializer(many = True, read_only = True)
    nodes = KubernetesClusterNodeSerializer(many = True, read_only = True)
    # master_size = SizeRefSerializer(source = "master_size_id", read_only = True)
    # worker_size = SizeRefSerializer(source = "worker_size_id", read_only = True)
    # template = KubernetesClusterTemplateRefSerializer(
    #     source = "template_id",
    #     read_only = True
    # )
    # status = serializers.ReadOnlyField(
    #     source = "status.name",
    #     read_only = True
    # )
    # health_status = serializers.ReadOnlyField(
    #     source = "health_status.name",
    #     allow_null = True,
    #     read_only = True
    # )

    def to_representation(self, obj):
        result = super().to_representation(obj)
        # If the info to build a link is in the context, add it
        request = self.context.get("request")
        tenant = self.context.get("tenant")
        if request and tenant:
            result.setdefault("links", {}).update({
                "self": request.build_absolute_uri(
                    reverse("azimuth:kubernetes_cluster_details", kwargs = {
                        "tenant": tenant,
                        "cluster": obj.id,
                    })
                ),
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
    machine_size = serializers.RegexField("^[a-z0-9-]+$")
    count = serializers.IntegerField(min_value = 0)

    def validate_machine_size(self, value):
        session = self.context["session"]
        try:
            return session.find_size(value)
        except errors.ObjectNotFoundError as exc:
            raise serializers.ValidationError(str(exc))


class CreateKubernetesClusterSerializer(serializers.Serializer):
    name = serializers.RegexField("^[a-z][a-z0-9-]+[a-z0-9]$")
    template = serializers.RegexField("^[a-z0-9-]+$")
    control_plane_size = serializers.RegexField("^[a-z0-9-]+$")
    node_groups = NodeGroupSpecSerializer(many = True)
    autohealing_enabled = serializers.BooleanField(default = True)
    cert_manager_enabled = serializers.BooleanField(default = False)
    ingress_enabled = serializers.BooleanField(default = False)
    monitoring_enabled = serializers.BooleanField(default = False)

    def validate_template(self, value):
        capi_session = self.context["capi_session"]
        try:
            return capi_session.find_cluster_template(value)
        except errors.ObjectNotFoundError as exc:
            raise serializers.ValidationError(str(exc))

    def validate_control_plane_size(self, value):
        session = self.context["session"]
        try:
            return session.find_size(value)
        except errors.ObjectNotFoundError as exc:
            raise serializers.ValidationError(str(exc))

    def validate_node_groups(self, value):
        # There must be at least one actual node, or the cluster will not deploy
        if sum(ng["count"] for ng in value) < 1:
            raise serializers.ValidationError("There must be at least one worker node.")
        return value


class UpdateKubernetesClusterSerializer(serializers.Serializer):
    template = serializers.RegexField("^[a-z0-9-]+$", required = False)
    control_plane_size = serializers.RegexField("^[a-z0-9-]+$", required = False)
    node_groups = NodeGroupSpecSerializer(many = True, required = False)
    autohealing_enabled = serializers.BooleanField(required = False)
    cert_manager_enabled = serializers.BooleanField(required = False)
    ingress_enabled = serializers.BooleanField(required = False)
    monitoring_enabled = serializers.BooleanField(required = False)

    def validate(self, data):
        if "template" in data and len(data) > 1:
            raise serializers.ValidationError("If template is given, no other fields are permitted.")
        return data

    def validate_template(self, value):
        capi_session = self.context["capi_session"]
        try:
            return capi_session.find_cluster_template(value)
        except errors.ObjectNotFoundError as exc:
            raise serializers.ValidationError(str(exc))

    def validate_control_plane_size(self, value):
        session = self.context["session"]
        try:
            return session.find_size(value)
        except errors.ObjectNotFoundError as exc:
            raise serializers.ValidationError(str(exc))

    def validate_node_groups(self, value):
        # There must be at least one actual node, or the cluster will not deploy
        if sum(ng["count"] for ng in value) < 1:
            raise serializers.ValidationError("There must be at least one worker node.")
        return value
