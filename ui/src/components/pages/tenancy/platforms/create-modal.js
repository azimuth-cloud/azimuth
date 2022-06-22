/**
 * This module contains the modal dialog for cluster creation.
 */

import React, { useState } from 'react';

import Button from 'react-bootstrap/Button';
import Card from 'react-bootstrap/Card';
import Col from 'react-bootstrap/Col';
import FormControl from 'react-bootstrap/FormControl';
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

import { sortBy, Loading, Error, Form, Field } from '../../../utils';
import { ConnectedSSHKeyUpdateModal } from '../../../ssh-key-update-modal';

import { ClusterParameterField } from './parameter-field';
import { ClusterTypeCard as ClusterTypeOverviewCard } from './grid';


const ClusterTypeCard = ({ clusterType, selected, onSelect }) => (
    <Card className="platform-type-card">
        <Card.Header as="h5">{clusterType.label}</Card.Header>
        <Card.Img src={clusterType.logo} />
        <Card.Body className="small">
            <ReactMarkdown children={clusterType.description} />
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
);


const ClusterTypeForm = ({ clusterTypes, selected, onSelect, goNext }) => {
    const sortedClusterTypes = sortBy(Object.values(clusterTypes), ct => ct.name);
    return (
        <>
            <Modal.Body className="cluster-type-select pb-0">
                <Row xs={1} md={2} lg={3} xl={4} className="justify-content-center">
                    {sortedClusterTypes.length > 0 ? (
                        sortedClusterTypes.map((ct, i) => (
                            <Col key={ct.name}>
                                <ClusterTypeCard
                                    clusterType={ct}
                                    selected={ct.name === selected}
                                    onSelect={() => onSelect(ct.name)}
                                />
                            </Col>
                        ))
                    ) : (
                        <Col className="text-center text-muted py-4">
                            No platform templates available.
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
    clusterType,
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
            ...clusterType.parameters
                .filter(p => p.required || p.default !== null)
                .map(p => ({ [p.name]: p.default !== null ? p.default : '' }))
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
                        <ClusterTypeOverviewCard clusterType={clusterType} />
                    </Col>
                </Row>
                <Field
                    name="name"
                    label="Platform name"
                    helpText="Must contain lower-case alphanumeric characters and dash (-) only."
                >
                    <FormControl
                        type="text"
                        placeholder="Platform name"
                        required
                        pattern="[a-z0-9\-]+"
                        autoComplete="off"
                        value={name}
                        onChange={handleNameChange}
                    />
                </Field>
                {clusterType.parameters.map(p => (
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
                    Create platform
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
    tenancyActions,
    sshKey
}) => {
    const [activeTab, setActiveTab] = useState('clusterType');
    const [clusterTypeName, setClusterTypeName] = useState('');
    const reset = () => {
        setActiveTab('clusterType');
        setClusterTypeName('');
    };

    const handleSubmit = ({ name, parameterValues }) => {
        create({
            name,
            cluster_type: clusterTypeName,
            parameter_values: parameterValues
        });
        onSuccess();
    };

    const clusterType = clusterTypeName ? tenancy.clusterTypes.data[clusterTypeName] : null;
    const showSSHKeyModal = (
        activeTab === "clusterParameters" &&
        clusterType &&
        clusterType.requires_ssh_key &&
        !sshKey.ssh_public_key
    );
    
    return (
        <>
            <Modal
                backdrop="static"
                onHide={onCancel}
                onExited={reset}
                // Use a large modal for the cluster type selection
                size={activeTab === "clusterType" ? "xl" : "lg"}
                show={show}
            >
                <Modal.Header closeButton>
                    <Modal.Title>Create a new platform</Modal.Title>
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
                                Pick a platform type
                            </Nav.Link>
                        </Nav.Item>
                        <Nav.Item>
                            <Nav.Link
                                eventKey="clusterParameters"
                                disabled={!clusterType}
                                className="p-3"
                            >
                                Configure platform
                            </Nav.Link>
                        </Nav.Item>
                    </Nav>
                </Modal.Body>
                {tenancy.clusterTypes.initialised ? (
                    activeTab === "clusterType" ? (
                        <ClusterTypeForm
                            clusterTypes={tenancy.clusterTypes.data}
                            selected={clusterTypeName}
                            onSelect={setClusterTypeName}
                            goNext={() => setActiveTab('clusterParameters')}
                        />
                    ) : (
                        <ClusterParametersForm
                            tenancy={tenancy}
                            tenancyActions={tenancyActions}
                            clusterType={clusterType}
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
                                    <Loading size="lg" message="Loading available platforms..."/>
                                )}
                            </Col>
                        </Row>
                    </Modal.Body>
                )}
            </Modal>
            <ConnectedSSHKeyUpdateModal
                show={showSSHKeyModal}
                onCancel={() => setActiveTab('clusterType')}
                warningText="The platform you have selected requires an SSH public key to be set."
            />
        </>
    );
};


export const CreatePlatformButton = ({ sshKey, disabled, creating, ...props }) => {
    const [visible, setVisible] = useState(false);
    const open = () => setVisible(true);
    const close = () => setVisible(false);
    return (
        <>
            <Button
                variant="success"
                disabled={disabled || creating}
                onClick={open}
                title="Create a new platform"
            >
                <FontAwesomeIcon
                    icon={creating ? faSyncAlt : faSitemap}
                    spin={creating}
                    className="me-2"
                />
                {creating ? 'Creating platform...' : 'New platform'}
            </Button>
            <CreateClusterModal
                show={visible}
                onSuccess={close}
                onCancel={close}
                sshKey={sshKey}
                creating={creating}
                {...props}
            />
        </>
    );
};
