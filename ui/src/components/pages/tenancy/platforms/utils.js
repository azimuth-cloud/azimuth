import React, { useRef, useState } from 'react';

import Button from 'react-bootstrap/Button';
import ButtonGroup from 'react-bootstrap/ButtonGroup';
import Card from 'react-bootstrap/Card';
import Col from 'react-bootstrap/Col';
import Image from 'react-bootstrap/Image';
import ListGroup from 'react-bootstrap/ListGroup';
import Modal from 'react-bootstrap/Modal';
import Overlay from 'react-bootstrap/Overlay';
import OverlayTrigger from 'react-bootstrap/OverlayTrigger';
import Row from 'react-bootstrap/Row';
import Tooltip from 'react-bootstrap/Tooltip';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
    faBell,
    faBookmark,
    faCheck,
    faExclamationTriangle,
    faExternalLinkAlt,
    faPaste,
    faStar,
    faSyncAlt,
    faTrash,
    faRedo
} from '@fortawesome/free-solid-svg-icons';
import {
    faStar as farStar
} from '@fortawesome/free-regular-svg-icons';

import ReactMarkdown from 'react-markdown';

import { DateTime } from 'luxon';


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


const PlatformCardHeaderIcon = ({ icon, tooltip, ...props }) => (
    <OverlayTrigger
        placement="top"
        trigger={["hover", "focus"]}
        rootClose
        overlay={<Tooltip>{tooltip}</Tooltip>}
    >
        <FontAwesomeIcon size="lg" icon={icon} {...props} />
    </OverlayTrigger>
);


export const PlatformCardHeader = ({
    children,
    currentUserIsOwner,
    expiresSoon,
    patchAvailable
}) => (
    <Card.Header>
        <div className="icons">
            <PlatformCardHeaderIcon
                className="me-3"
                icon={currentUserIsOwner ? faStar : farStar}
                tooltip={
                    currentUserIsOwner ?
                        "This platform belongs to you." :
                        "This platform belongs to somebody else."
                }
            />
            {expiresSoon && (
                <PlatformCardHeaderIcon
                    className="icon-expiring me-3"
                    icon={faBell}
                    tooltip="This platform will be deleted soon."
                />
            )}
            {patchAvailable && (
                <PlatformCardHeaderIcon
                    className="icon-patch-available"
                    icon={faRedo}
                    tooltip="An update is available for this platform."
                />
            )}
        </div>
        <div className="status">
            {children}
        </div>
    </Card.Header>
);


const PlatformServiceCopyButton = ({ service }) => {
    const [showCopied, setShowCopied] = useState(false);
    const target = useRef(null);

    const handleCopy = evt => {
        evt.preventDefault();
        evt.stopPropagation();
        navigator.clipboard.writeText(service.fqdn);
        setShowCopied(true);
        setTimeout(() => setShowCopied(false), 1000);
        target.current.blur();
    };

    return (
        <>
            <Button
                ref={target}
                title="Copy service URL to clipboard"
                variant="secondary"
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


const PlatformServiceListItem = ({ service, disabled }) => {
    const buttonRef = useRef(null);

    const openLinkInNewTab = evt => {
        evt.preventDefault();
        evt.stopPropagation();
        window.open(service.url, "_blank").focus();
        buttonRef.current.blur();
    };

    return (
        <ListGroup.Item
            disabled={disabled}
            onClick={openLinkInNewTab}
            className="service-list-group-item"
        >
            <div className="service-list-group-item-icon">
                {service.icon_url ? (
                    <img src={service.icon_url} alt={`${service.label} icon`} />
                ) : (
                    <FontAwesomeIcon icon={faBookmark} />
                )}
            </div>
            <div className="service-list-group-item-label">{service.label}</div>
            <ButtonGroup>
                <PlatformServiceCopyButton service={service} />
                <Button
                    ref={buttonRef}
                    title="Go to service"
                    href={service.url}
                    onClick={openLinkInNewTab}
                >
                    <FontAwesomeIcon icon={faExternalLinkAlt} fixedWidth />
                </Button>
            </ButtonGroup>
        </ListGroup.Item>
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


export const PlatformExpires = ({ schedule }) => {
    const expires = schedule.end_time.toRelative();
    return (
        <OverlayTrigger
            placement="top"
            trigger={["hover", "focus"]}
            rootClose
            overlay={
                <Tooltip className="text-nowrap">
                    {schedule.end_time.toUTC().toISO()}
                </Tooltip>
            }
        >
            {expiresSoon(schedule) ?
                <strong className="text-warning">
                    <FontAwesomeIcon icon={faExclamationTriangle} className="me-2" />
                    {expires}
                </strong> :
                <span>{expires}</span>
            }
        </OverlayTrigger>
    );
};


export const expiresSoon = schedule => {
    const oneDayFromNow = DateTime.now().plus({ days: 1 });
    return schedule.end_time < oneDayFromNow;
};
