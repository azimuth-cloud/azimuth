import React, { useState } from 'react';

import Button from 'react-bootstrap/Button';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faSitemap, faSyncAlt } from '@fortawesome/free-solid-svg-icons';

import { KubernetesClusterModalForm } from './modal-form';


export const CreateKubernetesClusterButton = ({
    sshKey,
    disabled,
    creating,
    create,
    ...props
}) => {
    const [visible, setVisible] = useState(false);
    const open = () => setVisible(true);
    const close = () => setVisible(false);

    const handleSuccess = data => {
        create(data);
        close();
    };

    return (
        <>
            <Button
                variant="success"
                disabled={disabled || creating}
                onClick={open}
                title="Create a new cluster"
            >
                <FontAwesomeIcon
                    icon={creating ? faSyncAlt : faSitemap}
                    spin={creating}
                    className="me-2"
                />
                {creating ? 'Creating cluster...' : 'New cluster'}
            </Button>
            <KubernetesClusterModalForm
                show={visible}
                onSuccess={handleSuccess}
                onCancel={close}
                {...props}
            />
        </>
    );
};
