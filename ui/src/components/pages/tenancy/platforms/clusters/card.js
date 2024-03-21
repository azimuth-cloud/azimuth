import React, { useState } from 'react';

import Badge from 'react-bootstrap/Badge';
import Button from 'react-bootstrap/Button';
import Card from 'react-bootstrap/Card';
import Col from 'react-bootstrap/Col';
import Modal from 'react-bootstrap/Modal';
import OverlayTrigger from 'react-bootstrap/OverlayTrigger';
import ProgressBar from 'react-bootstrap/ProgressBar';
import Row from 'react-bootstrap/Row';
import Table from 'react-bootstrap/Table';
import Tooltip from 'react-bootstrap/Tooltip';
import sadFace from "../../../../../../assets/face-frown-regular.svg";

import get from 'lodash/get';
import truncate from 'lodash/truncate';

import ReactMarkdown from 'react-markdown';

import nunjucks from 'nunjucks';
import { sprintf } from 'sprintf-js';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
    faExclamationCircle,
    faPen,
    faQuestionCircle,
    faShieldAlt,
    faSyncAlt,
} from '@fortawesome/free-solid-svg-icons';

import { PlatformTypeCard, PlatformServicesListGroup, PlatformDeleteButton } from '../utils';
import { Error } from '../../../../utils';


import { ClusterModalForm } from './form';


const nunjucksEnv = new nunjucks.Environment();
// Register the sprintf function as the 'format' filter
nunjucksEnv.addFilter("format", sprintf);
// Register an additional filter for selecting a service by name
nunjucksEnv.addFilter("service", (cluster, name) => cluster.services.find(s => s.name === name));


const ClusterUsage = ({ cluster, clusterType }) => {
    let usage;
    if( clusterType.usage_template ) {
        usage = nunjucksEnv.renderString(clusterType.usage_template, { cluster });
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


const ClusterPatched = ({ cluster, clusterType }) => {
    const patched = cluster.patched ? cluster.patched.toRelative() : cluster.created.toRelative()
    const newVersionAvailable = cluster.cluster_type_version && (cluster.cluster_type_version != clusterType.version);
    return !newVersionAvailable ?
        patched :
        <OverlayTrigger
            placement="top"
            overlay={<Tooltip>A new version is available, please patch this cluster.</Tooltip>}
            trigger="click"
            rootClose
        >
            <strong className="text-danger overlay-trigger">
                <FontAwesomeIcon icon={faExclamationCircle} className="me-2" />
                {patched}
            </strong>
        </OverlayTrigger>;
};


const ClusterStatusCard = ({ cluster, clusterType }) => (
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
                    <td>{cluster.created.toRelative()}</td>
                </tr>
                <tr>
                    <th>Created by</th>
                    <td>{cluster.created_by_username || '-'}</td>
                </tr>
                <tr>
                    <th>Deletes scheduled at:</th>
                    <td>{cluster.resource_schedule || 'Never'}</td>
                </tr>
                <tr>
                    <th>Updated</th>
                    <td>{cluster.updated ? cluster.updated.toRelative() : '-'}</td>
                </tr>
                <tr>
                    <th>Updated by</th>
                    <td>{cluster.updated_by_username || '-'}</td>
                </tr>
                <tr>
                    <th>Patched</th>
                    <td><ClusterPatched cluster={cluster} clusterType={clusterType} /></td>
                </tr>
            </tbody>
        </Table>
    </Card>
);


const ClusterServicesListGroup = ({ cluster }) => (
    <PlatformServicesListGroup
        services={cluster.services}
        // We want to disable the services until the first successful deploy
        // This means that updated is set on the cluster
        // We also want to disable them during a delete
        disabled={!cluster.updated || cluster.status === "DELETING"}
    />
);


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
    const [visible, setVisible] = useState(false);
    const open = () => setVisible(true);
    const close = () => setVisible(false);

    const clusterType = get(tenancy.clusterTypes.data, cluster.cluster_type) || clusterTypePlaceholder;

    const handleSubmit = data => {
        onSubmit({ parameter_values: data.parameterValues });
        close();
    };

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
            <ClusterModalForm
                show={visible}
                clusterType={clusterType}
                cluster={cluster}
                onSubmit={handleSubmit}
                onCancel={close}
                tenancy={tenancy}
                tenancyActions={tenancyActions}
            />
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

    const missingClusterType = clusterType.placeholder;
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
                    { missingClusterType && 
                        <Row className="justify-content-center">
                            <Col xs="auto">
                                <Error className="text-center" message={"WARNING: This cluster type is no longer available."} />
                            </Col>
                        </Row>
                    }
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
                                disabled={inFlight || working || missingClusterType}
                                onSubmit={clusterActions.update}
                                className="me-2"
                            />
                            <ClusterPatchButton
                                name={cluster.name}
                                inFlight={!!cluster.patching}
                                disabled={inFlight || working || missingClusterType}
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
                            <PlatformTypeCard
                                platformType={{
                                    name: clusterType.label,
                                    logo: clusterType.logo,
                                    description: clusterType.description
                                }}
                            />
                            <ClusterUsage cluster={cluster} clusterType={clusterType} />
                        </Col>
                        <Col xl={5}>
                            <ClusterStatusCard cluster={cluster} clusterType={clusterType} />
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

// Placeholder object which holds the minimum set of fields required for a successful UI render
const clusterTypePlaceholder = {
    logo: sadFace,
    label: "Cluster type unavailable",
    description: "",
    usage_template: "",
    version: null,
    parameters: [],
    // Used to conditionally render UI components when placeholder is in use
    placeholder: true,
}

export const ClusterCard = ({
    cluster,
    clusterTypes,
    clusterActions,
    tenancy,
    tenancyActions,
    notificationActions
}) => {
    // If cluster type is no longer available from the API (e.g. due to ACL changes in the tenancy) then use a placeholder.
    // NOTE(sd109) We set the placeholder's version to match the current cluster version so that users do not get prompted to patch their cluster.
    const clusterType = clusterTypes.data[cluster.cluster_type] || {...clusterTypePlaceholder, version: cluster.cluster_type_version};
    if (!clusterType.version) {
        notificationActions.error({
                title: 'Cluster type not found',
                message: `Unable to load cluster type '${cluster.cluster_type}' for cluster '${cluster.name}'`
        });
    }

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
                Created {cluster.created.toRelative()}<br/>
                Created by {cluster.created_by_username || 'unknown'}<br/>
                Deletes at: {cluster.resource_schedule || 'Never'}
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
