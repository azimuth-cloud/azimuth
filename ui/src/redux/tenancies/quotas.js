/**
 * This module contains Redux bits for loading tenancy quotas.
 */

import { merge, filter, map } from 'rxjs/operators';

import { combineEpics, ofType } from 'redux-observable';

import { StatusCodes } from 'http-status-codes';

import { createTenancyResource } from './resource';

import { actions as externalIpActions } from './external-ips';
import { actions as volumeActions } from './volumes';
import { actions as machineActions } from './machines';


const {
    actions,
    actionCreators,
    reducer,
    epic: resourceEpic
} = createTenancyResource('quota', { id: quota => quota.resource });


export { actions, actionCreators, reducer };

export const epic = combineEpics(
    resourceEpic,
    // When an action takes place that might effect the quotas, refresh them
    action$ => action$.pipe(
        ofType(externalIpActions.CREATE_SUCCEEDED),
        merge(action$.pipe(ofType(volumeActions.CREATE_SUCCEEDED))),
        merge(action$.pipe(ofType(volumeActions.DELETE_SUCCEEDED))),
        merge(action$.pipe(ofType(machineActions.CREATE_SUCCEEDED))),
        merge(action$.pipe(ofType(machineActions.DELETE_SUCCEEDED))),
        // Also consider a failed FETCH_ONE, as this might signify that a resource
        // was in a "deleting" phase that has now completed
        merge(action$.pipe(
            ofType(externalIpActions.FETCH_ONE_FAILED),
            merge(action$.pipe(ofType(volumeActions.FETCH_ONE_FAILED))),
            merge(action$.pipe(ofType(machineActions.FETCH_ONE_FAILED))),
            filter(action => action.payload.statusCode === StatusCodes.NOT_FOUND)
        )),
        map(action => actionCreators.fetchList(action.request.tenancyId))
    )
);
