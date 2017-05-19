"""
This module contains the `Django REST framework serializers`_ for the JASMIN Cloud API.

These serializers marshall objects from the :py:mod:`.provider.dto` package.

.. _Django REST framework serializers: http://www.django-rest-framework.org/api-guide/serializers/
"""

from django.urls import reverse
from django.contrib.auth import authenticate

from rest_framework import serializers

from .provider import dto


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(style = { 'input_type' : 'password' })


class TenancySerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only = True)
    name = serializers.CharField(read_only = True)

    def to_representation(self, obj):
        result = super().to_representation(obj)
        # If the info to build a link is in the context, add it
        request = self.context.get('request')
        if request:
            result.setdefault('links', {}).update({
                'quotas' : request.build_absolute_uri(
                    reverse('jasmin_cloud:quotas', kwargs = {
                        'tenant' : obj.id,
                    })
                ),
                'images' : request.build_absolute_uri(
                    reverse('jasmin_cloud:images', kwargs = {
                        'tenant' : obj.id,
                    })
                ),
                'sizes' : request.build_absolute_uri(
                    reverse('jasmin_cloud:sizes', kwargs = {
                        'tenant' : obj.id,
                    })
                ),
                'external_ips' : request.build_absolute_uri(
                    reverse('jasmin_cloud:external_ips', kwargs = {
                        'tenant' : obj.id,
                    })
                ),
                'machines' : request.build_absolute_uri(
                    reverse('jasmin_cloud:machines', kwargs = {
                        'tenant' : obj.id,
                    })
                ),
            })
        return result


class QuotaSerializer(serializers.Serializer):
    resource = serializers.CharField(read_only = True)
    units = serializers.CharField(read_only = True, allow_null = True)
    allocated = serializers.IntegerField(read_only = True)
    used = serializers.IntegerField(read_only = True)


class ImageSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only = True)
    name = serializers.CharField(read_only = True)
    is_public = serializers.BooleanField(read_only = True)
    nat_allowed = serializers.BooleanField(read_only = True)
    size = serializers.DecimalField(
        None, # No limit on the number of digits
        decimal_places = 2,
        coerce_to_string = False,
        read_only = True
    )

    def to_representation(self, obj):
        result = super().to_representation(obj)
        # If the info to build a link is in the context, add it
        request = self.context.get('request')
        tenant = self.context.get('tenant')
        if request and tenant:
            result.setdefault('links', {})['self'] = request.build_absolute_uri(
                reverse('jasmin_cloud:image_details', kwargs = {
                    'tenant' : tenant,
                    'image' : obj.id,
                })
            )
        return result


class SizeSerializer(serializers.Serializer):
    id = serializers.RegexField('^[a-z0-9-]+$', read_only = True)
    name = serializers.CharField(read_only = True)
    cpus = serializers.IntegerField(read_only = True)
    ram = serializers.IntegerField(read_only = True)

    def to_representation(self, obj):
        result = super().to_representation(obj)
        # If the info to build a link is in the context, add it
        request = self.context.get('request')
        tenant = self.context.get('tenant')
        if request and tenant:
            result.setdefault('links', {})['self'] = request.build_absolute_uri(
                reverse('jasmin_cloud:size_details', kwargs = {
                    'tenant' : tenant,
                    'size' : obj.id,
                })
            )
        return result


class VolumeSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only = True)
    name = serializers.CharField(read_only = True)
    size = serializers.IntegerField(min_value = 1)
    device = serializers.CharField(read_only = True)

    def to_representation(self, obj):
        result = super().to_representation(obj)
        # If the info to build a link is in the context, add it
        request = self.context.get('request')
        tenant = self.context.get('tenant')
        if request and tenant:
            result.setdefault('links', {})['self'] = request.build_absolute_uri(
                reverse('jasmin_cloud:machine_volume_details', kwargs = {
                    'tenant' : tenant,
                    'machine' : obj.machine_id,
                    'volume' : obj.id,
                })
            )
        return result


class MachineStatusSerializer(serializers.Serializer):
    name = serializers.CharField(read_only = True)
    type = serializers.CharField(source = 'type.name', read_only = True)
    details = serializers.CharField(read_only = True)

class MachineSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only = True)
    name = serializers.RegexField('^[a-z0-9\.\-_]+$')

    image = ImageSerializer(read_only = True)
    image_id = serializers.UUIDField(write_only = True)

    size = SizeSerializer(read_only = True)
    size_id = serializers.RegexField('^[a-z0-9-]+$', write_only = True)

    status = MachineStatusSerializer(read_only = True)
    power_state = serializers.CharField(read_only = True)
    task = serializers.CharField(read_only = True)
    fault = serializers.CharField(read_only = True)
    internal_ips = serializers.ListField(
        child = serializers.IPAddressField(),
        read_only = True
    )
    external_ips = serializers.ListField(
        child = serializers.IPAddressField(),
        read_only = True
    )
    nat_allowed = serializers.BooleanField(read_only = True)
    attached_volumes = VolumeSerializer(many = True, read_only = True)
    owner = serializers.CharField(read_only = True)
    created = serializers.DateTimeField(read_only = True)

    def to_representation(self, obj):
        result = super().to_representation(obj)
        # If the info to build a link is in the context, add it
        request = self.context.get('request')
        tenant = self.context.get('tenant')
        if request and tenant:
            result.setdefault('links', {}).update({
                'self' : request.build_absolute_uri(
                    reverse('jasmin_cloud:machine_details', kwargs = {
                        'tenant' : tenant,
                        'machine' : obj.id,
                    })
                ),
                'start' : request.build_absolute_uri(
                    reverse('jasmin_cloud:machine_start', kwargs = {
                        'tenant' : tenant,
                        'machine' : obj.id,
                    })
                ),
                'stop' : request.build_absolute_uri(
                    reverse('jasmin_cloud:machine_stop', kwargs = {
                        'tenant' : tenant,
                        'machine' : obj.id,
                    })
                ),
                'restart' : request.build_absolute_uri(
                    reverse('jasmin_cloud:machine_restart', kwargs = {
                        'tenant' : tenant,
                        'machine' : obj.id,
                    })
                ),
                'attach_external_ip' : request.build_absolute_uri(
                    reverse('jasmin_cloud:machine_attach_external_ip', kwargs = {
                        'tenant' : tenant,
                        'machine' : obj.id,
                    })
                ),
                'detach_external_ips' : request.build_absolute_uri(
                    reverse('jasmin_cloud:machine_detach_external_ips', kwargs = {
                        'tenant' : tenant,
                        'machine' : obj.id,
                    })
                ),
                'volumes' : request.build_absolute_uri(
                    reverse('jasmin_cloud:machine_volumes', kwargs = {
                        'tenant' : tenant,
                        'machine' : obj.id,
                    })
                ),
            })
        return result


class ExternalIPSerializer(serializers.Serializer):
    external_ip = serializers.IPAddressField(protocol = 'IPv4')
    internal_ip = serializers.IPAddressField(read_only = True)
