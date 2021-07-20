/**
 * This module contains the React component for the external IP modal.
 */

import React, { useState } from 'react';

import Button from 'react-bootstrap/Button';
import DropdownItem from 'react-bootstrap/DropdownItem';
import Modal from 'react-bootstrap/Modal';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faCheck } from '@fortawesome/free-solid-svg-icons';

import { Form, Field } from '../../utils';
import { ExternalIpSelectControl } from './resource-utils';


export const AttachExternalIpMenuItem = ({
    machine,
    externalIps,
    externalIpActions,
    disabled
}) => {
    const [visible, setVisible] = useState(false);
    const [externalIp, setExternalIp] = useState('');

    const open = () => setVisible(true);
    const close = () => { setVisible(false); setExternalIp(''); };

    const handleSubmit = evt => {
        evt.preventDefault();
        externalIpActions.update(externalIp, { machine_id: machine.id });
        close();
    };

    const availableIps = Object.values(externalIps.data || {})
        .filter(ip => !ip.updating && !ip.machine);
    return (
        <>
            <DropdownItem onSelect={open} disabled={disabled}>
                Attach external IP
            </DropdownItem>
            <Modal
                backdrop="static"
                onHide={!externalIps.creating ? close : undefined}
                show={visible}
            >
                <Modal.Header closeButton>
                    <Modal.Title>Attach external IP to {machine.name}</Modal.Title>
                </Modal.Header>
                <Form disabled={!!externalIps.creating} onSubmit={handleSubmit}>
                    <Modal.Body>
                        <Field name="externalIp" label="External IP">
                            <ExternalIpSelectControl
                                resource={externalIps}
                                resourceActions={externalIpActions}
                                required
                                value={externalIp}
                                onChange={setExternalIp}
                            />
                        </Field>
                    </Modal.Body>
                    <Modal.Footer>
                        <Button
                            variant="primary"
                            type="submit"
                            disabled={availableIps.length < 1}
                        >
                            <FontAwesomeIcon icon={faCheck} className="me-2" />
                            Attach IP
                        </Button>
                    </Modal.Footer>
                </Form>
            </Modal>
        </>
    );
};
