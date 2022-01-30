/**
 * This module contains the modal dialog for machine creation.
 */

import React, { useState } from 'react';

import Button from 'react-bootstrap/Button';
import InputGroup from 'react-bootstrap/InputGroup';
import Modal from 'react-bootstrap/Modal';
import FormControl from 'react-bootstrap/FormControl';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faDatabase, faPlus, faSyncAlt } from '@fortawesome/free-solid-svg-icons';

import { Form, Field } from '../../../utils';


export const CreateVolumeButton = ({ disabled, creating, create }) => {
    const [visible, setVisible] = useState(false);
    const [name, setName] = useState('');
    const [size, setSize] = useState('');

    const open = () => setVisible(true);
    const close = () => {
        setVisible(false);
        setName('');
        setSize('');
    };

    const handleChange = (setter) => (evt) => setter(evt.target.value);
    const handleSubmit = (evt) => {
        evt.preventDefault();
        create({ name: name, size: size });
        close();
    }

    return (
        <>
            <Button
                variant="success"
                disabled={disabled || creating}
                onClick={open}
                title="Create a new volume"
            >
                <FontAwesomeIcon
                    icon={creating ? faSyncAlt : faDatabase}
                    spin={creating}
                    className="me-2"
                />
                {creating ? 'Creating volume...' : 'New volume'}
            </Button>
            <Modal
                backdrop="static"
                onHide={close}
                show={visible}
            >
                <Modal.Header closeButton>
                    <Modal.Title>Create a new volume</Modal.Title>
                </Modal.Header>
                <Form onSubmit={handleSubmit}>
                    <Modal.Body>
                        <Field
                            name="name"
                            label="Volume name"
                            helpText="Must contain alphanumeric characters, dot (.), dash (-) and underscore (_) only."
                        >
                            <FormControl
                                placeholder="Volume name"
                                type="text"
                                required
                                pattern="[A-Za-z0-9\.\-_]+"
                                value={name}
                                onChange={handleChange(setName)}
                            />
                        </Field>
                        <Field
                            name="size"
                            label="Volume Size"
                            helpText="The volume size in GB."
                        >
                            <InputGroup>
                                <FormControl
                                    placeholder="Volume size"
                                    type="number"
                                    required
                                    min="1"
                                    step="1"
                                    value={size}
                                    onChange={handleChange(setSize)}
                                />
                                <InputGroup.Text>GB</InputGroup.Text>
                            </InputGroup>
                        </Field>
                    </Modal.Body>
                    <Modal.Footer>
                        <Button variant="success" type="submit">
                            <FontAwesomeIcon icon={faPlus} className="me-2" />
                            Create volume
                        </Button>
                    </Modal.Footer>
                </Form>
            </Modal>
        </>
    );
};
