/**
 * This module contains Redux bits for loading tenancy volumes.
 */

import { createTenancyResource } from './resource';


const activeStatuses = ['CREATING', 'ATTACHING', 'DETACHING', 'DELETING'];


const {
    actions,
    actionCreators,
    reducer,
    epic,
} = createTenancyResource('volume', {
    isActive: volume => activeStatuses.includes(volume.status.toUpperCase())
});


export { actions, actionCreators, reducer, epic };
