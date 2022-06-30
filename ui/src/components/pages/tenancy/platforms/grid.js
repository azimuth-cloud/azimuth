import React from 'react';

import Col from 'react-bootstrap/Col';
import Row from 'react-bootstrap/Row';

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
    platforms,
    tenancy,
    tenancyActions
}) => {
    const sortedPlatforms = sortBy(Object.values(platforms), p => p.name);
    if( sortedPlatforms.length > 0 ) {
        return (
            <Row xs={1} md={2} lg={3} xl={4}>
                {sortedPlatforms.map(platform => (
                    <Col key={platform.id}>
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
            <Row>
                <Col className="text-center text-muted py-5">
                    No platforms have been created yet.
                </Col>
            </Row>
        );
    }
};
