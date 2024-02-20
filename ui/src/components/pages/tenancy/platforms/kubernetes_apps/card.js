import React, { useState } from 'react';

import Badge from 'react-bootstrap/Badge';
import Button from 'react-bootstrap/Button';
import Card from 'react-bootstrap/Card';
import Col from 'react-bootstrap/Col';
import Modal from 'react-bootstrap/Modal';
import OverlayTrigger from 'react-bootstrap/OverlayTrigger';
import Row from 'react-bootstrap/Row';
import Table from 'react-bootstrap/Table';
import Tooltip from 'react-bootstrap/Tooltip';

import get from 'lodash/get';

import ReactMarkdown from 'react-markdown';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
    faCheck,
    faClock,
    faExclamationCircle,
    faExclamationTriangle,
    faPen,
    faQuestionCircle,
    faSyncAlt,
    faTimesCircle
} from '@fortawesome/free-solid-svg-icons';

import { sortBy } from '../../../../utils';
import sadFace from "../../../../../../assets/face-frown-regular.svg";

import { PlatformTypeCard, PlatformServicesListGroup, PlatformDeleteButton } from '../utils';

import { KubernetesAppModalForm } from './form';


// Minimal object structure required to render the UI card
// (used when app is deployed then app template access is restricted)
const kubernetesAppTemplatePlaceholder = {
    logo: sadFace,
    label: "App type unavailable",
    description: "",
    versions: [{
        name: "deprecated"
    }],
    // Used to detect when placeholder is in use 
    // to allow disabling buttons etc.
    placeholder: true,
}


const Usage = ({ kubernetesApp }) => {
    return (
        kubernetesApp.usage ? (
            <ReactMarkdown
                components={{
                    // Limit the headings to levels 5 and 6
                    h1: 'h5',
                    h2: 'h6',
                    h3: 'h6',
                    h4: 'h6',
                    h5: 'h6',
                    h6: 'h6',
                    // Links should open in a new tab
                    a: ({ node, children, ...props }) => (
                        <a target="_blank" {...props}>{children}</a>
                    )
                }}
                children={kubernetesApp.usage}
            />
        ) : (
            <Row className="justify-content-center text-muted">
                <Col xs="auto py-5">
                    App did not provide any details.
                </Col>
            </Row>
        )
    );
};


const statusStyles = {
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
};


const VersionText = ({ kubernetesAppTemplate, kubernetesApp }) => {
    // Indicate if the deployed version is unsupported or updates are available
    const version = kubernetesAppTemplate.versions.find(v => v.name === kubernetesApp.version);
    const versionIsLatest = (
        version &&
        version.name === kubernetesAppTemplate.versions[0].name
    );
    return versionIsLatest ?
        kubernetesApp.version :
        <OverlayTrigger
            placement="top"
            overlay={
                <Tooltip>
                    {
                        version ?
                            "An upgrade is available." :
                            "This version is no longer supported."
                    }
                </Tooltip>
            }
            trigger="click"
            rootClose
        >
            <Button
                variant="link"
                className={`fw-bold text-decoration-none text-${version ? "warning" : "danger"}`}
            >
                <FontAwesomeIcon
                    icon={version ? faExclamationTriangle : faExclamationCircle}
                    className="me-2"
                />
                {kubernetesApp.version}
            </Button>
        </OverlayTrigger>;
};


const StatusText = ({ kubernetesApp }) => {
    const [errorVisible, setErrorVisible] = useState(false);
    const openError = () => setErrorVisible(true);
    const closeError = () => setErrorVisible(false);

    const styles = statusStyles[kubernetesApp.status];

    if( kubernetesApp.status === "Failed" && kubernetesApp.failure_message ) {
        return (
            <>
                <Button
                    variant="link"
                    className={`fw-bold ${styles.className} text-decoration-none`}
                    onClick={openError}
                >
                    <FontAwesomeIcon
                        icon={styles.icon}
                        spin={styles.spin}
                        className="me-2"
                    />
                    {kubernetesApp.status}
                </Button>
                <Modal size="xl" show={errorVisible} backdrop="static" onHide={closeError}>
                    <Modal.Header closeButton>
                        <Modal.Title>Error message</Modal.Title>
                    </Modal.Header>
                    <Modal.Body>
                        <pre>
                            {kubernetesApp.failure_message}
                        </pre>
                    </Modal.Body>
                    <Modal.Footer>
                        <Button variant="secondary" onClick={closeError}>
                            Close
                        </Button>
                    </Modal.Footer>
                </Modal>
            </>
        );
    }
    else {
        return (
            <span className={`fw-bold ${styles.className}`}>
                <FontAwesomeIcon
                    icon={styles.icon}
                    spin={styles.spin}
                    className="me-2"
                />
                {kubernetesApp.status}
            </span>
        );
    }
};


const StatusCard = ({ kubernetesAppTemplate, kubernetesApp }) => (
    <Card className="mb-3">
        <Card.Header className="text-center">App status</Card.Header>
        <Table borderless className="details-table">
            <tbody>
                <tr>
                    <th>Name</th>
                    <td>{kubernetesApp.name}</td>
                </tr>
                <tr>
                    <th>Kubernetes cluster</th>
                    <td>{kubernetesApp.kubernetes_cluster.id}</td>
                </tr>
                <tr>
                    <th>Template</th>
                    <td>{kubernetesAppTemplate.label}</td>
                </tr>
                <tr>
                    <th>Version</th>
                    <td>
                        <VersionText
                            kubernetesAppTemplate={kubernetesAppTemplate}
                            kubernetesApp={kubernetesApp}
                        />
                    </td>
                </tr>
                <tr>
                    <th>Status</th>
                    <td>
                        <StatusText kubernetesApp={kubernetesApp} />
                    </td>
                </tr>
                <tr>
                    <th>Created</th>
                    <td>{kubernetesApp.created_at.toRelative()}</td>
                </tr>
            </tbody>
        </Table>
    </Card>
);


const ServicesCard = ({ kubernetesApp }) => (
    <Card className="mb-3">
        <Card.Header className="text-center">Services</Card.Header>
        {kubernetesApp.services.length > 0 ? (
            <PlatformServicesListGroup
                services={sortBy(kubernetesApp.services, s => s.label)}
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


const KubernetesAppUpdateButton = ({
    kubernetesApp,
    tenancy,
    tenancyActions,
    disabled,
    onSubmit,
    ...props
}) => {
    const [visible, setVisible] = useState(false);
    const open = () => setVisible(true);
    const close = () => setVisible(false);

    const kubernetesAppTemplate = get(
        tenancy.kubernetesAppTemplates.data,
        kubernetesApp.template.id,
        kubernetesAppTemplatePlaceholder,
    );

    const handleSubmit = data => {
        onSubmit({ version: data.version, values: data.values });
        close();
    };

    return (
        <>
            <Button
                {...props}
                variant="secondary"
                onClick={open}
                disabled={disabled || !kubernetesAppTemplate}
            >
                <FontAwesomeIcon
                    icon={!!kubernetesApp.updating ? faSyncAlt : faPen}
                    spin={!!kubernetesApp.updating}
                    className="me-2"
                />
                {!!kubernetesApp.updating ? 'Updating...' : 'Update'}
            </Button>
            {kubernetesAppTemplate && (
                <KubernetesAppModalForm
                    show={visible}
                    kubernetesAppTemplate={kubernetesAppTemplate}
                    kubernetesApp={kubernetesApp}
                    onSubmit={handleSubmit}
                    onCancel={close}
                    tenancy={tenancy}
                    tenancyActions={tenancyActions}
                />
            )}
        </>
    );
};


const KubernetesAppDetailsButton = ({
    kubernetesApp,
    kubernetesAppTemplate,
    kubernetesAppActions,
    tenancy,
    tenancyActions,
    ...props
}) => {
    const [visible, setVisible] = useState(false);
    const open = () => setVisible(true);
    const close = () => setVisible(false);

    const inFlight = !!kubernetesApp.updating || !!kubernetesApp.deleting;
    const working = kubernetesApp.status.endsWith("ing");

    return (
        <>
            <Button {...props} onClick={open}>
                Details
            </Button>
            <Modal size="xl" backdrop="static" onHide={close} show={visible}>
                <Modal.Header closeButton>
                    <Modal.Title>Platform details for {kubernetesApp.name}</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <Row className="justify-content-end mb-2">
                        <Col xs="auto">
                            <Button
                                variant="primary"
                                disabled={kubernetesApp.fetching}
                                onClick={kubernetesAppActions.fetchOne}
                                title="Refresh"
                                className="me-2"
                            >
                                <FontAwesomeIcon
                                    icon={faSyncAlt}
                                    spin={kubernetesApp.fetching}
                                    className="me-2"
                                />
                                Refresh
                            </Button>
                            <KubernetesAppUpdateButton
                                kubernetesApp={kubernetesApp}
                                tenancy={tenancy}
                                tenancyActions={tenancyActions}
                                disabled={inFlight || working || kubernetesAppTemplate.placeholder}
                                onSubmit={kubernetesAppActions.update}
                                className="me-2"
                            />
                            <PlatformDeleteButton
                                name={kubernetesApp.name}
                                inFlight={!!kubernetesApp.deleting}
                                disabled={inFlight || kubernetesApp.status === "Uninstalling"}
                                onConfirm={kubernetesAppActions.delete}
                            />
                        </Col>
                    </Row>
                    <Row>
                        <Col xl={7}>
                            <PlatformTypeCard
                                platformType={{
                                    name: kubernetesAppTemplate.label,
                                    logo: kubernetesAppTemplate.logo,
                                    description: kubernetesAppTemplate.description
                                }}
                            />
                            {!kubernetesAppTemplate.placeholder && <Usage kubernetesApp={kubernetesApp} />}
                        </Col>
                        <Col xl={5}>
                            <StatusCard
                                kubernetesApp={kubernetesApp}
                                kubernetesAppTemplate={kubernetesAppTemplate}
                            />
                            <ServicesCard kubernetesApp={kubernetesApp} />
                        </Col>
                    </Row>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={close}>
                        Close
                    </Button>
                </Modal.Footer>
            </Modal>
        </>
    );
};


const statusBadgeBg = {
    "Unknown": "secondary",
    "Pending": "secondary",
    "Preparing": "secondary",
    "Deployed": "success",
    "Failed": "danger",
    "Installing": "primary",
    "Upgrading": "primary",
    "Uninstalling": "primary",
};


const StatusBadge = ({ kubernetesAppTemplate, kubernetesApp }) => {
    // Indicate if the deployed version is unsupported or updates are available
    const version = kubernetesAppTemplate.versions.find(v => v.name === kubernetesApp.version);
    const versionIsLatest = (
        version &&
        version.name === kubernetesAppTemplate.versions[0].name
    );
    let statusText = kubernetesApp.status, statusBg = statusBadgeBg[kubernetesApp.status];
    if( kubernetesApp.status === "Deployed" ) {
        if( !version ) {
            statusText = "Unsupported";
            statusBg = "danger";
        }
        else if( !versionIsLatest ) {
            statusText = "Upgrade available";
            statusBg = "warning";
        }
    }
    return <Badge bg={statusBg}>{statusText.toUpperCase()}</Badge>;
};


export const KubernetesAppCard = ({
    kubernetesApp,
    kubernetesAppTemplates,
    kubernetesAppActions,
    tenancy,
    tenancyActions
}) => {
    const kubernetesAppTemplate = get(kubernetesAppTemplates.data, kubernetesApp.template.id, kubernetesAppTemplatePlaceholder);
    if( kubernetesAppTemplate ) {
        return (
            <Card className="platform-card">
                <Card.Header>
                    <StatusBadge
                        kubernetesAppTemplate={kubernetesAppTemplate}
                        kubernetesApp={kubernetesApp}
                    />
                </Card.Header>
                <Card.Img src={kubernetesAppTemplate.logo} />
                <Card.Body>
                    <Card.Title>{kubernetesApp.name}</Card.Title>
                    <Card.Subtitle>{kubernetesAppTemplate.label}</Card.Subtitle>
                </Card.Body>
                {kubernetesApp.services.length > 0 && (
                    <PlatformServicesListGroup
                        services={sortBy(kubernetesApp.services, s => s.label)}
                    />
                )}
                <Card.Body className="small text-muted">
                    Created {kubernetesApp.created_at.toRelative()}
                </Card.Body>
                <Card.Footer>
                    <KubernetesAppDetailsButton
                        kubernetesApp={kubernetesApp}
                        kubernetesAppTemplate={kubernetesAppTemplate}
                        kubernetesAppActions={kubernetesAppActions}
                        tenancy={tenancy}
                        tenancyActions={tenancyActions}
                    />
                </Card.Footer>
            </Card>
        );
    }
    else {
        return null;
    }
};
