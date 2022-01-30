/**
 * This module contains components for the tenancy machines page.
 */

import React from 'react';

import { usePageTitle } from '../../../utils';

import { useResourceInitialised, ResourcePanel } from '../resource-utils';
import { ClustersTable } from './table';
import { CreateClusterButton } from './create-modal';


const Clusters = ({ resourceData, resourceActions, ...props }) => (
    <ClustersTable
        clusters={resourceData}
        clusterActions={resourceActions}
        {...props}
    />
);


export const TenancyClustersPanel = ({ sshKey, tenancy, tenancyActions }) => {
    usePageTitle('Clusters');
    // The clusters panel requires the cluster types to render
    useResourceInitialised(tenancy.clusterTypes, tenancyActions.clusterType.fetchList);
    return (
        <ResourcePanel
            resource={tenancy.clusters}
            resourceActions={tenancyActions.cluster}
            resourceName="clusters"
            createButtonComponent={CreateClusterButton}
            createButtonExtraProps={({ sshKey, tenancy, tenancyActions })}
        >
            <Clusters tenancy={tenancy} tenancyActions={tenancyActions} />
        </ResourcePanel>
    );
};
