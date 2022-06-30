import React, { useState } from 'react';

import Button from 'react-bootstrap/Button';
import Card from 'react-bootstrap/Card';
import Col from 'react-bootstrap/Col';
import Image from 'react-bootstrap/Image';
import ListGroup from 'react-bootstrap/ListGroup';
import Modal from 'react-bootstrap/Modal';
import Row from 'react-bootstrap/Row';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
    faBookmark,
    faExternalLinkAlt,
    faSyncAlt,
    faTrash
} from '@fortawesome/free-solid-svg-icons';

import ReactMarkdown from 'react-markdown';

import { sortBy } from '../../../utils';


export const PlatformTypeCard = ({ platformType }) => (
    <Card className="platform-type-card">
        <Card.Body>
            <Row>
                <Col xs="auto">
                    <Image src={platformType.logo} />
                </Col>
                <Col>
                    <Card.Title>{platformType.name}</Card.Title>
                    <ReactMarkdown children={platformType.description} />
                </Col>
            </Row>
        </Card.Body>
    </Card>
);


export const PlatformServicesListGroup = ({ services, disabled }) => {
    const sortedServices = sortBy(services, service => service.label);
    return (
        <ListGroup variant="flush" activeKey={null}>
            {sortedServices.map(service => (
                <ListGroup.Item
                    key={service.name}
                    action
                    href={service.url}
                    disabled={disabled}
                    target="_blank"
                    className="service-list-group-item"
                >
                    <span>
                        {service.icon_url ? (
                            <img src={service.icon_url} alt={`${service.label} icon`} />
                        ) : (
                            <FontAwesomeIcon icon={faBookmark} />
                        )}
                    </span>
                    <span>{service.label}</span>
                    <span><FontAwesomeIcon icon={faExternalLinkAlt} /></span>
                </ListGroup.Item>
            ))}
        </ListGroup>
    );
};


export const PlatformDeleteButton = ({ name, inFlight, disabled, onConfirm, ...props }) => {
    const [visible, setVisible] = useState(false);

    const open = () => setVisible(true);
    const close = () => setVisible(false);
    const handleConfirm = () => { onConfirm(); close(); };

    return (
        <>
            <Button {...props} variant="danger" disabled={disabled} onClick={open}>
                <FontAwesomeIcon
                    icon={inFlight ? faSyncAlt : faTrash}
                    spin={inFlight}
                    className="me-2"
                />
                {inFlight ? 'Deleting...' : 'Delete'}
            </Button>
            <Modal show={visible} backdrop="static" keyboard={false}>
                <Modal.Body>
                    <p>Are you sure you want to delete {name}?</p>
                    <p><strong>Once deleted, a platform cannot be restored.</strong></p>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={close}>Cancel</Button>
                    <Button variant="danger" onClick={handleConfirm}>
                        Delete platform
                    </Button>
                </Modal.Footer>
            </Modal>
        </>
    );
};
