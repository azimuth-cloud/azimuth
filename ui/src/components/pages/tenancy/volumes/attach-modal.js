/**
 * This module contains the React component for the external IP modal.
 */

import React, { useState } from 'react';

import Button from 'react-bootstrap/Button';
import DropdownItem from 'react-bootstrap/DropdownItem';
import Modal from 'react-bootstrap/Modal';

import isEmpty from 'lodash/isEmpty';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faSignInAlt } from '@fortawesome/free-solid-svg-icons';

import { Form, Field } from '../../../utils';

import { MachineSelectControl } from '../resource-utils';


export const AttachVolumeMenuItem = ({ volume, machines, machineActions, attach }) => {
    const [visible, setVisible] = useState(false);
    const [machine, setMachine] = useState('');

    const open = () => setVisible(true);
    const close = () => { setVisible(false); setMachine(''); };

    const handleSubmit = (evt) => {
        evt.preventDefault();
        attach(machine);
        close();
    };

    return (
        <>
            <DropdownItem onClick={open} disabled={!!volume.machine}>
                Attach volume to machine
            </DropdownItem>
            <Modal
                backdrop="static"
                onHide={close}
                show={visible}
            >
                <Modal.Header closeButton>
                    <Modal.Title>Attach {volume.name} to machine</Modal.Title>
                </Modal.Header>
                <Form disabled={isEmpty(machines.data)} onSubmit={handleSubmit}>
                    <Modal.Body>
                        <Field name="machine" label="Attach To">
                            <MachineSelectControl
                                resource={machines}
                                resourceActions={machineActions}
                                required
                                value={machine}
                                onChange={setMachine}
                            />
                        </Field>
                    </Modal.Body>
                    <Modal.Footer>
                        <Button variant="primary" type="submit">
                            <FontAwesomeIcon icon={faSignInAlt} className="me-2" />
                            Attach volume
                        </Button>
                    </Modal.Footer>
                </Form>
            </Modal>
        </>
    );
};
