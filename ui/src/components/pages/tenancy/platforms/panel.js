/**
 * This module contains components for the tenancy machines page.
 */

import React from 'react';

import Button from 'react-bootstrap/Button';
import ButtonGroup from 'react-bootstrap/ButtonGroup';
import Col from 'react-bootstrap/Col';
import Row from 'react-bootstrap/Row';

import { StatusCodes } from 'http-status-codes';

import get from 'lodash/get';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faSyncAlt } from '@fortawesome/free-solid-svg-icons';

import { usePageTitle, Error, Loading } from '../../../utils';

import { useResourceInitialised } from '../resource-utils';
import { PlatformsGrid } from './grid';
import { CreatePlatformButton } from './create-modal';


// This function adds a boolean to each cluster that indicates whether it has another
// cluster that is dependent on it
const clustersWithLinks = tenancy => {
    const clusterTypes = get(tenancy, ['clusterTypes', 'data']) || {};
    const clusters = get(tenancy, ['clusters', 'data']) || {};
    // Find the parameters for each cluster type that correspond to other clusters
    const linkedParams = Object.assign(
        {},
        ...Object.values(clusterTypes).map(ct => ({
            [ct.name]: ct.parameters
                .filter(p => p.kind === "cloud.cluster")
                .map(p => p.name)
        }))
    );
    // Find the clusters that are linked to by other clusters by looking for
    // the values of the related parameters in each cluster
    const linkedClusters = Object.values(clusters)
        .map(c => get(linkedParams, c.cluster_type, []).map(p => c.parameter_values[p]))
        .flat();
    // Attach a "linkedTo" property to each cluster
    return Object.assign(
        {},
        ...Object.entries(clusters).map(([key, cluster]) => ({
            [key]: {
                ...cluster,
                linkedTo: linkedClusters.includes(cluster.name)
            }
        }))
    );
};


export const TenancyPlatformsPanel = ({
    sshKey,
    tenancy,
    tenancyActions
}) => {
    usePageTitle('Platforms');

    // Initialise the required resources
    useResourceInitialised(tenancy.sizes, tenancyActions.size.fetchList);
    useResourceInitialised(tenancy.clusterTypes, tenancyActions.clusterType.fetchList);
    useResourceInitialised(tenancy.clusters, tenancyActions.cluster.fetchList);
    useResourceInitialised(
        tenancy.kubernetesClusterTemplates,
        tenancyActions.kubernetesClusterTemplate.fetchList
    );
    useResourceInitialised(tenancy.kubernetesClusters, tenancyActions.kubernetesCluster.fetchList);

    const clustersNotFound = (
        get(tenancy.clusters.fetchError, "statusCode") === StatusCodes.NOT_FOUND
    );
    const kubernetesClustersNotFound = (
        get(tenancy.kubernetesClusters.fetchError, "statusCode") === StatusCodes.NOT_FOUND
    );
    const platformsNotFound = clustersNotFound && kubernetesClustersNotFound;

    // Get the aggregate resource for clusters + Kubernetes clusters
    const resource = {
        initialised: (
            // When both are not found, we don't want to become initialised
            !platformsNotFound &&
            (tenancy.clusters.initialised || clustersNotFound) &&
            (tenancy.kubernetesClusters.initialised || kubernetesClustersNotFound)
        ),
        fetching: tenancy.clusters.fetching || tenancy.kubernetesClusters.fetching,
        data: Object.assign(
            {},
            ...Object.entries(clustersWithLinks(tenancy)).map(
                ([key, value]) => ({
                    [`clusters/${key}`]: {
                        id: `clusters/${key}`,
                        kind: "cluster",
                        name: value.name,
                        object: value
                    }
                })
            ),
            ...Object.entries(tenancy.kubernetesClusters.data || {}).map(
                ([key, value]) => ({
                    [`kubernetesClusters/${key}`]: {
                        id: `kubernetesClusters/${key}`,
                        kind: "kubernetesCluster",
                        name: value.name,
                        object: value
                    }
                })
            )
        ),
        // Not found isn't really an error for platforms, so exclude them
        fetchErrors: Object.assign(
            {},
            ...[
                ["clusters", tenancy.clusters.fetchError],
                ["kubernetesClusters", tenancy.kubernetesClusters.fetchError]
            ].filter(
                ([_, e]) => !!e && e.statusCode !== StatusCodes.NOT_FOUND
            ).map(
                ([k, e]) => ({ [k]: e })
            )
        ),
        creating: tenancy.clusters.creating || tenancy.kubernetesClusters.creating
    };

    const refreshPlatforms = () => {
        if( !clustersNotFound ) tenancyActions.cluster.fetchList();
        if( !kubernetesClustersNotFound ) tenancyActions.kubernetesCluster.fetchList();
    };

    // If the resource failed to load because it was not found, disable the refresh button
    return (
        <>
            <Row className="justify-content-end mb-2">
                <Col xs="auto">
                    <ButtonGroup>
                        <CreatePlatformButton
                            disabled={!resource.initialised}
                            creating={!!resource.creating}
                            sshKey={sshKey}
                            tenancy={tenancy}
                            tenancyActions={tenancyActions}
                        />
                        <Button
                            variant="primary"
                            disabled={platformsNotFound || resource.fetching}
                            onClick={refreshPlatforms}
                            title={`Refresh platforms`}
                        >
                            <FontAwesomeIcon
                                icon={faSyncAlt}
                                spin={resource.fetching}
                                className="me-2"
                            />
                            Refresh
                        </Button>
                    </ButtonGroup>
                </Col>
            </Row>
            {resource.initialised ? (
                <PlatformsGrid
                    platforms={resource.data}
                    tenancy={tenancy}
                    tenancyActions={tenancyActions}
                />
            ) : (
                <Row className="justify-content-center">
                    {platformsNotFound ? (
                        <Col xs="auto py-3">
                            <Error message="Platforms are not supported." />
                        </Col>
                    ) : (
                        (resource.fetchErrors && !resource.fetching) ? (
                            <Col xs="auto py-3">
                                {Object.entries(resource.fetchErrors).map(([k, e]) =>
                                    <Error key={k} message={e.message} />
                                )}
                            </Col>
                        ) : (
                            <Col xs="auto py-5">
                                <Loading
                                    size="lg"
                                    iconSize="lg"
                                    message={`Loading platforms...`}
                                />
                            </Col>
                        )
                    )}
                </Row>
            )}
        </>
    );
};
