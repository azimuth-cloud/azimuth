/**
 * This module manages the Redux state for tenancy identity providers.
 */

import { of } from 'rxjs';
import { filter, map, merge, mergeMap, delay, takeUntil } from 'rxjs/operators';

import { combineEpics, ofType } from 'redux-observable';

import { actions as sessionActions } from '../session';
import { actions as tenancyActions } from './index';
import { actions as clusterActions } from './clusters';
import { actions as kubernetesAppActions } from './kubernetes-apps';
import { actions as kubernetesClusterActions } from './kubernetes-clusters';


export const actions = {
    FETCH: 'TENANCIES/IDENTITY_PROVIDER/FETCH',
    FETCH_SUCCEEDED: 'TENANCIES/IDENTITY_PROVIDER/FETCH_SUCCEEDED',
    FETCH_FAILED: 'TENANCIES/IDENTITY_PROVIDER/FETCH_FAILED',

    ENABLE: 'TENANCIES/IDENTITY_PROVIDER/ENABLE',
    ENABLE_SUCCEEDED: 'TENANCIES/IDENTITY_PROVIDER/ENABLE_SUCCEEDED',
    ENABLE_FAILED: 'TENANCIES/IDENTITY_PROVIDER/ENABLE_FAILED',
};


export const actionCreators = {
    fetch: tenancyId => ({
        type: actions.FETCH,
        tenancyId,
        apiRequest: true,
        // Let loading errors fail silently
        failSilently: true,
        successAction: actions.FETCH_SUCCEEDED,
        failureAction: actions.FETCH_FAILED,
        options: { url: `/api/tenancies/${tenancyId}/identity_provider/` }
    }),
    enable: tenancyId => ({
        type: actions.ENABLE,
        tenancyId,
        apiRequest: true,
        successAction: actions.ENABLE_SUCCEEDED,
        failureAction: actions.ENABLE_FAILED,
        options: {
            url: `/api/tenancies/${tenancyId}/identity_provider/`,
            method: 'POST'
        }
    }),
};


const initialState = {
    initialised: false, // This becomes true after the first successful fetch
    fetching: false,
    updating: false,
    enabled: false,
    status: null,
    admin_url: null,
    fetchError: null,
};

export function reducer(state = initialState, action) {
    switch(action.type) {
        case actions.FETCH:
            return { ...state, fetching: true };
        case actions.FETCH_SUCCEEDED:
            return {
                ...state,
                status: null,
                admin_url: null,
                ...action.payload,
                initialised: true,
                fetching: false,
                fetchError: null
            };
        case actions.FETCH_FAILED:
            return { ...state, fetching: false, fetchError: action.payload };
        case actions.ENABLE:
            return { ...state, updating: true };
        case actions.ENABLE_SUCCEEDED:
            return { ...state, ...action.payload, updating: false };
        case actions.ENABLE_FAILED:
            return { ...state, updating: false };
        default:
            return state;
    }
}


/**
 * The redux-observable epic for the IDP state
 */
export const epic = combineEpics(
    // Whenever the IDP is fetched successfully, wait 5 min before fetching it again
    action$ => action$.pipe(
        ofType(actions.FETCH_SUCCEEDED),
        mergeMap(action => {
            const tenancyId = action.request.tenancyId;
            // Cancel the timer if:
            //   * A separate fetch is requested before the timer expires
            //   * The session is terminated before the timer expires
            //   * A switch takes place to a different tenancy before the timer expires
            return of(actionCreators.fetch(tenancyId)).pipe(
                delay(300000),
                takeUntil(
                    action$.pipe(
                        ofType(actions.FETCH),
                        filter(action => action.tenancyId === tenancyId),
                        merge(action$.pipe(ofType(sessionActions.TERMINATED))),
                        merge(
                            action$.pipe(
                                ofType(tenancyActions.SWITCH),
                                filter(action => action.tenancyId !== tenancyId)
                            )
                        )
                    )
                )
            );
        })
    ),
    // When the IDP is fetched or updated and is enabled but not ready, reload it
    action$ => action$.pipe(
        ofType(actions.FETCH_SUCCEEDED),
        merge(action$.pipe(ofType(actions.ENABLE_SUCCEEDED))),
        filter(action => action.payload.enabled && action.payload.status !== "Ready"),
        mergeMap(action => {
            const tenancyId = action.request.tenancyId;
            // Cancel the timer if:
            //   * A fetch for the IDP is requested before the timer expires
            //   * The session is terminated while we are waitinge
            //   * A switch takes place to a different tenancy before the timer expires
            return of(actionCreators.fetch(tenancyId)).pipe(
                delay(5000),
                takeUntil(
                    action$.pipe(
                        ofType(actions.FETCH),
                        filter(action => action.tenancyId === tenancyId),
                        merge(action$.pipe(ofType(sessionActions.TERMINATED))),
                        merge(
                            action$.pipe(
                                ofType(tenancyActions.SWITCH),
                                filter(action => action.tenancyId !== tenancyId)
                            )
                        )
                    )
                )
            );
        })
    ),
    // When a platform creation succeeds, that might trigger the identity provider
    // to be enabled, so refresh
    action$ => action$.pipe(
        ofType(clusterActions.CREATE_SUCCEEDED),
        merge(action$.pipe(ofType(kubernetesAppActions.CREATE_SUCCEEDED))),
        merge(action$.pipe(ofType(kubernetesClusterActions.CREATE_SUCCEEDED))),
        map(action => actionCreators.fetch(action.request.tenancyId))
    ),
);
