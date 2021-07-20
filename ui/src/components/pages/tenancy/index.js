/**
 * This module contains components for the tenancy machines page.
 */

import React, { useEffect } from 'react';

import Col from 'react-bootstrap/Col';
import Nav from 'react-bootstrap/Nav';
import Row from 'react-bootstrap/Row';

import { LinkContainer } from 'react-router-bootstrap';
import { Redirect } from 'react-router-dom';

import get from 'lodash/get';

import { Loading, bindArgsToActions } from '../../utils';


export const TenancyPage = ({
    children,
    capabilities,
    sshKey,
    tenancies: { fetching, data: tenancies, current: currentTenancy },
    tenancyActions,
    match,
    notificationActions
}) => {
    // When the tenancy matched in the path changes, initiate a switch if required
    const matchedId = match.params.id;
    const currentId = get(currentTenancy, 'id');
    useEffect(
        () => { if( !fetching && matchedId !== currentId ) tenancyActions.switchTo(matchedId) },
        [fetching, matchedId, currentId]
    );

    // If the tenancy does not exist, emit a notification
    useEffect(
        () => {
            if( !currentId && !fetching && !(tenancies || {}).hasOwnProperty(matchedId) )
                notificationActions.error({
                    title: 'Not Found',
                    message: `Tenancy '${matchedId}' does not exist.`
                });
        },
        [fetching, matchedId, currentId, tenancies]
    );
    
    if( currentTenancy ) {
        // If there is a current tenancy, render the page
        const boundTenancyActions = {
            quota: bindArgsToActions(tenancyActions.quota, currentTenancy.id),
            image: bindArgsToActions(tenancyActions.image, currentTenancy.id),
            size: bindArgsToActions(tenancyActions.size, currentTenancy.id),
            externalIp: bindArgsToActions(tenancyActions.externalIp, currentTenancy.id),
            volume: bindArgsToActions(tenancyActions.volume, currentTenancy.id),
            machine: bindArgsToActions(tenancyActions.machine, currentTenancy.id),
            kubernetesClusterTemplate: bindArgsToActions(
                tenancyActions.kubernetesClusterTemplate,
                currentTenancy.id
            ),
            kubernetesCluster: bindArgsToActions(
                tenancyActions.kubernetesCluster,
                currentTenancy.id
            ),
            clusterType: bindArgsToActions(tenancyActions.clusterType, currentTenancy.id),
            cluster: bindArgsToActions(tenancyActions.cluster, currentTenancy.id)
        };
        return (
            <>
                <h1 className="border-bottom pb-1 mb-4">
                    <code>{currentTenancy.name}</code>
                </h1>
                <Nav as="ul" variant="tabs" activeKey={match.url} className="mb-3">
                    <Nav.Item as="li">
                        <LinkContainer exact to={`/tenancies/${currentTenancy.id}`}>
                            <Nav.Link>Overview</Nav.Link>
                        </LinkContainer>
                    </Nav.Item>
                    <Nav.Item as="li">
                        <LinkContainer to={`/tenancies/${currentTenancy.id}/machines`}>
                            <Nav.Link>Machines</Nav.Link>
                        </LinkContainer>
                    </Nav.Item>
                    {capabilities.supports_volumes && (
                        <Nav.Item as="li">
                            <LinkContainer to={`/tenancies/${currentTenancy.id}/volumes`}>
                                <Nav.Link>Volumes</Nav.Link>
                            </LinkContainer>
                        </Nav.Item>
                    )}
                    {capabilities.supports_kubernetes && (
                        <Nav.Item as="li">
                            <LinkContainer to={`/tenancies/${currentTenancy.id}/kubernetes`}>
                                <Nav.Link>Kubernetes</Nav.Link>
                            </LinkContainer>
                        </Nav.Item>
                    )}
                    {capabilities.supports_clusters && (
                        <Nav.Item as="li">
                            <LinkContainer to={`/tenancies/${currentTenancy.id}/clusters`}>
                                <Nav.Link>Clusters</Nav.Link>
                            </LinkContainer>
                        </Nav.Item>
                    )}
                </Nav>
                {React.Children.map(
                    // Pass the tenancy data to the children
                    children,
                    child => React.cloneElement(child, {
                        sshKey,
                        capabilities,
                        tenancy: currentTenancy,
                        tenancyActions: boundTenancyActions,
                        notificationActions
                    })
                )}
            </>
        );
    }
    else if( fetching || (tenancies || {}).hasOwnProperty(matchedId) ) {
        // If fetching tenancies or the matched id is in the tenancy data, allow more time
        return (
            <Row className="justify-content-center">
                <Col xs="auto" className="mt-5">
                    <Loading iconSize="lg" size="lg" message="Loading tenancies..." />
                </Col>
            </Row>
        );
    }
    else {
        // Otherwise redirect
        return <Redirect to="/dashboard" />;
    }
};
