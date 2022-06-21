/**
 * This module contains Redux bits for loading clusters sizes.
 */

import { map } from 'rxjs/operators';

import { combineEpics, ofType } from 'redux-observable';

import { createTenancyResource, nextStateEntry } from './resource';


const {
    actions: resourceActions,
    actionCreators: resourceActionCreators,
    reducer: resourceReducer,
    epic: resourceEpic
} = createTenancyResource('cluster', {
    isActive: cluster => ['CONFIGURING', 'DELETING'].includes(cluster.status),
    // Just convert the string dates to Date objects
    transform: cluster => ({
        ...cluster,
        created: !!cluster.created ? new Date(cluster.created) : undefined,
        updated: !!cluster.updated ? new Date(cluster.updated) : undefined,
        patched: !!cluster.patched ? new Date(cluster.patched) : undefined
    })
});


export const actions = {
    ...resourceActions,

    PATCH: 'TENANCIES/CLUSTER/PATCH',
    PATCH_SUCCEEDED: 'TENANCIES/CLUSTER/PATCH_SUCCEEDED',
    PATCH_FAILED: 'TENANCIES/CLUSTER/PATCH_FAILED',
};


export const actionCreators = {
    ...resourceActionCreators,

    patch: (tenancyId, clusterId) => ({
        type: actions.PATCH,
        tenancyId,
        clusterId,
        apiRequest: true,
        successAction: actions.PATCH_SUCCEEDED,
        failureAction: actions.PATCH_FAILED,
        options: {
            url: `/api/tenancies/${tenancyId}/clusters/${clusterId}/patch/`,
            method: 'POST'
        }
    })
};


export function reducer(state, action) {
    switch(action.type) {
        case actions.PATCH:
            // Only set the updating flag to true if we know about the cluster
            if( state.data.hasOwnProperty(action.clusterId) )
                return {
                    ...state,
                    data: Object.assign(
                        {},
                        state.data,
                        nextStateEntry(
                            state,
                            action.clusterId,
                            { patching: true }
                        )
                    ),
                };
            else
                return state;
        case actions.PATCH_SUCCEEDED:
            // The patched cluster is in the payload, so merge it
            return {
                ...state,
                data: Object.assign(
                    {},
                    state.data,
                    nextStateEntry(
                        state,
                        action.payload.id,
                        { ...action.payload, patching: false }
                    )
                ),
            };
        case actions.PATCH_FAILED:
            // Only set the updating flag to false if we know about the cluster
            if( state.data.hasOwnProperty(action.request.clusterId) )
                return {
                    ...state,
                    data: Object.assign(
                        {},
                        state.data,
                        nextStateEntry(
                            state,
                            action.request.clusterId,
                            { patching: false }
                        )
                    ),
                };
            else
                return state;
        default:
            // Any other actions, apply the resource reducer
            return resourceReducer(state, action);
    }
}


export const epic = combineEpics(
    resourceEpic,
    // When a patch takes place on a cluster, refresh it
    action$ => action$.pipe(
        ofType(actions.PATCH_SUCCEEDED),
        map(action =>
            actionCreators.fetchOne(action.request.tenancyId, action.payload.id)
        )
    )
);
