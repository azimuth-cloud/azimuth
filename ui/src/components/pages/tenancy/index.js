/**
 * This module contains components for the tenancy machines page.
 */

import React, { useEffect, useState } from 'react';

import Col from 'react-bootstrap/Col';
import Container from 'react-bootstrap/Container';
import Nav from 'react-bootstrap/Nav';
import NavDropdown from 'react-bootstrap/NavDropdown';
import Row from 'react-bootstrap/Row';

import { LinkContainer } from 'react-router-bootstrap';
import { Redirect, Route, Switch, useRouteMatch, useParams } from 'react-router-dom';

import get from 'lodash/get';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
    faDatabase,
    faDesktop,
    faKey,
    faSignOutAlt,
    faSitemap,
    faSlidersH,
    faTachometerAlt,
    faTools
} from '@fortawesome/free-solid-svg-icons';

import { Loading, bindArgsToActions, usePrevious } from '../../utils';

import { TenancyQuotasPanel } from './quotas';
import { TenancyMachinesPanel } from './machines';
import { TenancyVolumesPanel } from './volumes';
import { TenancyPlatformsPanel } from './platforms';

import { SSHKeyUpdateModal } from '../../ssh-key-update-modal';
import { expand } from 'rxjs/operators';


const SSHKeyUpdateNavLink = ({ sshKey, sshKeyActions }) => {
    const [visible, setVisible] = useState(false);
    const open = () => setVisible(true);
    const close = () => setVisible(false);
    return (
        <>
            <Nav.Link
                onClick={open}
                disabled={!sshKey.initialised}
                title="SSH public key"
            >
                <FontAwesomeIcon
                    icon={faKey}
                    fixedWidth
                />
                <span className="nav-link-text">SSH public key</span>
            </Nav.Link>
            <SSHKeyUpdateModal
                show={visible}
                // In this case, we just want to close the modal whether
                // it is a cancel or a successful submission
                onSuccess={close}
                onCancel={close}
                sshKey={sshKey}
                sshKeyActions={sshKeyActions}
            />
        </>
    );
};


const TenancyNav = ({
    sshKey,
    sshKeyActions,
    capabilities,
    url,
    currentTenancy,
    selectedResource
}) => {
    const [userExpanded, setUserExpanded] = useState(false);
    const toggleUserExpanded = () => setUserExpanded(expanded => !expanded);
    const supportsPlatforms = capabilities.supports_clusters || capabilities.supports_kubernetes;
    const selectedResourceIsAdvanced = ['machines', 'volumes'].includes(selectedResource);
    // If the cloud doesn't support platforms, always show the advanced resources
    // If the user is on an advanced tab, show the items even if they are not expanded
    const expanded = (userExpanded || !supportsPlatforms || selectedResourceIsAdvanced);

    return (
        <>
            <Nav as="ul" activeKey={url} className="sidebar-nav border-bottom">
                <Nav.Item as="li">
                    <LinkContainer to={`/tenancies`}>
                        <Nav.Link title="Switch tenancy">
                            <FontAwesomeIcon
                                icon={faSignOutAlt}
                                transform={{ rotate: 180 }}
                                fixedWidth
                            />
                            <span className="nav-link-text">Switch tenancy</span>
                        </Nav.Link>
                    </LinkContainer>
                </Nav.Item>
                <SSHKeyUpdateNavLink sshKey={sshKey} sshKeyActions={sshKeyActions} />
            </Nav>
            <Nav as="ul" variant="pills" activeKey={url} className="sidebar-nav">
                {supportsPlatforms && (
                    <Nav.Item as="li">
                        <LinkContainer to={`/tenancies/${currentTenancy.id}/platforms`}>
                            <Nav.Link title="Platforms">
                                <FontAwesomeIcon
                                    icon={faSitemap}
                                    fixedWidth
                                />
                                <span className="nav-link-text">Platforms</span>
                            </Nav.Link>
                        </LinkContainer>
                    </Nav.Item>
                )}
                <Nav.Item as="li">
                    <LinkContainer exact to={`/tenancies/${currentTenancy.id}/quotas`}>
                        <Nav.Link title="Quotas">
                            <FontAwesomeIcon
                                icon={faSlidersH}
                                fixedWidth
                            />
                            <span className="nav-link-text">Quotas</span>
                        </Nav.Link>
                    </LinkContainer>
                </Nav.Item>
                {currentTenancy.links.metrics && (
                    <Nav.Item as="li">
                        <Nav.Link
                            href={currentTenancy.links.metrics}
                            target="_blank"
                            title="Project metrics"
                        >
                            <FontAwesomeIcon
                                icon={faTachometerAlt}
                                fixedWidth
                            />
                            <span className="nav-link-text">Project metrics</span>
                        </Nav.Link>
                    </Nav.Item>
                )}
                {supportsPlatforms && (
                    <Nav.Item as="li">
                        <Nav.Link
                            title="Advanced"
                            onClick={toggleUserExpanded}
                            disabled={selectedResourceIsAdvanced}
                            className={`nav-toggle toggle-${expanded ? "show" : "hide"}`}
                        >
                            <FontAwesomeIcon
                                icon={faTools}
                                fixedWidth
                            />
                            <span className="nav-link-text">Advanced</span>
                        </Nav.Link>
                    </Nav.Item>
                )}
                {expanded && (
                    <>
                        <Nav.Item as="li" className={supportsPlatforms ? "nav-item-nested" : undefined}>
                            <LinkContainer to={`/tenancies/${currentTenancy.id}/machines`}>
                                <Nav.Link title="Machines">
                                    <FontAwesomeIcon
                                        icon={faDesktop}
                                        fixedWidth
                                    />
                                    <span className="nav-link-text">Machines</span>
                                </Nav.Link>
                            </LinkContainer>
                        </Nav.Item>
                        {capabilities.supports_volumes && (
                            <Nav.Item as="li" className={supportsPlatforms ? "nav-item-nested" : undefined}>
                                <LinkContainer to={`/tenancies/${currentTenancy.id}/volumes`}>
                                    <Nav.Link title="Volumes">
                                        <FontAwesomeIcon
                                            icon={faDatabase}
                                            fixedWidth
                                        />
                                        <span className="nav-link-text">Volumes</span>
                                    </Nav.Link>
                                </LinkContainer>
                            </Nav.Item>
                        )}
                    </>
                )}
            </Nav>
        </>
    );
};


export const TenancyPage = ({
    capabilities,
    sshKey,
    sshKeyActions,
    tenancies: { fetching, data: tenancies, current: currentTenancy },
    tenancyActions,
    notificationActions
}) => {
    // Get the path parameters
    const { path, url } = useRouteMatch();
    const { id: matchedId, resource: matchedResource } = useParams();

    // When the tenancy matched in the path changes, initiate a switch if required
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

    // Check if a matched resource is present
    // If not, redirect to one based on the available capabilities
    if( !matchedResource ) {
        const defaultResource = (
            capabilities.supports_clusters || capabilities.supports_kubernetes ?
                'platforms' :
                'quotas'
        );
        return <Redirect to={`${url}/${defaultResource}`} />;
    }
    
    if( currentTenancy ) {
        // If there is a current tenancy, render the page
        const tenancyProps = {
            sshKey,
            capabilities,
            tenancy: currentTenancy,
            tenancyActions: {
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
            },
            notificationActions
        };
        return (
            <Container fluid className="flex-grow-1 d-flex flex-column">
                <Row className="flex-grow-1">
                    <div className="sidebar">
                        <TenancyNav
                            sshKey={sshKey}
                            sshKeyActions={sshKeyActions}
                            capabilities={capabilities}
                            url={url}
                            currentTenancy={currentTenancy}
                            selectedResource={matchedResource}
                        />
                    </div>
                    <Col>
                        <h1 className="border-bottom pb-1 mb-4">
                            <code>{currentTenancy.name}</code>
                        </h1>
                        <Switch>
                            <Route exact path={`${path}/quotas`}>
                                <TenancyQuotasPanel {...tenancyProps} />
                            </Route>
                            <Route exact path={`${path}/machines`}>
                                <TenancyMachinesPanel {...tenancyProps} />
                            </Route>
                            <Route exact path={`${path}/volumes`}>
                                <TenancyVolumesPanel {...tenancyProps} />
                            </Route>
                            <Route exact path={`${path}/platforms`}>
                                <TenancyPlatformsPanel {...tenancyProps} />
                            </Route>
                        </Switch>
                    </Col>
                </Row>
            </Container>
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
        return <Redirect to="/tenancies" />;
    }
};
