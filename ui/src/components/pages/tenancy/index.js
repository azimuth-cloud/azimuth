/**
 * This module contains components for the tenancy machines page.
 */

import React, { useEffect, useState } from 'react';

import Col from 'react-bootstrap/Col';
import Container from 'react-bootstrap/Container';
import Nav from 'react-bootstrap/Nav';
import Row from 'react-bootstrap/Row';

import { LinkContainer } from 'react-router-bootstrap';
import { Navigate } from 'react-router-dom';

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

import { bindArgsToActions } from '../../utils';

import { TenancyQuotasPanel } from './quotas';
import { TenancyMachinesPanel } from './machines';
import { TenancyVolumesPanel } from './volumes';
import { TenancyPlatformsPanel } from './platforms';

import { SSHKeyUpdateModal } from '../../ssh-key-update-modal';


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
            <Nav as="ul" className="sidebar-nav border-bottom">
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
            <Nav as="ul" variant="pills" className="sidebar-nav">
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
                    <LinkContainer to={`/tenancies/${currentTenancy.id}/quotas`}>
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
                            active={false}
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


export const TenancyResourcePage = ({
    resource,
    capabilities,
    sshKey,
    sshKeyActions,
    tenancies: { current: currentTenancy },
    tenancyActions,
    notificationActions
}) => {
    // If a resource has been selected that we don't support, emit a notification
    useEffect(
        () => {
            if( !["platforms", "quotas", "machines", "volumes"].includes(resource) ) {
                notificationActions.error({
                    title: 'Not Found',
                    message: `Resource '${resource}' does not exist.`
                });
            }
        },
        [resource]
    );

    let PanelComponent;
    if( resource === "platforms" ) {
        PanelComponent = TenancyPlatformsPanel;
    }
    else if( resource === "quotas" ) {
        PanelComponent = TenancyQuotasPanel;
    }
    else if( resource === "machines" ) {
        PanelComponent = TenancyMachinesPanel;
    }
    else if( resource === "volumes" ) {
        PanelComponent = TenancyVolumesPanel;
    }
    else {
        return <Navigate to={`/tenancies/${currentTenancy.id}`} />;
    }
    return (
        <Container fluid className="flex-grow-1 d-flex flex-column">
            <Row className="flex-grow-1">
                <div className="sidebar-container">
                    <div className="sidebar">
                        <TenancyNav
                            sshKey={sshKey}
                            sshKeyActions={sshKeyActions}
                            capabilities={capabilities}
                            currentTenancy={currentTenancy}
                            selectedResource={resource}
                        />
                    </div>
                </div>
                <Col>
                    <h1 className="border-bottom pb-1 mb-4">
                        <code>{currentTenancy.name}</code>
                    </h1>
                    <PanelComponent
                        sshKey={sshKey}
                        capabilities={capabilities}
                        tenancy={currentTenancy}
                        // Bind all the actions to the current tenancy
                        tenancyActions={{
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
                        }}
                        notificationActions={notificationActions}
                    />
                </Col>
            </Row>
        </Container>
    );
};
