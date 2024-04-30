/**
 * This module contains Redux bits for loading clusters sizes.
 */

import { DateTime } from 'luxon';

import { createTenancyResource, nextStateEntry } from './resource';


const transformSchedule = schedule => ({
    ...schedule,
    end_time: DateTime.fromISO(schedule.end_time)
});


const {
    actions: resourceActions,
    actionCreators: resourceActionCreators,
    reducer: resourceReducer,
    epic
} = createTenancyResource('kubernetes_cluster', {
    // Mark clusters with an in-progress operation as active
    // Also mark unhealthy clusters as active if autohealing is enabled as there is a
    // high likelihood that a remediation will start soon
    isActive: cluster => (
        ["Reconciling", "Upgrading", "Deleting"].includes(cluster.status) ||
        (cluster.status === "Unhealthy" && cluster.autohealing_enabled)
    ),
    // Just convert the string dates to Date objects
    transform: cluster => ({
        ...cluster,
        nodes: cluster.nodes.map(
            node => ({
                ...node,
                created_at: DateTime.fromISO(node.created_at),
            })
        ),
        created_at: DateTime.fromISO(cluster.created_at),
        updated_at: !!cluster.updated_at ? DateTime.fromISO(cluster.updated_at) : undefined,
        schedule: !!cluster.schedule ? transformSchedule(cluster.schedule) : null
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
