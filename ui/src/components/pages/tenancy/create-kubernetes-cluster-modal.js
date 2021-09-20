/**
 * This module contains the modal dialog for machine creation.
 */

import React, { useState } from 'react';

import Button from 'react-bootstrap/Button';
import Col from 'react-bootstrap/Col';
import BSForm from 'react-bootstrap/Form';
import Modal from 'react-bootstrap/Modal';
import Row from 'react-bootstrap/Row';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faPlus, faSitemap, faSyncAlt } from '@fortawesome/free-solid-svg-icons';

import { Form, Field } from '../../utils';
import { ConnectedSSHKeyRequiredModal } from '../../ssh-key-update-modal';

import {
    KubernetesClusterTemplateSelectControl,
    SizeSelectControl
} from './resource-utils';


// We only need to populate defaults where the empty string is not suitable
const initialState = {
    'auto_scaling_enabled': false,
};


const CreateKubernetesClusterModal = ({
    onSuccess,
    onCancel,
    creating,
    create,
    kubernetesClusterTemplates,
    kubernetesClusterTemplateActions,
    sizes,
    sizeActions,
    ...props
}) => {
    const [state, setState] = useState(initialState);
    const getStateKey = key => state[key] || '';
    const setStateKey = key => value => setState(state => ({ ...state, [key]: value }));
    const setStateKeyFromInputEvent = key => evt => setStateKey(key)(evt.target.value);
    const setStateFromCheckboxEvent = key => evt => setStateKey(key)(evt.target.checked);
    const reset = () => setState(initialState);

    const handleClose = () => {
        reset();
        onCancel();
    };
    
    const handleSubmit = (evt) => {
        evt.preventDefault();
        create(state);
        reset();
        onSuccess();
    };

    return (
        <Modal backdrop="static" onHide={handleClose} size="lg" {...props}>
            <Modal.Header closeButton>
                <Modal.Title>Create a new Kubernetes cluster</Modal.Title>
            </Modal.Header>
            <Form
                disabled={!kubernetesClusterTemplates.initialised || !sizes.initialised}
                onSubmit={handleSubmit}
            >
                <Modal.Body>
                    <Field
                        name="name"
                        label="Cluster name"
                        helpText="Must contain alphanumeric characters and dash (-) only."
                    >
                        <BSForm.Control
                            type="text"
                            placeholder="Cluster name"
                            required
                            pattern="[A-Za-z0-9\-]+"
                            title="Must contain alphanumeric characters and dash (-) only."
                            autoComplete="off"
                            value={getStateKey('name')}
                            onChange={setStateKeyFromInputEvent('name')}
                        />
                    </Field>
                    <Field name="template" label="Cluster template">
                        <KubernetesClusterTemplateSelectControl
                            resource={kubernetesClusterTemplates}
                            resourceActions={kubernetesClusterTemplateActions}
                            required
                            value={getStateKey('template_id')}
                            onChange={setStateKey('template_id')}
                        />
                    </Field>
                    <Row xs={1} lg={2}>
                        <Col>
                            <Field
                                name="master_size_id"
                                label="Master Size"
                                helpText="The size to use for the Kubernetes master."
                            >
                                <SizeSelectControl
                                    resource={sizes}
                                    resourceActions={sizeActions}
                                    required
                                    value={getStateKey('master_size_id')}
                                    onChange={setStateKey('master_size_id')}
                                />
                            </Field>
                        </Col>
                        <Col>
                            <Field
                                name="worker_size_id"
                                label="Worker Size"
                                helpText="The size to use for the Kubernetes workers."
                            >
                                <SizeSelectControl
                                    resource={sizes}
                                    resourceActions={sizeActions}
                                    required
                                    value={getStateKey('worker_size_id')}
                                    onChange={setStateKey('worker_size_id')}
                                />
                            </Field>
                        </Col>
                    </Row>
                    <Field name="auto_scaling_enabled">
                        <BSForm.Check
                            label="Enable auto-scaling for cluster workers?"
                            checked={getStateKey('auto_scaling_enabled')}
                            onChange={setStateFromCheckboxEvent('auto_scaling_enabled')}
                        />
                    </Field>
                    {getStateKey('auto_scaling_enabled') ? (
                        <Row>
                            <Col>
                                <Field
                                    name="min_worker_count"
                                    label="Min worker count"
                                    helpText="The minimum number of workers in the cluster."
                                >
                                    <BSForm.Control
                                        placeholder="Min worker count"
                                        type="number"
                                        required
                                        min="1"
                                        step="1"
                                        value={getStateKey('min_worker_count')}
                                        onChange={setStateKeyFromInputEvent('min_worker_count')}
                                    />
                                </Field>
                            </Col>
                            <Col>
                                <Field
                                    name="max_worker_count"
                                    label="Max worker count"
                                    helpText="The maximum number of workers in the cluster."
                                >
                                    <BSForm.Control
                                        placeholder="Max worker count"
                                        type="number"
                                        required
                                        min="1"
                                        step="1"
                                        value={getStateKey('max_worker_count')}
                                        onChange={setStateKeyFromInputEvent('max_worker_count')}
                                    />
                                </Field>
                            </Col>
                        </Row>
                    ) : (
                        <Field
                            name="worker_count"
                            label="Worker count"
                            helpText="The number of workers in the cluster."
                        >
                            <BSForm.Control
                                placeholder="Worker count"
                                type="number"
                                required
                                min="1"
                                step="1"
                                value={getStateKey('worker_count')}
                                onChange={setStateKeyFromInputEvent('worker_count')}
                            />
                        </Field>
                    )}
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="success" type="submit">
                        <FontAwesomeIcon icon={faPlus} className="me-2" />
                        Create cluster
                    </Button>
                </Modal.Footer>
            </Form>
        </Modal>
    );
};


export const CreateKubernetesClusterButton = ({ sshKey, disabled, creating, ...props }) => {
    const [visible, setVisible] = useState(false);
    const open = () => setVisible(true);
    const close = () => setVisible(false);
    return (
        <>
            <Button
                variant="success"
                disabled={sshKey.fetching || disabled || creating}
                onClick={open}
                title="Create a new cluster"
            >
                <FontAwesomeIcon
                    icon={creating ? faSyncAlt : faSitemap}
                    spin={creating}
                    className="me-2"
                />
                {creating ? 'Creating cluster...' : 'New cluster'}
            </Button>
            <ConnectedSSHKeyRequiredModal
                show={visible}
                onSuccess={close}
                onCancel={close}
                showWarning={true}
            >
                <CreateKubernetesClusterModal creating={creating} {...props} />
            </ConnectedSSHKeyRequiredModal>
        </>
    );
};
