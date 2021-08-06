/**
 * This module contains components for the machines table.
 */

import React, { useState } from 'react';

import Button from 'react-bootstrap/Button';
import Col from 'react-bootstrap/Col';
import DropdownButton from 'react-bootstrap/DropdownButton';
import DropdownItem from 'react-bootstrap/DropdownItem';
import Form from 'react-bootstrap/Form';
import Image from 'react-bootstrap/Image';
import Modal from 'react-bootstrap/Modal';
import OverlayTrigger from 'react-bootstrap/OverlayTrigger';
import Popover from 'react-bootstrap/Popover';
import ProgressBar from 'react-bootstrap/ProgressBar';
import Row from 'react-bootstrap/Row';
import Table from 'react-bootstrap/Table';
import Tooltip from 'react-bootstrap/Tooltip';

import get from 'lodash/get';
import truncate from 'lodash/truncate';

import moment from 'moment';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
    faExclamationCircle,
    faQuestionCircle,
    faSave
} from '@fortawesome/free-solid-svg-icons';

import { bindArgsToActions, sortBy, Loading } from '../../utils';

import { ClusterParameterField } from './cluster-parameter-field';


const UpdateClusterParametersMenuItem = ({
    cluster,
    tenancy,
    tenancyActions,
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
            <DropdownItem onSelect={open} disabled={!clusterType}>
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


const ConfirmPatchMenuItem = ({ name, onConfirm }) => {
    const [visible, setVisible] = useState(false);

    const open = () => setVisible(true);
    const close = () => setVisible(false);
    const handleConfirm = () => { onConfirm(); close(); };

   return (
        <>
            <DropdownItem onSelect={open}>
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


const ClusterStatus = ({ cluster }) => (
    <span className={`fw-bold ${statusClasses[cluster.status]}`}>
        {cluster.status}
        {cluster.error_message && (
            <OverlayTrigger
                placement="right"
                overlay={(
                    <Popover>
                        <Popover.Header>Error message</Popover.Header>
                        <Popover.Body>{cluster.error_message}</Popover.Body>
                    </Popover>
                )}
                trigger="click"
                rootClose
            >
                <a
                    className="ms-1 text-reset overlay-trigger"
                    title="Error message"
                >
                    <FontAwesomeIcon icon={faQuestionCircle} />
                </a>
            </OverlayTrigger>
        )}
    </span>
);

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
    disabled,
    cluster,
    clusterActions,
    tenancy,
    tenancyActions
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
        <ConfirmPatchMenuItem
            name={cluster.name}
            onConfirm={clusterActions.patch}
        />
        <UpdateClusterParametersMenuItem
            cluster={cluster}
            tenancy={tenancy}
            tenancyActions={tenancyActions}
            onSubmit={clusterActions.update}
        />
        <ConfirmDeleteMenuItem
            name={cluster.name}
            disabled={cluster.linked}
            onConfirm={clusterActions.delete}
        />
    </DropdownButton>
);


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
                  disabled={!!highlightClass}
                  cluster={cluster}
                  tenancy={tenancy}
                  tenancyActions={tenancyActions}
                  clusterActions={clusterActions} />
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
