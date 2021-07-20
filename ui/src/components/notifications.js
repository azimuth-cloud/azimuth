/**
 * Module containing the React component responsible for rendering notifications.
 */

import React, { useEffect, useState } from 'react';
import ReactDOM from 'react-dom';

import Toast from 'react-bootstrap/Toast';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
    faCheckCircle,
    faExclamationCircle,
    faExclamationTriangle,
    faInfoCircle
} from '@fortawesome/free-solid-svg-icons';


const Icons = {
    info: faInfoCircle,
    success: faCheckCircle,
    warning: faExclamationTriangle,
    danger: faExclamationCircle
};


const Notification = ({ notification, onDismiss }) => {
    const icon = Icons[notification.level];
    const [visible, setVisible] = useState(true);
    const handleClose = () => {
        // Hide the notification to trigger the fade
        setVisible(false);
        // Run the callback once the transition is done
        setTimeout(onDismiss, 1000);
    };
    return (
        <Toast
            className={`border-${notification.level}`}
            animation
            show={visible}
            onClose={handleClose}
            autohide={!!notification.duration}
            delay={notification.duration}
        >
            <Toast.Header className={`text-${notification.level} align-baseline`}>
                <FontAwesomeIcon icon={icon} size="lg" className="me-2" />
                <strong className="me-auto">{notification.title}</strong>
            </Toast.Header>
            <Toast.Body>{notification.message}</Toast.Body>
        </Toast>
    );
};


export const Notifications = ({ notifications, notificationActions }) => {
    // Render using a portal so that we can sit over other elements
    // This creates an element to contain the portal
    const [container] = useState(() => document.createElement('div'));
    // This effect attaches and detaches the portal element to the body when the
    // component is mounted and unmounted
    useEffect(() => {
        document.body.appendChild(container);
        return () => document.body.removeChild(container);
    }, [container]);
    return ReactDOM.createPortal(
        <div className="notifications-container">
            {notifications.map(notification =>
                <Notification
                    key={notification.id}
                    notification={notification}
                    onDismiss={() => notificationActions.remove(notification.id)}
                />
            )}
        </div>,
        container
    );
};
