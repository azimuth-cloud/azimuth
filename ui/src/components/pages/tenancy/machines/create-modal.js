/**
 * This module contains the modal dialog for machine creation.
 */

import React, { useState } from 'react';

import Button from 'react-bootstrap/Button';
import BSForm from 'react-bootstrap/Form';
import Modal from 'react-bootstrap/Modal';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faDesktop, faPlus, faSyncAlt } from '@fortawesome/free-solid-svg-icons';

import get from 'lodash/get';

import { Form, Field } from '../../../utils';
import { ConnectedSSHKeyRequiredModal } from '../../../ssh-key-update-modal';

import { ImageSelectControl, SizeSelectControl } from '../resource-utils';


const CreateMachineModal = ({
    onSuccess,
    onCancel,
    creating,
    create,
    images,
    imageActions,
    sizes,
    sizeActions,
    ...props
}) => {
    // Use state to store the values as set by the user
    const [name, setName] = useState('');
    const [image, setImage] = useState('');
    const [size, setSize] = useState('');
    const reset = () => {
        setName('');
        setImage('');
        setSize('');
    };

    // When the modal is closed, reset the data before calling the cancel handler
    const handleClose = () => { reset(); onCancel(); };
    const setNameFromEvent = (evt) => setName(evt.target.value);

    // On form submission, initiate the machine create before closing
    const handleSubmit = (evt) => {
        evt.preventDefault();
        create({
            name,
            image_id: image,
            size_id: size,
        });
        reset();
        onSuccess();
    };

    return (
        <Modal backdrop="static" size="lg" onHide={handleClose} {...props}>
            <Modal.Header closeButton>
                <Modal.Title>Create a new machine</Modal.Title>
            </Modal.Header>
            <Form
                disabled={!images.initialised || !sizes.initialised}
                onSubmit={handleSubmit}
            >
                <Modal.Body>
                    <Field
                        name="name"
                        label="Machine name"
                        helpText="Must contain alphanumeric characters, dot (.) and dash (-) only."
                    >
                        <BSForm.Control
                            type="text"
                            placeholder="Machine name"
                            required
                            pattern="[A-Za-z0-9\.\-]+"
                            autoComplete="off"
                            value={name}
                            onChange={setNameFromEvent}
                        />
                    </Field>
                    <Field name="image" label="Image">
                        <ImageSelectControl
                            resource={images}
                            resourceActions={imageActions}
                            required
                            value={image}
                            onChange={setImage}
                        />
                    </Field>
                    <Field name="size" label="Size">
                        <SizeSelectControl
                            resource={sizes}
                            resourceActions={sizeActions}
                            required
                            value={size}
                            onChange={setSize}
                        />
                    </Field>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="success" type="submit">
                        <FontAwesomeIcon icon={faPlus} className="me-2" />
                        Create machine
                    </Button>
                </Modal.Footer>
            </Form>
        </Modal>
    );
};


export const CreateMachineButton = ({ sshKey, disabled, creating, ...props }) => {
    const [visible, setVisible] = useState(false);
    const open = () => setVisible(true);
    const close = () => setVisible(false);
    return (
        <>
            <Button
                variant="success"
                disabled={sshKey.fetching || disabled || creating}
                onClick={open}
                title="Create a new machine"
            >
                <FontAwesomeIcon
                    icon={creating ? faSyncAlt : faDesktop}
                    spin={creating}
                    className="me-2"
                />
                {creating ? 'Creating machine...' : 'New machine'}
            </Button>
            <ConnectedSSHKeyRequiredModal
                show={visible}
                onSuccess={close}
                onCancel={close}
                warningText="Before creating a machine, you must set an SSH public key."
            >
                <CreateMachineModal
                    creating={creating}
                    {...props}
                />
            </ConnectedSSHKeyRequiredModal>
        </>
    );
};
