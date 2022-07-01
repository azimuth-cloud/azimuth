/**
 * This module contains the React component for the splash page.
 */

import React from 'react';

import Container from 'react-bootstrap/Container';
import Button from 'react-bootstrap/Button';
import Col from 'react-bootstrap/Col';
import Row from 'react-bootstrap/Row';

import { LinkContainer } from 'react-router-bootstrap';

import { usePageTitle } from '../utils';

import get from 'lodash/get';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faCloud } from '@fortawesome/free-solid-svg-icons';

import { Loading } from '../utils';


export const SplashPage = ({ cloudsFetching, clouds, currentCloud }) => {
    // Set the page title
    usePageTitle('Home');
    // Get the current cloud label
    const cloudLabel = get(clouds, [currentCloud, "label"]);
    return (
        <Row>
            <Col>   
                <div className="p-5 mb-4 bg-light">
                    <Container fluid className="py-3">
                        <h1 className="display-5 fw-bold mb-4">
                            {cloudLabel ?
                                cloudLabel :
                                (cloudsFetching ? 
                                    <Loading message="Loading cloud info..." size="xl" /> :
                                    "Cloud Portal"
                                )
                            }
                        </h1>
                        <p className="col-md-8 fs-4">
                            This portal allows you to manage resources in your cloud tenancies.
                        </p>
                        <p className="col-md-8 fs-4">
                            You can quickly create virtual machines and expose them by connecting external
                            IP addresses, provision and attach volumes and, where supported, create and
                            manage clusters using Cluster-as-a-Service.
                        </p>
                        <LinkContainer to={`/tenancies`}>
                            <Button variant="primary" size="lg">
                                <FontAwesomeIcon fixedWidth icon={faCloud} className="me-2" />
                                My Tenancies
                            </Button>
                        </LinkContainer>
                    </Container>
                </div>
            </Col>
        </Row>
    );
};
