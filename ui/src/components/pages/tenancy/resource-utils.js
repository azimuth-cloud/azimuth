/**
 * Module containing a generic resource panel.
 */

import React, { useEffect } from 'react';

import Button from 'react-bootstrap/Button';
import ButtonGroup from 'react-bootstrap/ButtonGroup';
import Col from 'react-bootstrap/Col';
import FormControl from 'react-bootstrap/FormControl';
import InputGroup from 'react-bootstrap/InputGroup';
import Row from 'react-bootstrap/Row';

import get from 'lodash/get';
import startsWith from 'lodash/startsWith';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faExclamationCircle, faPlus, faSyncAlt } from '@fortawesome/free-solid-svg-icons';

import { StatusCodes } from 'http-status-codes';

import { formatSize, sortBy, Loading, Error, Select } from '../../utils';


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
            <Row className="justify-content-end mb-2">
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


export const SizeSelectControl = (props) => (
    <ResourceSelectControl
        resourceName="size"
        sortOptions={(sizes) => sortBy(sizes, s => [s.cpus, s.ram, s.disk])}
        formatOptionLabel={(opt) => (
            <>
                {opt.name}
                <small className="ms-2 text-muted">
                    {opt.cpus} cpus,{" "}
                    {formatSize(opt.ram, "MB")} RAM,{" "}
                    {formatSize(opt.disk, "GB")} disk
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
    ...props
}) => (
    <InputGroup>
        <ResourceSelectControl
            resourceName="external ip"
            resource={resource}
            resourceActions={resourceActions}
            getOptionLabel={(ip) => ip.external_ip}
            sortResources={(ips) => sortBy(ips, ip => ip.external_ip)}
            // The currently selected IP should be permitted, regardless of state
            resourceFilter={(ip) => (ip.id === value) || (!ip.updating && !ip.machine)}
            value={value}
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


export const KubernetesClusterTemplateSelectControl = (props) => (
    <ResourceSelectControl
        resourceName="Kubernetes cluster template"
        // Sort the templates by Kubernetes version with the highest at the top
        sortOptions={(templates) => sortBy(
            templates,
            t => [t.kubernetes_version, !t.ha_enabled],
            true
        )}
        formatOptionLabel={(opt) => (
            <>
                {opt.name}
                <small className="ms-2 text-muted">
                    Kubernetes version: {opt.kubernetes_version} 
                </small>
            </>
        )}
        {...props}
        {...props} 
    />
);


export const ClusterSelectControl = (props) => (
    <ResourceSelectControl resourceName="cluster" {...props} />
);
