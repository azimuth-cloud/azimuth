/**
 * Module containing the root application component.
 */

import React, { useEffect } from 'react';

import Col from 'react-bootstrap/Col';
import Row from 'react-bootstrap/Row';

import { Navigate, Routes, Route, useParams } from 'react-router-dom';

import { bindActionCreators } from 'redux';
import { connect } from 'react-redux';

import { actionCreators as sshKeyActions } from './redux/ssh-public-key';
import { actionCreators as tenancyActions } from './redux/tenancies';
import { actionCreators as notificationActions } from './redux/notifications';

import { Loading, bindArgsToActions } from './components/utils';

import { Navigation } from './components/navigation';
import { Notifications } from './components/notifications';
import { SplashPage } from './components/pages/splash';
import { TenanciesPage } from './components/pages/tenancies';
import { TenancyResourcePage } from './components/pages/tenancy';

import { Footer } from './components/footer';
import { useResourceInitialised } from './components/pages/tenancy/resource-utils';


/**
 * Where components need to be bound to the Redux state, generate the connectors
 */

const ConnectedNav = connect(
    (state) => ({
        initialising: state.session.initialising,
        username: state.session.username,
        tenancies: state.tenancies.data,
        currentTenancy: state.tenancies.current,
        cloudsFetching: state.clouds.fetching,
        clouds: state.clouds.available_clouds,
        currentCloud: state.clouds.current_cloud,
        links: state.clouds.links
    })
)(Navigation);


const ConnectedNotifications = connect(
    (state) => ({ notifications: state.notifications }),
    (dispatch) => ({
        notificationActions: bindActionCreators(notificationActions, dispatch)
    })
)(Notifications);


const ConnectedSplashPage = connect(
    (state) => ({
        cloudsFetching: state.clouds.fetching,
        clouds: state.clouds.available_clouds,
        currentCloud: state.clouds.current_cloud,
        links: state.clouds.links
    })
)(SplashPage);


const ConnectedTenanciesPage = connect(
    (state) => ({ tenancies: state.tenancies }),
)(TenanciesPage);


const ConnectedTenancyResourcePage = connect(
    (state) => ({
        capabilities: state.session.capabilities,
        sshKey: state.sshKey,
        tenancies: state.tenancies
    }),
    (dispatch) => ({
        tenancyActions: {
            idp: bindActionCreators(tenancyActions.idp, dispatch),
            quota: bindActionCreators(tenancyActions.quota, dispatch),
            image: bindActionCreators(tenancyActions.image, dispatch),
            size: bindActionCreators(tenancyActions.size, dispatch),
            externalIp: bindActionCreators(tenancyActions.externalIp, dispatch),
            volume: bindActionCreators(tenancyActions.volume, dispatch),
            machine: bindActionCreators(tenancyActions.machine, dispatch),
            kubernetesClusterTemplate: bindActionCreators(
                tenancyActions.kubernetesClusterTemplate,
                dispatch
            ),
            kubernetesCluster: bindActionCreators(tenancyActions.kubernetesCluster, dispatch),
            kubernetesAppTemplate: bindActionCreators(
                tenancyActions.kubernetesAppTemplate,
                dispatch
            ),
            kubernetesApp: bindActionCreators(tenancyActions.kubernetesApp, dispatch),
            clusterType: bindActionCreators(tenancyActions.clusterType, dispatch),
            cluster: bindActionCreators(tenancyActions.cluster, dispatch)
        },
        notificationActions: bindActionCreators(notificationActions, dispatch),
        sshKeyActions: bindActionCreators(sshKeyActions, dispatch)
    })
)(props => {
    const { resource: matchedResource } = useParams();

    const tenancyActions = props.tenancyActions;
    const currentTenancy = props.tenancies.current;

    // Bind actions to current tenancy here rather than within TenancyResourcePage
    // so that we can conditionally render the tenancy resource page based on
    // whether platforms usage is restricted or not within the given tenancy.
    return <TenancyResourcePage
        {...props}
        resource={matchedResource}
        tenancyActions={{
            idp: bindArgsToActions(tenancyActions.idp, currentTenancy.id),
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
            kubernetesAppTemplate: bindArgsToActions(
                tenancyActions.kubernetesAppTemplate,
                currentTenancy.id
            ),
            kubernetesApp: bindArgsToActions(
                tenancyActions.kubernetesApp,
                currentTenancy.id
            ),
            clusterType: bindArgsToActions(tenancyActions.clusterType, currentTenancy.id),
            cluster: bindArgsToActions(tenancyActions.cluster, currentTenancy.id)
        }}
    />;
});


const NotFound = connect(
    undefined,
    (dispatch) => ({
        notificationActions: bindActionCreators(notificationActions, dispatch)
    })
)(({ notificationActions }) => {
    notificationActions.error({
        title: 'Not Found',
        message: 'The page you requested was not found.'
    });
    return <Navigate to="/tenancies" />;
});


const RedirectToLogin = () => {
    useEffect(
        () => {
            // When the component mounts, redirect to the login page and come back
            // to the current page on a successful authentication
            window.location.replace(`/auth/login/?next=${window.location.pathname}`);
        },
        // No dependencies as we just want to run on first render
        []
    );
    // There is nothing to render
    return null;
}


const Protected = connect(
    (state) => ({ session: state.session })
)(({ children , session }) => {
    if (session.username) return children;
    else if (session.initialising) return null;
    else return <RedirectToLogin />;
});


/**
 * This component does two things:
 *
 *   1. Ensures that the tenancy matched by the URL exists, and redirects to selection if not
 *   2. Ensures that the tenancy matched by the URL is the currently loaded tenancy
 */
const EnsureTenancy = connect(
    (state) => ({ tenancies: state.tenancies }),
    (dispatch) => ({
        switchTenancy: tenancyId => dispatch(tenancyActions.switchTo(tenancyId)),
        notificationActions: bindActionCreators(notificationActions, dispatch),
    })
)(({
    children,
    tenancies: { fetching, data: tenancies, current: currentTenancy },
    switchTenancy,
    notificationActions
}) => {
    const { id: matchedId } = useParams();
    const currentId = currentTenancy ? currentTenancy.id : null;

    const matchedTenancyExists = (tenancies || {}).hasOwnProperty(matchedId);
    const matchedTenancyLoaded = matchedId === currentId;

    useEffect(
        () => {
            // If we are still fetching, then wait
            if( fetching ) return;
            // If the matched tenancy doesn't exist, raise a notification
            if( !matchedTenancyExists ) notificationActions.error({
                title: 'Not Found',
                message: `Tenancy '${matchedId}' does not exist.`
            });
            // If we need to switch tenancy, do that
            if( !matchedTenancyLoaded ) switchTenancy(matchedId);
        },
        [fetching, matchedTenancyExists, matchedTenancyLoaded]
    );

    if( matchedTenancyExists && matchedTenancyLoaded ) {
        return children;
    }
    else if( fetching ) {
        return (
            <Row className="justify-content-center">
                <Col xs="auto" className="mt-5">
                    <Loading iconSize="lg" size="lg" message="Loading tenancies..." />
                </Col>
            </Row>
        );
    }
    else if( !matchedTenancyExists ) {
        return <Navigate to="/tenancies" />;
    }
    else {
        // A switch has been requested - there is nothing to render
        return null;
    }
});


const RedirectToDefaultResource = connect(
    (state) => ({
        capabilities: state.session.capabilities,
        tenancies: state.tenancies,
        tenancyActions: state.tenancyActions,
    }),
)(({ capabilities, tenancies: { current: currentTenancy }, dispatch }) => {

    // We need to be able to dispatch calls to ClusterType and Kubernetes template lists
    // here to decide whether 'platforms' or 'machines' should be default resource.
    useResourceInitialised(
        currentTenancy.kubernetesClusterTemplates,
        () => dispatch(tenancyActions.kubernetesClusterTemplate.fetchList(currentTenancy.id))
    );
    useResourceInitialised(
        currentTenancy.clusterTypes,
        () => dispatch(tenancyActions.clusterType.fetchList(currentTenancy.id))
    );

    if (currentTenancy.clusterTypes.initialised && currentTenancy.kubernetesClusterTemplates.initialised) {

        const kubernetesClusterTemplatesAvailable = Object.getOwnPropertyNames(currentTenancy.kubernetesClusterTemplates.data).length > 0;
        const clusterTypesAvailable = Object.getOwnPropertyNames(currentTenancy.clusterTypes.data).length > 0;

        const defaultResource = (
            capabilities.supports_clusters || capabilities.supports_kubernetes ?
                ((kubernetesClusterTemplatesAvailable || clusterTypesAvailable) ? 'platforms' : 'machines') :
                'quotas'
        );
        return <Navigate to={`/tenancies/${currentTenancy.id}/${defaultResource}`} />;
    } else {
        return (
            <Row className="justify-content-center">
                <Col xs="auto py-5" className="mt-5">
                    <Loading iconSize="lg" size="lg" message="Loading..." />
                </Col>
            </Row>
        );
    }
});


export const Application = () => (
    <div className="sticky-footer-wrap">
        <div className="sticky-footer-content d-flex flex-column">
            <ConnectedNav />
            <ConnectedNotifications />
            <Routes>
                <Route index element={<ConnectedSplashPage />} />
                <Route
                    path="/tenancies/:id/:resource"
                    element={
                        <Protected>
                            <EnsureTenancy>
                                <ConnectedTenancyResourcePage />
                            </EnsureTenancy>
                        </Protected>
                    }
                />
                <Route
                    path="/tenancies/:id"
                    element={
                        <Protected>
                            <EnsureTenancy>
                                <RedirectToDefaultResource />
                            </EnsureTenancy>
                        </Protected>
                    }
                />
                <Route
                    path="/tenancies"
                    element={<Protected><ConnectedTenanciesPage /></Protected>}
                />
                <Route path="*" element={<NotFound />} />
            </Routes>
        </div>
        <Footer />
    </div>
);
