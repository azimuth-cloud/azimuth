import React from 'react';

import Button from 'react-bootstrap/Button';
import Card from 'react-bootstrap/Card';
import Col from 'react-bootstrap/Col';
import Row from 'react-bootstrap/Row';

import { Link } from "react-router-dom";

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faPlus } from '@fortawesome/free-solid-svg-icons';

import { bindArgsToActions, sortBy, Error } from '../../../utils';

import { ClusterCard } from './clusters';
import { KubernetesCard } from './kubernetes';


const PlatformCard = ({ platform, tenancy, tenancyActions, ...props }) => {
    if( platform.kind === "cluster" ) {
        return (
            <ClusterCard
                cluster={platform.object}
                clusterTypes={tenancy.clusterTypes}
                clusterActions={bindArgsToActions(tenancyActions.cluster, platform.object.id)}
                tenancy={tenancy}
                tenancyActions={tenancyActions}
                {...props}
            />
        );
    }
    else if( platform.kind === "kubernetesCluster" ) {
        return (
            <KubernetesCard
                kubernetesCluster={platform.object}
                kubernetesClusterActions={bindArgsToActions(
                    tenancyActions.kubernetesCluster,
                    platform.object.id
                )}
                tenancy={tenancy}
                tenancyActions={tenancyActions}
            />
        );
    }
    else {
        // This should never happen!
        return <Error message="Unknown cluster kind" />;
    }
}


export const PlatformsGrid = ({
    showCreateModal,
    creating,
    platforms,
    tenancy,
    tenancyActions
}) => {
    const sortedPlatforms = sortBy(Object.values(platforms), p => p.name);
    if( sortedPlatforms.length > 0 ) {
        return (
            <Row className="g-3 justify-content-center">
                {sortedPlatforms.map(platform => (
                    <Col key={platform.id} className="platform-card-wrapper">
                        <PlatformCard
                            platform={platform}
                            tenancy={tenancy}
                            tenancyActions={tenancyActions}
                        />
                    </Col>
                ))}
            </Row>
        );
    }
    else {
        return (
            <Row className="justify-content-center">
                <Col xs="auto py-5">
                    <Card className="create-platform-card">
                        <Card.Header as="h5" className="py-3">
                            Create a platform
                        </Card.Header>
                        <Card.Body>
                            <p>Create the first platform in this tenancy!</p>
                            <p className="mb-0">
                                Platforms help you become productive faster by automating{" "}
                                the deployment of complex software systems and making them{" "}
                                easy to access.
                            </p>
                        </Card.Body>
                        <Card.Footer className="text-center">
                            <Button
                                size="lg"
                                variant="success"
                                disabled={creating}
                                onClick={showCreateModal}
                            >
                                <FontAwesomeIcon
                                    icon={faPlus}
                                    className="me-2"
                                />
                                Create a platform
                            </Button>
                        </Card.Footer>
                    </Card>
                </Col>
            </Row>
        );
    }
};
