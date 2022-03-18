/**
 * This module contains components for the machines table.
 */

import React, { useState } from 'react';

import Button from 'react-bootstrap/Button';
import Card from 'react-bootstrap/Card';
import Col from 'react-bootstrap/Col';
import DropdownButton from 'react-bootstrap/DropdownButton';
import DropdownItem from 'react-bootstrap/DropdownItem';
import Form from 'react-bootstrap/Form';
import Image from 'react-bootstrap/Image';
import ListGroup from 'react-bootstrap/ListGroup';
import Modal from 'react-bootstrap/Modal';
import OverlayTrigger from 'react-bootstrap/OverlayTrigger';
import ProgressBar from 'react-bootstrap/ProgressBar';
import Row from 'react-bootstrap/Row';
import Table from 'react-bootstrap/Table';
import Tooltip from 'react-bootstrap/Tooltip';

import ReactMarkdown from 'react-markdown';

import get from 'lodash/get';
import truncate from 'lodash/truncate';

import moment from 'moment';

import nunjucks from 'nunjucks';
import { sprintf } from 'sprintf-js';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
    faBookmark,
    faExclamationCircle,
    faExternalLinkAlt,
    faQuestionCircle,
    faSave
} from '@fortawesome/free-solid-svg-icons';

import { bindArgsToActions, sortBy, Loading } from '../../../utils';

import { ClusterParameterField } from './parameter-field';


const ClusterOverview = ({ cluster, clusterTypes }) => {
    const {
        fetching,
        fetchError,
        data: { [cluster.cluster_type]: clusterType }
    } = clusterTypes;

    if( clusterType ) {
        let usage;
        if( clusterType.usage_template ) {
            // Register the sprintf function as the 'format' filter
            const env = new nunjucks.Environment();
            env.addFilter('format', sprintf);
            usage = env.renderString(clusterType.usage_template, { cluster });
        }
        return (
            <>
                <Card className="mb-3">
                    <Card.Body>
                        <Row>
                            <Col xs="auto" className="h-100 border-end">
                                <Image src={clusterType.logo} fluid style={{ maxHeight: '80px' }} />
                            </Col>
                            <Col>
                                <Card.Title className="border-bottom">{clusterType.label}</Card.Title>
                                <ReactMarkdown children={clusterType.description} />
                            </Col>
                        </Row>
                    </Card.Body>
                </Card>
                <ReactMarkdown
                    components={{
                        // Limit the headings to levels 5 and 6
                        h1: 'h5',
                        h2: 'h6',
                        h3: 'h6',
                        h4: 'h6',
                        h5: 'h6',
                        h6: 'h6',
                        // Links should open in a new tab
                        a: ({ node, children, ...props }) => (
                            <a target="_blank" {...props}>{children}</a>
                        )
                    }}
                    children={usage}
                />
            </>
        );
    }
    else if( fetching ) {
        return (
            <Row className="justify-content-center">
                <Col xs="auto" className="py-4">
                    <Loading size="lg" message="Loading cluster types..."/>
                </Col>
            </Row>
        );
    }
    else if( fetchError ) {
        return (
            <Row className="justify-content-center">
                <Col xs="auto" className="py-4">
                    <Error message={fetchError.message} />
                </Col>
            </Row>
        );
    }
    else {
        return (
            <Row className="justify-content-center">
                <Col xs="auto" className="py-4">
                    <Error message={`Unable to find cluster type '${cluster.cluster_type}'`} />
                </Col>
            </Row>
        );
    }
};


const ClusterServicesCard = ({ cluster }) => {
    const sortedServices = sortBy(cluster.services, service => service.name);
    return (
        <Card className="mb-3">
            <Card.Header className="text-center">Cluster services</Card.Header>
            {sortedServices.length > 0 ? (
                <ListGroup variant="flush" activeKey={null}>
                    {sortedServices.map(service => (
                        <ListGroup.Item
                            key={service.name}
                            action
                            href={service.url}
                            target="_blank"
                            className="service-list-group-item"
                        >
                            <span>
                                {service.icon_url ? (
                                    <img src={service.icon_url} alt={`${service.label} icon`} />
                                ) : (
                                    <FontAwesomeIcon icon={faBookmark} />
                                )}
                            </span>
                            <span>{service.label}</span>
                            <span><FontAwesomeIcon icon={faExternalLinkAlt} /></span>
                        </ListGroup.Item>
                    ))}
                </ListGroup>
            ) : (
                <Card.Body>
                    <Row>
                        <Col className="text-muted text-center">
                            No services enabled.
                        </Col>
                    </Row>
                </Card.Body>
            )}
        </Card>
    );
};


const ClusterDetailsMenuItem = ({ cluster, tenancy: { clusterTypes } }) => {
    const [visible, setVisible] = useState(false);
    const open = () => setVisible(true);
    const close = () => setVisible(false);

    return (
        <>
            <DropdownItem onSelect={open}>
                Cluster details
            </DropdownItem>
            <Modal size="xl" backdrop="static" onHide={close} show={visible}>
                <Modal.Header closeButton>
                    <Modal.Title>Cluster details for {cluster.name}</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <Row>
                        <Col xl={8}>
                            <ClusterOverview
                                cluster={cluster}
                                clusterTypes={clusterTypes}
                            />
                        </Col>
                        <Col xl={4}>
                            <ClusterServicesCard cluster={cluster} />
                        </Col>
                    </Row>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={close}>
                        Close
                    </Button>
                </Modal.Footer>
            </Modal>
        </>
    );
};


const UpdateClusterParametersMenuItem = ({
    cluster,
    tenancy,
    tenancyActions,
    disabled,
    onSubmit
}) => {
    const { clusterTypes: { data: clusterTypes } } = tenancy;
    const clusterType = get(clusterTypes, cluster.cluster_type);
    const parameters = get(clusterType, 'parameters', []);

    const [visible, setVisible] = useState(false);
    const [parameterValues, setParameterValues] = useState({});

    // Resets the parameter values to the current values for the cluster
    const resetParameterValues = () => setParameterValues(
        Object.assign(
            {},
            ...parameters
                .map(p => [
                    p.name,
                    get(cluster.parameter_values, p.name, p.default || '')
                ])
                .filter(([_, value]) => value !== '')
                .map(([name, value]) => ({ [name]: value }))
        )
    );

    // Each time the modal is opened, reset the parameters
    const open = () => { resetParameterValues(); setVisible(true); };
    const close = () => setVisible(false);

    const handleParameterValueChange = (name) => (value) => setParameterValues(
        prevState => {
            if( value !== '' ) {
                return { ...prevState, [name]: value };
            }
            else {
                const { [name]: _, ...nextState } = prevState;
                return nextState;
            }
        }
    );

    const handleSubmit = (evt) => {
        evt.preventDefault();
        onSubmit({ parameter_values: parameterValues });
        close();
    }

    // If the cluster has a cluster type that doesn't exist, disable updates
    // It will either become available, or it no longer exists
    return (
        <>
            <DropdownItem onSelect={open} disabled={disabled || !clusterType}>
                Update cluster options
            </DropdownItem>
            <Modal
                backdrop="static"
                size="lg"
                onHide={close}
                show={visible}
            >
                <Modal.Header closeButton>
                    <Modal.Title>Update cluster: {cluster.name}</Modal.Title>
                </Modal.Header>
                <Form onSubmit={handleSubmit}>
                    <Modal.Body>
                        {clusterType && (
                            <Row className="cluster-parameters-type justify-content-center mb-3">
                                <Col xs="auto">
                                    <Image src={clusterType.logo} fluid className="me-2" />
                                    <strong>{clusterType.label}</strong>
                                </Col>
                            </Row>
                        )}
                        {parameters.map(p => (
                            <ClusterParameterField
                                key={p.name}
                                tenancy={tenancy}
                                tenancyActions={tenancyActions}
                                isCreate={false}
                                parameter={p}
                                value={parameterValues[p.name] || ''}
                                onChange={handleParameterValueChange(p.name)}
                            />
                        ))}
                    </Modal.Body>
                    <Modal.Footer>
                        <Button variant="success" type="submit">
                            <FontAwesomeIcon icon={faSave} className="me-2" />
                            Update cluster
                        </Button>
                    </Modal.Footer>
                </Form>
            </Modal>
        </>
    );
};


const ConfirmPatchMenuItem = ({ name, disabled, onConfirm }) => {
    const [visible, setVisible] = useState(false);

    const open = () => setVisible(true);
    const close = () => setVisible(false);
    const handleConfirm = () => { onConfirm(); close(); };

   return (
        <>
            <DropdownItem onSelect={open} disabled={disabled}>
                Patch cluster
            </DropdownItem>
            <Modal show={visible} backdrop="static" keyboard={false}>
                <Modal.Body>
                    <p>Are you sure you want to patch {name}?</p>
                    <p>
                        <strong>
                            This is a potentially disruptive operation, and may affect
                            workloads on the cluster. Once started, it cannot be stopped.
                        </strong>
                    </p>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={close}>Cancel</Button>
                    <Button variant="primary" onClick={handleConfirm}>
                        Patch cluster
                    </Button>
                </Modal.Footer>
            </Modal>
        </>
    );
};


const ConfirmDeleteMenuItem = ({ name, disabled, onConfirm }) => {
    const [visible, setVisible] = useState(false);

    const open = () => setVisible(true);
    const close = () => setVisible(false);
    const handleConfirm = () => { onConfirm(); close(); };

    return (
        <>
            <DropdownItem
                className="text-danger"
                disabled={disabled}
                onSelect={open}
            >
                Delete cluster
            </DropdownItem>
            <Modal show={visible} backdrop="static" keyboard={false}>
                <Modal.Body>
                    <p>Are you sure you want to delete {name}?</p>
                    <p><strong>Once deleted, a cluster cannot be restored.</strong></p>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={close}>Cancel</Button>
                    <Button variant="danger" onClick={handleConfirm}>
                        Delete cluster
                    </Button>
                </Modal.Footer>
            </Modal>
        </>
    );
};


const statusClasses = {
    'CONFIGURING': 'text-primary',
    'READY': 'text-success',
    'DELETING': 'text-danger',
    'ERROR': 'text-danger'
};


const ClusterStatus = ({ cluster }) => {
    const [errorVisible, setErrorVisible] = useState(false);
    const openError = () => setErrorVisible(true);
    const closeError = () => setErrorVisible(false);

    return (
        <>
            <span className={`fw-bold ${statusClasses[cluster.status]}`}>
                {cluster.status}
                {cluster.error_message && (
                    <Button
                        variant="link"
                        className="ms-1 text-reset"
                        onClick={openError}
                    >
                        <FontAwesomeIcon icon={faQuestionCircle} />
                        <span className="visually-hidden">Error message</span>
                    </Button>
                )}
            </span>
            {cluster.error_message && (
                <Modal size="xl" show={errorVisible} backdrop="static" onHide={closeError}>
                    <Modal.Header closeButton>
                        <Modal.Title>Error message</Modal.Title>
                    </Modal.Header>
                    <Modal.Body>
                        <pre>
                            {cluster.error_message}
                        </pre>
                    </Modal.Body>
                    <Modal.Footer>
                        <Button variant="secondary" onClick={closeError}>
                            Close
                        </Button>
                    </Modal.Footer>
                </Modal>
            )}
        </>
    );
};

const ClusterTask = ({ cluster: { task } }) => {
    const label = truncate(task, { length: 40 });
    return <ProgressBar animated striped label={label} now={100} />;
};


const ClusterPatched = ({ cluster: { patched }}) => {
    const threshold = moment().subtract(2, 'weeks');
    const patchedMoment = moment(patched);
    return patchedMoment.isAfter(threshold) ?
        patchedMoment.fromNow() :
        <OverlayTrigger
            placement="top"
            overlay={<Tooltip>This cluster has not been patched recently.</Tooltip>}
            trigger="click"
            rootClose
        >
            <strong className="text-danger overlay-trigger">
                <FontAwesomeIcon icon={faExclamationCircle} className="me-2" />
                {patchedMoment.fromNow()}
            </strong>
        </OverlayTrigger>;
};


const ClusterActionsDropdown = ({
    cluster,
    clusterActions,
    tenancy,
    tenancyActions
}) => {
    const inFlight = !!cluster.updating || !!cluster.deleting;
    const working = ['CONFIGURING', 'DELETING'].includes(cluster.status);
    return (
        <DropdownButton
            variant="secondary"
            title={
                inFlight ? (
                    <Loading
                        message="Working..."
                        muted={false}
                        visuallyHidden
                        wrapperComponent="span"
                    />
                ) : (
                    'Actions'
                )
            }
            disabled={inFlight}
            className="float-end"
        >
            <ClusterDetailsMenuItem
                cluster={cluster}
                tenancy={tenancy}
            />
            <ConfirmPatchMenuItem
                name={cluster.name}
                disabled={working}
                onConfirm={clusterActions.patch}
            />
            <UpdateClusterParametersMenuItem
                cluster={cluster}
                tenancy={tenancy}
                tenancyActions={tenancyActions}
                disabled={working}
                onSubmit={clusterActions.update}
            />
            <ConfirmDeleteMenuItem
                name={cluster.name}
                disabled={cluster.linked}
                disabled={working}
                onConfirm={clusterActions.delete}
            />
        </DropdownButton>
    );
};


const ClusterRow = ({ cluster, clusterActions, tenancy, tenancyActions }) => {
    const { clusterTypes: { data: clusterTypes } } = tenancy;
    const highlightClass = (cluster.status === 'CONFIGURING') ?
        'table-info' :
        ((!!cluster.updating || !!cluster.deleting) ?
            'table-warning' :
            (cluster.status == 'DELETING' && 'table-danger')
        );
    return (
        <tr className={highlightClass || undefined}>
            <td>{cluster.name}</td>
            <td>{get(clusterTypes, [cluster.cluster_type, 'label'], '-')}</td>
            <td><ClusterStatus cluster={cluster} /></td>
            <td>{cluster.task ? <ClusterTask cluster={cluster} /> : '-'}</td>
            <td>{moment(cluster.created).fromNow()}</td>
            <td>{cluster.updated ? moment(cluster.updated).fromNow() : '-'}</td>
            <td>{cluster.patched ? <ClusterPatched cluster={cluster} /> : '-'}</td>
            <td className="resource-actions">
                <ClusterActionsDropdown
                    cluster={cluster}
                    tenancy={tenancy}
                    tenancyActions={tenancyActions}
                    clusterActions={clusterActions}
                />
            </td>
        </tr>
    );
}


export const ClustersTable = ({
    clusters,
    clusterActions,
    tenancy,
    tenancyActions
}) => {
    // We want to prevent clusters which are depended on by other clusters
    // from being deleted
    // So we need to work out which are the depended on clusters
    // First, create a map of all the parameters that link to another
    // cluster, indexed by cluster type
    const clusterTypes = get(tenancy, ['clusterTypes', 'data']) || {};
    const linkedParams = Object.assign(
        {},
        ...Object.values(clusterTypes).map(ct => ({
            [ct.name]: ct.parameters
                .filter(p => p.kind === "cloud.cluster")
                .map(p => p.name)
        }))
    );
    // Find the clusters that are linked to by other clusters by looking for
    // the values of the related parameters in each cluster
    const linkedClusters = Object.values(clusters)
        // Map each cluster to the list of clusters that it links to
        .map(c => get(linkedParams, c.cluster_type, []).map(p => c.parameter_values[p]))
        .flat();
    // Attach a "linkedTo" property to each cluster and sort them by name to
    // ensure a consistent rendering
    const clustersWithLinkedTo = Object.values(clusters)
        .map(c => ({ ...c, linkedTo: linkedClusters.includes(c.name) }));
    const sortedClusters = sortBy(clustersWithLinkedTo, c => c.name);
    return (
        <Table striped hover responsive className="resource-table clusters-table">
            <caption className="px-2">
                {sortedClusters.length} cluster{sortedClusters.length !== 1 && 's'}
            </caption>
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Cluster Type</th>
                    <th>Status</th>
                    <th>Task</th>
                    <th>Created</th>
                    <th>Updated</th>
                    <th>Patched</th>
                    <th></th>
                </tr>
            </thead>
            <tbody>
                {sortedClusters.map(cluster =>
                    <ClusterRow
                        key={cluster.id}
                        cluster={cluster}
                        tenancy={tenancy}
                        tenancyActions={tenancyActions}
                        clusterActions={bindArgsToActions(clusterActions, cluster.id)}
                    />
                )}
            </tbody>
        </Table>
    );
};
