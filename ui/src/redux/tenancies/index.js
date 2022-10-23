/**
 * This module contains Redux stuff for loading tenancies.
 */

import { of, merge } from 'rxjs';
import { map, mergeMap, delay, takeUntil, filter, withLatestFrom, partition } from 'rxjs/operators';

import get from 'lodash/get';

import { combineEpics, ofType } from 'redux-observable';

import { actions as sessionActions } from '../session';

import {
    actionCreators as quotaActionCreators,
    reducer as quotaReducer,
    epic as quotaEpic
} from './quotas';

import {
    actionCreators as imageActionCreators,
    reducer as imageReducer,
    epic as imageEpic
} from './images';

import {
    actionCreators as sizeActionCreators,
    reducer as sizeReducer,
    epic as sizeEpic
} from './sizes';

import {
    actionCreators as externalIpActionCreators,
    reducer as externalIpReducer,
    epic as externalIpEpic
} from './external-ips';

import {
    actionCreators as volumeActionCreators,
    reducer as volumeReducer,
    epic as volumeEpic
} from './volumes';

import {
    actionCreators as machineActionCreators,
    reducer as machineReducer,
    epic as machineEpic
} from './machines';

import {
    actionCreators as kubernetesClusterTemplateActionCreators,
    reducer as kubernetesClusterTemplateReducer,
    epic as kubernetesClusterTemplateEpic
} from './kubernetes-cluster-templates';

import {
    actionCreators as kubernetesClusterActionCreators,
    reducer as kubernetesClusterReducer,
    epic as kubernetesClusterEpic
} from './kubernetes-clusters';

import {
    actionCreators as kubernetesAppTemplateActionCreators,
    reducer as kubernetesAppTemplateReducer,
    epic as kubernetesAppTemplateEpic
} from './kubernetes-app-templates';

import {
    actionCreators as kubernetesAppActionCreators,
    reducer as kubernetesAppReducer,
    epic as kubernetesAppEpic
} from './kubernetes-apps';

import {
    actionCreators as clusterTypeActionCreators,
    reducer as clusterTypeReducer,
    epic as clusterTypeEpic
} from './cluster-types';

import {
    actionCreators as clusterActionCreators,
    reducer as clusterReducer,
    epic as clusterEpic
} from './clusters';


export const actions = {
    RESET: 'TENANCIES/RESET',

    FETCH_LIST: 'TENANCIES/FETCH_LIST',
    FETCH_LIST_SUCCEEDED: 'TENANCIES/FETCH_LIST_SUCCEEDED',
    FETCH_LIST_FAILED: 'TENANCIES/FETCH_LIST_FAILED',

    // Action that triggers a tenancy switch
    SWITCH: 'TENANCIES/SWITCH',
};


const tenancyActionCreators = {
    reset: () => ({ type: actions.RESET }),
    fetchList: () => ({
        type: actions.FETCH_LIST,
        apiRequest: true,
        successAction: actions.FETCH_LIST_SUCCEEDED,
        failureAction: actions.FETCH_LIST_FAILED,
        options: { url: '/api/tenancies/' }
    }),
    switchTo: (tenancyId) => ({
        type: actions.SWITCH,
        tenancyId
    })
}

export const actionCreators = {
    ...tenancyActionCreators,
    quota: quotaActionCreators,
    image: imageActionCreators,
    size: sizeActionCreators,
    externalIp: externalIpActionCreators,
    volume: volumeActionCreators,
    machine: machineActionCreators,
    kubernetesClusterTemplate: kubernetesClusterTemplateActionCreators,
    kubernetesCluster: kubernetesClusterActionCreators,
    kubernetesAppTemplate: kubernetesAppTemplateActionCreators,
    kubernetesApp: kubernetesAppActionCreators,
    clusterType: clusterTypeActionCreators,
    cluster: clusterActionCreators
}


// Initially, fetching is set to true since we assume the first thing we will do
// when possible is fetch the tenancy data
const initialState = {
    fetching: true,
    data: null,
    current: null
};
export function reducer(state = initialState, action) {
    switch(action.type) {
        case actions.RESET:
            return initialState;
        case actions.FETCH_LIST:
            return { ...state, fetching: true };
        case actions.FETCH_LIST_SUCCEEDED:
            // As well as updating the list, also update the current tenancy
            const nextData = Object.assign({}, ...action.payload.map(t => ({ [t.id]: t })));
            return {
                ...state,
                fetching: false,
                data: nextData,
                current: state.current !== null ?
                    { ...state.current, ...get(nextData, state.current.id, {}) } :
                    null
            };
        case actions.FETCH_LIST_FAILED:
            return { ...state, fetching: false };
        case actions.SWITCH:
            const switchTo = action.tenancyId;
            // Giving switchTo as null means clear the current tenancy
            if( switchTo === null ) return { ...state, current: null };
            // If we are already on the tenancy, do nothing
            if( switchTo === get(state.current, 'id') ) return state;
            // If the tenancy is not in the data, do nothing
            if( !(state.data || {}).hasOwnProperty(switchTo) ) return state;
            return {
                ...state,
                current: {
                    ...state.data[switchTo],
                    quotas: quotaReducer(undefined, action),
                    images: imageReducer(undefined, action),
                    sizes: sizeReducer(undefined, action),
                    externalIps: externalIpReducer(undefined, action),
                    volumes: volumeReducer(undefined, action),
                    machines: machineReducer(undefined, action),
                    kubernetesClusterTemplates: kubernetesClusterTemplateReducer(undefined, action),
                    kubernetesClusters: kubernetesClusterReducer(undefined, action),
                    kubernetesAppTemplates: kubernetesAppTemplateReducer(undefined, action),
                    kubernetesApps: kubernetesAppReducer(undefined, action),
                    clusterTypes: clusterTypeReducer(undefined, action),
                    clusters: clusterReducer(undefined, action)
                }
            };
        default:
            // If the action is associated with the current tenancy, apply the resource reducers
            if( state.current === null ) return state;
            const tenancyId = action.tenancyId || get(action, 'request.tenancyId');
            if( tenancyId !== state.current.id ) return state;
            return {
                ...state,
                current: {
                    ...state.current,
                    quotas: quotaReducer(state.current.quotas, action),
                    images: imageReducer(state.current.images, action),
                    sizes: sizeReducer(state.current.sizes, action),
                    externalIps: externalIpReducer(state.current.externalIps, action),
                    volumes: volumeReducer(state.current.volumes, action),
                    machines: machineReducer(state.current.machines, action),
                    kubernetesClusterTemplates: kubernetesClusterTemplateReducer(
                        state.current.kubernetesClusterTemplates,
                        action
                    ),
                    kubernetesClusters: kubernetesClusterReducer(
                        state.current.kubernetesClusters,
                        action
                    ),
                    kubernetesAppTemplates: kubernetesAppTemplateReducer(
                        state.current.kubernetesAppTemplates,
                        action
                    ),
                    kubernetesApps: kubernetesAppReducer(
                        state.current.kubernetesApps,
                        action
                    ),
                    clusterTypes: clusterTypeReducer(state.current.clusterTypes, action),
                    clusters: clusterReducer(state.current.clusters, action)
                }
            };
    }
}


export const epic = combineEpics(
    // When a session is started, load the tenancy list
    action$ => action$.pipe(
        ofType(sessionActions.INITIALISATION_SUCCEEDED),
        map(_ => tenancyActionCreators.fetchList())
    ),
    // Whenever the tenancy list is fetched successfully, wait 30 mins
    // before fetching them again
    action$ => action$.pipe(
        ofType(actions.FETCH_LIST_SUCCEEDED),
        mergeMap(_ => {
            // Cancel the timer if:
            //   * A separate fetch is requested before the timer expires
            //   * The session is terminated before the timer expires
            return of(tenancyActionCreators.fetchList()).pipe(
                delay(30 * 60 * 1000),
                takeUntil(
                    merge(
                        action$.pipe(ofType(actions.FETCH_LIST)),
                        action$.pipe(ofType(sessionActions.TERMINATED))
                    )
                )
            );
        })
    ),
    // When a session is terminated, reset the tenancy data
    action$ => action$.pipe(
        ofType(sessionActions.TERMINATED),
        map(_ => tenancyActionCreators.reset())
    ),
    // Whenever a tenancy switch happens to a tenancy that is not in the current
    // state, force a switch to no tenancy
    (action$, state$) => action$.pipe(
        ofType(actions.SWITCH),
        filter(action => !!action.tenancyId),
        withLatestFrom(state$),
        filter(([action, state]) => !(state.tenancies.data || {}).hasOwnProperty(action.tenancyId)),
        map(_ => tenancyActionCreators.switchTo(null))
    ),
    quotaEpic,
    imageEpic,
    sizeEpic,
    externalIpEpic,
    volumeEpic,
    machineEpic,
    kubernetesClusterTemplateEpic,
    kubernetesClusterEpic,
    kubernetesAppTemplateEpic,
    kubernetesAppEpic,
    clusterTypeEpic,
    clusterEpic
);
