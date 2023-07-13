import React, { useEffect, useState } from 'react';

import Button from 'react-bootstrap/Button';
import Col from 'react-bootstrap/Col';
import BSForm from 'react-bootstrap/Form';
import Modal from 'react-bootstrap/Modal';
import ProgressBar from 'react-bootstrap/ProgressBar';
import Row from 'react-bootstrap/Row';

import get from 'lodash/get';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faPlus, faSave } from '@fortawesome/free-solid-svg-icons';

import Cookies from 'js-cookie';

import { Error, Field, Form, Loading, sortBy } from '../../../../utils';

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
                const response = await fetch(
                    `/api/tenancies/${tenancyId}/clusters/schedule/`,
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


// The ordering for standard quotas
const quotaOrdering = ["machines", "volumes", "external_ips", "cpus", "ram", "storage"];


const ProjectedQuotaProgressBar = ({ quota }) => {
    const max = Math.max(quota.allocated, quota.projected);
    return (
        <div className="scheduling-projected-quota mb-3">
            {quota.label}
            <ProgressBar>
                <ProgressBar variant="info" now={quota.current} max={max} />
                <ProgressBar variant="warning" now={quota.delta} max={max} />
            </ProgressBar>
        </div>
    );
};


const ProjectedQuotas = ({ quotas }) => {
    const sortedQuotas = sortBy(
        quotas,
        q => {
            // Use a tuple of (index, name) so we can support unknown quotas
            const index = quotaOrdering.findIndex(el => el === q.resource);
            return [index >= 0 ? index : quotaOrdering.length, q.resource];
        }
    );
    return sortedQuotas.map(quota => <ProjectedQuotaProgressBar quota={quota} />);
};


const QuotaConfirmModal = ({ tenancyId, formState, visible, onCancel, onConfirm }) => {
    const { loading, fits, quotas, error } = useSchedulingData(tenancyId, formState);

    return (
        <Modal show={visible} backdrop="static" keyboard={false} size="md">
            <Modal.Header>
                <Modal.Title>Platform scheduling</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                {(loading || error) ? (
                    <Row className="justify-content-center">
                        <Col xs={`auto py-${loading ? 3 : 2}`}>
                            {loading ? (
                                <Loading message="Checking scheduling constraints..." />
                            ) : (
                                <Error message="Error checking scheduling constraints" />
                            )}
                        </Col>
                    </Row>
                ) : (
                    <Row>
                        <Col>
                            {fits ? (
                                <>
                                    <p>The selected options will consume the following resources:</p>
                                    <ProjectedQuotas quotas={quotas} />
                                    <p>Are you sure you want to proceed?</p>
                                </>
                            ): (
                                <>
                                    <p className="text-danger fw-bold">
                                        The selected options do not fit within your quotas:
                                    </p>
                                    <ProjectedQuotas quotas={quotas} />
                                    <p>Please revise the selected options and try again.</p>
                                </>
                            )}
                        </Col>
                    </Row>
                )}
            </Modal.Body>
            <Modal.Footer>
                <Button variant="secondary" onClick={onCancel}>Cancel</Button>
                <Button
                    variant="success"
                    onClick={onConfirm}
                    disabled={loading || error || !fits}
                >
                    <FontAwesomeIcon icon={faPlus} className="me-2" />
                    Create platform
                </Button>
            </Modal.Footer>
        </Modal>
    );
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
    const [name, setName] = useState(cluster ? cluster.name : "");
    const [parameterValues, setParameterValues] = useState(
        initialParameterValues(clusterType, cluster)
    );
    return [
        {
            clusterType,
            isEdit: !!cluster,
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
    const [showConfirm, setShowConfirm] = useState(false);

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
        setShowConfirm(true);
    };
    const handleCancel = () => setShowConfirm(false);
    const handleConfirm = () => onSubmit({
        name: formState.name,
        parameterValues: formState.parameterValues
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
            {showConfirm && (
                <QuotaConfirmModal
                    tenancyId={tenancy.id}
                    formState={formState}
                    visible={showConfirm}
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
