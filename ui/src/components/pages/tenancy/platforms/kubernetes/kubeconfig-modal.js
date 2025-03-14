import React, { useState } from 'react';

import Alert from 'react-bootstrap/Alert';
import Button from 'react-bootstrap/Button';
import Col from 'react-bootstrap/Col';
import Modal from 'react-bootstrap/Modal';
import Row from 'react-bootstrap/Row';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
    faCloudDownloadAlt,
    faPaste,
    faSyncAlt,
    faUser
} from '@fortawesome/free-solid-svg-icons';
 
import { Error, Loading } from '../../../../utils';


export const KubeconfigButton = ({ kubernetesCluster, kubernetesClusterActions, ...props }) => {
    const [visible, setVisible] = useState(false);
    const open = () => setVisible(true);
    const close = () => setVisible(false);

    const generateKubeconfig = () => {
        if( !kubernetesCluster.generatingKubeconfig && !kubernetesCluster.kubeconfig ) {
            kubernetesClusterActions.generateKubeconfig();
        }
    };

    // Make a download URI for the kubeconfig if present
    const downloadURI = kubernetesCluster.kubeconfig ?
        `data:text/plain;charset=utf-8,${encodeURIComponent(kubernetesCluster.kubeconfig)}` :
        null;

    let kubeconfigComponent = null;
    if( kubernetesCluster.generatingKubeconfig ) {
        kubeconfigComponent = (
            <Row className="justify-content-center">
                <Col xs="auto py-5">
                    <Loading message="Generating kubeconfig..." size="lg" />
                </Col>
            </Row>
        );
    }
    else if( kubernetesCluster.kubeconfig ) {
        kubeconfigComponent = (
            <Row>
                <Col>
                    <pre>{kubernetesCluster.kubeconfig}</pre>
                </Col>
            </Row>
        );
    }
    else if( kubernetesCluster.kubeconfigError ) {
        kubeconfigComponent = (
            <Row className="justify-content-center">
                <Col xs="auto">
                    <Error message={kubernetesCluster.kubeconfigError.message} />
                </Col>
            </Row>
        );
    }
 
    return (
        <>
            <Button onClick={open} variant="secondary" {...props}>
                <FontAwesomeIcon icon={faUser} className="me-2" />
                Kubeconfig
            </Button>
            <Modal
                size="lg"
                backdrop="static"
                onEntering={generateKubeconfig}
                onHide={close}
                show={visible}
            >
                <Modal.Header closeButton>
                    <Modal.Title>Kubeconfig for {kubernetesCluster.name}</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <Row className="justify-content-end mb-3">
                        <Col xs="auto">
                            <Button
                                variant="primary"
                                className="me-2"
                                disabled={
                                    kubernetesCluster.generatingKubeconfig ||
                                    !kubernetesCluster.kubeconfig
                                }
                                onClick={() => navigator.clipboard.writeText(kubernetesCluster.kubeconfig)}
                            >
                                <FontAwesomeIcon icon={faPaste} className="me-2" />
                                Copy to clipboard
                            </Button>
                            <a
                                className={[
                                    "btn btn-primary",
                                    kubernetesCluster.generatingKubeconfig || !downloadURI ? 'disabled' : '',
                                    "me-2"
                                ].join(" ")}
                                href={downloadURI}
                                download={`${kubernetesCluster.name}-kubeconfig.yaml`}
                                role="button"
                            >
                                <FontAwesomeIcon icon={faCloudDownloadAlt} className="me-2" />
                                Download
                            </a>
                            <Button
                                variant="primary"
                                disabled={kubernetesCluster.generatingKubeconfig}
                                onClick={kubernetesClusterActions.generateKubeconfig}
                            >
                                <FontAwesomeIcon
                                    icon={faSyncAlt}
                                    spin={kubernetesCluster.generatingKubeconfig}
                                    className="me-2"
                                />
                                Regenerate
                            </Button>
                        </Col>
                    </Row>
                    <Row>
                        <Col>
                            <Alert variant="info">
                                <p>
                                    Use this configuration file with the{" "}
                                    <a href="https://kubernetes.io/docs/tasks/tools/#kubectl" target="_blank">kubectl</a>{" "}
                                    command-line tool to access your cluster.
                                </p>
                                <p className="mb-0">
                                    In order to use this configuration file you must have the{" "}
                                    <a href="https://github.com/int128/kubelogin" target="_blank">oidc-login</a>{" "}
                                    plugin installed.
                                </p>
                            </Alert>
                        </Col>
                    </Row>
                    {kubeconfigComponent}
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="primary" onClick={close}>Close</Button>
                </Modal.Footer>
            </Modal>
        </>
    );
};
