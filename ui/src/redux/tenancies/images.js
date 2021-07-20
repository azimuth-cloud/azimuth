/**
 * This module contains Redux bits for loading tenancy images.
 */

import { createTenancyResource } from './resource';


const {
    actions,
    actionCreators,
    reducer,
    epic,
} = createTenancyResource('image');


export { actions, actionCreators, reducer, epic };
