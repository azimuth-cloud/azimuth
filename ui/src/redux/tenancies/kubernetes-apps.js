/**
 * This module contains Redux bits for loading Kubernetes apps.
 */

import { createTenancyResource } from './resource';


const {
    actions,
    actionCreators,
    reducer,
    epic,
} = createTenancyResource('kubernetes_app', {
    // Mark clusters with an in-progress operation as active
    // Also mark unhealthy clusters as active if autohealing is enabled as there is a
    // high likelihood that a remediation will start soon
    isActive: app => app.status.endsWith("ing"),
    // Just convert the string dates to Date objects
    transform: app => ({
        ...app,
        created_at: new Date(app.created_at)
    })
});


export { actions, actionCreators, reducer, epic };
