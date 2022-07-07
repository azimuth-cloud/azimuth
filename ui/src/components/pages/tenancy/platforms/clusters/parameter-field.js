/**
 * This module contains utilities for generating forms for cluster parameters.
 */

import React, { useEffect, useState } from 'react';

import Button from 'react-bootstrap/Button';
import FormCheck from 'react-bootstrap/FormCheck';
import FormControl from 'react-bootstrap/FormControl';
import InputGroup from 'react-bootstrap/InputGroup';

import ReactMarkdown from 'react-markdown';

import get from 'lodash/get';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faPlus, faTimes } from '@fortawesome/free-solid-svg-icons';

import { Field, Select, withCustomValidity } from '../../../../utils';

import {
    SizeSelectControl,
    ExternalIpSelectControl,
    VolumeSelectControl,
    MachineSelectControl,
    ClusterSelectControl
} from '../../resource-utils';


const InputWithCustomValidity = withCustomValidity("input");


const TextControl = ({
    id,
    value,
    onChange,
    tenancy: _,
    tenancyActions: __,
    secret,
    confirm,
    placeholder,
    min_length: minLength,
    max_length: maxLength,
    ...props
}) => {
    const [confirmation, setConfirmation] = useState('');
    // On first mount, set the confirmation to the given value
    useEffect(() => { setConfirmation(value) }, []);
    const inputType = secret ? "password" : "text";
    const validationMessage = value !== confirmation ? 'Confirmation does not match.' : '';
    return (
        <>
            <FormControl
                {...props}
                id={id}
                value={value}
                placeholder={placeholder}
                minLength={minLength}
                maxLength={maxLength}
                type={inputType}
                autoComplete="off"
                onChange={(evt) => onChange(evt.target.value)}
            />
            {confirm && (
                <FormControl
                    {...props}
                    id={`${id}-confirm`}
                    as={InputWithCustomValidity}
                    value={confirmation}
                    placeholder={`Confirm ${placeholder}`}
                    type={inputType}
                    onChange={(evt) => setConfirmation(evt.target.value)}
                    validationMessage={validationMessage}
                    className="mt-2"
                />
            )}
        </>
    );
};


const NumberControl = ({
    tenancy: _,
    tenancyActions: __,
    onChange,
    ...props
}) => (
    <FormControl
        {...props}
        type="number"
        autoComplete="off"
        onChange={(evt) => onChange(evt.target.value)}
    />
);


const IntegerControl = (props) => <NumberControl step="1" {...props} />;


const ChoiceControl = ({
    tenancy: _,
    tenancyActions: __,
    choices,
    className = "",
    ...props
}) => (
    <FormControl
        {...props}
        as={Select}
        className={`border-0 p-0 ${className}`}
        placeholder="Select one..."
        options={choices.map(c => ({ label: c, value: c }))}
    />
);


const ListControl = ({
    id,
    value,
    onChange,
    disabled,
    min_length: minLength = 0,
    max_length: maxLength,
    // As the default item, use a string with no options
    item = { kind: "string", options: {} },
    tenancy,
    tenancyActions
}) => {
    const currentList = value || [];

    // On first mount, pad the value to the minimum length if required
    useEffect(
        () => {
            const padding = Array(Math.max(minLength - currentList.length, 0)).fill('');
            onChange(currentList.concat(padding));
        },
        []
    )

    const itemAdded = () => onChange([...currentList, '']);
    const itemChanged = (idx) => (value) => onChange([
        ...currentList.slice(0, idx),
        value,
        ...currentList.slice(idx + 1)
    ]);
    const itemRemoved = (idx) => () => onChange([
        ...currentList.slice(0, idx),
        ...currentList.slice(idx + 1)
    ]);

    // Select the item control based on the item kind
    const ItemControl = get(kindToControlMap, item.kind, TextControl);
    return (
        <>
            {currentList.map((v, i) => (
                <InputGroup key={i} className="mb-2">
                    <ItemControl
                        {...item.options}
                        id={`${id}[${i}]`}
                        tenancy={tenancy}
                        tenancyActions={tenancyActions}
                        required={true}
                        value={v}
                        onChange={itemChanged(i)}
                        disabled={disabled}
                    />
                    <Button
                        variant="danger"
                        title="Remove item"
                        disabled={disabled || (currentList.length <= minLength)}
                        onClick={itemRemoved(i)}
                    >
                        <FontAwesomeIcon icon={faTimes} />
                    </Button>
                </InputGroup>
            ))}
            <Button
                variant="success"
                disabled={disabled || (maxLength && currentList.length >= maxLength)}
                onClick={itemAdded}
            >
                <FontAwesomeIcon icon={faPlus} className="me-2" />
                Add another item
            </Button>
        </>
    );
};


const CloudSizeControl = ({
    tenancy,
    tenancyActions,
    min_cpus: minCPUs,
    min_ram: minRAM,
    min_disk: minDisk,
    ...props
}) => (
    <SizeSelectControl
        {...props}
        resource={tenancy.sizes}
        resourceActions={tenancyActions.size}
        resourceFilter={(size) => {
            if( !!minCPUs && size.cpus < minCPUs ) return false;
            if( !!minRAM && size.ram < minRAM ) return false;
            if( !!minDisk && size.disk < minDisk ) return false;
            return true;
        }}
    />
);


const CloudMachineControl = ({
    tenancy,
    tenancyActions,
    ...props
}) => (
    <MachineSelectControl
        {...props}
        resource={tenancy.machines}
        resourceActions={tenancyActions.machine}
    />
);


const CloudIpControl = ({
    tenancy,
    tenancyActions,
    ...props
}) => (
    <ExternalIpSelectControl
        {...props}
        resource={tenancy.externalIps}
        resourceActions={tenancyActions.externalIp}
    />
);


const CloudVolumeControl = ({
    tenancy,
    tenancyActions,
    min_size: minSize,
    ...props
}) => (
    <VolumeSelectControl
        {...props}
        resource={tenancy.volumes}
        resourceActions={tenancyActions.volume}
        resourceFilter={(v) => (!minSize || v.size >= minSize)}
    />
);


const CloudClusterControl = ({
    value,
    tag,
    tenancy,
    tenancyActions,
    ...props
}) => {
    const hasTag = (c) => !tag || c.tags.includes(tag);
    const isReady = (c) => (value === c.name) || (c.status === 'READY');
    return (
        <ClusterSelectControl
            {...props}
            resource={tenancy.clusters}
            resourceActions={tenancyActions.cluster}
            resourceFilter={(c) => hasTag(c) && isReady(c)}
            // We work in names for clusters
            getOptionValue={(c) => c.name}
            value={value}
        />
    );
};


const kindToControlMap = {
    'integer': IntegerControl,
    'number': NumberControl,
    'choice': ChoiceControl,
    'list': ListControl,
    'cloud.size': CloudSizeControl,
    'cloud.machine': CloudMachineControl,
    'cloud.ip': CloudIpControl,
    'cloud.volume': CloudVolumeControl,
    'cloud.cluster': CloudClusterControl,
};


const BooleanParameterField = ({ parameter, value, onChange, isCreate }) => {
    const [initial, _] = useState(value);
    const checked = value ? true : false;
    // Boolean parameters support "immutable" and an option called "permanent"
    // The difference is subtle - an "immutable" boolean can only be set on create,
    // so if it is false on create it can never be set to true
    // However a "permanent" boolean can be set to true at any time, but once it
    // becomes true it can never be set back to false
    // Both options only take effect on an update
    const disabled = (
        !isCreate &&
        (parameter.immutable || (parameter.options.permanent && initial))
    );
    return (
        <Field
            label={parameter.label}
            helpText={
                <ReactMarkdown
                    components={{
                        // Links should open in a new tab
                        a: ({ node, children, ...props }) => (
                            <a target="_blank" {...props}>{children}</a>
                        )
                    }}
                    children={parameter.description}
                />
            }
        >
            <FormCheck
                id={parameter.name}
                type="checkbox"
                required={parameter.required}
                checked={checked}
                onChange={(evt) => onChange(evt.target.checked)}
                disabled={disabled}
                label={parameter.options.checkboxLabel || parameter.label}
            />
        </Field>
    );
};


const DefaultParameterField = ({
    tenancy,
    tenancyActions,
    parameter,
    value,
    onChange,
    isCreate
}) => {
    const Control = get(kindToControlMap, parameter.kind, TextControl);
    return (
        <Field
            label={parameter.label}
            required={parameter.required}
            helpText={
                <ReactMarkdown
                    components={{
                        // Links should open in a new tab
                        a: ({ node, children, ...props }) => (
                            <a target="_blank" {...props}>{children}</a>
                        )
                    }}
                    children={parameter.description}
                />
            }
        >
            <Control
                id={parameter.name}
                tenancy={tenancy}
                tenancyActions={tenancyActions}
                required={parameter.required}
                value={value}
                onChange={onChange}
                disabled={parameter.immutable && !isCreate}
                placeholder={parameter.label}
                {...parameter.options}
            />
        </Field>
    );
};


export const ClusterParameterField = (props) => {
    return props.parameter.kind == "boolean" ?
        <BooleanParameterField {...props} /> :
        <DefaultParameterField {...props} />;
};
