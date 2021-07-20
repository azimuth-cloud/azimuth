/**
 * This module contains the modal dialog for cluster creation.
 */

import React, { useEffect, useState } from 'react';

import Button from 'react-bootstrap/Button';
import Card from 'react-bootstrap/Card';
import Col from 'react-bootstrap/Col';
import FormControl from 'react-bootstrap/FormControl';
import Image from 'react-bootstrap/Image';
import Modal from 'react-bootstrap/Modal';
import Nav from 'react-bootstrap/Nav';
import Row from 'react-bootstrap/Row';

import ReactMarkdown from 'react-markdown';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
    faArrowCircleLeft,
    faArrowCircleRight,
    faCheckCircle,
    faPlus,
    faSitemap,
    faSyncAlt
} from '@fortawesome/free-solid-svg-icons';

import { sortBy, Loading, Error, Form, Field } from '../../utils';
import { ConnectedSSHKeyRequiredModal } from '../../ssh-key-update-modal';

import { ClusterParameterField } from './cluster-parameter-field';


const ClusterTypePanel = ({ clusterType, selected, onSelect }) => (
    <Col className="mb-3">
        <Card>
            <Card.Header as="h5">{clusterType.label}</Card.Header>
            <Card.Body className="text-center">
                <p><Image src={clusterType.logo} fluid /></p>
                <ReactMarkdown source={clusterType.description} />
            </Card.Body>
            <Card.Footer className="text-center">
                <Button
                    variant={selected ? "success" : "primary"}
                    onClick={onSelect}
                    disabled={selected}
                >
                    {selected &&
                        <FontAwesomeIcon icon={faCheckCircle} className="me-2" />
                    }
                    Select{selected && 'ed'}
                </Button>
            </Card.Footer>
        </Card>
    </Col>
);


const ClusterTypeForm = ({ clusterTypes, selected, onSelect, goNext }) => {
    const sortedClusterTypes = sortBy(Object.values(clusterTypes), ct => ct.name);
    return (
        <>
            <Modal.Body className="cluster-type-select pb-0">
                <Row xs={1} md={2} lg={3} xl={4} className="justify-content-center">
                    {sortedClusterTypes.length > 0 ? (
                        sortedClusterTypes.map((ct, i) => (
                            <ClusterTypePanel
                                key={i}
                                clusterType={ct}
                                selected={ct.name === selected}
                                onSelect={() => onSelect(ct.name)}
                            />
                        ))
                    ) : (
                        <Col className="text-center text-muted py-4">
                            No cluster types available.
                        </Col>
                    )}
                </Row>
            </Modal.Body>
            <Modal.Footer>
                <Button
                    variant="primary"
                    onClick={goNext}
                    disabled={!selected}
                >
                    <FontAwesomeIcon icon={faArrowCircleRight} className="me-2" />
                    Next
                </Button>
            </Modal.Footer>
        </>
    );
};


const ClusterParametersForm = ({
    clusterType: { label, logo, parameters },
    tenancy,
    tenancyActions,
    onSubmit,
    goBack
}) => {
    const [name, setName] = useState('');
    const [parameterValues, setParameterValues] = useState(
        // For the initial state use the required fields, setting defaults where present
        () => Object.assign(
            {},
            ...parameters
                .filter(p => p.required)
                .map(p => ({ [p.name]: p.default || '' }))
        )
    );

    const handleNameChange = evt => setName(evt.target.value);
    const handleParameterValueChange = (name) => (value) => setParameterValues(
        prevState => {
            if( value !== '' ) {
                return { ...prevState, [name]: value };
            }
            else {
                const { [name]: _, ...nextState } = prevState;
                return nextState;
            }
        }
    );
    const handleSubmit = (evt) => {
        evt.preventDefault();
        onSubmit({ name, parameterValues });
    };

    return (
        <Form onSubmit={handleSubmit}>
            <Modal.Body>
                <Row className="cluster-parameters-type justify-content-center mb-3">
                    <Col xs="auto">
                        <Image src={logo} fluid className="me-3" />
                        <strong>{label}</strong>
                    </Col>
                </Row>
                <Field
                    name="name"
                    label="Cluster name"
                    helpText="Must contain lower-case alphanumeric characters and dash (-) only."
                >
                    <FormControl
                        type="text"
                        placeholder="Cluster name"
                        required
                        pattern="[a-z0-9\-]+"
                        title="Must contain lower-case alphanumeric characters and dash (-) only."
                        autoComplete="off"
                        value={name}
                        onChange={handleNameChange}
                    />
                </Field>
                {parameters.map(p => (
                    <ClusterParameterField
                        key={p.name}
                        tenancy={tenancy}
                        tenancyActions={tenancyActions}
                        isCreate={true}
                        parameter={p}
                        value={parameterValues[p.name] || ''}
                        onChange={handleParameterValueChange(p.name)}
                    />
                ))}
            </Modal.Body>
            <Modal.Footer>
                <Button variant="primary" onClick={goBack}>
                    <FontAwesomeIcon icon={faArrowCircleLeft} className="me-2" />
                    Back
                </Button>
                <Button variant="success" type="submit">
                    <FontAwesomeIcon icon={faPlus} className="me-2" />
                    Create cluster
                </Button>
            </Modal.Footer>
        </Form>
    );
};


const CreateClusterModal = ({
    show,
    onSuccess,
    onCancel,
    create,
    tenancy,
    tenancyActions
}) => {
    const [activeTab, setActiveTab] = useState('clusterType');
    const [clusterType, setClusterType] = useState(null);
    const reset = () => {
        setActiveTab('clusterType');
        setClusterType(null);
    };

    // If we reset the active tab and cluster type when the modal closes, we
    // get an ugly flicker as the animation completes
    // Resetting data as the modal becomes visible fixes this
    useEffect(() => { if( show ) reset(); }, [show]);

    const handleSubmit = ({ name, parameterValues }) => {
        create({
            name,
            cluster_type: clusterType,
            parameter_values: parameterValues
        });
        onSuccess();
    };
    
    return (
        <Modal
            backdrop="static"
            onHide={onCancel}
            // Use a large modal for the cluster type selection
            size={activeTab === "clusterType" ? "xl" : "lg"}
            show={show}
        >
            <Modal.Header closeButton>
                <Modal.Title>Create a new cluster</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <Nav
                    variant="pills"
                    justify
                    activeKey={activeTab}
                    onSelect={setActiveTab}
                >
                    <Nav.Item>
                        <Nav.Link eventKey="clusterType" className="p-3">
                            Pick a cluster type
                        </Nav.Link>
                    </Nav.Item>
                    <Nav.Item>
                        <Nav.Link
                            eventKey="clusterParameters"
                            disabled={!clusterType}
                            className="p-3"
                        >
                            Set cluster options
                        </Nav.Link>
                    </Nav.Item>
                </Nav>
            </Modal.Body>
            {tenancy.clusterTypes.initialised ? (
                activeTab === "clusterType" ? (
                    <ClusterTypeForm
                        clusterTypes={tenancy.clusterTypes.data}
                        selected={clusterType}
                        onSelect={setClusterType}
                        goNext={() => setActiveTab('clusterParameters')}
                    />
                ) : (
                    <ClusterParametersForm
                        tenancy={tenancy}
                        tenancyActions={tenancyActions}
                        clusterType={tenancy.clusterTypes.data[clusterType]}
                        goBack={() => setActiveTab('clusterType')}
                        onSubmit={handleSubmit}
                    />
                )
            ) : (
                <Modal.Body>
                    <Row className="justify-content-center">
                        <Col xs="auto" className="py-4">
                            {(tenancy.clusterTypes.fetchError && !tenancy.clusterTypes.fetching) ? (
                                <Error message={tenancy.clusterTypes.fetchError.message} />
                            ) : (
                                <Loading size="lg" message="Loading cluster types..."/>
                            )}
                        </Col>
                    </Row>
                </Modal.Body>
            )}
        </Modal>
    );
};


export const CreateClusterButton = ({ sshKey, disabled, creating, ...props }) => {
    const [visible, setVisible] = useState(false);
    const open = () => setVisible(true);
    const close = () => setVisible(false);
    return (
        <>
            <Button
                variant="success"
                disabled={sshKey.fetching || disabled || creating}
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
            <ConnectedSSHKeyRequiredModal
                show={visible}
                onSuccess={close}
                onCancel={close}
                showWarning={true}
            >
                <CreateClusterModal creating={creating} {...props} />
            </ConnectedSSHKeyRequiredModal>
        </>
    );
};
