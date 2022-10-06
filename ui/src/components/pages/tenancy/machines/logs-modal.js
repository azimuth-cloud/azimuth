/**
 * This module contains the React component for the machine logs modal.
 */

import React, { useEffect, useRef, useState } from 'react';

import Alert from 'react-bootstrap/Alert';
import Button from 'react-bootstrap/Button';
import Col from 'react-bootstrap/Col';
import DropdownItem from 'react-bootstrap/DropdownItem';
import Modal from 'react-bootstrap/Modal';
import Row from 'react-bootstrap/Row';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faArrowDown, faCircleNotch, faSyncAlt } from '@fortawesome/free-solid-svg-icons';
 
import { Error, Loading } from '../../../utils';


export const MachineLogsMenuItem = ({ machine, machineActions, ...props }) => {
    const [visible, setVisible] = useState(false);
    const [following, setFollowing] = useState(false);
    const open = () => setVisible(true);
    const close = () => { setVisible(false); setFollowing(false); };

    // When the modal opens, refresh the logs even if they are already loaded
    useEffect(
        () => { if(visible && !machine.fetchingLogs) machineActions.fetchLogs(); },
        [visible]
    );

    // In order to scroll to the bottom of the pre, we need a reference to the DOM element
    const preRef = useRef(null);
    // In order to be able to cancel the scroll to bottom animation, we need to maintain
    // a reference to the current animation frame request
    const requestRef = useRef(null);
    // Animates scrolling closer to the bottom of the pre until the animation is cancelled
    const animateScroll = () => {
        // Work out how far there is still to scroll to the bottom
        const scrollCurrent = preRef.current.scrollTop;
        const scrollTarget = preRef.current.scrollHeight - preRef.current.clientHeight;
        const scrollRemaining = scrollTarget - scrollCurrent;
        if( scrollRemaining > 0 ) {
            // The further there is left to scroll, the further we scroll in each frame
            // To avoid scrolling *really* fast, and to make sure we eventually get to
            // zero, we clamp the number
            const scrollIncrement = Math.min(Math.max(scrollRemaining * 0.1, 5), 200);
            preRef.current.scrollTo(
                preRef.current.scrollLeft,
                Math.min(scrollCurrent + scrollIncrement, scrollTarget)
            );
        }
        // Request the next animation frame
        requestRef.current = requestAnimationFrame(animateScroll);
    };

    // When the user starts following, we want to begin the scroll-to-bottom animation
    // and stop it when they finish
    useEffect(
        () => {
            if( !following ) return;
            requestRef.current = requestAnimationFrame(animateScroll);
            return () => cancelAnimationFrame(requestRef.current);
        },
        [following]
    );
    
    // When the user begins following we also want to start repeated fetches of the logs
    // and cancel them when they stop
    useEffect(
        () => {
            // If transitioning into a fetching state, or not following, there is nothing to do
            if( !following || machine.fetchingLogs ) return;
            // If transitioning to a non-fetching state, set a timeout to fetch the logs again
            const timerId = setTimeout(() => machineActions.fetchLogs(), 3000);
            return () => clearTimeout(timerId);
        },
        [following, machine.fetchingLogs]
    );

    let logsComponent = null;
    if( machine.logs ) {
        logsComponent = (
            <>
                {machine.fetchLogsError && (
                    <Row>
                        <Col>
                            <Error message={machine.fetchLogsError.message} className="mb-0" />
                        </Col>
                    </Row>
                )}
                <Row>
                    <Col>
                        <pre ref={preRef}>{machine.logs.join('\n')}</pre>
                    </Col>
                </Row>
            </>
        );
    }
    else if( machine.fetchingLogs ) {
        logsComponent = (
            <Row className="justify-content-center">
                <Col xs="auto py-5">
                    <Loading message="Fetching logs..." size="lg" />
                </Col>
            </Row>
        );
    }
    else if( machine.fetchLogsError ) {
        logsComponent = (
            <Row className="justify-content-center">
                <Col xs="auto">
                    <Error message={machine.fetchLogsError.message} />
                </Col>
            </Row>
        );
    }
 
    return (
        <>
            <DropdownItem onClick={open} {...props}>
                View machine logs
            </DropdownItem>
            <Modal size="xl" backdrop="static" onHide={close} show={visible}>
                <Modal.Header closeButton>
                    <Modal.Title>Machine logs for {machine.name}</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <Row className="justify-content-end mb-3">
                        <Col xs="auto">
                            <Button
                                variant={following ? "outline-primary" : "primary"}
                                disabled={!machine.logs}
                                onClick={() => setFollowing(!following)}
                                className="me-2"
                            >
                                <FontAwesomeIcon
                                    icon={following ? faCircleNotch : faArrowDown}
                                    spin={following}
                                    className="me-2"
                                />
                                {following ? 'Following...' : 'Follow logs'}
                            </Button>
                            <Button
                                variant="primary"
                                disabled={machine.fetchingLogs}
                                onClick={machineActions.fetchLogs}
                            >
                                <FontAwesomeIcon
                                    icon={faSyncAlt}
                                    spin={machine.fetchingLogs}
                                    className="me-2"
                                />
                                Refresh
                            </Button>
                        </Col>
                    </Row>
                    {logsComponent}
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="primary" onClick={close}>Close</Button>
                </Modal.Footer>
            </Modal>
        </>
    );
};
