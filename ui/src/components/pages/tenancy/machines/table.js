/**
 * This module contains components for the machines table.
 */

import React, { useState } from 'react';

import Button from 'react-bootstrap/Button';
import DropdownButton from 'react-bootstrap/DropdownButton';
import DropdownItem from 'react-bootstrap/DropdownItem';
import Modal from 'react-bootstrap/Modal';
import OverlayTrigger from 'react-bootstrap/OverlayTrigger';
import Popover from 'react-bootstrap/Popover';
import ProgressBar from 'react-bootstrap/ProgressBar';
import Table from 'react-bootstrap/Table';

import get from 'lodash/get';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faQuestionCircle } from '@fortawesome/free-solid-svg-icons';

import { bindArgsToActions, Loading, useSortable } from '../../../utils';

import { MachineSizeLink } from '../resource-utils';
import { AttachExternalIpMenuItem } from './external-ip-modal';
import { MachineLogsMenuItem } from './logs-modal';
import { MachineFirewallMenuItem } from './firewall-modal';


const ConfirmDeleteMenuItem = ({ name, onConfirm }) => {
    const [visible, setVisible] = useState(false);

    const open = () => setVisible(true);
    const close = () => setVisible(false);
    const handleConfirm = () => { onConfirm(); close(); };

    return (
        <>
            <DropdownItem className="text-danger" onClick={open}>
                Delete machine
            </DropdownItem>
            <Modal show={visible} backdrop="static" keyboard={false}>
                <Modal.Body>
                    <p>Are you sure you want to delete {name}?</p>
                    <p><strong>Once deleted, a machine cannot be restored.</strong></p>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={close}>Cancel</Button>
                    <Button variant="danger" onClick={handleConfirm}>Delete machine</Button>
                </Modal.Footer>
            </Modal>
        </>
    );
};


const statusClasses = {
    'BUILD': 'text-primary',
    'ACTIVE': 'text-success',
    'ERROR': 'text-danger',
    'OTHER': 'text-muted'
};

const MachineStatus = ({ machine: { status }}) => (
    <span className={`fw-bold ${statusClasses[status.type]}`}>
        {status.name}
        {status.details && (
            <OverlayTrigger
                placement="right"
                overlay={(
                    <Popover>
                        <Popover.Header>Status details</Popover.Header>
                        <Popover.Body>{status.details}</Popover.Body>
                    </Popover>
                )}
                trigger="click"
                rootClose
            >
                <a
                    className="ms-1 text-reset overlay-trigger"
                    title="Details"
                >
                    <FontAwesomeIcon icon={faQuestionCircle} />
                </a>
            </OverlayTrigger>
        )}
    </span>
);


const MachineActionsDropdown = ({
    disabled,
    machine,
    machineExternalIp,
    externalIps,
    machineActions,
    externalIpActions
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
        <AttachExternalIpMenuItem
            machine={machine}
            externalIps={externalIps}
            externalIpActions={externalIpActions}
            disabled={(
                machine.status.type === 'ERROR' ||
                !!machineExternalIp ||
                !machine.nat_allowed
            )}
        />
        <DropdownItem
            onClick={() => externalIpActions.update(
                machineExternalIp,
                { machine_id: null }
            )}
            disabled={!machineExternalIp}
        >
            Detach external IP
        </DropdownItem>
        <MachineFirewallMenuItem
            machine={machine}
            machineActions={machineActions}
        />
        <DropdownItem
            onClick={machineActions.start}
            disabled={['ACTIVE', 'ERROR'].includes(machine.status.type)}
        >
            Start machine
        </DropdownItem>
        <DropdownItem
            onClick={machineActions.stop}
            disabled={machine.status.type !== 'ACTIVE'}
        >
            Stop machine
        </DropdownItem>
        <DropdownItem
            onClick={machineActions.restart}
            disabled={machine.status.type !== 'ACTIVE'}
        >
            Restart machine
        </DropdownItem>
        <MachineLogsMenuItem
            machine={machine}
            machineActions={machineActions}
            disabled={machine.status.type === 'ERROR'}
        />
        <ConfirmDeleteMenuItem
            name={machine.name}
            onConfirm={machineActions.delete}
        />
    </DropdownButton>
);


const MachineRow = ({
    machine,
    sizes,
    externalIps,
    machineActions,
    externalIpActions
}) => {
    // Find the external IP for the machine by searching the external IPs
    const externalIp = Object.values(externalIps.data || {})
        .find(ip => get(ip, ['machine', 'id']) === machine.id);
    const highlightClass = (machine.status.type === 'BUILD') ?
        'table-info' :
        ((machine.status.type === 'DELETED') ?
            'table-danger' :
            ((
                !!machine.updating ||
                !!machine.deleting ||
                !!machine.task ||
                // An updating external IP counts as an action in progress
                !!get(externalIp, ['updating'])
            ) && 'table-warning')
        );
    return (
        <tr className={highlightClass || undefined}>
            <td className="text-wrap">{machine.name}</td>
            {/* Allow long image names to wrap */}
            <td className="text-wrap">{get(machine.image, 'name', '-')}</td>
            <td><MachineSizeLink sizes={sizes} sizeId={machine.size.id} /></td>
            <td><MachineStatus machine={machine} /></td>
            <td>{machine.power_state}</td>
            <td>
                {machine.task ?
                    <ProgressBar now={100} animated label={machine.task} /> :
                    '-'
                }
            </td>
            <td>
                {machine.internal_ip || '-'}
                {externalIp && (
                    <>
                        <br />
                        {externalIp.external_ip}
                    </>
                )}
            </td>
            <td>{machine.created.toRelative()}</td>
            <td className="resource-actions">
                <MachineActionsDropdown
                    disabled={!!highlightClass}
                    machine={machine}
                    machineExternalIp={get(externalIp, ['id'])}
                    externalIps={externalIps}
                    machineActions={machineActions}
                    externalIpActions={externalIpActions}
                />
            </td>
        </tr>
    );
};


// Sort functions for each field of a machine that is sortable
const sortKeyFns = {
    'name': machine => machine.name,
    'image': machine => get(machine.image, 'name', '-'),
    'size': machine => [
        get(machine.size, 'cpus', -1),
        get(machine.size, 'ram', -1),
        get(machine.size, 'disk', -1)
    ],
    'created': machine => machine.created
};


export const MachinesTable = ({
    machines,
    images,
    sizes,
    externalIps,
    machineActions,
    externalIpActions
}) => {
    const [sortedMachines, SortableColumnHeading] = useSortable(
        // Replace the image and size refs with the corresponding objects from the
        // resources if they have loaded
        Object.values(machines).map(machine => ({
            ...machine,
            image: machine.image ? get(images.data, machine.image.id, machine.image) : null,
            size: machine.size ? get(sizes.data, machine.size.id, machine.size) : null,
        })),
        {
            keyFunctions: sortKeyFns,
            initialField: 'created',
            initialReverse: true
        }
    );
    return (
        <Table striped hover responsive className="resource-table machines-table">
            <caption className="px-2">
                {sortedMachines.length} machine{sortedMachines.length !== 1 && 's'}
            </caption>
            <thead>
                <tr>
                    <SortableColumnHeading field="name">Name</SortableColumnHeading>
                    <SortableColumnHeading field="image">Image</SortableColumnHeading>
                    <SortableColumnHeading field="size">Size</SortableColumnHeading>
                    <th>Status</th>
                    <th>Power State</th>
                    <th>Task</th>
                    <th>IP Addresses</th>
                    <SortableColumnHeading field="created">Created</SortableColumnHeading>
                    <th></th>
                </tr>
            </thead>
            <tbody>
                {sortedMachines.map(machine =>
                    <MachineRow
                        key={machine.id}
                        machine={machine}
                        sizes={sizes}
                        externalIps={externalIps}
                        machineActions={bindArgsToActions(machineActions, machine.id)}
                        externalIpActions={externalIpActions}
                    />
                )}
            </tbody>
        </Table>
    );
};
