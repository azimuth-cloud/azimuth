/**
 * This module contains utilities to build actions, reducers and epics for
 * tenancy resources.
 */

import { of } from 'rxjs';
import { filter, map, merge, mergeMap, delay, takeUntil } from 'rxjs/operators';

import { combineEpics, ofType } from 'redux-observable';

import { StatusCodes } from 'http-status-codes';

import { actions as sessionActions } from '../session';
import { actions as tenancyActions } from './index';


export function createActions(resourceName) {
    const prefix = `TENANCIES/${resourceName.toUpperCase()}`
    return {
        FETCH_LIST: `${prefix}/FETCH_LIST`,
        FETCH_LIST_SUCCEEDED: `${prefix}/FETCH_LIST_SUCCEEDED`,
        FETCH_LIST_FAILED: `${prefix}/FETCH_LIST_FAILED`,

        FETCH_ONE: `${prefix}/FETCH_ONE`,
        FETCH_ONE_SUCCEEDED: `${prefix}/FETCH_ONE_SUCCEEDED`,
        FETCH_ONE_FAILED: `${prefix}/FETCH_ONE_FAILED`,

        CREATE: `${prefix}/CREATE`,
        CREATE_SUCCEEDED: `${prefix}/CREATE_SUCCEEDED`,
        CREATE_FAILED: `${prefix}/CREATE_FAILED`,

        UPDATE: `${prefix}/UPDATE`,
        UPDATE_SUCCEEDED: `${prefix}/UPDATE_SUCCEEDED`,
        UPDATE_FAILED: `${prefix}/UPDATE_FAILED`,

        DELETE: `${prefix}/DELETE`,
        DELETE_SUCCEEDED: `${prefix}/DELETE_SUCCEEDED`,
        DELETE_FAILED: `${prefix}/DELETE_FAILED`,
    };
}


export function createActionCreators(resourceName, actions) {
    const resource = resourceName.toLowerCase();
    return {
        fetchList: tenancyId => ({
            type: actions.FETCH_LIST,
            tenancyId,
            apiRequest: true,
            successAction: actions.FETCH_LIST_SUCCEEDED,
            failureAction: actions.FETCH_LIST_FAILED,
            options: {
                url: `/api/tenancies/${tenancyId}/${resource}s/`
            }
        }),
        fetchOne: (tenancyId, resourceId) => ({
            type: actions.FETCH_ONE,
            tenancyId,
            resourceId,
            apiRequest: true,
            failSilently: true,
            successAction: actions.FETCH_ONE_SUCCEEDED,
            failureAction: actions.FETCH_ONE_FAILED,
            options: {
                url: `/api/tenancies/${tenancyId}/${resource}s/${resourceId}/`
            }
        }),
        create: (tenancyId, data) => ({
            type: actions.CREATE,
            tenancyId,
            apiRequest: true,
            successAction: actions.CREATE_SUCCEEDED,
            failureAction: actions.CREATE_FAILED,
            options: {
                url: `/api/tenancies/${tenancyId}/${resource}s/`,
                method: 'POST',
                body: data || {}
            }
        }),
        update: (tenancyId, resourceId, data) => ({
            type: actions.UPDATE,
            tenancyId,
            resourceId,
            apiRequest: true,
            successAction: actions.UPDATE_SUCCEEDED,
            failureAction: actions.UPDATE_FAILED,
            options: {
                url: `/api/tenancies/${tenancyId}/${resource}s/${resourceId}/`,
                method: 'PUT',
                body: data
            }
        }),
        delete: (tenancyId, resourceId) => ({
            type: actions.DELETE,
            tenancyId,
            resourceId,
            apiRequest: true,
            successAction: actions.DELETE_SUCCEEDED,
            failureAction: actions.DELETE_FAILED,
            options: {
                url: `/api/tenancies/${tenancyId}/${resource}s/${resourceId}/`,
                method: 'DELETE'
            }
        }),
    };
}


/**
 * Create the next state entry for the given set of updates to a resource.
 */
export function nextStateEntry(state, resourceId, updates) {
    const previous = (state.data || {})[resourceId];
    const next = { ...previous, ...updates };
    return { [resourceId]: next };
}

export function createReducer(actions, id, transform) {
    const initialState = {
        initialised: false,
        fetching: false,
        data: null,
        fetchError: null,
        creating: false
    };
    return (state = initialState, action) => {
        switch(action.type) {
            case actions.FETCH_LIST:
                return { ...state, fetching: true };
            case actions.FETCH_LIST_SUCCEEDED:
                return {
                    ...state,
                    initialised: true,
                    fetching: false,
                    data: Object.assign(
                        {},
                        ...action.payload.map(resource =>
                            nextStateEntry(state, id(resource), transform(resource))
                        )
                    ),
                    fetchError: null
                };
            case actions.FETCH_LIST_FAILED:
                return { ...state, fetching: false, fetchError: action.payload };
            case actions.FETCH_ONE_SUCCEEDED:
                return {
                    ...state,
                    data: Object.assign(
                        {},
                        state.data,
                        nextStateEntry(state, id(action.payload), transform(action.payload))
                    )
                };
            case actions.FETCH_ONE_FAILED:
                // If FETCH_ONE fails with a 404, remove the resource from the list
                if( action.payload.statusCode === StatusCodes.NOT_FOUND )
                    return {
                        ...state,
                        data: Object.assign(
                            {},
                            // Compare IDs as strings to avoid any mismatch between int/string
                            ...Object.entries(state.data)
                                .filter(([id, _]) => id.toString() !== action.request.resourceId.toString())
                                .map(([id, resource]) => ({ [id]: resource }))
                        )
                    };
                else
                    return state;
            case actions.CREATE:
                return { ...state, creating: true };
            case actions.CREATE_SUCCEEDED:
                return {
                    ...state,
                    data: Object.assign(
                        {},
                        state.data,
                        nextStateEntry(state, id(action.payload), transform(action.payload))
                    ),
                    creating: false
                };
            case actions.CREATE_FAILED:
                return { ...state, creating: false };
            case actions.UPDATE:
                // Only set the updating flag to true if we know about the object
                if( state.data.hasOwnProperty(action.resourceId) )
                    return {
                        ...state,
                        data: Object.assign(
                            {},
                            state.data,
                            nextStateEntry(state, action.resourceId, { updating: true })
                        ),
                    };
                else
                    return state;
            case actions.UPDATE_SUCCEEDED:
                return {
                    ...state,
                    data: Object.assign(
                        {},
                        state.data,
                        nextStateEntry(
                            state,
                            id(action.payload),
                            { ...transform(action.payload), updating: false }
                        )
                    )
                };
            case actions.UPDATE_FAILED:
                // Only set the updating flag to false if we know about the object
                if( state.data.hasOwnProperty(action.request.resourceId) )
                    return {
                        ...state,
                        data: Object.assign(
                            {},
                            state.data,
                            nextStateEntry(state, action.request.resourceId, { updating: false })
                        ),
                    };
                else
                    return state;
            case actions.DELETE:
                // Only set the deleting flag to true if we know about the object
                if( state.data.hasOwnProperty(action.resourceId) )
                    return {
                        ...state,
                        data: Object.assign(
                            {},
                            state.data,
                            nextStateEntry(state, action.resourceId, { deleting: true })
                        ),
                    };
                else
                    return state;
            case actions.DELETE_SUCCEEDED:
                // When a resource is deleted successfully, how we respond depends
                // on whether the delete returns a payload
                // If the delete doesn't return a payload, we just remove the
                // resource from the list
                if( !action.payload )
                    return {
                        ...state,
                        data: Object.assign(
                            {},
                            ...Object.entries(state.data)
                                .filter(([id, _]) => id !== action.request.resourceId)
                                .map(([id, resource]) => ({ [id]: resource }))
                        )
                    };
                // If the delete does return a payload, we refresh the resource
                // rather than removing it here (see epics below)
                // This is because it might not be deleted straight away, but might
                // change to an interesting state, which will be tracked until the
                // resource disappears (see epics below and FETCH_ONE_FAILED above)
                // We still want to set the deleting flag to false, so utilise
                // fall-through to do that
            case actions.DELETE_FAILED:
                // Only set the deleting flag to false if we know about the object
                if( state.data.hasOwnProperty(action.request.resourceId) )
                    return {
                        ...state,
                        data: Object.assign(
                            {},
                            state.data,
                            nextStateEntry(state, action.request.resourceId, { deleting: false })
                        ),
                    };
                else
                    return state;
            default:
                return state;
        }
    };
}


export function createEpic(actions, actionCreators, isActive, id) {
    return combineEpics(
        // Whenever a resource list is fetched successfully, wait 2 min before fetching it again
        action$ => action$.pipe(
            ofType(actions.FETCH_LIST_SUCCEEDED),
            mergeMap(action => {
                const tenancyId = action.request.tenancyId;
                // Cancel the timer if:
                //   * A separate fetch is requested before the timer expires
                //   * The session is terminated before the timer expires
                //   * A switch takes place to a different tenancy before the timer expires
                return of(actionCreators.fetchList(tenancyId)).pipe(
                    delay(120000),
                    takeUntil(
                        action$.pipe(
                            ofType(actions.FETCH_LIST),
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
        // Whenever a resource list is fetched, trigger an individual fetch for any
        // 'active' resources, as determined by the given predicate
        action$ => action$.pipe(
            ofType(actions.FETCH_LIST_SUCCEEDED),
            mergeMap(action => of(
                ...action.payload
                    .filter(isActive)
                    .map(resource =>
                        actionCreators.fetchOne(action.request.tenancyId, id(resource))
                    )
            ))
        ),
        // When a resource is fetched, created or updated and is active, wait 5s and
        // fetch it again
        action$ => action$.pipe(
            ofType(actions.FETCH_ONE_SUCCEEDED),
            merge(action$.pipe(ofType(actions.CREATE_SUCCEEDED))),
            merge(action$.pipe(ofType(actions.UPDATE_SUCCEEDED))),
            filter(action => isActive(action.payload)),
            mergeMap(action => {
                const tenancyId = action.request.tenancyId;
                const resourceId = id(action.payload);
                // Cancel the timer if:
                //   * A fetch for the same resource is requested before the
                //     timer expires
                //   * The session is terminated while we are waiting
                //   * A switch takes place to a different tenancy before the timer expires
                return of(actionCreators.fetchOne(tenancyId, resourceId)).pipe(
                    delay(5000),
                    takeUntil(
                        action$.pipe(
                            ofType(actions.FETCH_ONE),
                            filter(action => action.tenancyId === tenancyId),
                            filter(action => action.resourceId === resourceId),
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
        // When a resource is deleted but returns a payload, trigger a fetch of
        // the resource as it might be doing something interesting
        // When it disappears, the reducer will remove it
        action$ => action$.pipe(
            ofType(actions.DELETE_SUCCEEDED),
            filter(action => !!action.payload),
            map(action =>
                actionCreators.fetchOne(action.request.tenancyId, id(action.payload))
            )
        )
    );
}


export function createTenancyResource(resourceName, options = {}) {
    const {
        isActive = _ => false,
        id = resource => resource.id,
        transform = resource => resource
    } = options;
    const actions = createActions(resourceName);
    const actionCreators = createActionCreators(resourceName, actions);
    const reducer = createReducer(actions, id, transform);
    const epic = createEpic(actions, actionCreators, isActive, id);
    return { actions, actionCreators, reducer, epic };
}
