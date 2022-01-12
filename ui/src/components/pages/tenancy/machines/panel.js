/**
 * This module contains components for the tenancy machines page.
 */

import React from 'react';

import { usePageTitle } from '../../../utils';

import { useResourceInitialised, ResourcePanel } from '../resource-utils';
import { CreateMachineButton } from './create-modal';
import { MachinesTable } from './table';


const Machines = ({ resourceData, resourceActions, ...props }) => (
    <MachinesTable
        machines={resourceData}
        machineActions={resourceActions}
        {...props}
    />
);


export const TenancyMachinesPanel = ({
    sshKey,
    capabilities,
    tenancy: {
        machines,
        images,
        sizes,
        externalIps
    },
    tenancyActions: {
        machine: machineActions,
        image: imageActions,
        size: sizeActions,
        externalIp: externalIpActions
    }
}) => {
    // Set the page title
    usePageTitle("Machines");
    // The panel also requires the images, sizes and external IPs to render
    useResourceInitialised(images, imageActions.fetchList);
    useResourceInitialised(sizes, sizeActions.fetchList);
    useResourceInitialised(externalIps, externalIpActions.fetchList);
    return (
        <ResourcePanel
            resource={machines}
            resourceActions={machineActions}
            resourceName="machines"
            createButtonComponent={CreateMachineButton}
            createButtonExtraProps={{
                sshKey,
                capabilities,
                images,
                imageActions,
                sizes,
                sizeActions
            }}
        >
            <Machines
                images={images}
                sizes={sizes}
                externalIps={externalIps}
                externalIpActions={externalIpActions}
            />
        </ResourcePanel>
    );
};
