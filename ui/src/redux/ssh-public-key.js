/**
 * This module manages the Redux state for the SSH public key.
 */

import { map } from 'rxjs/operators';
 
import { combineEpics, ofType } from 'redux-observable';

import { actions as sessionActions } from './session';
import { actionCreators as notificationActionCreators } from './notifications';


export const actions = {
    FETCH: 'SSH_PUBLIC_KEY/FETCH',
    FETCH_SUCCEEDED: 'SSH_PUBLIC_KEY/FETCH_SUCCEEDED',
    FETCH_FAILED: 'SSH_PUBLIC_KEY/FETCH_FAILED',

    UPDATE: 'SSH_PUBLIC_KEY/UPDATE',
    UPDATE_SUCCEEDED: 'SSH_PUBLIC_KEY/UPDATE_SUCCEEDED',
    UPDATE_FAILED: 'SSH_PUBLIC_KEY/UPDATE_FAILED'
};


export const actionCreators = {
    fetch: () => ({
        type: actions.FETCH,
        apiRequest: true,
        // Let loading errors fail silently
        failSilently: true,
        successAction: actions.FETCH_SUCCEEDED,
        failureAction: actions.FETCH_FAILED,
        options: { url: '/api/ssh_public_key/' }
    }),

    update: (ssh_public_key) => ({
        type: actions.UPDATE,
        apiRequest: true,
        successAction: actions.UPDATE_SUCCEEDED,
        failureAction: actions.UPDATE_FAILED,
        options: {
            url: `/api/ssh_public_key/`,
            method: 'PUT',
            body: { ssh_public_key }
        }
    })
};


/**
 * The redux reducer for the SSH key state.
 */
const initialState = {
    initialised: false, // This becomes true after the first successful fetch
    fetching: true,
    updating: false,
    ssh_public_key: null,
    ssh_key_is_public: true,
    can_update: false,
    allowed_key_types: [],
    rsa_min_bits: 0
};

export function reducer(state = initialState, action) {
    switch(action.type) {
        case actions.FETCH:
            return { ...state, fetching: true };
        case actions.FETCH_SUCCEEDED:
            return { ...action.payload, initialised: true, fetching: false };
        case actions.FETCH_FAILED:
            return { ...state, fetching: false };

        case actions.UPDATE:
            return { ...state, updating: true };
        case actions.UPDATE_SUCCEEDED:
            return { ...state, ...action.payload, updating: false };
        case actions.UPDATE_FAILED:
            return { ...state, updating: false };
        default:
            return state;
    }
}


/**
 * The redux-observable epic for the SSH key state.
 */
export const epic = combineEpics(
    // When a session is started, load the SSH key info list
    (action$) => action$.pipe(
        ofType(sessionActions.INITIALISATION_SUCCEEDED),
        map(_ => actionCreators.fetch())
    ),
    // When the SSH key is successfully updated, emit a success notification
    (action$) => action$.pipe(
        ofType(actions.UPDATE_SUCCEEDED),
        map(action => notificationActionCreators.success({
            title: 'SSH public key updated',
            message: 'Your SSH public key was successfully updated.'
        }))
    )
);
