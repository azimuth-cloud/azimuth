/**
 * This module contains components for the tenancy machines page.
 */

import React from 'react';

import { usePageTitle } from '../../../utils';

import { useResourceInitialised, ResourcePanel } from '../resource-utils';
import { PlatformsGrid } from './grid';
import { CreatePlatformButton } from './create-modal';


const Platforms = ({ resourceData, resourceActions, ...props }) => (
    <PlatformsGrid
        clusters={resourceData}
        clusterActions={resourceActions}
        {...props}
    />
);


export const TenancyPlatformsPanel = ({ sshKey, tenancy, tenancyActions }) => {
    usePageTitle('Platforms');
    // The clusters panel requires the cluster types to render
    useResourceInitialised(tenancy.clusterTypes, tenancyActions.clusterType.fetchList);
    return (
        <ResourcePanel
            resource={tenancy.clusters}
            resourceActions={tenancyActions.cluster}
            resourceName="platforms"
            createButtonComponent={CreatePlatformButton}
            createButtonExtraProps={({ sshKey, tenancy, tenancyActions })}
        >
            <Platforms tenancy={tenancy} tenancyActions={tenancyActions} />
        </ResourcePanel>
    );
};
