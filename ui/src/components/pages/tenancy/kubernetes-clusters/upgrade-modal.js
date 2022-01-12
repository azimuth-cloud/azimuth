import React, { useState } from 'react';

import Alert from 'react-bootstrap/Alert';
import Button from 'react-bootstrap/Button';
import DropdownItem from 'react-bootstrap/DropdownItem';
import Modal from 'react-bootstrap/Modal';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faArrowAltCircleUp } from '@fortawesome/free-solid-svg-icons';

import { Form, Field } from '../../../utils';

import { KubernetesClusterTemplateSelectControl } from '../resource-utils';


export const UpgradeKubernetesClusterMenuItem = ({
    kubernetesCluster,
    kubernetesClusterActions,
    kubernetesClusterTemplates,
    kubernetesClusterTemplateActions
}) => {
    const [visible, setVisible] = useState(false);
    const open = () => setVisible(true);
    const close = () => setVisible(false);

    const [template, setTemplate] = useState(kubernetesCluster.template.id);
    const reset = () => setTemplate(kubernetesCluster.template.id);

    const handleCancel = () => {
        reset();
        close();
    };

    const handleSubmit = (evt) => {
        evt.preventDefault();
        reset();
        close();
        kubernetesClusterActions.update({ template }, true);
    };

    return (
        <>
            <DropdownItem
                onSelect={open}
                disabled={kubernetesCluster.status.endsWith("ing")}
            >
                Upgrade cluster
            </DropdownItem>
            <Modal size="lg" backdrop="static" onHide={handleCancel} show={visible}>
                <Modal.Header closeButton>
                    <Modal.Title>Upgrade Kubernetes cluster {kubernetesCluster.name}</Modal.Title>
                </Modal.Header>
                <Form onSubmit={handleSubmit}>
                    <Modal.Body>
                        <Alert variant="warning" className="text-center">
                            <p>
                                Upgrading a Kubernetes cluster is a long-running and potentially
                                disruptive operation that may affect workloads running on the cluster.
                            </p>
                            <p className="mb-0">
                                Once started, an upgrade cannot be stopped.
                            </p>
                        </Alert>
                        <Field
                            name="template"
                            label="Cluster template"
                            helpText="The template determines the Kubernetes version for the cluster."
                        >
                            <KubernetesClusterTemplateSelectControl
                                resource={kubernetesClusterTemplates}
                                resourceActions={kubernetesClusterTemplateActions}
                                required
                                value={template}
                                onChange={setTemplate}
                            />
                        </Field>
                    </Modal.Body>
                    <Modal.Footer>
                        <Button variant="success" type="submit">
                            <FontAwesomeIcon icon={faArrowAltCircleUp} className="me-2" />
                            Upgrade cluster
                        </Button>
                    </Modal.Footer>
                </Form>
            </Modal>
        </>
    );
};
