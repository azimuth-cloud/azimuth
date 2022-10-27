/**
 * This module contains Redux bits for loading Kubernetes apps.
 */

import { merge, filter, map } from 'rxjs/operators';

import { combineEpics, ofType } from 'redux-observable';

import { StatusCodes } from 'http-status-codes';

import { DateTime } from 'luxon';

import { createTenancyResource } from './resource';

import { actions as kubernetesClusterActions } from './kubernetes-clusters';


const {
    actions,
    actionCreators,
    reducer,
    epic: resourceEpic
} = createTenancyResource('kubernetes_app', {
    // Mark clusters with an in-progress operation as active
    // Also mark unhealthy clusters as active if autohealing is enabled as there is a
    // high likelihood that a remediation will start soon
    isActive: app => app.status.endsWith("ing"),
    // Just convert the string dates to Date objects
    transform: app => ({
        ...app,
        created_at: DateTime.fromISO(app.created_at)
    })
});


export { actions, actionCreators, reducer };

export const epic = combineEpics(
    resourceEpic,
    // When a Kubernetes cluster disappears, refresh the apps
    action$ => action$.pipe(
        ofType(kubernetesClusterActions.FETCH_ONE_FAILED),
        filter(action => action.payload.statusCode === StatusCodes.NOT_FOUND),
        map(action => actionCreators.fetchList(action.request.tenancyId))
    )
);
