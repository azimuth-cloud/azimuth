import React, { useState } from 'react';

import Badge from 'react-bootstrap/Badge';
import Button from 'react-bootstrap/Button';
import Card from 'react-bootstrap/Card';
import Col from 'react-bootstrap/Col';
import Form from 'react-bootstrap/Form';
import Image from 'react-bootstrap/Image';
import ListGroup from 'react-bootstrap/ListGroup';
import Modal from 'react-bootstrap/Modal';
import OverlayTrigger from 'react-bootstrap/OverlayTrigger';
import ProgressBar from 'react-bootstrap/ProgressBar';
import Row from 'react-bootstrap/Row';
import Table from 'react-bootstrap/Table';
import Tooltip from 'react-bootstrap/Tooltip';

import get from 'lodash/get';
import truncate from 'lodash/truncate';

import moment from 'moment';

import ReactMarkdown from 'react-markdown';

import nunjucks from 'nunjucks';
import { sprintf } from 'sprintf-js';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
    faBookmark,
    faExclamationCircle,
    faExternalLinkAlt,
    faPen,
    faQuestionCircle,
    faSave,
    faShieldAlt,
    faSyncAlt,
    faTrash
} from '@fortawesome/free-solid-svg-icons';

import { bindArgsToActions, sortBy } from '../../../utils';

import { ClusterParameterField } from './parameter-field';


const clustersWithLinks = (clusterTypes, clusters) => {
    // Find the parameters for each cluster type that correspond to other clusters
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
        .map(c => get(linkedParams, c.cluster_type, []).map(p => c.parameter_values[p]))
        .flat();
    // Attach a "linkedTo" property to each cluster
    const clustersWithLinkedTo = Object.values(clusters)
        .map(c => ({ ...c, linkedTo: linkedClusters.includes(c.name) }));
    return clustersWithLinkedTo;
};


export const ClusterTypeCard = ({ clusterType }) => (
    <Card className="cluster-type-card">
        <Card.Body>
            <Row>
                <Col xs="auto">
                    <Image src={clusterType.logo} />
                </Col>
                <Col>
                    <Card.Title>{clusterType.label}</Card.Title>
                    <ReactMarkdown children={clusterType.description} />
                </Col>
            </Row>
        </Card.Body>
    </Card>
);


const ClusterUsage = ({ cluster, clusterType }) => {
    let usage;
    if( clusterType.usage_template ) {
        // Register the sprintf function as the 'format' filter
        const env = new nunjucks.Environment();
        env.addFilter('format', sprintf);
        usage = env.renderString(clusterType.usage_template, { cluster });
    }
    return (
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
    );
};


const statusTextClasses = {
    'CONFIGURING': 'text-primary',
    'READY': 'text-success',
    'DELETING': 'text-danger',
    'ERROR': 'text-danger'
};


const ClusterStatusText = ({ cluster }) => {
    const [errorVisible, setErrorVisible] = useState(false);
    const openError = () => setErrorVisible(true);
    const closeError = () => setErrorVisible(false);

    return (
        <>
            <span className={`fw-bold ${statusTextClasses[cluster.status]}`}>
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


const ClusterStatusCard = ({ cluster }) => (
    <Card className="mb-3">
        <Card.Header className="text-center">Cluster status</Card.Header>
        <Table borderless className="details-table">
            <tbody>
                <tr>
                    <th>Name</th>
                    <td>{cluster.name}</td>
                </tr>
                <tr>
                    <th>Status</th>
                    <td>
                        <ClusterStatusText cluster={cluster} />
                    </td>
                </tr>
                <tr>
                    <th>Task</th>
                    <td>{cluster.task ? <ClusterTask cluster={cluster} /> : '-'}</td>
                </tr>
                <tr>
                    <th>Created</th>
                    <td>{moment(cluster.created).fromNow()}</td>
                </tr>
                <tr>
                    <th>Updated</th>
                    <td>{cluster.updated ? moment(cluster.updated).fromNow() : '-'}</td>
                </tr>
                <tr>
                    <th>Patched</th>
                    <td>{cluster.patched ? <ClusterPatched cluster={cluster} /> : '-'}</td>
                </tr>
            </tbody>
        </Table>
    </Card>
);


const ClusterServicesListGroup = ({ cluster }) => {
    const sortedServices = sortBy(cluster.services, service => service.name);
    // We want to disable the services until the first successful deploy
    // This means that updated is set on the cluster
    // We also want to disable them during a delete
    const disabled = !cluster.updated || cluster.status === "DELETING";
    return (
        <ListGroup variant="flush" activeKey={null}>
            {sortedServices.map(service => (
                <ListGroup.Item
                    key={service.name}
                    action
                    href={service.url}
                    disabled={disabled}
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
    );
};


const ClusterServicesCard = ({ cluster }) => (
    <Card className="mb-3">
        <Card.Header className="text-center">Cluster services</Card.Header>
        {cluster.services.length > 0 ? (
            <ClusterServicesListGroup cluster={cluster} />
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


const ClusterUpdateButton = ({
    cluster,
    tenancy,
    tenancyActions,
    disabled,
    onSubmit,
    ...props
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
            <Button
                {...props}
                variant="secondary"
                onClick={open}
                disabled={disabled || !clusterType}
            >
                <FontAwesomeIcon
                    icon={!!cluster.updating ? faSyncAlt : faPen}
                    spin={!!cluster.updating}
                    className="me-2"
                />
                {!!cluster.updating ? 'Updating...' : 'Update'}
            </Button>
            <Modal
                backdrop="static"
                size="lg"
                onHide={close}
                show={visible}
            >
                <Modal.Header closeButton>
                    <Modal.Title>Update platform: {cluster.name}</Modal.Title>
                </Modal.Header>
                <Form onSubmit={handleSubmit}>
                    <Modal.Body>
                        {clusterType && (
                            <Row className="cluster-parameters-type justify-content-center mb-3">
                                <Col xs="auto">
                                    <ClusterTypeCard clusterType={clusterType} />
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
                            Update platform
                        </Button>
                    </Modal.Footer>
                </Form>
            </Modal>
        </>
    );
};


const ClusterPatchButton = ({ name, inFlight, disabled, onConfirm, ...props }) => {
    const [visible, setVisible] = useState(false);

    const open = () => setVisible(true);
    const close = () => setVisible(false);
    const handleConfirm = () => { onConfirm(); close(); };

   return (
        <>
            <Button {...props} variant="warning" disabled={disabled} onClick={open}>
                <FontAwesomeIcon
                    icon={inFlight ? faSyncAlt : faShieldAlt}
                    spin={inFlight}
                    className="me-2"
                />
                {inFlight ? 'Patching...' : 'Patch'}
            </Button>
            <Modal show={visible} backdrop="static" keyboard={false}>
                <Modal.Body>
                    <p>Are you sure you want to patch {name}?</p>
                    <p>
                        <strong>
                            This is a potentially disruptive operation, and may affect
                            workloads on the platform. Once started, it cannot be stopped.
                        </strong>
                    </p>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={close}>Cancel</Button>
                    <Button variant="primary" onClick={handleConfirm}>
                        Patch platform
                    </Button>
                </Modal.Footer>
            </Modal>
        </>
    );
};


const PlatformDeleteButton = ({ name, inFlight, disabled, onConfirm, ...props }) => {
    const [visible, setVisible] = useState(false);

    const open = () => setVisible(true);
    const close = () => setVisible(false);
    const handleConfirm = () => { onConfirm(); close(); };

    return (
        <>
            <Button {...props} variant="danger" disabled={disabled} onClick={open}>
                <FontAwesomeIcon
                    icon={inFlight ? faSyncAlt : faTrash}
                    spin={inFlight}
                    className="me-2"
                />
                {inFlight ? 'Deleting...' : 'Delete'}
            </Button>
            <Modal show={visible} backdrop="static" keyboard={false}>
                <Modal.Body>
                    <p>Are you sure you want to delete {name}?</p>
                    <p><strong>Once deleted, a platform cannot be restored.</strong></p>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={close}>Cancel</Button>
                    <Button variant="danger" onClick={handleConfirm}>
                        Delete platform
                    </Button>
                </Modal.Footer>
            </Modal>
        </>
    );
};


const ClusterDetailsButton = ({
    cluster,
    clusterType,
    clusterActions,
    tenancy,
    tenancyActions,
    ...props
}) => {
    const [visible, setVisible] = useState(false);
    const open = () => setVisible(true);
    const close = () => setVisible(false);

    const inFlight = !!cluster.updating || !!cluster.patching || !!cluster.deleting;
    const working = ['CONFIGURING', 'DELETING'].includes(cluster.status);

    return (
        <>
            <Button {...props} onClick={open}>
                Details
            </Button>
            <Modal size="xl" backdrop="static" onHide={close} show={visible}>
                <Modal.Header closeButton>
                    <Modal.Title>Platform details for {cluster.name}</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <Row className="justify-content-end mb-2">
                        <Col xs="auto">
                            <Button
                                variant="primary"
                                disabled={cluster.fetching}
                                onClick={clusterActions.fetchOne}
                                title="Refresh"
                                className="me-2"
                            >
                                <FontAwesomeIcon
                                    icon={faSyncAlt}
                                    spin={cluster.fetching}
                                    className="me-2"
                                />
                                Refresh
                            </Button>
                            <ClusterUpdateButton
                                cluster={cluster}
                                tenancy={tenancy}
                                tenancyActions={tenancyActions}
                                disabled={inFlight || working}
                                onSubmit={clusterActions.update}
                                className="me-2"
                            />
                            <ClusterPatchButton
                                name={cluster.name}
                                inFlight={!!cluster.patching}
                                disabled={inFlight || working}
                                onConfirm={clusterActions.patch}
                                className="me-2"
                            />
                            <PlatformDeleteButton
                                name={cluster.name}
                                inFlight={!!cluster.deleting}
                                disabled={inFlight || working || cluster.linkedTo}
                                onConfirm={clusterActions.delete}
                            />
                        </Col>
                    </Row>
                    <Row>
                        <Col xl={7}>
                            <ClusterTypeCard clusterType={clusterType} />
                            <ClusterUsage cluster={cluster} clusterType={clusterType} />
                        </Col>
                        <Col xl={5}>
                            <ClusterStatusCard cluster={cluster} />
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


const statusBadgeBg = {
    'CONFIGURING': 'primary',
    'READY': 'success',
    'DELETING': 'danger',
    'ERROR': 'danger'
};


const ClusterCard = ({
    cluster,
    clusterTypes,
    clusterActions,
    tenancy,
    tenancyActions
}) => {
    const clusterType = clusterTypes.data[cluster.cluster_type];
    const updatedAt = cluster.updated || cluster.created;
    return (
        <Card className="platform-card">
            <Card.Header>
                <Badge bg={statusBadgeBg[cluster.status]}>{cluster.status}</Badge>
            </Card.Header>
            <Card.Img src={clusterType.logo} />
            <Card.Body>
                <Card.Title>{cluster.name}</Card.Title>
                <Card.Subtitle>{clusterType.label}</Card.Subtitle>
            </Card.Body>
            {cluster.services.length > 0 && (
                <ClusterServicesListGroup cluster={cluster} />
            )}
            {cluster.task && (
                <Card.Body>
                    <ClusterTask cluster={cluster} />
                </Card.Body>
            )}
            <Card.Body className="small text-muted">
                Updated {moment(updatedAt).fromNow()}
            </Card.Body>
            <Card.Footer>
                <ClusterDetailsButton
                    cluster={cluster}
                    clusterType={clusterType}
                    clusterActions={clusterActions}
                    tenancy={tenancy}
                    tenancyActions={tenancyActions}
                />
            </Card.Footer>
        </Card>
    );
};


export const PlatformsGrid = ({
    clusters,
    clusterActions,
    tenancy,
    tenancyActions
}) => {
    const clusterTypes = get(tenancy, ['clusterTypes', 'data']) || {};
    const sortedClusters = sortBy(clustersWithLinks(clusterTypes, clusters), c => c.name);
    if( sortedClusters.length > 0 ) {
        return (
            <Row xs={1} md={2} lg={3} xl={4}>
                {sortedClusters.map(cluster => (
                    <Col key={cluster.id}>
                        <ClusterCard
                            cluster={cluster}
                            clusterTypes={tenancy.clusterTypes}
                            clusterActions={bindArgsToActions(clusterActions, cluster.id)}
                            tenancy={tenancy}
                            tenancyActions={tenancyActions}
                        />
                    </Col>
                ))}
            </Row>
        );
    }
    else {
        return (
            <Row>
                <Col className="text-center text-muted py-5">
                    No platforms have been created yet.
                </Col>
            </Row>
        );
    }
};
