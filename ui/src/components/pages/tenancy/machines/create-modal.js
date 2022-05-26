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
    sshKey,
    capabilities,
    ...props
}) => {
    // Use state to store the values as set by the user
    const [name, setName] = useState('');
    const [image, setImage_] = useState('');
    const [size, setSize] = useState('');
    const [webConsoleSupported, setWebConsoleSupported_] = useState(false);
    const [webConsoleEnabled, setWebConsoleEnabled_] = useState(false);
    const setImage = imageId => {
        setImage_(imageId);
        setWebConsoleSupported(get(images.data, [imageId, "web_console_supported"], false));
    };
    const setWebConsoleSupported = supported_ => {
        const supported = capabilities.supports_apps && supported_;
        setWebConsoleSupported_(supported);
        setWebConsoleEnabled(supported && webConsoleEnabled);
    };
    const setWebConsoleEnabled = enabled_ => {
        const enabled = enabled_ || !sshKey.ssh_public_key
        setWebConsoleEnabled_(enabled);
    };
    const reset = () => {
        setName('');
        setImage_('');
        setSize('');
        setWebConsoleSupported_(false);
        setWebConsoleEnabled_(false);
    };

    // When the modal is closed, reset the data before calling the cancel handler
    const handleClose = () => { reset(); onCancel(); };
    const setNameFromEvent = (evt) => setName(evt.target.value);
    const setWebConsoleEnabledFromEvent = evt => setWebConsoleEnabled(evt.target.checked);

    // On form submission, initiate the machine create before closing
    const handleSubmit = (evt) => {
        evt.preventDefault();
        create({
            name,
            image_id: image,
            size_id: size,
            web_console_enabled: webConsoleEnabled
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
                            showWebConsoleLabel={capabilities.supports_apps}
                            // When the user doesn't have an SSH key, they can only select images
                            // that support the web console
                            disableWebConsoleNotSupported={!sshKey.ssh_public_key}
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
                    {capabilities.supports_apps && (<>
                        <Field
                            name="web_console_enabled"
                            helpText={
                                <>
                                    {image && !webConsoleSupported && (
                                        <p className="mb-1 text-warning">
                                            <strong>
                                                The selected image does not support the web console.
                                            </strong>
                                        </p>
                                    )}
                                    {webConsoleEnabled && !sshKey.ssh_public_key && (
                                        <p className="mb-1 text-warning">
                                            <strong>
                                                This option has been automatically selected because
                                                you do not have an SSH public key configured.
                                            </strong>
                                        </p>
                                    )}
                                    <p className="mb-0">
                                        Installs software that provides access to the machine via a web browser.
                                    </p>
                                </>
                            }
                        >
                            <BSForm.Check
                                disabled={!webConsoleSupported || !sshKey.ssh_public_key}
                                label="Enable web console?"
                                checked={webConsoleEnabled}
                                onChange={setWebConsoleEnabledFromEvent}
                            />
                        </Field>
                    </>)}
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


export const CreateMachineButton = ({ sshKey, capabilities, disabled, creating, ...props }) => {
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
            {capabilities.supports_apps ? (
                <CreateMachineModal
                    show={visible}
                    onSuccess={close}
                    onCancel={close}
                    creating={creating}
                    sshKey={sshKey}
                    capabilities={capabilities}
                    {...props}
                />
            ) : (
                <ConnectedSSHKeyRequiredModal
                    show={visible}
                    onSuccess={close}
                    onCancel={close}
                    showWarning={true}
                >
                    <CreateMachineModal
                        creating={creating}
                        sshKey={sshKey}
                        capabilities={capabilities}
                        {...props}
                    />
                </ConnectedSSHKeyRequiredModal>
            )}
        </>
    );
};
