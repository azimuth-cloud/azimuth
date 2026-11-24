/**
 * This module contains components for the tenancy machines page.
 */

import React, { useEffect, useState } from 'react';

import Alert from 'react-bootstrap/Alert';
import Button from 'react-bootstrap/Button';
import Col from 'react-bootstrap/Col';
import Container from 'react-bootstrap/Container';
import Nav from 'react-bootstrap/Nav';
import Row from 'react-bootstrap/Row';

import { LinkContainer } from 'react-router-bootstrap';
import { Navigate } from 'react-router-dom';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
    faDatabase,
    faDesktop,
    faKey,
    faSignOutAlt,
    faSitemap,
    faSlidersH,
    faTachometerAlt,
    faTools,
    faUsers,
    faExclamationTriangle,
    faClose
} from '@fortawesome/free-solid-svg-icons';

import { TenancyIdpPanel } from './idp';
import { TenancyQuotasPanel } from './quotas';
import { TenancyMachinesPanel } from './machines';
import { TenancyVolumesPanel } from './volumes';
import { TenancyPlatformsPanel } from './platforms';
import { useResourceInitialised } from './resource-utils';

import { Error, Loading } from '../../utils';

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

const QuotaPopup = ({
    currentTenancy
}) => {
    const quotas = currentTenancy.quotas

    const quota_warn = 0.8;
    const quota_critical = 0.95;

    if (quotas.initialised){
        const [show, setShow] = useState(true);
        const highUsage = Object.values(quotas.data).filter(
            ({ used, allocated }) => used / allocated > quota_warn
        );

        if(highUsage.length > 0){
            const criticalUsage = highUsage.some( 
            ({ used, allocated }) => used / allocated > quota_critical
            );

            if(criticalUsage){
                return (
                    <LinkContainer to={`/tenancies/${currentTenancy.id}/quotas`}>
                    <Alert 
                        variant='danger'
                        className="d-inline-flex gap-3 py-2 px-2 small align-items-center text-danger alert-hover"
                    >
                        <FontAwesomeIcon
                            icon={faExclamationTriangle}
                            size="md" className="me-2"
                        />
                         <span className="text-decoration-underline">Critical: resource over {quota_critical * 100}% used</span>
                    </Alert>
                    </LinkContainer>
                )
            }else {
                return (
                    <LinkContainer to={`/tenancies/${currentTenancy.id}/quotas`}>
                    <Alert
                    show={show}
                    variant="warning"
                    className="d-inline-flex gap-3 py-2 px-2 small align-items-center text-warning alert-hover"
                    >
                        <div>
                            <FontAwesomeIcon
                                icon={faExclamationTriangle}
                                size="md" className="me-2"
                            />
                            <span className="text-decoration-underline">Warning: resource over {quota_warn * 100}% used</span>
                        </div>

                        <Button
                            variant="outline-warning"
                            onClick={(e) => {
                                e.stopPropagation();
                                setShow(false);
                            }}
                            aria-label="Close"
                        >
                            <FontAwesomeIcon icon={faClose} size="lg" />
                        </Button>
                    </Alert>
                    </LinkContainer>
                )
            }
        }
    }
}

const TenancyNav = ({
    sshKey,
    sshKeyActions,
    capabilities,
    currentTenancy,
    selectedResource,
    supportsPlatforms,
}) => {
    // When the nav is mounted, we show the sidebar by applying a class
    // The class is removed on a timer, after which the hover CSS rules take over
    const [sidebarExpanded, setSidebarExpanded] = useState(true);
    useEffect(
        () => {
            const timeout = setTimeout(() => setSidebarExpanded(false), 500);
            return () => clearTimeout(timeout);
        },
        []
    );

    // Determine whether to show the advanced menu items or not
    const [userExpanded, setUserExpanded] = useState(false);
    const toggleUserExpanded = () => setUserExpanded(expanded => !expanded);
    const selectedResourceIsAdvanced = ['machines', 'volumes'].includes(selectedResource);
    
    // If the cloud doesn't support platforms, always show the advanced resources
    // If the cloud doesn't support machines or volumes, don't show the advanced tab
    const showAdvanced = (capabilities.supports_machines && capabilities.supports_volumes) || !supportsPlatforms
    // If the cloud doesn't support platforms, always show the advanced resources
    // If the user is on an advanced tab, expand the items even if they are not expanded
    const expandAdvanced = (userExpanded || !supportsPlatforms || selectedResourceIsAdvanced);

    return (
        <div className={`sidebar${sidebarExpanded ? " expanded" : ""}`}>
            <Nav as="ul" variant="pills" className="sidebar-nav">
                {supportsPlatforms && (
                    <>
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
                        <Nav.Item as="li">
                            <LinkContainer to={`/tenancies/${currentTenancy.id}/idp`}>
                                <Nav.Link title="Identity Provider">
                                    <FontAwesomeIcon
                                        icon={faUsers}
                                        fixedWidth
                                    />
                                    <span className="nav-link-text">Identity Provider</span>
                                </Nav.Link>
                            </LinkContainer>
                        </Nav.Item>
                    </>
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
                {showAdvanced && (
                    <Nav.Item as="li">
                        <Nav.Link
                            title="Advanced"
                            onClick={toggleUserExpanded}
                            disabled={selectedResourceIsAdvanced}
                            className={`nav-toggle toggle-${expandAdvanced ? "show" : "hide"}`}
                        >
                            <FontAwesomeIcon
                                icon={faTools}
                                fixedWidth
                            />
                            <span className="nav-link-text">Advanced</span>
                        </Nav.Link>
                    </Nav.Item>
                )}
                {expandAdvanced && (
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
            <Nav as="ul" className="sidebar-nav border-top border-2">
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
        </div>
    );
};


// A map of platform names to the panel components
const PlatformPanelComponents = {
    "idp": TenancyIdpPanel,
    "platforms": TenancyPlatformsPanel,
    "quotas": TenancyQuotasPanel,
    "machines": TenancyMachinesPanel,
    "volumes": TenancyVolumesPanel,
};


export const TenancyResourcePage = ({
    resource,
    userId,
    supportsPlatforms,
    sshKey,
    sshKeyActions,
    currentTenancy,
    tenancyActions,
    notificationActions
}) => {
    // Ensure that the tenancy capabilities are loaded
    useResourceInitialised(currentTenancy.capabilities, tenancyActions.capabilities.fetch);
    useResourceInitialised(currentTenancy.quotas, tenancyActions.quota.fetchList);

    // If a resource has been selected that we don't support, emit a notification
    useEffect(
        () => {
            if( !PlatformPanelComponents.hasOwnProperty(resource) ) {
                notificationActions.error({
                    title: 'Not Found',
                    message: `Resource '${resource}' does not exist.`
                });
            }
        },
        [resource]
    );

    // Calculate the panel component to use
    // For unsupported resources, we redirect to the main tenancy page
    let PanelComponent;
    if( PlatformPanelComponents.hasOwnProperty(resource) ) {
        PanelComponent = PlatformPanelComponents[resource];
    }
    else {
        return <Navigate to={`/tenancies/${currentTenancy.id}`} />;
    }

    // We only render the page once the capabilities have initialised
    return (
        <Container fluid className="flex-grow-1 d-flex flex-column">
            <Row className="flex-grow-1">
                <div className="sidebar-container">
                    <TenancyNav
                        sshKey={sshKey}
                        sshKeyActions={sshKeyActions}
                        capabilities={currentTenancy.capabilities}
                        currentTenancy={currentTenancy}
                        selectedResource={resource}
                        supportsPlatforms={supportsPlatforms}
                    />
                </div>
                <Col>
                    <h1 className="border-bottom border-2 pb-1 mb-4">
                    <Row>
                        <Col lg={4}>
                            <code>{currentTenancy.name}</code>
                        </Col>
                        <Col lg={8} className="d-flex justify-content-end">
                            <QuotaPopup
                            currentTenancy={currentTenancy}
                            />
                        </Col>
                    </Row>
                    </h1>
                    {currentTenancy.capabilities.initialised ? (
                        <PanelComponent
                            userId={userId}
                            sshKey={sshKey}
                            capabilities={currentTenancy.capabilities}
                            tenancy={currentTenancy}
                            tenancyActions={tenancyActions}
                            notificationActions={notificationActions}
                            supportsPlatforms={supportsPlatforms}
                        />
                    ) : (
                        <Row className="justify-content-center">
                            {(currentTenancy.capabilities.fetchError && !currentTenancy.capabilities.fetching) ? (
                                <Col xs="auto py-3">
                                    <Error message={currentTenancy.capabilities.fetchError.message} />
                                </Col>
                            ) : (
                                <Col xs="auto py-5" className="mt-5">
                                    <Loading iconSize="lg" size="lg" message="Loading..." />
                                </Col>
                            )}
                        </Row>
                    )}
                </Col>
            </Row>
        </Container>
    );
};
