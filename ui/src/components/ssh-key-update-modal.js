/**
 * This module contains the React component for the SSH key update modal.
 */

import React, { useEffect, useRef, useState } from 'react';

import Alert from 'react-bootstrap/Alert';
import Button from 'react-bootstrap/Button';
import FormControl from 'react-bootstrap/FormControl';
import Modal from 'react-bootstrap/Modal';

import { bindActionCreators } from 'redux';
import { useDispatch, useSelector } from 'react-redux';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faKey, faSyncAlt } from '@fortawesome/free-solid-svg-icons';

import { parseKey } from 'sshpk';

import { actionCreators } from '../redux/ssh-public-key';
 
import { Form, Field, Loading, withCustomValidity } from './utils';


// Function to validate an SSH key and return a validation message
const validateSSHKey = (value, allowedKeyTypes, rsaMinBits) => {
    // Allow empty values from this validation
    if( !value ) return;
    // Try to parse the SSH key
    let sshKey;
    try {
        sshKey = parseKey(value, 'ssh');
    }
    catch {
        return 'Please enter a valid SSH public key.';
    }
    // Check that the value starts with one of the allowed types
    const keyType = value.split(/\s+/)[0];
    if( !allowedKeyTypes.includes(keyType) ) {
        return `Keys of type '${keyType}' are not permitted.`;
    }
    if( sshKey.type === 'rsa' && sshKey.size < rsaMinBits ) {
        return `RSA keys must have at least ${rsaMinBits} bits (${sshKey.size} given).`;
    }
};


const TextareaWithCustomValidity = withCustomValidity("textarea");


const SSHKeyInput = ({ value, onChange, allowedKeyTypes, rsaMinBits, ...props }) => {
    // Calculate the validation message for the current value
    const validationMessage = validateSSHKey(value, allowedKeyTypes, rsaMinBits) || '';
    // Call the onChange handler with the actual value from the field
    const handleChange = (evt) => onChange(evt.target.value);
    return (
        <TextareaWithCustomValidity
            value={value}
            onChange={handleChange}
            validationMessage={validationMessage}
            {...props}
        />
    );
};

 
export const SSHKeyUpdateModal = ({
    show,
    onSuccess,  // Success in this context is the form submitting successfully
    onCancel,
    sshKey,
    sshKeyActions,
    showWarning = false,
    ...props
}) => {
    const [sshPublicKey, setSSHPublicKey] = useState(sshKey.ssh_public_key || '');
    // Account for the case where the SSH key is not initialised when the modal is opened
    // The form will be disabled until the SSH key is initialised so this is safe to do
    useEffect(
        () => { if( sshKey.initialised ) setSSHPublicKey(sshKey.ssh_public_key || ''); },
        [sshKey.initialised]
    );
    // In order to avoid a flicker, we reset the key as the modal opens, not closes
    useEffect(
        () => { if( show ) setSSHPublicKey(sshKey.ssh_public_key || ''); },
        [show]
    );

    const handleSubmit = (evt) => {
        evt.preventDefault();
        sshKeyActions.update(sshPublicKey);
        if( onSuccess ) onSuccess();
    };
 
    return (
        <Modal backdrop="static" show={show} onHide={onCancel} size="lg" {...props}>
            <Modal.Header closeButton>
                <Modal.Title>SSH public key</Modal.Title>
            </Modal.Header>
            <Form
                onSubmit={handleSubmit}
                disabled={!sshKey.can_update || !sshKey.initialised || sshKey.updating}
            >
                <Modal.Body>
                    <Alert variant="info">
                        <p className="mb-0">
                            This SSH public key will be injected into machines that you create,
                            allowing you to access those machines via SSH.
                        </p>
                    </Alert>
                    {sshKey.can_update && showWarning && (
                        <Alert variant="warning">
                            <p className="mb-0">
                                Before creating a machine or cluster, you must
                                set an SSH public key.
                            </p>
                        </Alert>
                    )}
                    {sshKey.initialised && !sshKey.can_update && (
                        <Alert variant="warning">
                            <p className="mb-0">
                                This key is retrieved from another system and cannot be updated here.
                                If you do not know how to set or update this key, please contact
                                your system administrator or helpdesk.
                            </p>
                        </Alert>
                    )}
                    <Field
                        name="ssh_public_key"
                        label="SSH Public Key"
                        helpText={
                            sshKey.can_update ?
                                `Allowed key types: ${sshKey.allowed_key_types.sort().join(', ')}` :
                                undefined
                        }
                    >
                        {sshKey.fetching ? (
                            <Loading message="Loading SSH public key..." />
                        ) : (
                            <FormControl
                                as={SSHKeyInput}
                                rows={8}
                                value={sshPublicKey}
                                onChange={setSSHPublicKey}
                                placeholder="No SSH public key set."
                                required
                                readOnly={!sshKey.can_update}
                                allowedKeyTypes={sshKey.allowed_key_types}
                                rsaMinBits={sshKey.rsa_min_bits}
                            />
                        )}
                    </Field>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="primary" type="submit">
                        <FontAwesomeIcon
                            icon={sshKey.updating ? faSyncAlt : faKey}
                            spin={sshKey.updating}
                            className="me-2"
                        />
                        Update key
                    </Button>
                </Modal.Footer>
            </Form>
        </Modal>
    );
};


export const ConnectedSSHKeyUpdateModal = (props) => {
    const dispatch = useDispatch();
    const sshKeyState = useSelector(state => state.sshKey);
    const sshKeyActions = bindActionCreators(actionCreators, dispatch);
    return (
        <SSHKeyUpdateModal
            {...props}
            sshKey={sshKeyState}
            sshKeyActions={sshKeyActions}
        />
    );
};


// This component wraps another modal and requires that an SSH key is set
// before it will show that modal
export const SSHKeyRequiredModal = ({
    children,
    show,
    onSuccess,
    onCancel,
    sshKey,
    ...props
}) => (
    <>
        {React.Children.map(
            children,
            c => React.cloneElement(
                c,
                { show, onSuccess, onCancel }
            )
        )}
        <SSHKeyUpdateModal
            show={
                // We need to show the SSH key modal over the wrapped modal if
                // the modal is visible and either
                show && (
                    // the user has no SSH key and is able to set one
                    (!sshKey.ssh_public_key && sshKey.can_update) ||
                    // or the SSH key is updating
                    sshKey.updating
                )
            }
            onCancel={onCancel}
            sshKey={sshKey}
            {...props}
        />
    </>
);


export const ConnectedSSHKeyRequiredModal = (props) => {
    const dispatch = useDispatch();
    const sshKeyState = useSelector(state => state.sshKey);
    const sshKeyActions = bindActionCreators(actionCreators, dispatch);
    return (
        <SSHKeyRequiredModal
            {...props}
            sshKey={sshKeyState}
            sshKeyActions={sshKeyActions}
        />
    );
};
