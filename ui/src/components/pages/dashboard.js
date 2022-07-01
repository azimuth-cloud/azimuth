/**
 * This module contains the component for rendering the tenancies dashboard.
 */

import React, { useState } from 'react';

import Alert from 'react-bootstrap/Alert';
import Card from 'react-bootstrap/Card';
import Col from 'react-bootstrap/Col';
import ListGroup from 'react-bootstrap/ListGroup';
import Row from 'react-bootstrap/Row';

import { LinkContainer } from 'react-router-bootstrap';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faInfoCircle } from '@fortawesome/free-solid-svg-icons';

import Cookies from 'js-cookie';

import { sortBy, usePageTitle, Loading } from '../utils';


export const Dashboard = ({ tenancies: { fetching, data: tenancies }}) => {
    usePageTitle('Dashboard');

    const [showHint, setShowHint] = useState(Cookies.get("azimuth-dashboard-hint-dismissed") !== "1");
    const dismissHint = () => {
        Cookies.set("azimuth-dashboard-hint-dismissed", "1");
        setShowHint(false);
    };

    // Sort the tenancies by name before rendering
    const sortedTenancies = sortBy(Object.values(tenancies || {}), t => t.name);
    return (
        <>
            <h1 className="border-bottom pb-1 mb-4">Dashboard</h1>
            {showHint && (
                <Row>
                    <Col md={{ span: 8, offset: 2 }}>
                        <Alert variant="primary" dismissible onClose={dismissHint}>
                            <Alert.Heading>Welcome!</Alert.Heading>
                            <p>Please pick the tenancy you want to work in.</p>
                            <hr />
                            <p>
                                Cloud resources are allocated to specific tenancies and are shared
                                with everyone in that tenancy - for example you may have a cloud
                                tenancy assigned to your project for all the members of your project
                                to colloborate in.
                            </p>
                            <p className="mb-0">
                                If you want personal resources, you will need a personal tenancy.
                            </p>
                        </Alert>
                    </Col>
                </Row>
            )}
            <Row>
                <Col md={{ span: 6, offset: 3 }}>
                    <Card>
                        <Card.Header as="h5" className="py-3">Available tenancies</Card.Header>
                        {sortedTenancies.length > 0 ? (
                            <ListGroup variant="flush">
                                {sortedTenancies.map(t =>
                                    <LinkContainer
                                        key={t.id}
                                        to={`/tenancies/${t.id}`}
                                    >
                                        <ListGroup.Item action className="py-3">
                                            <code>{t.name}</code>
                                        </ListGroup.Item>
                                    </LinkContainer>
                                )}
                            </ListGroup>
                        ) : (
                            <Card.Body>
                                {fetching ? (
                                    <Loading message="Fetching tenancies..." />
                                ) : (
                                    "You do not belong to any tenancies."
                                )}
                            </Card.Body>
                        )}
                    </Card>
                </Col>
            </Row>
        </>
    );
};
