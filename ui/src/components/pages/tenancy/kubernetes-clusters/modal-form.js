import React, { useEffect, useState } from 'react';

import Button from 'react-bootstrap/Button';
import ButtonGroup from 'react-bootstrap/ButtonGroup';
import Card from 'react-bootstrap/Card';
import Col from 'react-bootstrap/Col';
import BSForm from 'react-bootstrap/Form';
import Modal from 'react-bootstrap/Modal';
import Row from 'react-bootstrap/Row';
import Table from 'react-bootstrap/Table';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
    faBan,
    faEdit,
    faPlus,
    faSave
} from '@fortawesome/free-solid-svg-icons';

import { Error, Form, Field, withCustomValidity } from '../../../utils';

import {
    MachineSizeLink,
    KubernetesClusterTemplateSelectControl,
    SizeSelectControl
} from '../resource-utils';


const InputWithCustomValidity = withCustomValidity("input");


const NodeGroupModalForm = ({
    nodeGroupNames,
    nodeGroup,
    onSuccess,
    onCancel,
    sizes,
    sizeActions,
    ...props
}) => {
    const [state, setState] = useState({});
    useEffect(() => { setState(nodeGroup || {}); }, [nodeGroup]);

    const getStateKey = key => state[key] || '';
    const setStateKey = key => value => setState(state => ({ ...state, [key]: value }));
    const setStateKeyFromInputEvent = key => evt => setStateKey(key)(evt.target.value);

    const handleCancel = () => {
        setState({});
        onCancel();
    };

    const handleSubmit = (evt) => {
        evt.preventDefault();
        setState({});
        onSuccess(state);
    };

    const nameInUseMessage = (
        nodeGroupNames.some(name => name === getStateKey('name')) ?
            'Name is already in use for another node group.' :
            ''
    );

    return (
        <Modal backdrop="static" onHide={handleCancel} size="lg" {...props}>
            <Modal.Header closeButton>
                <Modal.Title>{nodeGroup ? 'Edit' : 'Add'} node group</Modal.Title>
            </Modal.Header>
            <Form onSubmit={handleSubmit}>
                <Modal.Body>
                    <Field
                        name="name"
                        label="Name"
                        helpText="Must contain lower-case alphanumeric characters and dash (-) only."
                    >
                        <BSForm.Control
                            as={InputWithCustomValidity}
                            type="text"
                            placeholder="Name"
                            required
                            pattern="^[a-z][a-z0-9-]+[a-z0-9]$"
                            autoComplete="off"
                            value={getStateKey('name')}
                            onChange={setStateKeyFromInputEvent('name')}
                            validationMessage={nameInUseMessage}
                        />
                    </Field>
                    <Field
                        name="machine_size"
                        label="Node Size"
                        helpText="The size to use for nodes in the group."
                    >
                        <SizeSelectControl
                            resource={sizes}
                            resourceActions={sizeActions}
                            required
                            value={getStateKey('machine_size')}
                            onChange={setStateKey('machine_size')}
                        />
                    </Field>
                    <Field
                        name="count"
                        label="Node Count"
                        helpText="The target number of nodes in the group."
                    >
                        <BSForm.Control
                            placeholder="Node Count"
                            type="number"
                            required
                            min="0"
                            step="1"
                            value={getStateKey('count')}
                            onChange={setStateKeyFromInputEvent('count')}
                        />
                    </Field>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="success" type="submit">
                        <FontAwesomeIcon icon={faSave} className="me-2" />
                        Save node group
                    </Button>
                </Modal.Footer>
            </Form>
        </Modal>
    );
};


const initialState = kubernetesCluster => {
    if( kubernetesCluster ) {
        return {
            name: kubernetesCluster.name,
            template: kubernetesCluster.template.id,
            control_plane_size: kubernetesCluster.control_plane_size.id,
            node_groups: kubernetesCluster.node_groups.map(ng => ({
                name: ng.name,
                machine_size: ng.machine_size.id,
                count: ng.count
            })),
            autohealing_enabled: kubernetesCluster.autohealing_enabled,
            cert_manager_enabled: kubernetesCluster.cert_manager_enabled,
            dashboard_enabled: kubernetesCluster.dashboard_enabled,
            ingress_enabled: kubernetesCluster.ingress_enabled,
            monitoring_enabled: kubernetesCluster.monitoring_enabled,
            apps_enabled: kubernetesCluster.apps_enabled
        };
    }
    else {
        // There is no existing cluster, so set some defaults
        return {
            name: '',
            template: '',
            control_plane_size: '',
            node_groups: [],
            autohealing_enabled: true,
            cert_manager_enabled: false,
            dashboard_enabled: true,
            ingress_enabled: false,
            monitoring_enabled: true,
            apps_enabled: true
        };
    }
};


export const KubernetesClusterModalForm = ({
    kubernetesCluster,
    onSuccess,
    onCancel,
    kubernetesClusterTemplates,
    kubernetesClusterTemplateActions,
    sizes,
    sizeActions,
    show,
    ...props
}) => {
    const [state, setState] = useState(initialState(kubernetesCluster));
    useEffect(() => { setState(initialState(kubernetesCluster)); }, [kubernetesCluster]);

    const getStateKey = key => state[key] || '';
    const setStateKey = key => value => setState(state => ({ ...state, [key]: value }));
    const setStateKeyFromInputEvent = key => evt => setStateKey(key)(evt.target.value);
    const setStateFromCheckboxEvent = key => evt => setStateKey(key)(evt.target.checked);

    // This state holds the index of the node group that is currently being edited
    const [nodeGroupEditIdx, setNodeGroupEditIdx] = useState(-1);
    const cancelNodeGroupEdit = () => setNodeGroupEditIdx(-1);
    const handleNodeGroupEdit = ngState => {
        const idx = nodeGroupEditIdx;
        setNodeGroupEditIdx(-1);
        setState(state => ({
            ...state,
            node_groups: [
                ...state.node_groups.slice(0, idx),
                ngState,
                ...state.node_groups.slice(idx + 1)
            ]
        }));
    };
    const removeNodeGroup = idx => () => setState(state => ({
        ...state,
        node_groups: [
            ...state.node_groups.slice(0, idx),
            ...state.node_groups.slice(idx + 1)
        ]
    }));

    const workerCount = state.node_groups.map(ng => parseInt(ng.count)).reduce((a, b) => a + b, 0);
    const workerCountMessage = workerCount < 1 ? 'At least one worker node is required.' : '';
    const [showWorkerCountMessage, setShowWorkerCountMessage] = useState(false);
    const workerCountOnInvalid = () => setShowWorkerCountMessage(true);

    const handleCancel = () => {
        setState(initialState(kubernetesCluster));
        setShowWorkerCountMessage(false);
        onCancel();
    };

    const handleSubmit = (evt) => {
        evt.preventDefault();
        setState(initialState(kubernetesCluster));
        setShowWorkerCountMessage(false);
        onSuccess(state);
    };

    return (
        <>
            <Modal backdrop="static" onHide={handleCancel} size="lg" show={show} {...props}>
                <Modal.Header closeButton>
                    <Modal.Title>
                        {kubernetesCluster ?
                            `Update Kubernetes cluster ${kubernetesCluster.name}` :
                            'Create a new Kubernetes cluster'
                        }
                    </Modal.Title>
                </Modal.Header>
                <Form
                    disabled={!kubernetesClusterTemplates.initialised || !sizes.initialised}
                    onSubmit={handleSubmit}
                >
                    <Modal.Body>
                        <Field
                            name="name"
                            label="Cluster name"
                            helpText="Must contain lower-case alphanumeric characters and dash (-) only."
                        >
                            <BSForm.Control
                                type="text"
                                placeholder="Cluster name"
                                required
                                pattern="^[a-z][a-z0-9-]+[a-z0-9]$"
                                autoComplete="off"
                                disabled={kubernetesCluster}
                                value={getStateKey('name')}
                                onChange={setStateKeyFromInputEvent('name')}
                            />
                        </Field>
                        <Field
                            name="template"
                            label="Cluster template"
                            helpText="The template determines the Kubernetes version for the cluster."
                        >
                            <KubernetesClusterTemplateSelectControl
                                resource={kubernetesClusterTemplates}
                                resourceActions={kubernetesClusterTemplateActions}
                                required
                                disabled={kubernetesCluster}
                                value={getStateKey('template')}
                                onChange={setStateKey('template')}
                            />
                        </Field>
                        <Field
                            name="control_plane_size"
                            label="Control Plane Size"
                            helpText="The size to use for the Kubernetes control plane node(s)."
                        >
                            <SizeSelectControl
                                resource={sizes}
                                resourceActions={sizeActions}
                                required
                                value={getStateKey('control_plane_size')}
                                onChange={setStateKey('control_plane_size')}
                            />
                        </Field>
                        <Field
                            name="autohealing_enabled"
                            helpText="If enabled, the cluster will try to remediate unhealthy nodes automatically."
                        >
                            <BSForm.Check
                                label="Enable auto-healing?"
                                checked={getStateKey('autohealing_enabled')}
                                onChange={setStateFromCheckboxEvent('autohealing_enabled')}
                            />
                        </Field>
                        <Card className="mb-3">
                            <Card.Header>Node Groups</Card.Header>
                            {showWorkerCountMessage && workerCountMessage !== '' && (
                                <Card.Body>
                                    <Row xs="auto" className="justify-content-center">
                                        <Col className="text-center">
                                            <Error className="mb-0" message={workerCountMessage} />
                                        </Col>
                                    </Row>
                                </Card.Body>
                            )}
                            <div className="table-responsive mb-0 pb-0">
                                <Table className="mb-0">
                                    <thead>
                                        <tr>
                                            <th className="ps-3">Name</th>
                                            <th className="text-nowrap">Node Size</th>
                                            <th className="text-nowrap">Node Count</th>
                                            <th className="pe-3" style={{ width: "1%" }}></th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {state.node_groups.map((ng, idx) => (
                                            <tr key={idx}>
                                                <td className="ps-3 align-middle">
                                                    {ng.name}
                                                </td>
                                                <td className="align-middle">
                                                    <MachineSizeLink sizes={sizes} sizeId={ng.machine_size} />
                                                </td>
                                                <td className="align-middle">
                                                    {ng.count}
                                                </td>
                                                <td className="pe-3 align-middle" style={{ width: '1%' }}>
                                                    <ButtonGroup>
                                                        <Button
                                                            variant="primary"
                                                            title="Edit node group"
                                                            onClick={() => setNodeGroupEditIdx(idx)}
                                                        >
                                                            <FontAwesomeIcon icon={faEdit} fixedWidth />
                                                        </Button>
                                                        <Button
                                                            variant="danger"
                                                            title="Remove node group"
                                                            onClick={removeNodeGroup(idx)}
                                                            disabled={state.node_groups.length < 2}
                                                        >
                                                            <FontAwesomeIcon icon={faBan} fixedWidth />
                                                        </Button>
                                                    </ButtonGroup>
                                                </td>
                                            </tr>
                                        ))}
                                        {state.node_groups.length === 0 && (
                                            <tr>
                                                <td className="p-3 text-muted text-center" colSpan="4">
                                                    No node groups configured yet.    
                                                </td>
                                            </tr>
                                        )}
                                        <tr>
                                            <td className="px-3 pb-3 border-0 text-center" colSpan="4">
                                                <Button
                                                    variant="success"
                                                    onClick={() => setNodeGroupEditIdx(state.node_groups.length)}
                                                    title="Add node group"
                                                >
                                                    <FontAwesomeIcon
                                                        icon={faPlus}
                                                        className="me-2"
                                                    />
                                                    Add node group
                                                </Button>
                                            </td>
                                        </tr>
                                    </tbody>
                                </Table>
                            </div>
                        </Card>
                        <Card>
                            <Card.Header>Cluster Addons</Card.Header>
                            <Card.Body className="pb-0">
                                <Field
                                    name="cert_manager_enabled"
                                >
                                    <BSForm.Check
                                        label="Enable cert-manager?"
                                        checked={getStateKey('cert_manager_enabled')}
                                        onChange={setStateFromCheckboxEvent('cert_manager_enabled')}
                                    />
                                </Field>
                                <Field
                                    name="dashboard_enabled"
                                >
                                    <BSForm.Check
                                        label="Enable Kubernetes Dashboard?"
                                        checked={getStateKey('dashboard_enabled')}
                                        onChange={setStateFromCheckboxEvent('dashboard_enabled')}
                                    />
                                </Field>
                                <Field
                                    name="ingress_enabled"
                                >
                                    <BSForm.Check
                                        label="Enable Kubernetes Ingress?"
                                        checked={getStateKey('ingress_enabled')}
                                        onChange={setStateFromCheckboxEvent('ingress_enabled')}
                                    />
                                </Field>
                                <Field
                                    name="monitoring_enabled"
                                >
                                    <BSForm.Check
                                        label="Enable cluster monitoring?"
                                        checked={getStateKey('monitoring_enabled')}
                                        onChange={setStateFromCheckboxEvent('monitoring_enabled')}
                                    />
                                </Field>
                                <Field
                                    name="apps_enabled"
                                >
                                    <BSForm.Check
                                        label="Enable applications dashboard?"
                                        checked={getStateKey('apps_enabled')}
                                        onChange={setStateFromCheckboxEvent('apps_enabled')}
                                    />
                                </Field>
                            </Card.Body>
                        </Card>
                    </Modal.Body>
                    <Modal.Footer>
                        <InputWithCustomValidity
                            id="worker_count"
                            tabIndex={-1}
                            autoComplete="off"
                            style={{
                                opacity: 0,
                                width: "100%",
                                height: 0,
                                padding: 0,
                                border: 0,
                                margin: 0,
                                position: "absolute"
                            }}
                            value={workerCount}
                            onChange={() => {/* NOOP */}}
                            onInvalid={workerCountOnInvalid}
                            validationMessage={workerCountMessage}
                        />
                        <Button variant="success" type="submit">
                            {kubernetesCluster ? (
                                <>
                                    <FontAwesomeIcon icon={faSave} className="me-2" />
                                    Update cluster
                                </>
                            ) : (
                                <>
                                    <FontAwesomeIcon icon={faPlus} className="me-2" />
                                    Create cluster
                                </>
                            )}
                        </Button>
                    </Modal.Footer>
                </Form>
            </Modal>
            <NodeGroupModalForm
                show={nodeGroupEditIdx >= 0}
                nodeGroupNames={state.node_groups.filter((_, i) => i !== nodeGroupEditIdx).map(ng => ng.name)}
                nodeGroup={state.node_groups[nodeGroupEditIdx]}
                onSuccess={handleNodeGroupEdit}
                onCancel={cancelNodeGroupEdit}
                sizes={sizes}
                sizeActions={sizeActions}
            />
        </>
    );
};
