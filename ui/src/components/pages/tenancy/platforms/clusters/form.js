import React, { useEffect, useState } from 'react';

import Button from 'react-bootstrap/Button';
import Col from 'react-bootstrap/Col';
import BSForm from 'react-bootstrap/Form';
import Modal from 'react-bootstrap/Modal';
import Row from 'react-bootstrap/Row';

import get from 'lodash/get';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faPlus, faSave } from '@fortawesome/free-solid-svg-icons';

import Cookies from 'js-cookie';

import { Error, Field, Form } from '../../../../utils';

import { PlatformSchedulingModal } from '../scheduling';
import { PlatformTypeCard } from '../utils';

import { ClusterParameterField } from './parameter-field';


const useSchedulingData = (tenancyId, formState) => {
    const [state, setState] = useState({
        loading: true,
        fits: false,
        quotas: null,
        error: null
    });

    const setData = (fits, data) => setState({
        loading: false,
        fits,
        quotas: data.quotas,
        error: null
    });
    const setError = error => setState({
        loading: false,
        fits: false,
        quotas: null,
        error
    });

    useEffect(
        () => {
            const fetchData = async () => {
                const headers = { 'Content-Type': 'application/json' };
                const csrfToken = Cookies.get('csrftoken');
                if( csrfToken ) headers['X-CSRFToken'] = csrfToken;
                const url = formState.id ?
                    `/api/tenancies/${tenancyId}/clusters/${formState.id}/schedule/` :
                    `/api/tenancies/${tenancyId}/clusters/schedule/`;
                const response = await fetch(
                    url,
                    {
                        method: "POST",
                        headers,
                        credentials: "same-origin",
                        body: JSON.stringify({
                            name: formState.name,
                            cluster_type: formState.clusterType.name,
                            parameter_values: formState.parameterValues
                        })
                    }
                );
                if( response.ok || response.status === 409 ) {
                    const data = await response.json();
                    setData(response.ok, data);
                }
                else {
                    setError(new Error("HTTP request failed"));
                }
            };
            fetchData().catch(setError);
        },
        []
    );
    return state;
};


const initialParameterValues = (clusterType, cluster) => {
    if( cluster ) {
        return Object.assign(
            {},
            ...clusterType.parameters
                .map(p => [
                    p.name,
                    get(cluster.parameter_values, p.name, p.default || "")
                ])
                .filter(([_, value]) => value !== "")
                .map(([name, value]) => ({ [name]: value }))
        )
    }
    else {
        return Object.assign(
            {},
            ...clusterType.parameters
                .filter(p => p.required || p.default !== null)
                .map(p => ({ [p.name]: p.default !== null ? p.default : "" }))
        );
    }
};


export const useClusterFormState = (clusterType, cluster) => {
    const [id, _] = useState(cluster ? cluster.id : "");
    const [name, setName] = useState(cluster ? cluster.name : "");
    const [parameterValues, setParameterValues] = useState(
        initialParameterValues(clusterType, cluster)
    );
    return [
        {
            clusterType,
            isEdit: !!cluster,
            id,
            name,
            setName,
            parameterValues,
            setParameterValues
        },
        () => {
            setName(cluster ? cluster.name : "");
            setParameterValues(initialParameterValues(clusterType, cluster));
        }
    ]
};

export const ClusterForm = ({
    formState,
    onSubmit,
    tenancy,
    tenancyActions,
    ...props
}) => {
    const [showScheduling, setShowScheduling] = useState(false);

    const handleNameChange = evt => formState.setName(evt.target.value);
    const handleParameterValueChange = (name) => (value) => formState.setParameterValues(
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
        setShowScheduling(true);
    };
    const handleCancel = () => setShowScheduling(false);
    const handleConfirm = schedule => onSubmit({
        name: formState.name,
        parameterValues: formState.parameterValues,
        schedule
    });
    return (
        <>
            <Form {...props} onSubmit={handleSubmit}>
                <Field
                    name="name"
                    label="Platform name"
                    helpText="Must contain lower-case alphanumeric characters and dash (-) only."
                >
                    <BSForm.Control
                        type="text"
                        placeholder="Platform name"
                        required
                        pattern="^[a-z][a-z0-9\-]+[a-z0-9]$"
                        autoComplete="off"
                        disabled={formState.isEdit}
                        value={formState.name}
                        onChange={handleNameChange}
                        autoFocus
                    />
                </Field>
                {formState.clusterType.parameters.map(p => (
                    <ClusterParameterField
                        key={p.name}
                        tenancy={tenancy}
                        tenancyActions={tenancyActions}
                        isCreate={!formState.isEdit}
                        parameter={p}
                        value={formState.parameterValues[p.name] || ''}
                        onChange={handleParameterValueChange(p.name)}
                    />
                ))}
            </Form>
            {showScheduling && (
                <PlatformSchedulingModal
                    useSchedulingData={() => useSchedulingData(tenancy.id, formState)}
                    onCancel={handleCancel}
                    onConfirm={handleConfirm}
                />
            )}
        </>
    );
};


export const ClusterModalForm = ({
    show,
    clusterType,
    cluster,
    onSubmit,
    onCancel,
    tenancy,
    tenancyActions,
    ...props
}) => {
    const formId = (
        cluster ?
            `cluster-update-${cluster.id}` :
            "cluster-create"
    );
    const [formState, resetForm] = useClusterFormState(clusterType, cluster);
    return (
        <Modal
            backdrop="static"
            onHide={onCancel}
            onEnter={resetForm}
            onExited={resetForm}
            size="lg"
            show={show}
            {...props}
        >
            <Modal.Header closeButton>
                <Modal.Title>
                    {cluster ?
                        `Update platform ${cluster.name}` :
                        'Create a new platform'
                    }
                </Modal.Title>
            </Modal.Header>
            <Modal.Body>
                {clusterType && (
                    <Row className="justify-content-center">
                        <Col xs="auto">
                            <PlatformTypeCard
                                platformType={{
                                    name: clusterType.label,
                                    logo: clusterType.logo,
                                    description: clusterType.description
                                }}
                            />
                        </Col>
                    </Row>
                )}
                <ClusterForm
                    id={formId}
                    formState={formState}
                    onSubmit={onSubmit}
                    tenancy={tenancy}
                    tenancyActions={tenancyActions}
                />
            </Modal.Body>
            <Modal.Footer>
                <Button variant="success" type="submit" form={formId}>
                    {cluster ? (
                        <>
                            <FontAwesomeIcon icon={faSave} className="me-2" />
                            Update platform
                        </>
                    ) : (
                        <>
                            <FontAwesomeIcon icon={faPlus} className="me-2" />
                            Create platform
                        </>
                    )}
                </Button>
            </Modal.Footer>
        </Modal>
    );
};
