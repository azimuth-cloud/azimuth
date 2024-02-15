import React, { useEffect, useState } from 'react';

import Badge from 'react-bootstrap/Badge';
import Button from 'react-bootstrap/Button';
import Card from 'react-bootstrap/Card';
import Col from 'react-bootstrap/Col';
import Modal from 'react-bootstrap/Modal';
import Nav from 'react-bootstrap/Nav';
import Row from 'react-bootstrap/Row';
import Table from 'react-bootstrap/Table';
import Tab from 'react-bootstrap/Tab';

import get from 'lodash/get';

import { DateTime } from 'luxon';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
    faCheck,
    faClock,
    faExclamationTriangle,
    faPen,
    faQuestionCircle,
    faSyncAlt,
    faTimes,
    faTimesCircle
} from '@fortawesome/free-solid-svg-icons';

import { sortBy } from '../../../../utils';

import { MachineSizeLink } from '../../resource-utils';

import { PlatformServicesListGroup, PlatformDeleteButton } from '../utils';

import { UpgradeKubernetesClusterButton } from './upgrade-modal';
import { KubeconfigButton } from './kubeconfig-modal';
import { KubernetesClusterModalForm } from './form';
import KubernetesIcon from './kubernetes-logo.png';


const statusStyles = {
    cluster: {
        "Initialising": {
            icon: faSyncAlt,
            className: 'text-muted',
            spin: true
        },
        "Reconciling": {
            icon: faSyncAlt,
            className: 'text-muted',
            spin: true
        },
        "Upgrading": {
            icon: faSyncAlt,
            className: 'text-muted',
            spin: true
        },
        "Ready": {
            icon: faCheck,
            className: 'text-success'
        },
        "Deleting": {
            icon: faSyncAlt,
            className: 'text-danger',
            spin: true
        },
        "Unhealthy": {
            icon: faExclamationTriangle,
            className: 'text-warning'
        },
        "Failed": {
            icon: faTimesCircle,
            className: 'text-danger'
        },
        "Unknown": {
            icon: faQuestionCircle,
            className: 'text-muted'
        }
    },
    controlPlane: {
        "Pending": {
            icon: faClock,
            className: 'text-muted'
        },
        "ScalingUp": {
            icon: faSyncAlt,
            className: 'text-muted',
            spin: true
        },
        "ScalingDown": {
            icon: faSyncAlt,
            className: 'text-muted',
            spin: true
        },
        "Upgrading": {
            icon: faSyncAlt,
            className: 'text-muted',
            spin: true
        },
        "Ready": {
            icon: faCheck,
            className: 'text-success'
        },
        "Deleting": {
            icon: faSyncAlt,
            className: 'text-danger',
            spin: true
        },
        "Unhealthy": {
            icon: faExclamationTriangle,
            className: 'text-warning'
        },
        "Failed": {
            icon: faTimesCircle,
            className: 'text-danger'
        },
        "Unknown": {
            icon: faQuestionCircle,
            className: 'text-muted'
        }
    },
    node: {
        "Pending": {
            icon: faClock,
            className: 'text-muted'
        },
        "Provisioning": {
            icon: faSyncAlt,
            className: 'text-muted',
            spin: true
        },
        "Ready": {
            icon: faCheck,
            className: 'text-success'
        },
        "Deleting": {
            icon: faSyncAlt,
            className: 'text-danger',
            spin: true
        },
        "Deleted": {
            icon: faTimes,
            className: 'text-danger',
        },
        "Unhealthy": {
            icon: faExclamationTriangle,
            className: 'text-warning'
        },
        "Failed": {
            icon: faTimesCircle,
            className: 'text-danger'
        },
        "Unknown": {
            icon: faQuestionCircle,
            className: 'text-muted'
        }
    },
    addon: {
        "Unknown": {
            icon: faQuestionCircle,
            className: 'text-muted'
        },
        "Pending": {
            icon: faClock,
            className: 'text-muted'
        },
        "Preparing": {
            icon: faClock,
            className: 'text-muted'
        },
        "Deployed": {
            icon: faCheck,
            className: 'text-success'
        },
        "Failed": {
            icon: faTimesCircle,
            className: 'text-danger'
        },
        "Installing": {
            icon: faSyncAlt,
            className: 'text-muted',
            spin: true
        },
        "Upgrading": {
            icon: faSyncAlt,
            className: 'text-muted',
            spin: true
        },
        "Uninstalling": {
            icon: faSyncAlt,
            className: 'text-muted',
            spin: true
        },
    }
};


const ComponentStatus = ({ styles, status }) => {
    const statusStyles = styles[status];
    return (
        <span className={`fw-bold ${statusStyles.className}`}>
            <FontAwesomeIcon
                icon={statusStyles.icon}
                spin={statusStyles.spin}
                className="me-2"
            />
            {status}
        </span>
    );
};


const ClusterTemplate = ({ kubernetesClusterTemplates, kubernetesCluster }) => {
    const template = get(kubernetesClusterTemplates.data, kubernetesCluster.template.id);
    const className = template && template.deprecated ? "fw-bold text-danger" : undefined;
    return (
        <span className={className}>
            {template && template.deprecated && (
                <FontAwesomeIcon
                    icon={faExclamationTriangle}
                    className="me-2"
                />
            )}
            {template ? template.name : '-'}
            {template && template.deprecated && " (deprecated)"}
        </span>
    );
};


const WorkersStatus = ({ kubernetesCluster }) => {
    const workers = kubernetesCluster.nodes.filter(n => n.role === "worker");
    const workerCount = workers.length;
    const readyCount = workers.filter(n => n.status.toLowerCase() === "ready").length;
    const className = readyCount === workerCount ? 'text-success' : 'text-warning fw-bold';
    const icon = readyCount === workerCount ? faCheck : faExclamationTriangle;
    return (
        <span className={className}>
            {icon && <FontAwesomeIcon icon={icon} className="me-2" />}
            {workerCount} ({readyCount} ready)
        </span>
    );
};


const ClusterOverviewCard = ({ kubernetesCluster, kubernetesClusterTemplates }) => (
    <Card className="mb-3">
        <Card.Header className="text-center">Cluster details</Card.Header>
        <Table borderless className="details-table">
            <tbody>
                <tr>
                    <th>Name</th>
                    <td>{kubernetesCluster.name}</td>
                </tr>
                <tr>
                    <th>Template</th>
                    <td>
                        <ClusterTemplate
                            kubernetesClusterTemplates={kubernetesClusterTemplates}
                            kubernetesCluster={kubernetesCluster}
                        />
                    </td>
                </tr>
                <tr>
                    <th>Kubernetes version</th>
                    <td>{kubernetesCluster.kubernetes_version || '-'}</td>
                </tr>
                <tr>
                    <th>Status</th>
                    <td>
                        <ComponentStatus
                            styles={statusStyles.cluster}
                            status={kubernetesCluster.status}
                        />
                    </td>
                </tr>
                <tr>
                    <th>Autohealing?</th>
                    <td>
                        {kubernetesCluster.autohealing_enabled ? (
                            <span className="text-success">
                                <FontAwesomeIcon icon={faCheck} className="me-2" />
                                Enabled
                            </span>
                        ) : (
                            <span className="text-danger">
                                <FontAwesomeIcon icon={faTimes} className="me-2" />
                                Disabled
                            </span>
                        )}
                    </td>
                </tr>
                <tr>
                    <th>Workers</th>
                    <td><WorkersStatus kubernetesCluster={kubernetesCluster} /></td>
                </tr>
                <tr>
                    <th>Created</th>
                    <td>{kubernetesCluster.created_at.toRelative()}</td>
                </tr>
                <tr>
                    <th>Created by</th>
                    <td>{kubernetesCluster.created_by_username || '-'}</td>
                </tr>
                <tr>
                    <th>Updated by</th>
                    <td>{kubernetesCluster.updated_by_username || '-'}</td>
                </tr>
            </tbody>
        </Table>
    </Card>
);


const ControlPlaneCard = ({ kubernetesCluster, sizes }) => (
    <Card className="mb-3">
        <Card.Header className="text-center">Control plane</Card.Header>
        <Table borderless className="details-table">
            <tbody>
                <tr>
                    <th>Status</th>
                    <td>
                        <ComponentStatus
                            styles={statusStyles.controlPlane}
                            status={kubernetesCluster.control_plane_status}
                        />
                    </td>
                </tr>
                <tr>
                    <th>Size</th>
                    <td>
                        <MachineSizeLink
                            sizes={sizes}
                            sizeId={kubernetesCluster.control_plane_size.id}
                        />
                    </td>
                </tr>
                <tr>
                    <th>Node Count</th>
                    <td>{kubernetesCluster.nodes.filter(n => n.role === "control-plane").length}</td>
                </tr>
            </tbody>
        </Table>
    </Card>
);


const ServicesCard = ({ kubernetesCluster }) => (
    <Card className="mb-3">
        <Card.Header className="text-center">Services</Card.Header>
        {kubernetesCluster.services.length > 0 ? (
            <PlatformServicesListGroup
                services={sortBy(kubernetesCluster.services, s => s.label)}
            />
        ) : (
            <Card.Body>
                <Row>
                    <Col className="text-muted text-center">
                        No services available.
                    </Col>
                </Row>
            </Card.Body>
        )}
    </Card>
);


const AddonsCard = ({ kubernetesCluster }) => {
    const sortedAddons = sortBy(kubernetesCluster.addons, addon => addon.name);
    return (
        <Card className="mb-3">
            <Card.Header className="text-center">Cluster addons</Card.Header>
            {sortedAddons.length > 0 ? (
                <Table borderless className="details-table">
                    <tbody>
                        {sortedAddons.map(addon => (
                            <tr key={addon.name}>
                                <th><code>{addon.name}</code></th>
                                <td>
                                    <ComponentStatus
                                        styles={statusStyles.addon}
                                        status={addon.status}
                                    />
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </Table>
            ) : (
                <Card.Body>
                    <Row>
                        <Col className="text-muted text-center">
                            No addons installed.
                        </Col>
                    </Row>
                </Card.Body>
            )}
        </Card>
    );
};


const ClusterOverviewPanel = ({ kubernetesCluster, kubernetesClusterTemplates, sizes }) => (
    <Row xs="1" xl="2">
        <Col>
            <ClusterOverviewCard
                kubernetesCluster={kubernetesCluster}
                kubernetesClusterTemplates={kubernetesClusterTemplates}
            />
            <ControlPlaneCard kubernetesCluster={kubernetesCluster} sizes={sizes} />
        </Col>
        <Col>
            <ServicesCard kubernetesCluster={kubernetesCluster} />
            <AddonsCard kubernetesCluster={kubernetesCluster} />
        </Col>
    </Row>
);


const NodesTable = ({ kubernetesCluster, sizes }) => {
    const sortedNodes = sortBy(kubernetesCluster.nodes, node => [node.role, node.name]);
    return (
        <Table striped hover responsive className="resource-table mb-0">
            <caption className="px-2">
                {sortedNodes.length} node{sortedNodes.length !== 1 && 's'}
            </caption>
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Status</th>
                    <th>Size</th>
                    <th>Kubelet Version</th>
                    <th>IP address</th>
                    <th>Age</th>
                </tr>
            </thead>
            <tbody>
                {sortedNodes.map(node => (
                    <tr key={node.name}>
                        <td>
                            <div><code>{node.name}</code></div>
                            <div>
                                <Badge className="me-2" bg="primary">{node.role}</Badge>
                                <Badge bg="info">{node.node_group}</Badge>
                            </div>
                        </td>
                        <td>
                            <ComponentStatus
                                styles={statusStyles.node}
                                status={node.status}
                            />
                        </td>
                        <td>
                            <MachineSizeLink sizes={sizes} sizeId={node.size.id} />
                        </td>
                        <td>{node.kubelet_version || '-'}</td>
                        <td>{node.ip || '-'}</td>
                        <td>{node.created_at.toRelative()}</td>
                    </tr>
                ))}
            </tbody>
        </Table>
    );
};


const UpdateKubernetesClusterButton = ({
    kubernetesCluster,
    kubernetesClusterActions,
    kubernetesClusterTemplates,
    kubernetesClusterTemplateActions,
    sizes,
    sizeActions,
    externalIps,
    externalIpActions,
    disabled,
    ...props
}) => {
    const [visible, setVisible] = useState(false);
    const open = () => setVisible(true);
    const close = () => setVisible(false);

    // We need to be able to tell the difference between update and upgrade
    const [inFlight, setInFlight] = useState(false);
    useEffect(
        () => { if( inFlight && !kubernetesCluster.updating ) setInFlight(false); },
        [!!kubernetesCluster.updating]
    );

    const handleSubmit = data => {
        // Remove the name and template from the data for an update
        const { name, template, ...patchData } = data;
        kubernetesClusterActions.update(patchData);
        setInFlight(true);
        close();
    };

    return (
        <>
            <Button
                {...props}
                variant="success"
                onClick={open}
                disabled={disabled}
            >
                <FontAwesomeIcon
                    icon={inFlight ? faSyncAlt : faPen}
                    spin={inFlight}
                    className="me-2"
                />
                {inFlight ? 'Updating...' : 'Update'}
            </Button>
            <KubernetesClusterModalForm
                show={visible}
                kubernetesCluster={kubernetesCluster}
                onSubmit={handleSubmit}
                onCancel={close}
                kubernetesClusterTemplates={kubernetesClusterTemplates}
                kubernetesClusterTemplateActions={kubernetesClusterTemplateActions}
                sizes={sizes}
                sizeActions={sizeActions}
                externalIps={externalIps}
                externalIpActions={externalIpActions}
            />
        </>
    );
};


const KubernetesClusterDetailsButton = ({
    kubernetesCluster,
    kubernetesClusterActions,
    kubernetesClusterTemplates,
    kubernetesClusterTemplateActions,
    sizes,
    sizeActions,
    externalIps,
    externalIpActions
}) => {
    const [visible, setVisible] = useState(false);
    const open = () => setVisible(true);
    const close = () => setVisible(false);

    const inFlight = !!kubernetesCluster.updating || !!kubernetesCluster.deleting;

    return (
        <>
            <Button onClick={open}>Details</Button>
            <Modal size="xl" backdrop="static" onHide={close} show={visible}>
                <Modal.Header closeButton>
                    <Modal.Title>Cluster details for {kubernetesCluster.name}</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <Tab.Container defaultActiveKey="overview">
                        <Row className="mb-4">
                            <Col>
                                <Nav variant="pills" justify>
                                    <Nav.Item>
                                        <Nav.Link eventKey="overview" className="p-3">
                                            Overview
                                        </Nav.Link>
                                    </Nav.Item>
                                    <Nav.Item>
                                        <Nav.Link eventKey="nodes" className="p-3">
                                            Nodes
                                        </Nav.Link>
                                    </Nav.Item>
                                </Nav>
                            </Col>
                        </Row>
                        <Tab.Content>
                            <Tab.Pane eventKey="overview">
                                <Row className="justify-content-end mb-2">
                                    <Col xs="auto">
                                        <Button
                                            variant="primary"
                                            disabled={kubernetesCluster.fetching}
                                            onClick={kubernetesClusterActions.fetchOne}
                                            title="Refresh"
                                            className="me-2"
                                        >
                                            <FontAwesomeIcon
                                                icon={faSyncAlt}
                                                spin={kubernetesCluster.fetching}
                                                className="me-2"
                                            />
                                            Refresh
                                        </Button>
                                        <KubeconfigButton
                                            kubernetesCluster={kubernetesCluster}
                                            kubernetesClusterActions={kubernetesClusterActions}
                                            disabled={kubernetesCluster.status === "Deleting"}
                                            className="me-2"
                                        />
                                        <UpdateKubernetesClusterButton
                                            kubernetesCluster={kubernetesCluster}
                                            kubernetesClusterActions={kubernetesClusterActions}
                                            kubernetesClusterTemplates={kubernetesClusterTemplates}
                                            kubernetesClusterTemplateActions={kubernetesClusterTemplateActions}
                                            sizes={sizes}
                                            sizeActions={sizeActions}
                                            externalIps={externalIps}
                                            externalIpActions={externalIpActions}
                                            disabled={inFlight || kubernetesCluster.status === "Deleting"}
                                            className="me-2"
                                        />
                                        <UpgradeKubernetesClusterButton
                                            kubernetesCluster={kubernetesCluster}
                                            kubernetesClusterActions={kubernetesClusterActions}
                                            kubernetesClusterTemplates={kubernetesClusterTemplates}
                                            kubernetesClusterTemplateActions={kubernetesClusterTemplateActions}
                                            disabled={inFlight || kubernetesCluster.status === "Deleting"}
                                            className="me-2"
                                        />
                                        <PlatformDeleteButton
                                            name={kubernetesCluster.name}
                                            inFlight={!!kubernetesCluster.deleting}
                                            disabled={inFlight || kubernetesCluster.status === "Deleting"}
                                            onConfirm={kubernetesClusterActions.delete}
                                        />
                                    </Col>
                                </Row>
                                <ClusterOverviewPanel
                                    kubernetesCluster={kubernetesCluster}
                                    kubernetesClusterTemplates={kubernetesClusterTemplates}
                                    sizes={sizes}
                                />
                            </Tab.Pane>
                            <Tab.Pane eventKey="nodes">
                                <Row className="justify-content-end mb-2">
                                    <Col xs="auto">
                                        <Button
                                            variant="primary"
                                            disabled={kubernetesCluster.fetching}
                                            onClick={kubernetesClusterActions.fetchOne}
                                            title="Refresh"
                                            className="me-2"
                                        >
                                            <FontAwesomeIcon
                                                icon={faSyncAlt}
                                                spin={kubernetesCluster.fetching}
                                                className="me-2"
                                            />
                                            Refresh
                                        </Button>
                                    </Col>
                                </Row>
                                <NodesTable
                                    kubernetesCluster={kubernetesCluster}
                                    sizes={sizes}
                                />
                            </Tab.Pane>
                        </Tab.Content>
                    </Tab.Container>
                </Modal.Body>
                <Modal.Footer>
                    <Button
                        variant="secondary"
                        onClick={close}
                        // Ensure that the button appears over the margin for the
                        // responsive wrapper
                        style={{ zIndex: 9999 }}
                    >
                        Close
                    </Button>
                </Modal.Footer>
            </Modal>
        </>
    )
};


const statusBadgeBg = {
    "Initialising": "primary",
    "Reconciling": "primary",
    "Upgrading": "primary",
    "Ready": "success",
    "Deleting": "danger",
    "Unhealthy": "warning",
    "Failed": "danger",
    "Unknown": "secondary"
};


export const KubernetesCard = ({
    kubernetesCluster,
    kubernetesClusterActions,
    tenancy,
    tenancyActions
}) => {
    return (
        <Card className="platform-card">
            <Card.Header>
                <Badge bg={statusBadgeBg[kubernetesCluster.status]}>
                    {kubernetesCluster.status.toUpperCase()}
                </Badge>
            </Card.Header>
            <Card.Img src={KubernetesIcon} />
            <Card.Body>
                <Card.Title>{kubernetesCluster.name}</Card.Title>
                <Card.Subtitle>Kubernetes</Card.Subtitle>
            </Card.Body>
            {kubernetesCluster.services.length > 0 && (
                <PlatformServicesListGroup
                    services={sortBy(kubernetesCluster.services, s => s.label)}
                />
            )}
            <Card.Body className="small text-muted">
                Created {kubernetesCluster.created_at.toRelative()}<br/>
                Created by {kubernetesCluster.created_by_username || 'unknown'}
            </Card.Body>
            <Card.Footer>
                <KubernetesClusterDetailsButton
                    kubernetesCluster={kubernetesCluster}
                    kubernetesClusterActions={kubernetesClusterActions}
                    kubernetesClusterTemplates={tenancy.kubernetesClusterTemplates}
                    kubernetesClusterTemplateActions={tenancyActions.kubernetesClusterTemplate}
                    sizes={tenancy.sizes}
                    sizeActions={tenancyActions.size}
                    externalIps={tenancy.externalIps}
                    externalIpActions={tenancyActions.externalIp}
                />
            </Card.Footer>
        </Card>
    );
};
