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
    faPaste,
    faCheckCircle,
    faExclamationTriangle,
    faTimesCircle,
    faSyncAlt
} from '@fortawesome/free-solid-svg-icons';

import { bindArgsToActions, formatSize, sortBy, Loading, useSortable } from '../../utils';

import { KubeconfigMenuItem } from './kubeconfig-modal';


const EnabledIcon = ({ value }) => (
    value ? (
        <span className="text-primary">
            <FontAwesomeIcon icon={faCheck} />
            <span className="sr-only">Enabled</span>
        </span>
    ) : (
        "-"
    )
);


const getStatusVariant = (status) => {
    if( status.startsWith("DELETE_") || status.endsWith("_FAILED") ) return 'danger';
    if( status.endsWith("_IN_PROGRESS") ) {
        return status.startsWith("CREATE_") ? 'info' : 'warning';
    }
    return 'primary';
};


const getHealthStatusVariant = (status) => {
    switch( status ) {
        case 'HEALTHY': return 'success';
        case 'UNHEALTHY': return 'danger';
        default: return 'muted';
    }
};


const getStatusDetailItemVariant = (item) => {
    switch( item.toLowerCase() ) {
        case 'ok':
        case 'true':
            return 'success';
        default:
            return 'danger';
    }
};


const ClusterStatusPills = ({ kubernetesCluster }) => {
    const statusVariant = getStatusVariant(kubernetesCluster.status);
    const healthStatusVariant = getHealthStatusVariant(kubernetesCluster.health_status);
    return (
        <Row>
            <Col>
                <div className={`status-pill status-pill-${statusVariant}`}>
                    <h6 className="status-pill-title">Cluster Status</h6>
                    <div>
                        {kubernetesCluster.status.endsWith("_IN_PROGRESS") && (
                            <FontAwesomeIcon icon={faSyncAlt} spin={true} className="me-2" />
                        )}
                        <strong>{kubernetesCluster.status}</strong>
                    </div>
                </div>
            </Col>
            <Col>
                <div className={`status-pill status-pill-${healthStatusVariant}`}>
                    <h6 className="status-pill-title">Cluster Health</h6>
                    <strong>{kubernetesCluster.health_status || 'UNKNOWN'}</strong>
                </div>
            </Col>
        </Row>
    );
};


const ClusterStatusDetailAlert = ({ statusDetail }) => (
    <Row className="justify-content-center mt-3">
        <Col xs="auto">
            <Alert variant="warning">{statusDetail}</Alert>
        </Col>
    </Row>
);


const SizeLink = ({ sizes, sizeId }) => {
    const size = get(sizes.data, sizeId);
    if( size ) {
        return (
            <OverlayTrigger
                placement="top"
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
                                </tbody>
                            </Table>
                        </Popover.Body>
                    </Popover>
                )}
                trigger="click"
                rootClose
            >
                <Button variant="link">{size.name}</Button>
            </OverlayTrigger>
        );
    }
    else if( sizes.fetching ) {
        return <Loading message="Loading sizes..." />;
    }
    else {
        return sizeId;
    }
};


const ClusterInfoPanel = ({ kubernetesCluster, sizes, notificationActions }) => (
    <>
        <Row className="text-center mb-3">
            <Col xs={12} lg={4}>
                <Row className="mb-3">
                    <Col xs={5} lg={12} className="text-muted">
                        Kubernetes version
                    </Col>
                    <Col xs={7} lg={12}>
                        {kubernetesCluster.kubernetes_version || (
                            <span className="text-muted">Not known</span>
                        )}
                    </Col>
                </Row>
            </Col>
            <Col xs={12} lg={4}>
                <Row className="mb-3">
                    <Col xs={5} lg={12} className="text-muted">
                        API address
                    </Col>
                    <Col xs={7} lg={12}>
                        <a target="_blank" href={kubernetesCluster.api_address}>
                            {kubernetesCluster.api_address || (
                                <span className="text-muted">Not known</span>
                            )}
                        </a>
                    </Col>
                </Row>
            </Col>
            <Col xs={12} lg={4}>
                <Row className="mb-3">
                    <Col xs={5} lg={12} className="text-muted">
                        HA enabled?
                    </Col>
                    <Col xs={7} lg={12}>
                        <EnabledIcon value={kubernetesCluster.master_count > 1} />
                    </Col>
                </Row>
            </Col>
        </Row>
        <Row className="text-center mb-3">
            <Col xs={12} lg={6}>
                <Row className="mb-3">
                    <Col xs={5} lg={12} className="text-muted">
                        Control plane size
                    </Col>
                    <Col xs={7} lg={12}>
                        <SizeLink
                            sizes={sizes}
                            sizeId={kubernetesCluster.master_size.id}
                        />
                    </Col>
                </Row>
            </Col>
            <Col xs={12} lg={6}>
                <Row className="mb-3">
                    <Col xs={5} lg={12} className="text-muted">
                        Control plane node count
                    </Col>
                    <Col xs={7} lg={12}>
                        {kubernetesCluster.master_count}
                    </Col>
                </Row>
            </Col>
        </Row>
        <Row className="text-center mb-3">
            <Col xs={12} lg={4}>
                <Row className="mb-3">
                    <Col xs={5} lg={12} className="text-muted">
                        Auto-scaling enabled?
                    </Col>
                    <Col xs={7} lg={12}>
                        <EnabledIcon
                            value={kubernetesCluster.auto_scaling_enabled}
                        />
                        {kubernetesCluster.auto_scaling_enabled && (
                            <span className="text-muted">
                                {" "}
                                (min: {kubernetesCluster.min_worker_count},{" "}
                                max: {kubernetesCluster.max_worker_count})
                            </span>
                        )}
                    </Col>
                </Row>
            </Col>
            <Col xs={12} lg={4}>
                <Row className="mb-3">
                    <Col xs={5} lg={12} className="text-muted">
                        Worker size
                    </Col>
                    <Col xs={7} lg={12}>
                        <SizeLink
                            sizes={sizes}
                            sizeId={kubernetesCluster.worker_size.id}
                        />
                    </Col>
                </Row>
            </Col>
            <Col xs={12} lg={4}>
                <Row className="mb-3">
                    <Col xs={5} lg={12} className="text-muted">
                        Current worker count
                    </Col>
                    <Col xs={7} lg={12}>
                        {kubernetesCluster.worker_count}
                    </Col>
                </Row>
            </Col>
        </Row>
        <Row className="text-center mb-3">
            <Col xs={12} lg={6}>
                <Row className="mb-3">
                    <Col xs={5} lg={12} className="text-muted">
                        Monitoring enabled?
                    </Col>
                    <Col xs={7} lg={12}>
                        <EnabledIcon
                            value={kubernetesCluster.monitoring_enabled}
                        />
                    </Col>
                </Row>
            </Col>
            <Col xs={12} lg={6}>
                <Row className="mb-3">
                    <Col xs={5} lg={12} className="text-muted">
                        Grafana admin password
                    </Col>
                    <Col xs={7} lg={12}>
                        {kubernetesCluster.monitoring_enabled ? (
                            <>
                                ********************
                                <Button
                                    variant="link"
                                    className="ms-2"
                                    onClick={() => navigator.clipboard
                                        .writeText(kubernetesCluster.grafana_admin_password)
                                        .then(() => notificationActions.success({
                                            'title': 'Copied successfully',
                                            'message': 'Grafana admin password copied to clipboard.'
                                        }))
                                    }
                                >
                                    <FontAwesomeIcon icon={faPaste} />
                                    <span className="sr-only">Copy to clipboard</span>
                                </Button>
                            </>
                        ) : (
                            '-'
                        )}
                    </Col>
                </Row>
            </Col>
        </Row>
        <Row className="text-center">
            <Col xs={12} lg={6}>
                <Row className="mb-3">
                    <Col xs={5} lg={12} className="text-muted">
                        Created
                    </Col>
                    <Col xs={7} lg={12}>
                        {moment(kubernetesCluster.created_at).fromNow()}
                    </Col>
                </Row>
            </Col>
            <Col xs={12} lg={6}>
                <Row className="mb-3">
                    <Col xs={5} lg={12} className="text-muted">
                        Updated
                    </Col>
                    <Col xs={7} lg={12}>
                        {kubernetesCluster.created_at ?
                            moment(kubernetesCluster.created_at).fromNow() :
                            '-'
                        }
                    </Col>
                </Row>
            </Col>
        </Row>
    </>
);


const ClusterHealthPanel = ({ healthDetail }) => {
    const healthDetailItems = sortBy(Object.entries(healthDetail || {}), item => item[0]);
    return (
        <Row>
            <Col>
                <Table borderless className="mb-0">
                    <tbody>
                        {healthDetailItems.map(([k, v]) => (
                            <tr key={k}>
                                <th className="w-50 text-end align-middle">
                                    <code>{k}</code>
                                </th>
                                <td className="align-middle">
                                    <Badge pill bg={getStatusDetailItemVariant(v)}>
                                        {v}
                                    </Badge>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </Table>
            </Col>
        </Row>
    );
};


const ClusterDetailsModal = ({
    kubernetesCluster,
    sizes,
    notificationActions,
    onHide,
    ...props
}) => (
    <Modal backdrop="static" size="lg" onHide={onHide} {...props}>
        <Modal.Header>
            <Modal.Title>Kubernetes cluster: {kubernetesCluster.name}</Modal.Title>
        </Modal.Header>
        <Modal.Body>
            <ClusterStatusPills kubernetesCluster={kubernetesCluster} />
            {kubernetesCluster.status_detail && (
                <ClusterStatusDetailAlert statusDetail={kubernetesCluster.status_detail} />
            )}
            <Row>
                <Col>
                    <Tabs defaultActiveKey="info" justify className="my-3">
                        <Tab eventKey="info" title="Cluster Information">
                            <ClusterInfoPanel
                                kubernetesCluster={kubernetesCluster}
                                sizes={sizes}
                                notificationActions={notificationActions}
                            />
                        </Tab>
                        <Tab
                            eventKey="health"
                            title="Cluster Health"
                            disabled={!kubernetesCluster.health_status_detail}
                        >
                            <ClusterHealthPanel
                                healthDetail={kubernetesCluster.health_status_detail}
                            />
                        </Tab>
                    </Tabs>
                </Col>
            </Row>
        </Modal.Body>
        <Modal.Footer>
            <Button variant="primary" onClick={onHide}>Close</Button>
        </Modal.Footer>
    </Modal>
);


const ClusterDetailsLink = ({ kubernetesCluster, sizes, notificationActions }) => {
    const [modalVisible, setModalVisible] = useState(false);
    const open = () => setModalVisible(true);
    const close = () => setModalVisible(false);
    return (
        <>
            <Button variant="link" onClick={open}>
                {kubernetesCluster.name}
            </Button>
            <ClusterDetailsModal
                kubernetesCluster={kubernetesCluster}
                sizes={sizes}
                notificationActions={notificationActions}
                show={modalVisible}
                onHide={close}
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


const getStatusStyles = (status, healthStatus) => {
    if( status.endsWith("_IN_PROGRESS") ) {
        return {
            icon: faSyncAlt,
            className: 'text-muted',
            text: status,
            spin: true
        };
    }
    else if( status.endsWith("_FAILED") ) {
        return {
            icon: faTimesCircle,
            className: 'text-danger',
            text: status
        };
    }
    else {
        switch( healthStatus ) {
            case 'HEALTHY':
                return {
                    icon: faCheckCircle,
                    className: 'text-success',
                    text: healthStatus
                };
            case 'UNHEALTHY':
                return {
                    icon: faExclamationTriangle,
                    className: 'text-warning',
                    text: healthStatus
                };
            default:
                return {
                    icon: faCheckCircle,
                    className: 'text-muted',
                    text: healthStatus
                };
        }
    }
};


const ClusterStatus = ({ kubernetesCluster }) => {
    const statusStyles = getStatusStyles(
        kubernetesCluster.status,
        kubernetesCluster.health_status
    );
    return (
        <span className={statusStyles.className}>
            <FontAwesomeIcon icon={statusStyles.icon} spin={statusStyles.spin} />
            <span className="sr-only">{statusStyles.text}</span>
        </span>
    );
};


const ClusterActionsDropdown = ({
    disabled,
    kubernetesCluster,
    kubernetesClusterActions
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
        <ConfirmDeleteMenuItem
            name={kubernetesCluster.name}
            onConfirm={kubernetesClusterActions.delete}
        />
    </DropdownButton>
);


const ClusterRow = ({
    kubernetesCluster,
    kubernetesClusterActions,
    sizes,
    notificationActions
}) => {
    let highlightClasses = null;
    if( kubernetesCluster.updating ) {
        highlightClasses = 'table-warning';
    }
    else if( kubernetesCluster.deleting ) {
        highlightClasses = 'table-danger';
    }
    else if( kubernetesCluster.status.endsWith("_IN_PROGRESS") ) {
        if( kubernetesCluster.status.startsWith("CREATE_") ) {
            highlightClasses = 'table-info';
        }
        else if( kubernetesCluster.status.startsWith("DELETE_") ) {
            highlightClasses = 'table-danger';
        }
        else {
            highlightClasses = 'table-warning';
        }
    }
    return (
        <tr className={highlightClasses || undefined}>
            <td>
                <ClusterDetailsLink
                    kubernetesCluster={kubernetesCluster}
                    sizes={sizes}
                    notificationActions={notificationActions}
                />
            </td>
            <td><ClusterStatus kubernetesCluster={kubernetesCluster} /></td>
            <td>{kubernetesCluster.kubernetes_version || '-'}</td>
            <td>{kubernetesCluster.master_count}</td>
            <td>{kubernetesCluster.worker_count}</td>
            <td><EnabledIcon value={kubernetesCluster.auto_scaling_enabled} /></td>
            <td><EnabledIcon value={kubernetesCluster.monitoring_enabled} /></td>
            <td>{moment(kubernetesCluster.created_at).fromNow()}</td>
            <td>
                {kubernetesCluster.updated_at ?
                    moment(kubernetesCluster.updated_at).fromNow() :
                    '-'
                }
            </td>
            <td className="resource-actions">
                <ClusterActionsDropdown
                    disabled={!!highlightClasses}
                    kubernetesCluster={kubernetesCluster}
                    kubernetesClusterActions={kubernetesClusterActions}
                />
            </td>
        </tr>
    );
};


export const KubernetesClustersTable = ({
    kubernetesClusters,
    kubernetesClusterActions,
    sizes,
    notificationActions
}) => {
    const [sortedClusters, SortableColumnHeading] = useSortable(
        Object.values(kubernetesClusters),
        { initialField: 'name', initialReverse: false }
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
                    <SortableColumnHeading field="kubernetes_version">
                        Kubernetes Version
                    </SortableColumnHeading>
                    <th>Master Count</th>
                    <th>Worker Count</th>
                    <th>Auto-scaling enabled?</th>
                    <th>Monitoring enabled?</th>
                    <SortableColumnHeading field="created_at">
                        Created
                    </SortableColumnHeading>
                    <SortableColumnHeading field="updated_at">
                        Updated
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
                        sizes={sizes}
                        notificationActions={notificationActions}
                    />
                )}
            </tbody>
        </Table>
    );
};
