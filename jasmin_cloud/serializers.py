"""
Django REST framework serializers for objects from the :py:mod:`~.cloud.dto` package.
"""

import collections

from django.urls import reverse

from rest_framework import serializers

from .provider import dto, errors


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
    return type(
        dto_class.__name__ + 'Serializer',
        (serializers.Serializer, ),
        {
            name: serializers.ReadOnlyField()
            for name in dto_class._fields
            if name not in exclude
        }
    )


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(write_only = True)
    password = serializers.CharField(
        write_only = True,
        style = { 'input_type': 'password' }
    )


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


class ImageSerializer(make_dto_serializer(dto.Image, exclude = ['vm_type'])):
    def to_representation(self, obj):
        result = super().to_representation(obj)
        # If the info to build a link is in the context, add it
        request = self.context.get('request')
        tenant = self.context.get('tenant')
        if request and tenant:
            result.setdefault('links', {})['self'] = request.build_absolute_uri(
                reverse('jasmin_cloud:image_details', kwargs = {
                    'tenant': tenant,
                    'image': obj.id,
                })
            )
        return result


class SizeSerializer(make_dto_serializer(dto.Size)):
    def to_representation(self, obj):
        result = super().to_representation(obj)
        # If the info to build a link is in the context, add it
        request = self.context.get('request')
        tenant = self.context.get('tenant')
        if request and tenant:
            result.setdefault('links', {})['self'] = request.build_absolute_uri(
                reverse('jasmin_cloud:size_details', kwargs = {
                    'tenant': tenant,
                    'size': obj.id,
                })
            )
        return result


Ref = collections.namedtuple('Ref', ['id'])


class VolumeRefSerializer(serializers.Serializer):
    id = serializers.ReadOnlyField()

    def to_representation(self, obj):
        result = super().to_representation(obj)
        # If the info to build a link is in the context, add it
        request = self.context.get('request')
        tenant = self.context.get('tenant')
        if request and tenant:
            result.setdefault('links', {})['self'] = request.build_absolute_uri(
                reverse('jasmin_cloud:volume_details', kwargs = {
                    'tenant': tenant,
                    'volume': obj.id,
                })
            )
        return result


class MachineRefSerializer(serializers.Serializer):
    id = serializers.ReadOnlyField()

    def to_representation(self, obj):
        result = super().to_representation(obj)
        # If the info to build a link is in the context, add it
        request = self.context.get('request')
        tenant = self.context.get('tenant')
        if request and tenant:
            result.setdefault('links', {}).update({
                'self': request.build_absolute_uri(
                    reverse('jasmin_cloud:machine_details', kwargs = {
                        'tenant': tenant,
                        'machine': obj.id,
                    })
                ),
            })
        return result


class VolumeSerializer(
    VolumeRefSerializer,
    make_dto_serializer(dto.Volume, exclude = ['status', 'machine_id'])
):
    status = serializers.ReadOnlyField(source = 'status.name')
    machine = MachineRefSerializer(read_only = True, allow_null = True)

    def to_representation(self, obj):
        # Convert raw ids to refs before serializing
        obj.machine = Ref(obj.machine_id) if obj.machine_id else None
        return super().to_representation(obj)


class CreateVolumeSerializer(serializers.Serializer):
    name = serializers.CharField(write_only = True)
    size = serializers.IntegerField(write_only = True, min_value = 1)


class UpdateVolumeSerializer(serializers.Serializer):
    machine_id = serializers.UUIDField(write_only = True, allow_null = True)


class MachineStatusSerializer(make_dto_serializer(dto.Machine.Status)):
    type = serializers.ReadOnlyField(source = 'type.name')


class MachineSerializer(
    MachineRefSerializer,
    make_dto_serializer(dto.Machine, exclude = ['attached_volume_ids'])
):
    name = serializers.CharField()

    image = ImageSerializer(read_only = True)
    image_id = serializers.UUIDField(write_only = True)

    size = SizeSerializer(read_only = True)
    size_id = serializers.RegexField('^[a-z0-9-]+$', write_only = True)

    status = MachineStatusSerializer(read_only = True)
    attached_volumes = VolumeRefSerializer(many = True, read_only = True)

    def to_representation(self, obj):
        # Convert volume ids to refs before serializing
        obj.attached_volumes = [Ref(v) for v in obj.attached_volume_ids]
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
    machine = MachineRefSerializer(read_only = True, allow_null = True)
    machine_id = serializers.UUIDField(write_only = True, allow_null = True)

    def to_representation(self, obj):
        # Convert raw ids to refs before serializing
        obj.machine = Ref(obj.machine_id) if obj.machine_id else None
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


class ClusterTypeRefSerializer(serializers.Serializer):
    name = serializers.ReadOnlyField()

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


ClusterTypeParameterSerializer = make_dto_serializer(dto.ClusterType.Parameter)


class ClusterTypeSerializer(
    ClusterTypeRefSerializer,
    make_dto_serializer(dto.ClusterType)
):
    parameters = ClusterTypeParameterSerializer(many = True, read_only = True)


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
        return data

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
