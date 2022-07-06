/**
 * This module provides the navigation component.
 */

import React, { useState } from 'react';

import Container from 'react-bootstrap/Container';
import Nav from 'react-bootstrap/Nav';
import Navbar from 'react-bootstrap/Navbar';
import NavDropdown from 'react-bootstrap/NavDropdown';

import { LinkContainer } from 'react-router-bootstrap';

import get from 'lodash/get';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
    faBook,
    faCloud,
    faTachometerAlt,
    faUser
} from '@fortawesome/free-solid-svg-icons';

import { sortBy, Loading } from './utils';
import { SSHKeyUpdateModal } from './ssh-key-update-modal';


const SSHKeyUpdateMenuItem = ({ sshKey, sshKeyActions }) => {
    const [visible, setVisible] = useState(false);
    const open = () => setVisible(true);
    const close = () => setVisible(false);
    return (
        <>
            <NavDropdown.Item onSelect={open} disabled={!sshKey.initialised}>
                SSH public key
            </NavDropdown.Item>
            <SSHKeyUpdateModal
                show={visible}
                // In this case, we just want to close the modal whether
                // it is a cancel or a successful submission
                onSuccess={close}
                onCancel={close}
                sshKey={sshKey}
                sshKeyActions={sshKeyActions}
            />
        </>
    );
};


export const Navigation = ({
    initialising,
    username,
    cloudsFetching,
    clouds,
    currentCloud: currentCloudName,
    tenancies,
    sshKey,
    sshKeyActions,
    links
}) => {
    const currentCloud = get(clouds, currentCloudName);
    const sortedClouds = sortBy(
        Object.entries(clouds || {})
            .map(([name, cloud]) => ({ name, ...cloud }))
            .filter(cloud => cloud.name !== currentCloudName),
        cloud => cloud.label
    );
    const sortedTenancies = sortBy(
        Object.values(tenancies || {}),
        tenancy => tenancy.name
    );
    return (
        <Navbar bg="dark" variant="dark" className="mb-3" expand="lg">
            <Container>
                <LinkContainer to="/">
                    <Navbar.Brand>
                        {currentCloud ?
                            currentCloud.label :
                            (cloudsFetching ? <Loading /> : "Azimuth")
                        }
                    </Navbar.Brand>
                </LinkContainer>
                <Navbar.Toggle aria-controls="navbar-main" />
                <Navbar.Collapse id="navbar-main">
                    <Nav className="me-auto">
                        {/* Only show the cloud switcher if there is more than one cloud */}
                        {currentCloud && sortedClouds.length > 0 && (
                            <NavDropdown
                                title={(
                                    <>
                                        <FontAwesomeIcon icon={faCloud} className="me-2" />
                                        Other Clouds
                                    </>
                                )}
                            >
                                {sortedClouds.map(c =>
                                    <NavDropdown.Item key={c.name} href={c.url}>
                                        {c.label}
                                    </NavDropdown.Item>
                                )}
                            </NavDropdown>
                        )}
                    </Nav>
                    <Nav>
                        {username && links && links.metrics && (
                            <Nav.Link href={links.metrics} target="_blank" active={false}>
                                <FontAwesomeIcon icon={faTachometerAlt} className="me-2" />
                                Cloud Metrics
                            </Nav.Link>
                        )}
                        {links && links.documentation && (
                            <Nav.Link href={links.documentation} target="_blank" active={false}>
                                <FontAwesomeIcon icon={faBook} className="me-2" />
                                Documentation
                            </Nav.Link>
                        )}
                        {username ? (
                            <NavDropdown
                                title={(
                                    <>
                                        <FontAwesomeIcon icon={faUser} className="me-2" />
                                        {username}
                                    </>
                                )}
                            >
                                <SSHKeyUpdateMenuItem
                                    sshKey={sshKey}
                                    sshKeyActions={sshKeyActions}
                                />
                                <NavDropdown.Item href={`/auth/logout/?next=/`}>
                                    Sign out
                                </NavDropdown.Item>
                            </NavDropdown>
                        ) : (
                            initialising ? (
                                <Navbar.Text><Loading message="Loading..." /></Navbar.Text>
                            ) : (
                                <Nav.Link href={`/auth/login/?next=${window.location.pathname}`}>
                                    Sign In
                                </Nav.Link>
                            )
                        )}
                    </Nav>
                </Navbar.Collapse>
            </Container>
        </Navbar>
    );
};
