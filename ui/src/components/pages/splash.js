/**
 * This module contains the React component for the splash page.
 */

import React from 'react';

import Button from 'react-bootstrap/Button';
import Col from 'react-bootstrap/Col';
import Container from 'react-bootstrap/Container';
import Image from 'react-bootstrap/Image';
import Row from 'react-bootstrap/Row';

import { LinkContainer } from 'react-router-bootstrap';

import { usePageTitle } from '../utils';

import get from 'lodash/get';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faCloud } from '@fortawesome/free-solid-svg-icons';

import { Loading } from '../utils';


export const SplashPage = ({ cloudsFetching, clouds, currentCloud, links }) => {
    // Set the page title
    usePageTitle('Home');
    // Get the current cloud label
    const cloudLabel = get(clouds, [currentCloud, "label"]);
    return (
        <div className="p-5 mb-4 bg-light">
            <Container fluid className="py-4">
                <h1 className="display-5 fw-bold mb-4">
                    {cloudLabel ?
                        cloudLabel :
                        (cloudsFetching ? 
                            <Loading message="Loading cloud info..." size="xl" /> :
                            "Azimuth Portal"
                        )
                    }
                </h1>
                <Row xs={1} lg={2}>
                    <Col className="mb-3">
                        <p className="fs-4">
                            Welcome to Azimuth, a portal to help you access the platforms and storage that
                            you need to get science done.
                        </p>
                        <p>
                            Using Azimuth, you can quickly create the platforms you need for your science.
                            Advanced users can also manage virtual machines directly, provision and attach
                            cloud storage and expose machines to the internet by connecting external IP addresses.
                        </p>
                        {links && links.documentation && (
                            <p>
                                For help getting started, check out the{" "}
                                <a href={links.documentation} target="_blank">documentation</a>.
                            </p>
                        )}
                        <LinkContainer to={`/tenancies`}>
                            <Button variant="primary" size="lg">
                                <FontAwesomeIcon fixedWidth icon={faCloud} className="me-2" />
                                My Tenancies
                            </Button>
                        </LinkContainer>
                    </Col>
                    <Col className="splash-images">
                        <Row className="mb-3">
                            <Col>
                                <Image
                                    thumbnail
                                    title="OpenStack"
                                    src="https://object-storage-ca-ymq-1.vexxhost.net/swift/v1/6e4619c416ff4bd19e1c087f27a43eea/www-images-prod/openstack-logo/OpenStack-Logo-Vertical.png"
                                />
                                <Image
                                    thumbnail
                                    title="Slurm"
                                    src="https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Slurm_logo.svg/158px-Slurm_logo.svg.png"
                                />
                                <Image
                                    thumbnail
                                    title="Kubernetes"
                                    src="https://cncf-branding.netlify.app/img/projects/kubernetes/stacked/color/kubernetes-stacked-color.png"
                                />
                            </Col>
                        </Row>
                        <Row>
                            <Col>
                                <Image
                                    thumbnail
                                    title="Jupyter"
                                    src="https://raw.githubusercontent.com/jupyter/design/master/logos/Square%20Logo/squarelogo-greytext-orangebody-greymoons/squarelogo-greytext-orangebody-greymoons.png"
                                />
                                <Image
                                    thumbnail
                                    title="Kubeflow"
                                    src="https://user-images.githubusercontent.com/5319646/37641015-10cb00f6-2c53-11e8-9195-65f2dbc60955.jpg"
                                />
                                <Image
                                    thumbnail
                                    title="Dask"
                                    src="https://docs.dask.org/en/stable/_images/dask_horizontal.svg"
                                />
                            </Col>
                        </Row>
                    </Col>
                </Row>
            </Container>
        </div>
    );
};
