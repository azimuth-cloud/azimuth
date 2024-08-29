/**
 * This module provides the navigation component.
 */

import React from 'react';

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
    faSignOutAlt,
    faTachometerAlt,
    faLifeRing,
} from '@fortawesome/free-solid-svg-icons';

import { sortBy, Loading } from './utils';


export const Navigation = ({
    initialising,
    username,
    cloudsFetching,
    clouds,
    currentCloud: currentCloudName,
    tenancies,
    links
}) => {
    const currentCloud = get(clouds, currentCloudName);
    console.log(links);
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
        <Navbar bg="dark" variant="dark" expand="lg">
            <Container fluid>
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

                        {links && links.support && (
                            <Nav.Link href={links.support} target="_blank" active={false}>
                                <FontAwesomeIcon icon={faLifeRing} className="me-2" />
                                Support
                            </Nav.Link>
                        )}

                        {username ? (
                            <Nav.Link href={`/auth/logout/?next=/`} active={false}>
                                <FontAwesomeIcon icon={faSignOutAlt} className="me-2" />
                                Sign out ({username})
                            </Nav.Link>
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
