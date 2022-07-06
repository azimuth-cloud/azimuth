/**
 * Module containing the root application component.
 */

import React, { useEffect } from 'react';

import Container from 'react-bootstrap/Container';

import { Switch, Route, Redirect } from 'react-router-dom';

import { bindActionCreators } from 'redux';
import { connect } from 'react-redux';

import { actionCreators as sshKeyActions } from './redux/ssh-public-key';
import { actionCreators as tenancyActions } from './redux/tenancies';
import { actionCreators as notificationActions } from './redux/notifications';

import { Navigation } from './components/navigation';
import { Notifications } from './components/notifications';
import { SplashPage } from './components/pages/splash';
import { TenanciesPage } from './components/pages/tenancies';
import { TenancyPage } from './components/pages/tenancy';


/**
 * Where components need to be bound to the Redux state, generate the connectors
 */

const ConnectedNav = connect(
    (state) => ({
        initialising: state.session.initialising,
        username: state.session.username,
        sshKey: state.sshKey,
        tenancies: state.tenancies.data,
        currentTenancy: state.tenancies.current,
        cloudsFetching: state.clouds.fetching,
        clouds: state.clouds.available_clouds,
        currentCloud: state.clouds.current_cloud,
        links: state.clouds.links
    }),
    (dispatch) => ({
        sshKeyActions: bindActionCreators(sshKeyActions, dispatch)
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


const ConnectedTenancyPage = connect(
    (state) => ({
        capabilities: state.session.capabilities,
        sshKey: state.sshKey,
        tenancies: state.tenancies
    }),
    (dispatch) => ({
        tenancyActions: {
            switchTo: (tenancyId) => dispatch(tenancyActions.switchTo(tenancyId)),
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
            kubernetesCluster: bindActionCreators(
                tenancyActions.kubernetesCluster,
                dispatch
            ),
            clusterType: bindActionCreators(tenancyActions.clusterType, dispatch),
            cluster: bindActionCreators(tenancyActions.cluster, dispatch)
        },
        notificationActions: bindActionCreators(notificationActions, dispatch)
    })
)(TenancyPage);


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
    return <Redirect to="/tenancies" />;
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


const ProtectedRoute = connect(
    (state) => ({ session: state.session })
)(({ component: Component, session, ...rest }) => (
    <Route
        {...rest}
        render={props => {
            if( session.username ) return <Component {...props} />;
            else if( session.initialising ) return null;
            else return <RedirectToLogin />;
        }}
    />
));


export const Application = () => (
    <>
        <ConnectedNav />
        <Container>
            <ConnectedNotifications />
            <Switch>
                <Route exact path="/" component={ConnectedSplashPage} />
                <ProtectedRoute
                    exact
                    path="/tenancies"
                    component={ConnectedTenanciesPage}
                />
                <ProtectedRoute
                    path="/tenancies/:id/:resource?"
                    component={ConnectedTenancyPage}
                />
                <Route component={NotFound} />
            </Switch>
        </Container>
    </>
);
