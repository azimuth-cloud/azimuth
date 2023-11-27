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

import DaskLogo from './dask-logo.svg';
import JupyterLogo from './jupyter-logo.png';
import KubeflowLogo from './kubeflow-logo.jpg';
import KubernetesLogo from './kubernetes-logo.png';
import OpenStackLogo from './openstack-logo.png';
import SlurmLogo from './slurm-logo.png';


export const SplashPage = ({ cloudsFetching, clouds, currentCloud, links }) => {
    // Set the page title
    usePageTitle('Home');
    // Get the current cloud label
    const cloudLabel = get(clouds, [currentCloud, "label"]);
    return (
        <Container className="py-4">
            <div className="p-5 mb-4 bg-light border border-2">
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
                                <Image thumbnail title="OpenStack" src={OpenStackLogo} />
                                <Image thumbnail title="Slurm" src={SlurmLogo} />
                                <Image thumbnail title="Kubernetes" src={KubernetesLogo} />
                            </Col>
                        </Row>
                        <Row>
                            <Col>
                                <Image thumbnail title="Jupyter" src={JupyterLogo} />
                                <Image thumbnail title="Kubeflow" src={KubeflowLogo} />
                                <Image thumbnail title="Dask" src={DaskLogo} />
                            </Col>
                        </Row>
                    </Col>
                </Row>
            </div>
        </Container>
    );
};
