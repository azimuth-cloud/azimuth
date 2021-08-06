/**
 * This module contains Redux bits for loading tenancy external ips.
 */

import { merge, map } from 'rxjs/operators';

import { combineEpics, ofType } from 'redux-observable';

import { createTenancyResource, nextStateEntry } from './resource';

import { actions as externalIpActions } from './external-ips';


const {
    actions: resourceActions,
    actionCreators: resourceActionCreators,
    reducer: resourceReducer,
    epic: resourceEpic
} = createTenancyResource('machine', {
    isActive: machine => (['BUILD', 'DELETED'].includes(machine.status.type) || !!machine.task),
    // Just convert the string date to a Date object
    transform: machine =>
        machine.hasOwnProperty('created') ?
            { ...machine, created: new Date(machine.created) } :
            machine
});


export const actions = {
    ...resourceActions,

    FETCH_LOGS: 'TENANCIES/MACHINE/FETCH_LOGS',
    FETCH_LOGS_SUCCEEDED: 'TENANCIES/MACHINE/FETCH_LOGS_SUCCEEDED',
    FETCH_LOGS_FAILED: 'TENANCIES/MACHINE/FETCH_LOGS_FAILED',

    FETCH_FIREWALL_RULES: 'TENANCIES/MACHINE/FETCH_FIREWALL_RULES',
    FETCH_FIREWALL_RULES_SUCCEEDED: 'TENANCIES/MACHINE/FETCH_FIREWALL_RULES_SUCCEEDED',
    FETCH_FIREWALL_RULES_FAILED: 'TENANCIES/MACHINE/FETCH_FIREWALL_RULES_FAILED',

    ADD_FIREWALL_RULE: 'TENANCIES/MACHINE/ADD_FIREWALL_RULE',
    ADD_FIREWALL_RULE_SUCCEEDED: 'TENANCIES/MACHINE/ADD_FIREWALL_RULE_SUCCEEDED',
    ADD_FIREWALL_RULE_FAILED: 'TENANCIES/MACHINE/ADD_FIREWALL_RULE_FAILED',

    REMOVE_FIREWALL_RULE: 'TENANCIES/MACHINE/REMOVE_FIREWALL_RULE',
    REMOVE_FIREWALL_RULE_SUCCEEDED: 'TENANCIES/MACHINE/REMOVE_FIREWALL_RULE_SUCCEEDED',
    REMOVE_FIREWALL_RULE_FAILED: 'TENANCIES/MACHINE/REMOVE_FIREWALL_RULE_FAILED',

    START: 'TENANCIES/MACHINE/START',
    START_SUCCEEDED: 'TENANCIES/MACHINE/START_SUCCEEDED',
    START_FAILED: 'TENANCIES/MACHINE/START_FAILED',

    STOP: 'TENANCIES/MACHINE/STOP',
    STOP_SUCCEEDED: 'TENANCIES/MACHINE/STOP_SUCCEEDED',
    STOP_FAILED: 'TENANCIES/MACHINE/STOP_FAILED',

    RESTART: 'TENANCIES/MACHINE/RESTART',
    RESTART_SUCCEEDED: 'TENANCIES/MACHINE/RESTART_SUCCEEDED',
    RESTART_FAILED: 'TENANCIES/MACHINE/RESTART_FAILED',
};


export const actionCreators = {
    ...resourceActionCreators,

    fetchLogs: (tenancyId, machineId) => ({
        type: actions.FETCH_LOGS,
        tenancyId,
        machineId,
        apiRequest: true,
        // All errors are reported via the modal UI
        failSilently: true,
        successAction: actions.FETCH_LOGS_SUCCEEDED,
        failureAction: actions.FETCH_LOGS_FAILED,
        options: {
            url: `/api/tenancies/${tenancyId}/machines/${machineId}/logs/`,
            method: 'GET'
        }
    }),
    fetchFirewallRules: (tenancyId, machineId) => ({
        type: actions.FETCH_FIREWALL_RULES,
        tenancyId,
        machineId,
        apiRequest: true,
        // All errors are reported via the modal UI
        failSilently: true,
        successAction: actions.FETCH_FIREWALL_RULES_SUCCEEDED,
        failureAction: actions.FETCH_FIREWALL_RULES_FAILED,
        options: {
            url: `/api/tenancies/${tenancyId}/machines/${machineId}/firewall_rules/`,
            method: 'GET'
        }
    }),
    addFirewallRule: (tenancyId, machineId, data) => ({
        type: actions.ADD_FIREWALL_RULE,
        tenancyId,
        machineId,
        apiRequest: true,
        successAction: actions.ADD_FIREWALL_RULE_SUCCEEDED,
        failureAction: actions.ADD_FIREWALL_RULE_FAILED,
        options: {
            url: `/api/tenancies/${tenancyId}/machines/${machineId}/firewall_rules/`,
            method: 'POST',
            body: data || {}
        }
    }),
    removeFirewallRule: (tenancyId, machineId, ruleId) => ({
        type: actions.REMOVE_FIREWALL_RULE,
        tenancyId,
        machineId,
        ruleId,
        apiRequest: true,
        successAction: actions.REMOVE_FIREWALL_RULE_SUCCEEDED,
        failureAction: actions.REMOVE_FIREWALL_RULE_FAILED,
        options: {
            url: `/api/tenancies/${tenancyId}/machines/${machineId}/firewall_rules/${ruleId}/`,
            method: 'DELETE'
        }
    }),
    start: (tenancyId, machineId) => ({
        type: actions.START,
        tenancyId,
        machineId,
        apiRequest: true,
        successAction: actions.START_SUCCEEDED,
        failureAction: actions.START_FAILED,
        options: {
            url: `/api/tenancies/${tenancyId}/machines/${machineId}/start/`,
            method: 'POST'
        }
    }),
    stop: (tenancyId, machineId) => ({
        type: actions.STOP,
        tenancyId,
        machineId,
        apiRequest: true,
        successAction: actions.STOP_SUCCEEDED,
        failureAction: actions.STOP_FAILED,
        options: {
            url: `/api/tenancies/${tenancyId}/machines/${machineId}/stop/`,
            method: 'POST'
        }
    }),
    restart: (tenancyId, machineId) => ({
        type: actions.RESTART,
        tenancyId,
        machineId,
        apiRequest: true,
        successAction: actions.RESTART_SUCCEEDED,
        failureAction: actions.RESTART_FAILED,
        options: {
            url: `/api/tenancies/${tenancyId}/machines/${machineId}/restart/`,
            method: 'POST'
        }
    })
};


export function reducer(state, action) {
    switch(action.type) {
        case actions.FETCH_LOGS:
            // Only register the fetch if we know about the machine
            if( state.data.hasOwnProperty(action.machineId) )
                return {
                    ...state,
                    data: Object.assign(
                        {},
                        state.data,
                        nextStateEntry(
                            state,
                            action.machineId,
                            { fetchingLogs: true }
                        )
                    ),
                };
            else
                return state;
        case actions.FETCH_LOGS_SUCCEEDED:
            // Only store the logs if we already know about the machine
            if( state.data.hasOwnProperty(action.request.machineId) )
                return {
                    ...state,
                    data: Object.assign(
                        {},
                        state.data,
                        nextStateEntry(
                            state,
                            action.request.machineId,
                            {
                                logs: action.payload.logs,
                                fetchingLogs: false,
                                fetchLogsError: undefined
                            }
                        )
                    ),
                };
            else
                return state;
        case actions.FETCH_LOGS_FAILED:
            // Only store the error if we already know about the machine
            if( state.data.hasOwnProperty(action.request.machineId) )
                return {
                    ...state,
                    data: Object.assign(
                        {},
                        state.data,
                        nextStateEntry(
                            state,
                            action.request.machineId,
                            { fetchLogsError: action.payload, fetchingLogs: false }
                        )
                    ),
                };
            else
                return state;
        case actions.FETCH_FIREWALL_RULES:
            // Only register the fetch if we know about the machine
            if( state.data.hasOwnProperty(action.machineId) )
                return {
                    ...state,
                    data: Object.assign(
                        {},
                        state.data,
                        nextStateEntry(
                            state,
                            action.machineId,
                            { fetchingFirewallRules: true }
                        )
                    ),
                };
            else
                return state;
        case actions.FETCH_FIREWALL_RULES_SUCCEEDED:
            // Only store the logs if we already know about the machine
            if( state.data.hasOwnProperty(action.request.machineId) )
                return {
                    ...state,
                    data: Object.assign(
                        {},
                        state.data,
                        nextStateEntry(
                            state,
                            action.request.machineId,
                            {
                                firewallRules: action.payload,
                                fetchingFirewallRules: false,
                                fetchFirewallRulesError: undefined
                            }
                        )
                    ),
                };
            else
                return state;
        case actions.FETCH_FIREWALL_RULES_FAILED:
            // Only store the error if we already know about the machine
            if( state.data.hasOwnProperty(action.request.machineId) )
                return {
                    ...state,
                    data: Object.assign(
                        {},
                        state.data,
                        nextStateEntry(
                            state,
                            action.request.machineId,
                            {
                                fetchFirewallRulesError: action.payload,
                                fetchingFirewallRules: false
                            }
                        )
                    ),
                };
            else
                return state;
        case actions.ADD_FIREWALL_RULE:
            // Only register the fetch if we know about the machine
            if( state.data.hasOwnProperty(action.machineId) )
                return {
                    ...state,
                    data: Object.assign(
                        {},
                        state.data,
                        nextStateEntry(
                            state,
                            action.machineId,
                            { addingFirewallRule: true }
                        )
                    ),
                };
            else
                return state;
        case actions.ADD_FIREWALL_RULE_SUCCEEDED:
            // Only store the logs if we already know about the machine
            if( state.data.hasOwnProperty(action.request.machineId) )
                return {
                    ...state,
                    data: Object.assign(
                        {},
                        state.data,
                        nextStateEntry(
                            state,
                            action.request.machineId,
                            {
                                firewallRules: action.payload,
                                addingFirewallRule: false
                            }
                        )
                    ),
                };
            else
                return state;
        case actions.ADD_FIREWALL_RULE_FAILED:
            // Only store the error if we already know about the machine
            if( state.data.hasOwnProperty(action.request.machineId) )
                return {
                    ...state,
                    data: Object.assign(
                        {},
                        state.data,
                        nextStateEntry(
                            state,
                            action.request.machineId,
                            { addingFirewallRule: false }
                        )
                    ),
                };
            else
                return state;
        case actions.REMOVE_FIREWALL_RULE:
            // Only register the fetch if we know about the machine
            if( state.data.hasOwnProperty(action.machineId) )
                return {
                    ...state,
                    data: Object.assign(
                        {},
                        state.data,
                        nextStateEntry(
                            state,
                            action.machineId,
                            { removingFirewallRule: action.ruleId }
                        )
                    ),
                };
            else
                return state;
        case actions.REMOVE_FIREWALL_RULE_SUCCEEDED:
            // Only store the logs if we already know about the machine
            if( state.data.hasOwnProperty(action.request.machineId) )
                return {
                    ...state,
                    data: Object.assign(
                        {},
                        state.data,
                        nextStateEntry(
                            state,
                            action.request.machineId,
                            {
                                firewallRules: action.payload,
                                removingFirewallRule: undefined
                            }
                        )
                    ),
                };
            else
                return state;
        case actions.REMOVE_FIREWALL_RULE_FAILED:
            // Only store the error if we already know about the machine
            if( state.data.hasOwnProperty(action.request.machineId) )
                return {
                    ...state,
                    data: Object.assign(
                        {},
                        state.data,
                        nextStateEntry(
                            state,
                            action.request.machineId,
                            { removingFirewallRule: undefined }
                        )
                    ),
                };
            else
                return state;
        case actions.START:
        case actions.STOP:
        case actions.RESTART:
            // Only set the updating flag to true if we know about the machine
            if( state.data.hasOwnProperty(action.machineId) )
                return {
                    ...state,
                    data: Object.assign(
                        {},
                        state.data,
                        nextStateEntry(
                            state,
                            action.machineId,
                            { updating: true }
                        )
                    ),
                };
            else
                return state;
        case actions.START_SUCCEEDED:
        case actions.STOP_SUCCEEDED:
        case actions.RESTART_SUCCEEDED:
            // The updated machine is in the payload, so merge it
            return {
                ...state,
                data: Object.assign(
                    {},
                    state.data,
                    nextStateEntry(
                        state,
                        action.payload.id,
                        { ...action.payload, updating: false }
                    )
                ),
            };
        case actions.START_FAILED:
        case actions.STOP_FAILED:
        case actions.RESTART_FAILED:
            // Only set the updating flag to false if we know about the machine
            if( state.data.hasOwnProperty(action.request.machineId) )
                return {
                    ...state,
                    data: Object.assign(
                        {},
                        state.data,
                        nextStateEntry(
                            state,
                            action.request.machineId,
                            { updating: false }
                        )
                    ),
                };
            else
                return state;
        // When an external IP is being updated to set the machine ID, mark
        // that machine as updating
        case externalIpActions.UPDATE:
            if( state.data.hasOwnProperty(action.options.body.machine_id) )
                return {
                    ...state,
                    data: Object.assign(
                        {},
                        state.data,
                        nextStateEntry(
                            state,
                            action.options.body.machine_id,
                            { updating: true }
                        )
                    ),
                };
            else
                return state;
        case externalIpActions.UPDATE_SUCCEEDED:
        case externalIpActions.UPDATE_FAILED:
            if( state.data.hasOwnProperty(action.request.options.body.machine_id) )
                return {
                    ...state,
                    data: Object.assign(
                        {},
                        state.data,
                        nextStateEntry(
                            state,
                            action.request.options.body.machine_id,
                            { updating: false }
                        )
                    ),
                };
            else
                return state;
        default:
            // Any other actions, apply the resource reducer
            return resourceReducer(state, action);
    }
}


export const epic = combineEpics(
    resourceEpic,
    // When a power action takes place on a machine, refresh the machine
    action$ => action$.pipe(
        ofType(actions.START_SUCCEEDED),
        merge(action$.pipe(ofType(actions.STOP_SUCCEEDED))),
        merge(action$.pipe(ofType(actions.RESTART_SUCCEEDED))),
        map(action =>
            actionCreators.fetchOne(action.request.tenancyId, action.payload.id)
        )
    )
);
