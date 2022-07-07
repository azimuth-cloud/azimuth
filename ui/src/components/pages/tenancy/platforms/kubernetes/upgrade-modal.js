import React, { useEffect, useState } from 'react';

import Alert from 'react-bootstrap/Alert';
import Button from 'react-bootstrap/Button';
import Modal from 'react-bootstrap/Modal';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
    faArrowAltCircleUp,
    faShieldAlt,
    faSyncAlt
} from '@fortawesome/free-solid-svg-icons';

import { Form, Field } from '../../../../utils';

import { KubernetesClusterTemplateSelectControl } from '../../resource-utils';


export const UpgradeKubernetesClusterButton = ({
    kubernetesCluster,
    kubernetesClusterActions,
    kubernetesClusterTemplates,
    kubernetesClusterTemplateActions,
    disabled,
    ...props
}) => {
    const [visible, setVisible] = useState(false);
    const open = () => setVisible(true);
    const close = () => setVisible(false);

    const [template, setTemplate] = useState(kubernetesCluster.template.id);
    const reset = () => setTemplate(kubernetesCluster.template.id);

    const [inFlight, setInFlight] = useState(false);
    useEffect(
        () => { if( inFlight && !kubernetesCluster.updating ) setInFlight(false); },
        [!!kubernetesCluster.updating]
    );

    const handleSubmit = (evt) => {
        evt.preventDefault();
        kubernetesClusterActions.update({ template }, true);
        setInFlight(true);
        close();
    };

    return (
        <>
            <Button {...props} variant="warning" disabled={disabled} onClick={open}>
                <FontAwesomeIcon
                    icon={inFlight ? faSyncAlt : faShieldAlt}
                    spin={inFlight}
                    className="me-2"
                />
                {inFlight ? 'Upgrading...' : 'Upgrade'}
            </Button>
            <Modal size="lg" backdrop="static" onHide={close} onExited={reset} show={visible}>
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
