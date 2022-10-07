/**
 * Module containing a generic resource panel.
 */

import React, { useEffect, useState } from 'react';

import Badge from 'react-bootstrap/Badge';
import Button from 'react-bootstrap/Button';
import ButtonGroup from 'react-bootstrap/ButtonGroup';
import Col from 'react-bootstrap/Col';
import FormControl from 'react-bootstrap/FormControl';
import InputGroup from 'react-bootstrap/InputGroup';
import OverlayTrigger from 'react-bootstrap/OverlayTrigger';
import Popover from 'react-bootstrap/Popover';
import Row from 'react-bootstrap/Row';
import Table from 'react-bootstrap/Table';

import get from 'lodash/get';
import startsWith from 'lodash/startsWith';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faExclamationCircle, faPlus, faSyncAlt } from '@fortawesome/free-solid-svg-icons';

import { StatusCodes } from 'http-status-codes';

import { compareElementwise, formatSize, sortBy, Loading, Error, Select } from '../../utils';


// This hook ensures that the given resource is initialised
export const useResourceInitialised = (resource, fetchList) => {
    const { initialised, fetching, fetchError } = resource;
    useEffect(
        () => { if( !initialised && !fetching && !fetchError ) fetchList(); },
        [initialised, fetching, fetchError]
    )
};


export const ResourcePanel = ({
    children,
    resource,
    resourceActions,
    resourceName,
    createButtonComponent: CreateButtonComponent,
    createButtonExtraProps = {}
}) => {
    // When the panel is mounted, ensure that the resource is initialised
    useResourceInitialised(resource, resourceActions.fetchList);
    // If the resource failed to load because it was not found, disable the refresh button
    const notFound = get(resource.fetchError, 'statusCode') === StatusCodes.NOT_FOUND;
    return (
        <>
            <Row className="justify-content-end mb-3">
                <Col xs="auto">
                    <ButtonGroup>
                        {CreateButtonComponent && (
                            <CreateButtonComponent
                                disabled={!resource.initialised}
                                creating={resource.creating}
                                create={resourceActions.create}
                                {...createButtonExtraProps}
                            />
                        )}
                        <Button
                            variant="primary"
                            disabled={notFound || resource.fetching}
                            onClick={resourceActions.fetchList}
                            title={`Refresh ${resourceName}`}
                        >
                            <FontAwesomeIcon
                                icon={faSyncAlt}
                                spin={resource.fetching}
                                className="me-2"
                            />
                            Refresh
                        </Button>
                    </ButtonGroup>
                </Col>
            </Row>
            {resource.initialised ? (
                <Row>
                    <Col>
                        {React.Children.map(
                            children,
                            c => React.cloneElement(
                                c,
                                { resourceData: resource.data, resourceActions }
                            )
                        )}
                    </Col>
                </Row>
            ) : (
                <Row className="justify-content-center">
                    {(resource.fetchError && !resource.fetching) ? (
                        <Col xs="auto py-3">
                            <Error message={resource.fetchError.message} />
                        </Col>
                    ) : (
                        <Col xs="auto py-5">
                            <Loading
                                size="lg"
                                iconSize="lg"
                                message={`Loading ${resourceName}...`}
                            />
                        </Col>
                    )}
                </Row>
            )}
        </>
    );
};


const MachineSizePopover = ({ children, size, ...props }) => (
    <OverlayTrigger
        {...props}
        overlay={(
            <Popover>
                <Popover.Header><code>{size.name}</code></Popover.Header>
                <Popover.Body className="px-3 py-1">
                    <Table borderless className="mb-0">
                        <tbody>
                            <tr>
                                <th className="text-end">CPUs</th>
                                <td>{size.cpus}</td>
                            </tr>
                            <tr>
                                <th className="text-end">RAM</th>
                                <td>{formatSize(size.ram, "MB")}</td>
                            </tr>
                            <tr>
                                <th className="text-end">Disk size</th>
                                <td>{formatSize(size.disk, "GB")}</td>
                            </tr>
                            {size.ephemeral_disk > 0 && (
                                <tr>
                                    <th className="text-end">Ephemeral disk</th>
                                    <td>{formatSize(size.ephemeral_disk, "GB")}</td>
                                </tr>
                            )}
                        </tbody>
                    </Table>
                </Popover.Body>
            </Popover>
        )}
        trigger="click"
        rootClose
    >
        {children}
    </OverlayTrigger>
);


export const MachineSizeLink = ({ sizes, sizeId }) => {
    const size = get(sizes.data, sizeId);
    if( size ) {
        return (
            <MachineSizePopover size={size} placement="top">
                <Button variant="link">{size.name}</Button>
            </MachineSizePopover>
        );
    }
    else if( sizes.fetching ) {
        return <Loading message="Loading sizes..." />;
    }
    else {
        return sizeId || '-';
    }
};


const ResourceSelectControlPlaceholder = ({
    resource: { initialised, fetching, fetchError },
    resourceName,
    resourceNamePlural
}) => {
    const startsWithVowel = ['a', 'e', 'i', 'o', 'u'].some((c) => startsWith(resourceName, c));
    if( initialised ) {
        return `Select a${startsWithVowel ? 'n' : ''} ${resourceName}...`;
    }
    else if( fetchError && !fetching ) {
        return (
            <span className="text-danger">
                <FontAwesomeIcon icon={faExclamationCircle} className="me-2" />
                {fetchError.message}
            </span>
        );
    }
    else {
        return <Loading message={`Loading ${resourceNamePlural}...`} />;
    }
};


const ResourceSelectControl = ({
    resource,
    resourceActions,
    resourceName,
    resourceNamePlural = `${resourceName}s`,
    resourceFilter = (_) => true,
    disabled,
    ...props
}) => {
    // Ensure that the resource is initialised
    useResourceInitialised(resource, resourceActions.fetchList);
    return (
        <FormControl
            as={Select}
            // By default, use the item id as the value and the name as the label
            getOptionValue={item => item.id}
            getOptionLabel={item => item.name}
            {...props}
            // Pass the filtered resources as the options
            options={Object.values(resource.data || {}).filter(resourceFilter)}
            // Use a placeholder component
            placeholder={(
                <ResourceSelectControlPlaceholder
                    resource={resource}
                    resourceName={resourceName}
                    resourceNamePlural={resourceNamePlural}
                />
            )}
            // Disable the control if there are no resources to select
            disabled={disabled || !resource.data}
        />
    );
};


export const ImageSelectControl = (props) => (
    <ResourceSelectControl resourceName="image" {...props} />
);


const defaultSizeDescription = size => {
    const descriptionParts = [
        `${size.cpus} cpus`,
        `${formatSize(size.ram, "MB")} RAM`,
        `${formatSize(size.disk, "GB")} disk`
    ];
    if( size.ephemeral_disk > 0 )
        descriptionParts.push(`${formatSize(size.ephemeral_disk, "GB")} ephemeral disk`)
    return descriptionParts.join(", ");
};


export const SizeSelectControl = (props) => (
    <ResourceSelectControl
        resourceName="size"
        // Maintain the ordering from the API
        sortOptions={(sizes) => sortBy(
            sizes,
            s => [s.sort_idx || 0, s.cpus, s.ram, s.disk, s.ephemeral_disk]
        )}
        formatOptionLabel={(opt) => (
            <>
                {opt.name}
                <small className="ms-2 text-muted">
                    {opt.description || defaultSizeDescription(opt)}
                </small>
            </>
        )}
        {...props}
    />
);


export const ExternalIpSelectControl = ({
    value,
    resource,
    resourceActions,
    isInvalid,
    ...props
}) => (
    <InputGroup className={isInvalid ? "is-invalid" : undefined}>
        <ResourceSelectControl
            resourceName="external ip"
            resource={resource}
            resourceActions={resourceActions}
            getOptionLabel={(ip) => ip.external_ip}
            sortResources={(ips) => sortBy(ips, ip => ip.external_ip)}
            // The currently selected IP should be permitted, regardless of state
            resourceFilter={(ip) => (ip.id === value) || (!ip.updating && !ip.machine)}
            value={value}
            isInvalid={isInvalid}
            {...props}
        />
        <Button
            variant="success"
            disabled={props.disabled || resource.creating}
            onClick={() => resourceActions.create()}
            title="Allocate new IP"
        >
            <FontAwesomeIcon
                icon={resource.creating ? faSyncAlt : faPlus}
                fixedWidth
                spin={resource.creating}
            />
        </Button>
    </InputGroup>
);


export const VolumeSelectControl = (props) => (
    <ResourceSelectControl resourceName="volume" {...props} />
);


export const MachineSelectControl = (props) => (
    <ResourceSelectControl resourceName="machine" {...props} />
);


const splitSemVerVersion = (version) => version.split(".").map(p => parseInt(p));


export const KubernetesClusterTemplateSelectControl = ({ resource, value, ...props }) => {
    // Get the Kubernetes version of the initial value
    const [initialValue, _] = useState(value);
    const initialTemplate = (resource.data || {})[initialValue];
    const initialKubernetesVersion = (initialTemplate || {}).kubernetes_version;
    return (
        <ResourceSelectControl
            resourceName="Kubernetes cluster template"
            resource={resource}
            // Only allow the selection of a deprecated template if it is the initial value
            resourceFilter={ct => ct.id === initialValue || !ct.deprecated}
            // Sort the templates by Kubernetes version with the highest at the top
            sortOptions={(templates) => sortBy(
                templates,
                t => [t.kubernetes_version],
                true
            )}
            // Disable templates whose Kubernetes version is less than the initial value
            isOptionDisabled={(opt) => {
                if( initialKubernetesVersion ) {
                    const initialParts = splitSemVerVersion(initialKubernetesVersion);
                    const optionParts = splitSemVerVersion(opt.kubernetes_version);
                    return compareElementwise(optionParts, initialParts) < 0;
                }
                else {
                    // If there is no initial version, all options are available
                    return false;
                }
            }}
            formatOptionLabel={(opt) => (
                <>
                    {opt.name}
                    <small className="ms-2 text-muted">
                        Kubernetes version: {opt.kubernetes_version}
                    </small>
                </>
            )}
            value={value}
            {...props} 
        />
    );
};


export const ClusterSelectControl = (props) => (
    <ResourceSelectControl resourceName="cluster" {...props} />
);
