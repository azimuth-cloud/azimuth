/**
 * This module contains Redux bits for loading Kubernetes cluster templates.
 */

import { createTenancyResource } from './resource';


const {
    actions,
    actionCreators,
    reducer,
    epic,
} = createTenancyResource('kubernetes_cluster_template');


export { actions, actionCreators, reducer, epic };
