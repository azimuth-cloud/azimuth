/**
 * This module contains Redux bits for loading tenancy external ips.
 */

import { map, merge, filter } from 'rxjs/operators';

import { combineEpics, ofType } from 'redux-observable';

import { StatusCodes } from 'http-status-codes';

import { createTenancyResource } from './resource';

import { actions as machineActions } from './machines';


const {
    actions,
    actionCreators,
    reducer,
    epic: resourceEpic,
} = createTenancyResource('external_ip');


const epic = combineEpics(
    resourceEpic,
    // An update of an external IP record may affect others, so refresh the
    // whole list
    action$ => action$.pipe(
        ofType(actions.UPDATE_SUCCEEDED),
        map(action => actionCreators.fetchList(action.request.tenancyId))
    ),
    // When a machine is deleted or a fetch fails with a 404, refresh the IP list
    // in case it had an external IP
    action$ => action$.pipe(
        ofType(machineActions.DELETE_SUCCEEDED),
        merge(action$.pipe(
            ofType(machineActions.FETCH_ONE_FAILED),
            filter(action => action.payload.statusCode === StatusCodes.NOT_FOUND)
        )),
        map(action => actionCreators.fetchList(action.request.tenancyId))
    )
);


export { actions, actionCreators, reducer, epic };
