"""
Module providing validation utilities for cloud providers.
"""

import functools
import typing as t

import voluptuous as v

from ..provider import base as cloud_base, errors as cloud_errors

from . import dto, engine, errors


#: Sentinel object for no previous value
NO_PREVIOUS = object()


class ValidatedParams(dict):
    """
    Wrapper that marks a set of parameters as having been validated.
    """
    __validated__ = True


def build_validator(
    cloud_session: cloud_base.ScopedSession,
    cluster_manager: engine.ClusterManager,
    parameter_spec: t.Iterable[dto.ClusterParameter],
    prev_params: t.Mapping[str, t.Any] = {}
) -> t.Callable[[t.Mapping[str, t.Any]], t.Mapping[str, t.Any]]:
    """
    Builds and returns a validator function for the given parameter spec and previous
    parameter values.

    A validator function takes the parameters to validate as it's only argument and returns
    the validated parameters on success. On failure, a `ValidationError` is raised.
    """
    spec = {}
    for param in parameter_spec:
        # Build the key depending on whether it is required
        key_class = v.Required if param.required else v.Optional
        if param.default is not None:
            key = key_class(param.name, default = param.default)
        else:
            key = key_class(param.name)
        # Combine kind-specific and immutability constraints
        prev_value = prev_params.get(param.name, NO_PREVIOUS)
        spec[key] = v.All(
            kind_constraint(
                cloud_session,
                cluster_manager,
                param.kind,
                param.options,
                prev_value
            ),
            immutability_constraint(param, prev_value)
        )
    return use_schema(v.Schema(spec))


def use_schema(schema):
    """
    Returns a function that validates incoming data using the given schema.

    If a ``voluptuous.MultipleInvalid`` error is raised, it is converted into
    a :py:class:`~.errors.ValidationError`.
    """
    def validate(params):
        try:
            return ValidatedParams(schema(params))
        except v.MultipleInvalid as exc:
            raise errors.ValidationError(
                'At least one field is invalid',
                # Build a dict of the errors
                { str(e.path[0]): e.msg for e in exc.errors }
            )
    return validate


def immutability_constraint(param, prev_value):
    def immutable(value):
        # If the parameter is not immutable, any value is fine
        if not param.immutable:
            return value
        # If there is no previous value, any value is fine
        if prev_value is NO_PREVIOUS:
            return value
        # If we get this far, the previous and new values must match
        if prev_value == value:
            return value
        else:
            raise v.Invalid('This parameter cannot be changed.')
    return immutable


def kind_constraint(cloud_session, cluster_manager, kind, options, prev_value):
    """
    Returns a schema constraint for the given kind and options.
    """
    constraint = getattr(kind_constraint, kind)
    return constraint(
        cloud_session = cloud_session,
        cluster_manager = cluster_manager,
        options = options,
        prev_value = prev_value
    )


def register_constraint(kind):
    """
    Returns a decorator that registers the decorated function as providing
    a constraint for the given kind.
    """
    def decorator(func):
        setattr(kind_constraint, kind, func)
        return func
    return decorator


@register_constraint('list')
def list_constraint(cloud_session, cluster_manager, options, prev_value):
    constraints = []
    if 'min_length' in options:
        constraints.append(v.Length(min = options['min_length']))
    if 'max_length' in options:
        constraints.append(v.Length(max = options['max_length']))
    # Apply a validator to each item, if given
    if 'item' in options:
        item_kind = options['item']['kind']
        item_options = options['item'].get('options', {})
        prev_len = len(prev_value) if prev_value is not NO_PREVIOUS else 0
        def validate_items(value):
            # The validator to use for each element depends on whether there is an existing
            # value at that index
            schemas = map(
                v.Schema,
                (
                    kind_constraint(
                        cloud_session,
                        cluster_manager,
                        item_kind,
                        item_options,
                        prev_value[idx] if prev_len > idx else NO_PREVIOUS
                    )
                    for idx in range(len(value))
                )
            )
            try:
                return [schema(x) for x, schema in zip(value, schemas)]
            except v.Invalid:
                raise v.Invalid("At least one item does not match the item specification.")
        constraints.append(validate_items)
    return v.All(v.Coerce(list), *constraints)


@register_constraint("string")
def string_constraint(options, **kwargs):
    constraints = []
    if 'min_length' in options:
        constraints.append(v.Length(min = options['min_length']))
    if 'max_length' in options:
        constraints.append(v.Length(max = options['max_length']))
    if 'pattern' in options:
        constraints.append(v.Match(options['pattern']))
    return v.All(v.Coerce(str), *constraints)


def number_constraints(options):
    """
    Produces a list of constraints common between int and float.
    """
    constraints = []
    if 'min' in options:
        constraints.append(v.Range(min = options['min']))
    if 'max' in options:
        constraints.append(v.Range(max = options['max']))
    return constraints


@register_constraint("integer")
def integer_constraint(options, **kwargs):
    # We only want to coerce strings - not floats as that could
    # be an unexpected behaviour
    return v.All(v.Any(int, str), v.Coerce(int), *number_constraints(options))


@register_constraint("number")
def float_constraint(options, **kwargs):
    return v.All(v.Coerce(float), *number_constraints(options))


@register_constraint("boolean")
def boolean_constraint(options, prev_value, **kwargs):
    # Booleans support a "permanent" option indicating that once a parameter
    # has become true, it cannot become false again
    def permanent(value):
        if options.get("permanent") and prev_value and not value:
            raise v.Invalid("This value cannot be unset.")
        return value
    # The built-in Boolean validator ends up casting any value to a bool
    # We want to be stricter and actively reject anything except:
    #   - bool
    #   - 1 / 0
    #   - "1" / "0"
    #   - "true" / "false"
    #   - "yes" / "no"
    return v.All(
        v.Any(
            # Don't use "bool" because that would result in a coercion which we don't want
            v.In([True, False]),
            # This covers 0/1 and "0"/"1"
            v.All(int, v.In([0, 1]), bool),
            v.All(str, v.In(["true", "false", "yes", "no"]), v.Boolean())
        ),
        permanent
    )


@register_constraint("choice")
def choice_constraint(options, **kwargs):
    return v.In(options['choices'])


def convert_not_found(func, msg):
    """
    Decorator that converts a not found error into `voluptuous.Invalid`.
    """
    @functools.wraps(func)
    def decorator(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (errors.ObjectNotFoundError, cloud_errors.ObjectNotFoundError):
            raise v.Invalid(msg)
    return decorator


@register_constraint("cloud.size")
def cloud_size_constraint(cloud_session, options, **kwargs):
    def min_cpus(size):
        if 'min_cpus' in options and size.cpus < options['min_cpus']:
            raise v.Invalid('Size does not have enough CPUs.')
        return size
    def min_ram(size):
        if 'min_ram' in options and size.ram < options['min_ram']:
            raise v.Invalid('Size does not have enough RAM.')
        return size
    def min_disk(size):
        if 'min_disk' in options and size.disk < options['min_disk']:
            raise v.Invalid('Size does not have enough disk.')
        return size
    def min_ephemeral_disk(size):
        if (
            'min_ephemeral_disk' in options and
            size.ephemeral_disk < options['min_ephemeral_disk']
        ):
            raise v.Invalid('Size does not have enough ephemeral disk.')
        return size
    def has_properties(size):
        for prop in options.get('has_properties', []):
            prop_name = prop['name']
            if prop_name not in size.additional_properties:
                raise v.Invalid(f'Size does not have required property \'{prop_name}\'.')
            if 'value' in prop and str(prop['value']) != size.additional_properties[prop_name]:
                raise v.Invalid(f'Property \'{prop_name}\' does not have required value.')
        return size
    return v.All(
        v.Coerce(str),
        convert_not_found(
            lambda v: cloud_session.find_size(v),
            "Not a valid size."
        ),
        min_cpus,
        min_ram,
        min_disk,
        min_ephemeral_disk,
        has_properties,
        lambda s: s.id
    )


@register_constraint("cloud.machine")
def cloud_machine_constraint(cloud_session, **kwargs):
    return v.All(
        v.Coerce(str),
        convert_not_found(
            lambda v: cloud_session.find_machine(v),
            "Not a valid machine."
        ),
        lambda m: m.id
    )


@register_constraint("cloud.ip")
def cloud_ip_constraint(cloud_session, prev_value, **kwargs):
    # If the given IP matches the previous value, that is OK
    # Otherwise, require that the IP be available for attaching
    def ip_available(ip):
        if prev_value == ip.id or ip.machine_id is None:
            return ip
        else:
            raise v.Invalid('External IP is not available.')
    return v.All(
        v.Coerce(str),
        convert_not_found(
            lambda v: cloud_session.find_external_ip(v),
            "Not a valid external ip."
        ),
        ip_available,
        lambda ip: ip.id
    )


@register_constraint("cloud.volume_size")
def cloud_volume_size_constraint(options, **kwargs):
    # A volume size is just an integer with a minimum of 1
    options.setdefault("min", 1)
    return integer_constraint(options, **kwargs)


@register_constraint("cloud.volume")
def cloud_volume_constraint(cloud_session, options, **kwargs):
    def min_size(vol):
        if 'min_size' in options and v.size < options['min_size']:
            raise v.Invalid('Volume is too small.')
        return vol
    return v.All(
        v.Coerce(str),
        convert_not_found(
            lambda v: cloud_session.find_volume(v),
            "Not a valid volume."
        ),
        min_size,
        lambda v: v.id
    )


@register_constraint("cloud.cluster")
def cloud_cluster_constraint(cluster_manager, options, prev_value, **kwargs):
    # Cluster values come in by name
    def find_by_name(name):
        try:
            return next(c for c in cluster_manager.clusters() if c.name == name)
        except StopIteration:
            raise v.Invalid("Not a valid cluster.")
    def has_tag(cluster):
        if 'tag' in options and options['tag'] not in cluster.tags:
            raise v.Invalid("Cluster does not have tag '{}'.".format(options['tag']))
        return cluster
    # Only allow clusters that are in the READY state or were selected last time
    def is_ready(cluster):
        if cluster.name == prev_value or cluster.status is dto.ClusterStatus.READY:
            return cluster
        else:
            raise v.Invalid("Cluster is not ready.")
    return v.All(
        v.Coerce(str),
        find_by_name,
        has_tag,
        is_ready,
        lambda c: c.name
    )
