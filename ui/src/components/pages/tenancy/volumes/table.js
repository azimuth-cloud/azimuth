/**
 * This module contains components for the machines table.
 */

import React, { useState } from 'react';

import Table from 'react-bootstrap/Table';
import Button from 'react-bootstrap/Button';
import Modal from 'react-bootstrap/Modal';
import DropdownButton from 'react-bootstrap/DropdownButton';
import DropdownItem from 'react-bootstrap/DropdownItem';

import get from 'lodash/get';

import { bindArgsToActions, formatSize, sortBy, Loading } from '../../../utils';

import { AttachVolumeMenuItem } from './attach-modal';


const ConfirmDeleteMenuItem = ({ name, disabled, onConfirm }) => {
    const [visible, setVisible] = useState(false);

    const open = () => setVisible(true);
    const close = () => setVisible(false);
    const handleConfirm = () => { onConfirm(); close(); };

    return (
        <>
            <DropdownItem
                className={disabled ? undefined : "text-danger"}
                disabled={disabled}
                onClick={open}
            >
                Delete volume
            </DropdownItem>
            <Modal show={visible} backdrop="static" keyboard={false}>
                <Modal.Body>
                    <p>Are you sure you want to delete {name}?</p>
                    <p><strong>Once deleted, a volume cannot be restored.</strong></p>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={close}>Cancel</Button>
                    <Button variant="danger" onClick={handleConfirm}>
                        Delete volume
                    </Button>
                </Modal.Footer>
            </Modal>
        </>
    );
};


const statusClasses = {
    'CREATING': 'text-primary',
    'AVAILABLE': 'text-success',
    'ATTACHING': 'text-secondary',
    'DETACHING': 'text-secondary',
    'IN_USE': 'text-success',
    'DELETING': 'text-danger',
    'ERROR': 'text-danger',
    'OTHER': 'text-secondary'
};

const VolumeStatus = ({ status }) => (
    <span className={`fw-bold ${statusClasses[status]}`}>
        {status}
    </span>
);


const VolumeActionsDropdown = ({
    disabled,
    volume,
    volumeActions,
    machines,
    machineActions
}) => (
    <DropdownButton
        variant="secondary"
        title={
            disabled ? (
                <Loading
                    message="Working..."
                    muted={false}
                    visuallyHidden
                    wrapperComponent="span"
                />
            ) : (
                'Actions'
            )
        }
        disabled={disabled}
        className="float-end"
    >
        <AttachVolumeMenuItem
            volume={volume}
            machines={machines}
            machineActions={machineActions}
            attach={(mid) => volumeActions.update({ machine_id: mid })}
        />
        <DropdownItem
            disabled={!volume.machine}
            onClick={() => volumeActions.update({ machine_id: null })}
        >
            Detach volume from machine
        </DropdownItem>
        <ConfirmDeleteMenuItem
            name={volume.name}
            disabled={!['AVAILABLE', 'ERROR'].includes(volume.status.toUpperCase())}
            onConfirm={volumeActions.delete}
        />
    </DropdownButton>
);


const VolumeRow = ({ volume, volumeActions, machines, machineActions }) => {
    const status = volume.status.toUpperCase();
    const highlightClass = (status === 'CREATING') ?
        'table-info' :
        ((status === 'DELETING') ?
            'table-danger' :
            (
                ['ATTACHING', 'DETACHING'].includes(status) ||
                !!volume.updating ||
                !!volume.deleting
            ) && 'table-warning'
        );
    // Try and find the attached machine
    const attachedTo = get(machines, ['data', get(volume.machine, 'id')]);
    return (
        <tr className={highlightClass || undefined}>
            <td className="text-wrap">{volume.name}</td>
            <td><VolumeStatus status={volume.status} /></td>
            <td>{formatSize(volume.size, "GB")}</td>
            <td className="text-wrap">
                {attachedTo ? (
                    `Attached to ${get(attachedTo, 'name') || '-'} on ${volume.device}`
                ) : (
                    '-'
                )}
            </td>
            <td>
                <VolumeActionsDropdown
                    disabled={!!highlightClass}
                    volume={volume}
                    volumeActions={volumeActions}
                    machines={machines}
                    machineActions={machineActions}
                />
            </td>
        </tr>
    );
}


export const VolumesTable = ({ volumes, volumeActions, machines, machineActions }) => {
    // Sort the volumes by name to ensure a consistent rendering
    const sortedVolumes = sortBy(Object.values(volumes), v => v.name);
    return (
        <Table striped hover responsive className="resource-table volumes-table">
            <caption className="px-2">
                {sortedVolumes.length} volume{sortedVolumes.length !== 1 && 's'}
            </caption>
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Status</th>
                    <th>Size</th>
                    <th>Attached To</th>
                    <th></th>
                </tr>
            </thead>
            <tbody>
                {sortedVolumes.map(volume =>
                    <VolumeRow
                        key={volume.id}
                        volume={volume}
                        volumeActions={bindArgsToActions(volumeActions, volume.id)}
                        machines={machines}
                        machineActions={machineActions}
                    />
                )}
            </tbody>
        </Table>
    );
};
