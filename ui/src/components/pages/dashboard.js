/**
 * This module contains the component for rendering the tenancies dashboard.
 */

import React from 'react';

import Card from 'react-bootstrap/Card';
import Col from 'react-bootstrap/Col';
import ListGroup from 'react-bootstrap/ListGroup';
import Row from 'react-bootstrap/Row';

import { LinkContainer } from 'react-router-bootstrap';

import { sortBy, usePageTitle, Loading } from '../utils';


export const Dashboard = ({ tenancies: { fetching, data: tenancies }}) => {
    usePageTitle('Dashboard');
    // Sort the tenancies by name before rendering
    const sortedTenancies = sortBy(Object.values(tenancies || {}), t => t.name);
    return (
        <>
            <h1 className="border-bottom pb-1 mb-4">Dashboard</h1>
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
