/**
 * This module contains components for the machines table.
 */

import React, { useState } from 'react';

import Alert from 'react-bootstrap/Alert';
import Badge from 'react-bootstrap/Badge';
import Button from 'react-bootstrap/Button';
import Col from 'react-bootstrap/Col';
import DropdownButton from 'react-bootstrap/DropdownButton';
import DropdownItem from 'react-bootstrap/DropdownItem';
import Modal from 'react-bootstrap/Modal';
import OverlayTrigger from 'react-bootstrap/OverlayTrigger';
import Popover from 'react-bootstrap/Popover';
import Row from 'react-bootstrap/Row';
import Table from 'react-bootstrap/Table';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';

import get from 'lodash/get';

import moment from 'moment';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
    faCheck,
    faClock,
    faExclamationTriangle,
    faQuestionCircle,
    faSyncAlt,
    faTimes,
    faTimesCircle
} from '@fortawesome/free-solid-svg-icons';

import { bindArgsToActions, formatSize, sortBy, Loading, useSortable } from '../../../utils';

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
    addons: {
        "Pending": {
            icon: faClock,
            className: 'text-muted'
        },
        "Deploying": {
            icon: faSyncAlt,
            className: 'text-muted',
            spin: true
        },
        "Deployed": {
            icon: faCheck,
            className: 'text-muted'
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
        "Provisioned": {
            icon: faCheck,
            className: 'text-muted'
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
    }
};


const NodeSizeLink = ({ kubernetesCluster, node, sizes }) => {
    let sizeId;
    if( node.role === "control-plane" ) {
        sizeId = kubernetesCluster.control_plane_size.id;
    }
    else {
        const nodeGroup = kubernetesCluster.node_groups.find(ng => ng.name === node.node_group);
        sizeId = get(nodeGroup, ['machine_size', 'id']);
    }
    return <MachineSizeLink sizes={sizes} sizeId={sizeId} />;
};


const NodeDetailsMenuItem = ({ kubernetesCluster, sizes }) => {
    const [visible, setVisible] = useState(false);
    const open = () => setVisible(true);
    const close = () => setVisible(false);

    const sortedNodes = sortBy(kubernetesCluster.nodes, node => [node.role, node.name]);

    return (
        <>
            <DropdownItem onSelect={open}>
                Cluster node details
            </DropdownItem>
            <Modal size="xl" backdrop="static" onHide={close} show={visible}>
                <Modal.Header closeButton>
                    <Modal.Title>Cluster nodes for {kubernetesCluster.name}</Modal.Title>
                </Modal.Header>
                <Modal.Body>
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
                                        <NodeSizeLink
                                            kubernetesCluster={kubernetesCluster}
                                            node={node}
                                            sizes={sizes}
                                        />
                                    </td>
                                    <td>{node.kubelet_version || '-'}</td>
                                    <td>{node.ip || '-'}</td>
                                </tr>
                            ))}
                        </tbody>
                    </Table>
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
                Update cluster
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
                className="text-danger"
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
        />
        <NodeDetailsMenuItem kubernetesCluster={kubernetesCluster} sizes={sizes} />
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
            <td>{kubernetesCluster.kubernetes_version}</td>
            <td>
                <ComponentStatus
                    styles={statusStyles.controlPlane}
                    status={kubernetesCluster.control_plane_status}
                />
            </td>
            <td><WorkersStatus kubernetesCluster={kubernetesCluster} /></td>
            <td>
                <ComponentStatus
                    styles={statusStyles.addons}
                    status={kubernetesCluster.addons_status}
                />
            </td>
            <td>{moment(kubernetesCluster.created_at).fromNow()}</td>
            <td className="resource-actions">
                <ClusterActionsDropdown
                    disabled={!!highlightClasses || kubernetesCluster.status === "Deleting"}
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
                    <th>Kubernetes Version</th>
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
