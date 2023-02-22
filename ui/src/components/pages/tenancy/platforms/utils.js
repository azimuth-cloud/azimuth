import React, { useRef, useState } from 'react';

import Button from 'react-bootstrap/Button';
import Card from 'react-bootstrap/Card';
import Col from 'react-bootstrap/Col';
import FormControl from 'react-bootstrap/FormControl';
import FormGroup from 'react-bootstrap/FormGroup';
import FormText from 'react-bootstrap/FormText';
import Image from 'react-bootstrap/Image';
import InputGroup from 'react-bootstrap/InputGroup';
import ListGroup from 'react-bootstrap/ListGroup';
import Modal from 'react-bootstrap/Modal';
import Overlay from 'react-bootstrap/Overlay';
import Popover from 'react-bootstrap/Popover';
import Row from 'react-bootstrap/Row';
import Tooltip from 'react-bootstrap/Tooltip';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
    faBookmark,
    faCheck,
    faCopy,
    faExternalLinkAlt,
    faPaste,
    faSyncAlt,
    faTrash
} from '@fortawesome/free-solid-svg-icons';

import ReactMarkdown from 'react-markdown';


export const PlatformTypeCard = ({ platformType }) => (
    <Card className="platform-type-card">
        <Card.Body>
            <Row>
                <Col xs="auto">
                    <Image src={platformType.logo} />
                </Col>
                <Col>
                    <Card.Title>{platformType.name}</Card.Title>
                    <ReactMarkdown
                        components={{
                            // Links should open in a new tab
                            a: ({ node, children, ...props }) => (
                                <a target="_blank" {...props}>{children}</a>
                            )
                        }}
                        children={platformType.description}
                    />
                </Col>
            </Row>
        </Card.Body>
    </Card>
);


const PlatformServiceCopyLinkButton = ({ service }) => {
    const [showCopied, setShowCopied] = useState(false);
    const target = useRef(null);

    const handleCopy = () => {
        navigator.clipboard.writeText(service.fqdn);
        setShowCopied(true);
        setTimeout(() => setShowCopied(false), 3000);
    };

    return (
        <>
            <Button
                ref={target}
                title="Copy to clipboard"
                variant="secondary"
                className="service-popover-copy-btn"
                onClick={handleCopy}
            >
                <FontAwesomeIcon icon={showCopied ? faCheck : faPaste} fixedWidth />
            </Button>
            <Overlay
                target={target.current}
                show={showCopied}
                placement="top"
            >
                <Tooltip>Copied!</Tooltip>
            </Overlay>
        </>
    );
};


const PlatformServicePopover = React.forwardRef(
    ({ service, onLinkFollowed, ...props }, ref) => (
        <Popover ref={ref} {...props} className="service-popover">
            <Popover.Header>{service.label}</Popover.Header>
            <Popover.Body>
                <FormGroup>
                    <InputGroup>
                        <FormControl
                            aria-label={`${service.label} FQDN`}
                            disabled
                            value={service.fqdn}
                        />
                        <PlatformServiceCopyLinkButton service={service} />
                        <Button
                            title="Go to service"
                            variant="info"
                            href={service.url}
                            target="_blank"
                            onClick={onLinkFollowed}
                        >
                            <FontAwesomeIcon icon={faExternalLinkAlt} fixedWidth />
                        </Button>
                    </InputGroup>
                    <FormText>
                        The URL for the service.<br />
                        You can either visit the service directly or copy the URL to share with others.
                    </FormText>
                </FormGroup>
            </Popover.Body>
        </Popover>
    )
);


const PlatformServiceListItem = ({ service, disabled }) => {
    const [showPopover, setShowPopover] = useState(false);
    const target = useRef(null);

    return (
        <>
            <ListGroup.Item
                ref={target}
                action
                disabled={disabled}
                className="service-list-group-item"
                onClick={() => setShowPopover(!showPopover)}
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
            <Overlay
                target={target.current}
                show={showPopover}
                placement="top"
                rootClose
                onHide={() => setShowPopover(false)}
            >
                <PlatformServicePopover
                    service={service}
                    onLinkFollowed={() => setShowPopover(false)}
                />
            </Overlay>
        </>
    );
};


export const PlatformServicesListGroup = ({ services, disabled }) => (
    <ListGroup variant="flush" activeKey={null}>
        {services.map(service => (
            <PlatformServiceListItem
                key={service.name}
                service={service}
                disabled={disabled}
            />
        ))}
    </ListGroup>
);


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
