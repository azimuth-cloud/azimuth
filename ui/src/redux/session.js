/**
 * Action creators and reducers for the User section of the state.
 */

import { ajax } from 'rxjs/ajax';
import { of } from 'rxjs';
import { map, filter, mergeMap, delay, catchError } from 'rxjs/operators';

import { combineEpics } from 'redux-observable';

import Cookies from 'js-cookie';

import { StatusCodes, getReasonPhrase } from 'http-status-codes';


export const actions = {
    // Action that is dispatched when a session is terminated by a 401
    TERMINATED: 'SESSION/TERMINATED',

    // Actions that are dispatched during the initialisation process
    INITIALISE: 'SESSION/INITIALISE',
    INITIALISATION_SUCCEEDED: 'SESSION/INITIALISATION_SUCCEEDED',
    INITIALISATION_FAILED: 'SESSION/INITIALISATION_FAILED',
};


export const actionCreators = {
    initialise: () => ({
        type: actions.INITIALISE,
        apiRequest: true,
        failSilently: true,
        successAction: actions.INITIALISATION_SUCCEEDED,
        failureAction: actions.INITIALISATION_FAILED,
        options: { url: '/api/session/' }
    })
};


const initialState = {
    initialising: true,
    user_id: null,
    username: null
};

/**
 * The redux reducer for the session state.
 */
export function reducer(state = initialState, action) {
    switch(action.type) {
        case actions.INITIALISE:
            return { ...state, initialising: true };
        case actions.INITIALISATION_SUCCEEDED:
            return {
                ...state,
                ...action.payload,
                initialising: false
            };
        case actions.INITIALISATION_FAILED:
        case actions.TERMINATED:
            return { ...state, ...initialState, initialising: false };
        default:
            return state;
    }
}

/**
 * redux-observable epic to dispatch a TERMINATED action whenever a request
 * fails with a 401. This includes when initialisation fails.
 */
function apiAuthenticationErrorEpic(action$) {
    return action$.pipe(
        filter(action => !!action.error),
        filter(action => action.payload.statusCode === StatusCodes.UNAUTHORIZED ),
        map(_ => ({ type: actions.TERMINATED }))
    );
}


/**
 * redux-observable epic to look for 503 temporarily unavailable and retry
 */
function retryTemporarilyUnavailableEpic(action$) {
    return action$.pipe(
        filter(action => !!action.error),
        filter(action => action.payload.statusCode === StatusCodes.SERVICE_UNAVAILABLE),
        // Wait 10s and try again
        delay(10000),
        map(action => action.request)
    );
}


export class ApiError extends Error {
    constructor(message, statusCode) {
        super(message)
        this.statusCode = statusCode;
    }

    get title() {
        return this.statusCode > 0 ? getReasonPhrase(this.statusCode) : 'API Error';
    }
}

/**
 * redux-observable epic that reacts to actions flagged as API requests by making
 * the corresponding API call.
 *
 * If the request completes successfully, it dispatches the specified success action
 * with the response data as the payload.
 *
 * If the request fails, it dispatches the specified failure action with an ``ApiError``
 * as the payload.
 */
function apiRequestEpic(action$) {
    // Listen for actions with the apiRequest flag
    return action$.pipe(
        filter(action => action.apiRequest),
        mergeMap(
            action => {
                // The action then has an expected structure
                const { options, successAction, failureAction } = action;
                const method = options.method || 'GET';
                // Make sure we ask for JSON
                const headers = { 'Content-Type': 'application/json' };
                // For POST/PATCH/PUT/DELETE, include the CSRF token if present
                if( ['POST', 'PATCH', 'PUT', 'DELETE'].includes(method.toUpperCase()) ) {
                    const csrfToken = Cookies.get('csrftoken');
                    if( csrfToken ) headers['X-CSRFToken'] = csrfToken;
                }
                // Make the API request
                // If the session is terminated, discard any active requests
                const request = {
                    ...options,
                    withCredentials: true, // Include cookies with the request
                    headers: headers,
                    responseType: 'json' /* Ask for JSON please! */
                };
                return ajax(request).pipe(
                    map(response => ({
                        type: successAction,
                        payload: response.response,
                        request: action
                    })),
                    catchError(error => {
                        // Transform AjaxErrors into ApiErrors by inspecting the response for details
                        // If there is no response, check to see if it is because we are offline
                        const response = error.xhr.response;
                        const apiError = response ? (
                            response.detail ?
                               new ApiError(response.detail, error.status) :
                                new ApiError(JSON.stringify(response), error.status)
                            ) : (
                                navigator.onLine ?
                                    new ApiError('Error communicating with API server.', error.status) :
                                    new ApiError('No internet connection.', StatusCodes.SERVICE_UNAVAILABLE)
                            );
                        return of({
                            type: failureAction,
                            error: true,
                            silent: !!action.failSilently,
                            payload: apiError,
                            request: action
                        });
                    })
                );
            },
            // Allow at most 2 concurrent requests
            // This means one long-running request, like a large list fetch,
            // won't block other small requests, but our requests are reasonably
            // rate limited
            2
        )
    );
}


export const epic = combineEpics(
    apiRequestEpic,
    apiAuthenticationErrorEpic,
    retryTemporarilyUnavailableEpic
);
