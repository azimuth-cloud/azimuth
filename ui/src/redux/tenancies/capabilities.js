/**
 * This module manages the Redux state for tenancy capabilities.
 */

export const actions = {
    FETCH: 'TENANCIES/CAPABILITIES/FETCH',
    FETCH_SUCCEEDED: 'TENANCIES/CAPABILITIES/FETCH_SUCCEEDED',
    FETCH_FAILED: 'TENANCIES/CAPABILITIES/FETCH_FAILED',
};


export const actionCreators = {
    fetch: tenancyId => ({
        type: actions.FETCH,
        tenancyId,
        apiRequest: true,
        // Let loading errors fail silently
        failSilently: true,
        successAction: actions.FETCH_SUCCEEDED,
        failureAction: actions.FETCH_FAILED,
        options: { url: `/api/tenancies/${tenancyId}/capabilities/` }
    }),
};


const initialState = {
    // State to do with the fetching
    initialised: false, // This becomes true after the first successful fetch
    fetching: false,
    fetchError: null,

    // Defaults for the actual data
    supports_volumes: false,
    supports_machines: false,
    supports_clusters: false,
    supports_kubernetes: false,
    supports_apps: false,
    supports_scheduling: false,
};

export function reducer(state = initialState, action) {
    switch(action.type) {
        case actions.FETCH:
            return { ...state, fetching: true };
        case actions.FETCH_SUCCEEDED:
            return {
                ...state,
                ...action.payload,
                initialised: true,
                fetching: false,
                fetchError: null
            };
        case actions.FETCH_FAILED:
            return { ...state, fetching: false, fetchError: action.payload };
        default:
            return state;
    }
}
