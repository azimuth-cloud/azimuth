/**
 * This module contains components for the tenancy machines page.
 */

import React from 'react';

import { usePageTitle } from '../../../utils';

import { useResourceInitialised, ResourcePanel } from '../resource-utils';
import { CreateVolumeButton } from './create-modal';
import { VolumesTable } from './table';


const Volumes = ({ resourceData, resourceActions, machines, machineActions }) => (
    <VolumesTable
        volumes={resourceData}
        volumeActions={resourceActions}
        machines={machines}
        machineActions={machineActions}
    />
);


export const TenancyVolumesPanel = ({ tenancy, tenancyActions }) => {
    usePageTitle('Volumes');
    // To render the volumes, we need the machines
    useResourceInitialised(tenancy.machines, tenancyActions.machine.fetchList);
    return (
        <ResourcePanel
            resource={tenancy.volumes}
            resourceActions={tenancyActions.volume}
            resourceName="volumes"
            createButtonComponent={CreateVolumeButton}
        >
            <Volumes
                machines={tenancy.machines}
                machineActions={tenancyActions.machine}
            />
        </ResourcePanel>
    );
};
