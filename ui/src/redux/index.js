/**
 * This module configures and exposes the Redux store.
 */

import { combineReducers, applyMiddleware, compose, createStore } from 'redux';
import { combineEpics, createEpicMiddleware } from 'redux-observable';

import {
    actionCreators as cloudsActionCreators,
    reducer as cloudsReducer
} from './clouds';

import {
    actionCreators as sessionActionCreators,
    reducer as sessionReducer,
    epic as sessionEpic
} from './session';

import {
    reducer as sshKeyReducer,
    epic as sshKeyEpic
} from './ssh-public-key';

import {
    reducer as tenanciesReducer,
    epic as tenanciesEpic
} from './tenancies';

import {
    reducer as notificationReducer,
    epic as notificationEpic
} from './notifications';


const rootReducer = combineReducers({
    clouds: cloudsReducer,
    session: sessionReducer,
    sshKey: sshKeyReducer,
    notifications: notificationReducer,
    tenancies: tenanciesReducer
});

const rootEpic = combineEpics(sessionEpic, sshKeyEpic, notificationEpic, tenanciesEpic);

const epicMiddleware = createEpicMiddleware();
const composeEnhancers = window.__REDUX_DEVTOOLS_EXTENSION_COMPOSE__ || compose;
export const store = createStore(
    rootReducer,
    composeEnhancers(applyMiddleware(epicMiddleware))
);

epicMiddleware.run(rootEpic);

// Initialise the session
store.dispatch(cloudsActionCreators.fetch());
store.dispatch(sessionActionCreators.initialise());
