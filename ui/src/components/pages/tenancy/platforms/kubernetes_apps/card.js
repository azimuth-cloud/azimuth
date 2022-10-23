import React, { useState } from 'react';

import Badge from 'react-bootstrap/Badge';
import Button from 'react-bootstrap/Button';
import Card from 'react-bootstrap/Card';
import Col from 'react-bootstrap/Col';
import Modal from 'react-bootstrap/Modal';
import Row from 'react-bootstrap/Row';
import Table from 'react-bootstrap/Table';

import moment from 'moment';

import get from 'lodash/get';

import ReactMarkdown from 'react-markdown';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
    faCheck,
    faClock,
    faQuestionCircle,
    faSyncAlt,
    faTimesCircle
} from '@fortawesome/free-solid-svg-icons';

import { sortBy } from '../../../../utils';

import { PlatformTypeCard, PlatformServicesListGroup, PlatformDeleteButton } from '../utils';


const Usage = ({ kubernetesApp }) => {
    return (
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
            children={kubernetesApp.usage || "No usage available."}
        />
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


const StatusText = ({ kubernetesApp }) => {
    const styles = statusStyles[kubernetesApp.status];
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
};


const StatusCard = ({ kubernetesApp, kubernetesAppTemplate }) => (
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
                    <td>{kubernetesApp.version}</td>
                </tr>
                <tr>
                    <th>Status</th>
                    <td>
                        <StatusText kubernetesApp={kubernetesApp} />
                    </td>
                </tr>
                <tr>
                    <th>Created</th>
                    <td>{moment(kubernetesApp.created_at).fromNow()}</td>
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


const KubernetesAppDetailsButton = ({
    kubernetesApp,
    kubernetesAppTemplate,
    kubernetesAppActions,
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
                            <Usage kubernetesApp={kubernetesApp} />
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


export const KubernetesAppCard = ({
    kubernetesApp,
    kubernetesAppTemplates,
    kubernetesAppActions
}) => {
    const kubernetesAppTemplate = get(kubernetesAppTemplates.data, kubernetesApp.template.id);
    if( kubernetesAppTemplate ) {
        return (
            <Card className="platform-card">
                <Card.Header>
                    <Badge bg={statusBadgeBg[kubernetesApp.status]}>
                        {kubernetesApp.status.toUpperCase()}
                    </Badge>
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
                    Created {moment(kubernetesApp.created_at).fromNow()}
                </Card.Body>
                <Card.Footer>
                    <KubernetesAppDetailsButton
                        kubernetesApp={kubernetesApp}
                        kubernetesAppTemplate={kubernetesAppTemplate}
                        kubernetesAppActions={kubernetesAppActions}
                    />
                </Card.Footer>
            </Card>
        );
    }
    else {
        return null;
    }
};
