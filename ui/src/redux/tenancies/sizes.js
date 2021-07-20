/**
 * This module contains Redux bits for loading tenancy sizes.
 */

import { createTenancyResource } from './resource';


const {
    actions,
    actionCreators,
    reducer,
    epic,
} = createTenancyResource('size');


export { actions, actionCreators, reducer, epic };
