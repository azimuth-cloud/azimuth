/**
 * This module contains components for the machines table.
 */

import React, { useState } from 'react';

import Badge from 'react-bootstrap/Badge';
import Button from 'react-bootstrap/Button';
import Card from 'react-bootstrap/Card';
import Col from 'react-bootstrap/Col';
import DropdownButton from 'react-bootstrap/DropdownButton';
import DropdownItem from 'react-bootstrap/DropdownItem';
import ListGroup from 'react-bootstrap/ListGroup';
import Modal from 'react-bootstrap/Modal';
import Nav from 'react-bootstrap/Nav';
import Row from 'react-bootstrap/Row';
import Table from 'react-bootstrap/Table';
import Tab from 'react-bootstrap/Tab';

import get from 'lodash/get';

import moment from 'moment';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
    faBookmark,
    faCheck,
    faClock,
    faExclamationTriangle,
    faExternalLinkAlt,
    faQuestionCircle,
    faSyncAlt,
    faTimes,
    faTimesCircle
} from '@fortawesome/free-solid-svg-icons';

import { bindArgsToActions, sortBy, Loading, useSortable } from '../../../utils';

import { MachineSizeLink } from '../resource-utils';
import { UpgradeKubernetesClusterMenuItem } from './upgrade-modal';
import { KubeconfigMenuItem } from './kubeconfig-modal';
import { KubernetesClusterModalForm } from './modal-form';


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
        "Pending": {
            icon: faClock,
            className: 'text-muted'
        },
        "Installing": {
            icon: faSyncAlt,
            className: 'text-muted',
            spin: true
        },
        "Ready": {
            icon: faCheck,
            className: 'text-success'
        },
        "Uninstalling": {
            icon: faSyncAlt,
            className: 'text-muted',
            spin: true
        },
        "Failed": {
            icon: faTimesCircle,
            className: 'text-danger'
        },
        "Unknown": {
            icon: faQuestionCircle,
            className: 'text-muted'
        }
    }
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
                    <th>Node groups</th>
                    <td>{kubernetesCluster.node_groups.length}</td>
                </tr>
                <tr>
                    <th>Created</th>
                    <td>{moment(kubernetesCluster.created_at).fromNow()}</td>
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


const ServiceCard = ({ kubernetesCluster }) => {
    const sortedServices = sortBy(kubernetesCluster.services, service => service.name);
    return (
        <Card className="mb-3">
            <Card.Header className="text-center">Services</Card.Header>
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
            <ServiceCard kubernetesCluster={kubernetesCluster} />
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
                        <td>{moment(node.created_at).fromNow(true)}</td>
                    </tr>
                ))}
            </tbody>
        </Table>
    );
};


const KubernetesClusterDetailsMenuItem = ({
    kubernetesCluster,
    kubernetesClusterTemplates,
    sizes
}) => {
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
                    <Modal.Title>Cluster details for {kubernetesCluster.name}</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <Tab.Container id="left-tabs-example" defaultActiveKey="overview">
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
                                <ClusterOverviewPanel
                                    kubernetesCluster={kubernetesCluster}
                                    kubernetesClusterTemplates={kubernetesClusterTemplates}
                                    sizes={sizes}
                                />
                            </Tab.Pane>
                            <Tab.Pane eventKey="nodes">
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

const UpdateKubernetesClusterMenuItem = ({
    kubernetesCluster,
    kubernetesClusterActions,
    kubernetesClusterTemplates,
    kubernetesClusterTemplateActions,
    sizes,
    sizeActions
}) => {
    const [visible, setVisible] = useState(false);
    const open = () => setVisible(true);
    const close = () => setVisible(false);

    const handleSuccess = data => {
        // Remove the name and template from the data for an update
        const { name, template, ...patchData } = data;
        kubernetesClusterActions.update(patchData, true);
        close();
    };

    return (
        <>
            <DropdownItem
                onSelect={open}
                disabled={kubernetesCluster.status.endsWith("ing")}
            >
                Modify cluster
            </DropdownItem>
            <KubernetesClusterModalForm
                show={visible}
                kubernetesCluster={kubernetesCluster}
                onSuccess={handleSuccess}
                onCancel={close}
                kubernetesClusterTemplates={kubernetesClusterTemplates}
                kubernetesClusterTemplateActions={kubernetesClusterTemplateActions}
                sizes={sizes}
                sizeActions={sizeActions}
            />
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
                className={disabled ? undefined : "text-danger"}
                disabled={disabled}
                onSelect={open}
            >
                Delete cluster
            </DropdownItem>
            <Modal show={visible} backdrop="static" keyboard={false}>
                <Modal.Body>
                    <p>Are you sure you want to delete {name}?</p>
                    <p><strong>Once deleted, a Kubernetes cluster cannot be restored.</strong></p>
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


const AddonsStatus = ({ kubernetesCluster }) => {
    const addons = kubernetesCluster.addons;
    const count = addons.length;
    const readyCount = addons.filter(a => a.status.toLowerCase() === "ready").length;
    const failedCount = addons.filter(a => a.status.toLowerCase() === "failed").length;
    const inProgressCount = addons
        .filter(a => ["pending", "installing", "uninstalling"].includes(a.status.toLowerCase()))
        .length;
    let className, icon, spin = false;
    if( readyCount === count ) {
        className = "text-success";
        icon = faCheck;
    }
    else if( inProgressCount > 0 ) {
        className = "text-muted";
        icon = faSyncAlt;
        spin = true;
    }
    else if( failedCount > 0 ) {
        className = "text-warning";
        icon = faExclamationTriangle;
    }
    else {
        className = "text-muted";
        icon = faQuestionCircle;
    }
    return (
        <span className={className}>
            {icon && <FontAwesomeIcon icon={icon} spin={spin} className="me-2" />}
            {count} ({readyCount} ready)
        </span>
    );
};


const ClusterActionsDropdown = ({
    disabled,
    kubernetesCluster,
    kubernetesClusterActions,
    kubernetesClusterTemplates,
    kubernetesClusterTemplateActions,
    sizes,
    sizeActions
}) => (
    <DropdownButton
        variant="secondary"
        title={
            disabled ? (
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
        disabled={disabled}
        className="float-end"
    >
        <KubeconfigMenuItem
            kubernetesCluster={kubernetesCluster}
            kubernetesClusterActions={kubernetesClusterActions}
            disabled={kubernetesCluster.status === "Deleting"}
        />
        <KubernetesClusterDetailsMenuItem
            kubernetesCluster={kubernetesCluster}
            kubernetesClusterTemplates={kubernetesClusterTemplates}
            sizes={sizes}
        />
        <UpdateKubernetesClusterMenuItem
            kubernetesCluster={kubernetesCluster}
            kubernetesClusterActions={kubernetesClusterActions}
            kubernetesClusterTemplates={kubernetesClusterTemplates}
            kubernetesClusterTemplateActions={kubernetesClusterTemplateActions}
            sizes={sizes}
            sizeActions={sizeActions}
        />
        <UpgradeKubernetesClusterMenuItem
            kubernetesCluster={kubernetesCluster}
            kubernetesClusterActions={kubernetesClusterActions}
            kubernetesClusterTemplates={kubernetesClusterTemplates}
            kubernetesClusterTemplateActions={kubernetesClusterTemplateActions}
        />
        <ConfirmDeleteMenuItem
            name={kubernetesCluster.name}
            onConfirm={kubernetesClusterActions.delete}
            disabled={kubernetesCluster.status === "Deleting"}
        />
    </DropdownButton>
);


const ClusterRow = ({
    kubernetesCluster,
    kubernetesClusterActions,
    kubernetesClusterTemplates,
    kubernetesClusterTemplateActions,
    sizes,
    sizeActions
}) => {
    let highlightClasses = null;
    if( kubernetesCluster.updating ) {
        highlightClasses = 'table-warning';
    }
    else if( kubernetesCluster.deleting ) {
        highlightClasses = 'table-danger';
    }
    return (
        <tr className={highlightClasses || undefined}>
            <td>{kubernetesCluster.name}</td>
            <td>
                <ComponentStatus
                    styles={statusStyles.cluster}
                    status={kubernetesCluster.status}
                />
            </td>
            <td>
                <ClusterTemplate
                    kubernetesClusterTemplates={kubernetesClusterTemplates}
                    kubernetesCluster={kubernetesCluster}
                />
            </td>
            <td>
                <ComponentStatus
                    styles={statusStyles.controlPlane}
                    status={kubernetesCluster.control_plane_status}
                />
            </td>
            <td><WorkersStatus kubernetesCluster={kubernetesCluster} /></td>
            <td><AddonsStatus kubernetesCluster={kubernetesCluster} /></td>
            <td>{moment(kubernetesCluster.created_at).fromNow()}</td>
            <td className="resource-actions">
                <ClusterActionsDropdown
                    disabled={!!highlightClasses}
                    kubernetesCluster={kubernetesCluster}
                    kubernetesClusterActions={kubernetesClusterActions}
                    kubernetesClusterTemplates={kubernetesClusterTemplates}
                    kubernetesClusterTemplateActions={kubernetesClusterTemplateActions}
                    sizes={sizes}
                    sizeActions={sizeActions}
                />
            </td>
        </tr>
    );
};


export const KubernetesClustersTable = ({
    kubernetesClusters,
    kubernetesClusterActions,
    kubernetesClusterTemplates,
    kubernetesClusterTemplateActions,
    sizes,
    sizeActions
}) => {
    const [sortedClusters, SortableColumnHeading] = useSortable(
        Object.values(kubernetesClusters),
        { initialField: 'created_at', initialReverse: true }
    );
    return (
        <Table striped hover responsive className="resource-table">
            <caption className="px-2">
                {sortedClusters.length} cluster{sortedClusters.length !== 1 && 's'}
            </caption>
            <thead>
                <tr>
                    <SortableColumnHeading field="name">Name</SortableColumnHeading>
                    <th>Status</th>
                    <th>Template</th>
                    <th>Control Plane</th>
                    <th>Workers</th>
                    <th>Addons</th>
                    <SortableColumnHeading field="created_at">
                        Created
                    </SortableColumnHeading>
                    <th></th>
                </tr>
            </thead>
            <tbody>
                {sortedClusters.map(cluster =>
                    <ClusterRow
                        key={cluster.id}
                        kubernetesCluster={cluster}
                        kubernetesClusterActions={bindArgsToActions(
                            kubernetesClusterActions,
                            cluster.id
                        )}
                        kubernetesClusterTemplates={kubernetesClusterTemplates}
                        kubernetesClusterTemplateActions={kubernetesClusterTemplateActions}
                        sizes={sizes}
                        sizeActions={sizeActions}
                    />
                )}
            </tbody>
        </Table>
    );
};
