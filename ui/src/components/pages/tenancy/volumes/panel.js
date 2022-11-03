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
import { CreateVolumeButton } from './create-modal';
import { VolumesTable } from './table';


const Volumes = ({
    resourceData,
    resourceActions,
    platformsAvailable,
    machines,
    machineActions
}) => (
    <>
        {platformsAvailable && (
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
                            Deleting volumes that are part of a platform may cause
                            potentially unrecoverable issues, including data loss.
                        </div>
                    </Alert>
                </Col>
            </Row>
        )}
        <VolumesTable
            volumes={resourceData}
            volumeActions={resourceActions}
            machines={machines}
            machineActions={machineActions}
        />
    </>
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
                platformsAvailable={tenancy.platforms_available}
                machines={tenancy.machines}
                machineActions={tenancyActions.machine}
            />
        </ResourcePanel>
    );
};
