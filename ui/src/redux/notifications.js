/**
 * This module manages the Redux state for the messaging subsystem.
 */

import { filter, map } from 'rxjs/operators';


export const actions = {
    NOTIFY: 'NOTIFICATIONS/NOTIFY',
    REMOVE: 'NOTIFICATIONS/REMOVE',
    CLEAR: 'NOTIFICATIONS/CLEAR'
};


function notify(notification, level) {
    return {
        type: actions.NOTIFY,
        payload: { ...notification, level }
    };
}
export const actionCreators = {
    notify,
    info: (notification) => notify(notification, 'info'),
    success: (notification) => notify(notification, 'success'),
    warning: (notification) => notify(notification, 'warning'),
    error: (notification) => notify(notification, 'danger'),
    remove: (id) => ({ type: actions.REMOVE, id }),
    clear: () => ({ type: actions.CLEAR })
};


// Global next id
let nextId = 0;


export function reducer(state = [], action) {
    switch(action.type) {
        case actions.NOTIFY:
            // To avoid duplicate notifications for the same message, check if the
            // incoming notification matches one we already have
            const existingIdx = state.findIndex(n =>
                n.level === action.payload.level &&
                n.title === action.payload.title &&
                n.message === action.payload.message
            );
            const duration = action.payload.duration || 5000;
            if( existingIdx >= 0 ) {
                const prev = state[existingIdx];
                // The duration should be reset to the new duration
                const next = { ...prev, duration, times: prev.times + 1 };
                return [
                    ...state.slice(0, existingIdx),
                    next,
                    ...state.slice(existingIdx + 1)
                ];
            }
            else {
                return [...state, { ...action.payload, id: nextId++, duration, times: 1 }];
            }
        case actions.REMOVE:
            return state.filter(notification => notification.id !== action.id);
        case actions.CLEAR:
            return [];
        default:
            return state;
    }
}

/**
 * This epic will raise an error notification for any action with the error flag
 * except those that are explicitly silenced.
 */
export function epic(action$) {
    return action$.pipe(
        filter(action => !!action.error),
        filter(action => !action.silent),
        map(action => actionCreators.error({
            title: action.payload.title,
            message: action.payload.message
        }))
    );
}
