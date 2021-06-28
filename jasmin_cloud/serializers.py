"""
Django REST framework serializers for objects from the :py:mod:`~.cloud.dto` package.
"""

import collections
import dataclasses

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives.serialization import load_ssh_public_key

from django.urls import reverse

from rest_framework import serializers

from .provider import dto, errors
from .settings import cloud_settings


def make_dto_serializer(dto_class, exclude = []):
    """
    Returns a new serializer class for the given DTO class, which should be
    a ``namedtuple``.

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
        dto_class.__name__ + 'Serializer',
        (serializers.Serializer, ),
        {
            name: serializers.ReadOnlyField()
            for name in fields
            if name not in exclude
        }
    )


Ref = collections.namedtuple('Ref', ['id'])


class RefSerializer(serializers.Serializer):
    id = serializers.ReadOnlyField()

    def to_representation(self, obj):
        # If the object is falsey, the representation is None
        if not obj:
            return None
        # If the given object is a scalar, convert it to a ref first
        if not hasattr(obj, 'id'):
            obj = Ref(obj)
        result = super().to_representation(obj)
        # If the info to build a link is in the context, add it
        request = self.context.get('request')
        tenant = self.context.get('tenant')
        if request and tenant:
            result.setdefault('links', {})['self'] = self.get_self_link(
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
        if key_type == 'ssh-rsa' and public_key.key_size < cloud_settings.SSH_RSA_MIN_BITS:
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
        request = self.context.get('request')
        if request:
            result.setdefault('links', {}).update({
                'quotas': request.build_absolute_uri(
                    reverse('jasmin_cloud:quotas', kwargs = {
                        'tenant': obj.id,
                    })
                ),
                'images': request.build_absolute_uri(
                    reverse('jasmin_cloud:images', kwargs = {
                        'tenant': obj.id,
                    })
                ),
                'sizes': request.build_absolute_uri(
                    reverse('jasmin_cloud:sizes', kwargs = {
                        'tenant': obj.id,
                    })
                ),
                'volumes': request.build_absolute_uri(
                    reverse('jasmin_cloud:volumes', kwargs = {
                        'tenant': obj.id,
                    })
                ),
                'external_ips': request.build_absolute_uri(
                    reverse('jasmin_cloud:external_ips', kwargs = {
                        'tenant': obj.id,
                    })
                ),
                'machines': request.build_absolute_uri(
                    reverse('jasmin_cloud:machines', kwargs = {
                        'tenant': obj.id,
                    })
                ),
                'kubernetes_cluster_templates': request.build_absolute_uri(
                    reverse('jasmin_cloud:kubernetes_cluster_templates', kwargs = {
                        'tenant': obj.id,
                    })
                ),
                'kubernetes_clusters': request.build_absolute_uri(
                    reverse('jasmin_cloud:kubernetes_clusters', kwargs = {
                        'tenant': obj.id,
                    })
                ),
                'cluster_types': request.build_absolute_uri(
                    reverse('jasmin_cloud:cluster_types', kwargs = {
                        'tenant': obj.id,
                    })
                ),
                'clusters': request.build_absolute_uri(
                    reverse('jasmin_cloud:clusters', kwargs = {
                        'tenant': obj.id,
                    })
                ),
            })
        return result


QuotaSerializer = make_dto_serializer(dto.Quota)


class ImageRefSerializer(RefSerializer):
    def get_self_link(self, request, tenant, id):
        return request.build_absolute_uri(
            reverse('jasmin_cloud:image_details', kwargs = {
                'tenant': tenant,
                'image': id,
            })
        )


ImageSerializer = type(
    'ImageSerializer',
    (ImageRefSerializer, make_dto_serializer(dto.Image, exclude = ['vm_type'])),
    {}
)


class SizeRefSerializer(RefSerializer):
    def get_self_link(self, request, tenant, id):
        return request.build_absolute_uri(
            reverse('jasmin_cloud:size_details', kwargs = {
                'tenant': tenant,
                'size': id,
            })
        )


SizeSerializer = type(
    'SizeSerializer',
    (SizeRefSerializer, make_dto_serializer(dto.Size)),
    {}
)


class VolumeRefSerializer(RefSerializer):
    def get_self_link(self, request, tenant, id):
        return request.build_absolute_uri(
            reverse('jasmin_cloud:volume_details', kwargs = {
                'tenant': tenant,
                'volume': id,
            })
        )


class MachineRefSerializer(RefSerializer):
    def get_self_link(self, request, tenant, id):
        return request.build_absolute_uri(
            reverse('jasmin_cloud:machine_details', kwargs = {
                'tenant': tenant,
                'machine': id,
            })
        )


class VolumeSerializer(
    VolumeRefSerializer,
    make_dto_serializer(dto.Volume, exclude = ['status', 'machine_id'])
):
    status = serializers.ReadOnlyField(source = 'status.name')
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
    type = serializers.ReadOnlyField(source = 'type.name')


class MachineSerializer(
    MachineRefSerializer,
    make_dto_serializer(dto.Machine, exclude = ['attached_volume_ids'])
):
    name = serializers.CharField()

    image = ImageRefSerializer(source = "image_id", read_only = True)
    image_id = serializers.UUIDField(write_only = True)

    size = SizeRefSerializer(source = "size_id", read_only = True)
    size_id = serializers.RegexField('^[a-z0-9-]+$', write_only = True)

    status = MachineStatusSerializer(read_only = True)
    attached_volumes = VolumeRefSerializer(
        source = 'attached_volume_ids',
        many = True,
        read_only = True
    )

    def to_representation(self, obj):
        result = super().to_representation(obj)
        # If the info to build a link is in the context, add it
        request = self.context.get('request')
        tenant = self.context.get('tenant')
        if request and tenant:
            result.setdefault('links', {}).update({
                'start': request.build_absolute_uri(
                    reverse('jasmin_cloud:machine_start', kwargs = {
                        'tenant': tenant,
                        'machine': obj.id,
                    })
                ),
                'stop': request.build_absolute_uri(
                    reverse('jasmin_cloud:machine_stop', kwargs = {
                        'tenant': tenant,
                        'machine': obj.id,
                    })
                ),
                'restart': request.build_absolute_uri(
                    reverse('jasmin_cloud:machine_restart', kwargs = {
                        'tenant': tenant,
                        'machine': obj.id,
                    })
                ),
            })
        return result


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
        request = self.context.get('request')
        tenant = self.context.get('tenant')
        if request and tenant:
            result.setdefault('links', {})['self'] = request.build_absolute_uri(
                reverse('jasmin_cloud:external_ip_details', kwargs = {
                    'tenant': tenant,
                    'ip': obj.id,
                })
            )
        return result


class KubernetesClusterTemplateRefSerializer(RefSerializer):
    def get_self_link(self, request, tenant, id):
        return request.build_absolute_uri(
            reverse('jasmin_cloud:kubernetes_cluster_template_details', kwargs = {
                'tenant': tenant,
                'template': id,
            })
        )


KubernetesClusterTemplateSerializer = type(
    'KubernetesClusterTemplateSerializer',
    (
        KubernetesClusterTemplateRefSerializer,
        make_dto_serializer(dto.KubernetesClusterTemplate)
    ),
    {}
)


class KubernetesClusterSerializer(
    make_dto_serializer(
        dto.KubernetesCluster,
        exclude = [
            'template_id',
            'master_size_id',
            'worker_size_id',
            'status',
            'health_status'
        ]
    )
):
    master_size = SizeRefSerializer(source = 'master_size_id', read_only = True)
    worker_size = SizeRefSerializer(source = 'worker_size_id', read_only = True)
    template = KubernetesClusterTemplateRefSerializer(
        source = 'template_id',
        read_only = True
    )
    status = serializers.ReadOnlyField(
        source = 'status.name',
        read_only = True
    )
    health_status = serializers.ReadOnlyField(
        source = 'health_status.name',
        allow_null = True,
        read_only = True
    )

    def to_representation(self, obj):
        result = super().to_representation(obj)
        # If the info to build a link is in the context, add it
        request = self.context.get('request')
        tenant = self.context.get('tenant')
        if request and tenant:
            result.setdefault('links', {})['self'] = request.build_absolute_uri(
                reverse('jasmin_cloud:kubernetes_cluster_details', kwargs = {
                    'tenant': tenant,
                    'cluster': obj.id,
                })
            )
        return result


class CreateKubernetesClusterSerializer(serializers.Serializer):
    name = serializers.RegexField('^[a-z0-9-_]+$')
    template_id = serializers.RegexField('^[a-z0-9-]+$')
    master_size_id = serializers.RegexField('^[a-z0-9-]+$')
    worker_size_id = serializers.RegexField('^[a-z0-9-]+$')
    monitoring_enabled = serializers.BooleanField(default = False)
    grafana_admin_password = serializers.CharField(required = False)
    auto_healing_enabled = serializers.BooleanField(default = False)
    auto_scaling_enabled = serializers.BooleanField(default = False)
    # Worker count should be given if auto-scaling is not enabled
    worker_count = serializers.IntegerField(required = False, min_value = 1)
    # If auto-scaling is enabled, min and max worker count should be given
    min_worker_count = serializers.IntegerField(required = False, min_value = 1)
    max_worker_count = serializers.IntegerField(required = False, min_value = 1)

    def validate(self, data):
        errors = {}
        if data['auto_scaling_enabled']:
            if 'min_worker_count' not in data:
                errors['min_worker_count'] = [
                    'This field is required when auto-scaling is enabled.',
                ]
            elif 'max_worker_count' not in data:
                errors['max_worker_count'] = [
                    'This field is required when auto-scaling is enabled.',
                ]
            elif data['max_worker_count'] < data['min_worker_count']:
                errors['max_worker_count'] = [
                    'Must be greater than or equal to min worker count.',
                ]
        else:
            if 'worker_count' not in data:
                errors['worker_count'] = [
                    'This field is required when auto-scaling is not enabled.',
                ]
        if data['monitoring_enabled'] and 'grafana_admin_password' not in data:
            errors['grafana_admin_password'] = [
                'This field is required when monitoring is enabled.',
            ]
        if errors:
            raise serializers.ValidationError(errors)
        else:
            return data


class UpdateKubernetesClusterSerializer(serializers.Serializer):
    pass


ClusterParameterSerializer = make_dto_serializer(dto.ClusterParameter)


class ClusterTypeSerializer(make_dto_serializer(dto.ClusterType)):
    parameters = ClusterParameterSerializer(many = True, read_only = True)

    def to_representation(self, obj):
        result = super().to_representation(obj)
        # If the info to build a link is in the context, add it
        request = self.context.get('request')
        tenant = self.context.get('tenant')
        if request and tenant:
            result.setdefault('links', {})['self'] = request.build_absolute_uri(
                reverse('jasmin_cloud:cluster_type_details', kwargs = {
                    'tenant': tenant,
                    'cluster_type': obj.name,
                })
            )
        return result


class ClusterSerializer(make_dto_serializer(dto.Cluster)):
    status = serializers.ReadOnlyField(source = 'status.name')

    def to_representation(self, obj):
        result = super().to_representation(obj)
        # If the info to build a link is in the context, add it
        request = self.context.get('request')
        tenant = self.context.get('tenant')
        if request and tenant:
            result.setdefault('links', {}).update({
                'self': request.build_absolute_uri(
                    reverse('jasmin_cloud:cluster_details', kwargs = {
                        'tenant': tenant,
                        'cluster': obj.id,
                    })
                ),
                'patch': request.build_absolute_uri(
                    reverse('jasmin_cloud:cluster_patch', kwargs = {
                        'tenant': tenant,
                        'cluster': obj.id,
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
        session = self.context['session']
        try:
            return session.find_cluster_type(value)
        except errors.ObjectNotFoundError as exc:
            raise serializers.ValidationError(str(exc))

    def validate(self, data):
        # Force a validation of the parameter values for the cluster type
        # Convert the provider error into a DRF ValidationError
        session = self.context['session']
        try:
            data['parameter_values'] = session.validate_cluster_params(
                data['cluster_type'],
                data['parameter_values']
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
        session = self.context['session']
        cluster = self.context['cluster']
        try:
            data['parameter_values'] = session.validate_cluster_params(
                cluster.cluster_type,
                data['parameter_values'],
                cluster.parameter_values
            )
        except errors.ValidationError as exc:
            raise serializers.ValidationError({ "parameter_values": exc.errors })
        return data
