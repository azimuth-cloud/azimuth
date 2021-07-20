/**
 * This module contains Redux bits for loading clusters sizes.
 */

import { createTenancyResource, nextStateEntry } from './resource';


const {
    actions: resourceActions,
    actionCreators: resourceActionCreators,
    reducer: resourceReducer,
    epic
} = createTenancyResource('kubernetes_cluster', {
    isActive: cluster => cluster.status.endsWith("_IN_PROGRESS"),
    // Just convert the string dates to Date objects
    transform: cluster => ({
        ...cluster,
        created_at: new Date(cluster.created_at),
        updated_at: !!cluster.updated_at ? new Date(cluster.updated_at) : undefined
    })
});


const actions = {
    ...resourceActions,

    GENERATE_KUBECONFIG: 'TENANCIES/KUBERNETES_CLUSTER/GENERATE_KUBECONFIG',
    GENERATE_KUBECONFIG_SUCCEEDED: 'TENANCIES/KUBERNETES_CLUSTER/GENERATE_KUBECONFIG_SUCCEEDED',
    GENERATE_KUBECONFIG_FAILED: 'TENANCIES/KUBERNETES_CLUSTER/GENERATE_KUBECONFIG_FAILED',
};


const actionCreators = {
    ...resourceActionCreators,

    generateKubeconfig: (tenancyId, clusterId) => ({
        type: actions.GENERATE_KUBECONFIG,
        tenancyId,
        clusterId,
        apiRequest: true,
        // All errors are reported via the modal UI
        failSilently: true,
        successAction: actions.GENERATE_KUBECONFIG_SUCCEEDED,
        failureAction: actions.GENERATE_KUBECONFIG_FAILED,
        options: {
            url: `/api/tenancies/${tenancyId}/kubernetes_clusters/${clusterId}/kubeconfig/`,
            method: 'POST'
        }
    })
};


const reducer = (state, action) => {
    switch(action.type) {
        case actions.GENERATE_KUBECONFIG:
            if( state.data.hasOwnProperty(action.clusterId) )
                return {
                    ...state,
                    data: Object.assign(
                        {},
                        state.data,
                        nextStateEntry(
                            state,
                            action.clusterId,
                            { generatingKubeconfig: true }
                        )
                    ),
                };
            else
                return state;
        case actions.GENERATE_KUBECONFIG_SUCCEEDED:
            return {
                ...state,
                data: Object.assign(
                    {},
                    state.data,
                    nextStateEntry(
                        state,
                        action.request.clusterId,
                        {
                            ...action.payload,
                            generatingKubeconfig: false,
                            kubeconfigError: undefined
                        }
                    )
                ),
            };
        case actions.GENERATE_KUBECONFIG_FAILED:
            if( state.data.hasOwnProperty(action.request.clusterId) )
                return {
                    ...state,
                    data: Object.assign(
                        {},
                        state.data,
                        nextStateEntry(
                            state,
                            action.request.clusterId,
                            {
                                generatingKubeconfig: false,
                                kubeconfigError: action.payload
                            }
                        )
                    ),
                };
            else
                return state;
        default:
            // Any other actions, apply the resource reducer
            return resourceReducer(state, action);
    }
};


export { actions, actionCreators, reducer, epic };
