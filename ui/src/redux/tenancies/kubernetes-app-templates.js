/**
 * This module contains Redux bits for loading Kubernetes app templates.
 */

import { createTenancyResource } from './resource';


const {
    actions,
    actionCreators,
    reducer,
    epic,
} = createTenancyResource('kubernetes_app_template');


export { actions, actionCreators, reducer, epic };
