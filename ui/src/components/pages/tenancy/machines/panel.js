/**
 * This module contains components for the tenancy machines page.
 */

import React from 'react';

import Alert from 'react-bootstrap/Alert';
import Col from 'react-bootstrap/Col';
import Row from 'react-bootstrap/Row';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faExclamationCircle } from '@fortawesome/free-solid-svg-icons';

import { usePageTitle } from '../../../utils';

import { useResourceInitialised, ResourcePanel } from '../resource-utils';
import { CreateMachineButton } from './create-modal';
import { MachinesTable } from './table';


const Machines = ({ resourceData, resourceActions, capabilities, ...props }) => (
        <>
        {(capabilities.supports_clusters || capabilities.supports_kubernetes) && (
            <Row className="justify-content-center">
                <Col xs="auto">
                    <Alert variant="warning" className="d-flex align-items-center">
                        <div className="me-3">
                            <FontAwesomeIcon
                                icon={faExclamationCircle}
                                size="lg"
                            />
                        </div>
                        <div>
                            Deleting machines that are part of a platform may cause
                            potentially unrecoverable issues.
                        </div>
                    </Alert>
                </Col>
            </Row>
        )}
        <MachinesTable
            machines={resourceData}
            machineActions={resourceActions}
            capabilities={capabilities}
            {...props}
        />
    </>
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
                capabilities={capabilities}
                images={images}
                sizes={sizes}
                externalIps={externalIps}
                externalIpActions={externalIpActions}
            />
        </ResourcePanel>
    );
};
