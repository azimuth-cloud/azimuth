import React, { useEffect, useState } from 'react';

import Button from 'react-bootstrap/Button';
import Col from 'react-bootstrap/Col';
import BSForm from 'react-bootstrap/Form';
import InputGroup from 'react-bootstrap/InputGroup';
import Modal from 'react-bootstrap/Modal';
import Row from 'react-bootstrap/Row';

import { StatusCodes } from 'http-status-codes';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
    faExclamationCircle,
    faExclamationTriangle,
    faPlus,
    faSave,
    faSyncAlt
} from '@fortawesome/free-solid-svg-icons';

import { Field, Form, Select } from '../../../../utils';

import { SchemaField, getInitialValueFromSchema } from '../../../../json-schema-field';

import { KubernetesClusterSelectControl } from '../../resource-utils';

import { PlatformTypeCard } from '../utils';

import { KubernetesClusterModalForm } from '../kubernetes/form';


const KubernetesClusterSelectControlWithCreate = ({
    kubernetesClusterTemplates,
    kubernetesClusterTemplateActions,
    sizes,
    sizeActions,
    externalIps,
    externalIpActions,
    tenancy,
    capabilities,
    ...props
}) => {
    const [modalVisible, setModalVisible] = useState(false);
    const showModal = () => setModalVisible(true);
    const hideModal = () => setModalVisible(false);

    const [createdClusterName, setCreatedClusterName] = useState("");
    const createdCluster = createdClusterName ?
        Object.values(props.resource.data).find(c => c.name == createdClusterName) :
        null;

    const handleSubmit = data => {
        props.resourceActions.create(data);
        setCreatedClusterName(data.name);
        hideModal();
    };

    useEffect(
        () => {
            if( createdCluster ) {
                props.onChange(createdCluster.id);
                setCreatedClusterName("");
            }
        },
        [createdCluster]
    )

    return (
        <>
            <InputGroup className={props.isInvalid ? "is-invalid" : undefined}>
                <KubernetesClusterSelectControl
                    {...props}
                    disabled={props.disabled || props.resource.creating}
                />
                <Button
                    variant="success"
                    disabled={props.disabled || props.resource.creating}
                    onClick={showModal}
                    title="Create a Kubernetes cluster"
                >
                    <FontAwesomeIcon
                        icon={props.resource.creating ? faSyncAlt : faPlus}
                        fixedWidth
                        spin={props.resource.creating}
                    />
                </Button>
            </InputGroup>
            <KubernetesClusterModalForm
                show={modalVisible}
                onSubmit={handleSubmit}
                onCancel={hideModal}
                kubernetesClusterTemplates={kubernetesClusterTemplates}
                kubernetesClusterTemplateActions={kubernetesClusterTemplateActions}
                sizes={sizes}
                sizeActions={sizeActions}
                externalIps={externalIps}
                externalIpActions={externalIpActions}
                tenancy={tenancy}
                capabilities={capabilities}
            />
        </>
    );
};


const initialValues = (kubernetesAppTemplate, kubernetesApp) => {
    if( kubernetesApp ) {
        const version = kubernetesAppTemplate.versions.find(v => v.name === kubernetesApp.version);
        // If the version is no longer supported, there is no schema to populate defaults
        return (
            version ?
                getInitialValueFromSchema(
                    version.values_schema,
                    version.ui_schema,
                    kubernetesApp.values
                ) :
                kubernetesApp.values
        );
    }
    else {
        const version = kubernetesAppTemplate.versions[0];
        return getInitialValueFromSchema(version.values_schema, version.ui_schema);
    }
};


const initialState = (kubernetesAppTemplate, kubernetesApp) => ({
    name: kubernetesApp?.name || "",
    kubernetesCluster: kubernetesApp?.kubernetes_cluster?.id || "",
    // Use the latest version by default
    version: kubernetesApp ? kubernetesApp.version : kubernetesAppTemplate.versions[0].name,
    values: initialValues(kubernetesAppTemplate, kubernetesApp),
});


export const useKubernetesAppFormState = (kubernetesAppTemplate, kubernetesApp) => {
    const [state, setState] = useState(initialState(kubernetesAppTemplate, kubernetesApp));
    const setName = name => setState(state => ({ ...state, name }));
    const setKubernetesCluster = kubernetesCluster => setState(state => ({ ...state, kubernetesCluster }));
    // When the version changes, we also want to recompute the values to fill in any new defaults
    const setVersion = version => setState(state => {
        const templateVersion = kubernetesAppTemplate.versions.find(v => v.name === version);
        return {
            ...state,
            version,
            values: getInitialValueFromSchema(
                templateVersion.values_schema,
                templateVersion.ui_schema,
                state.values
            )
        };
    });
    const setValues = values => setState(state => ({ ...state, values }));

    return [
        {
            ...state,
            kubernetesAppTemplate,
            kubernetesApp,
            isEdit: !!kubernetesApp,
            setName,
            setKubernetesCluster,
            setVersion,
            setValues
        },
        () => setState(initialState(kubernetesAppTemplate, kubernetesApp))
    ]
};



export const KubernetesAppForm = ({
    formState,
    onSubmit,
    tenancy,
    tenancyActions,
    capabilities,
    ...props
}) => {
    const handleNameChange = evt => formState.setName(evt.target.value);
    const handleSubmit = evt => {
        evt.preventDefault();
        onSubmit({
            name: formState.name,
            kubernetesCluster: formState.kubernetesCluster,
            version: formState.version,
            values: formState.values
        });
    };

    const {
        externalIps,
        kubernetesClusters,
        kubernetesClusterTemplates,
        sizes
    } = tenancy;
    const {
        externalIp: externalIpActions,
        kubernetesCluster: kubernetesClusterActions,
        kubernetesClusterTemplate: kubernetesClusterTemplateActions,
        size: sizeActions
    } = tenancyActions;

    const selectedVersion = formState.kubernetesAppTemplate.versions.find(
        version => version.name === formState.version
    );
    const selectedVersionIsLatest = (
        selectedVersion &&
        selectedVersion.name === formState.kubernetesAppTemplate.versions[0].name
    );

    // Determine if Kubernetes clusters are supported or not
    // If they are, we require a cluster to be selected when creating an app
    // If they are not, we allow apps to be created with no cluster selected
    // NOTE(mkjpryor) this logic assumes that the clusters have been fetched already
    //                this is a reasonable assumption since they are loaded when the
    //                platforms page loads
    const kubernetesClustersSupported = (
        kubernetesClusters.initialised ||
        !kubernetesClusters.fetchError ||
        kubernetesClusters.fetchError.statusCode !== StatusCodes.NOT_FOUND
    );

    return (
        <Form
            {...props}
            disabled={
                kubernetesClustersSupported && (
                    !kubernetesClusters.initialised ||
                    kubernetesClusters.creating
                )
            }
            onSubmit={handleSubmit}
        >
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
            {kubernetesClustersSupported && (
                <Field
                    name="kubernetes_cluster"
                    label="Kubernetes cluster"
                    helpText="The Kubernetes cluster to deploy the platform on."
                >
                    <KubernetesClusterSelectControlWithCreate
                        resource={kubernetesClusters}
                        resourceActions={kubernetesClusterActions}
                        required
                        disabled={formState.isEdit}
                        value={formState.kubernetesCluster}
                        onChange={formState.setKubernetesCluster}
                        kubernetesClusterTemplates={kubernetesClusterTemplates}
                        kubernetesClusterTemplateActions={kubernetesClusterTemplateActions}
                        sizes={sizes}
                        sizeActions={sizeActions}
                        externalIps={externalIps}
                        externalIpActions={externalIpActions}
                        tenancy={tenancy}
                        capabilities={capabilities}
                    />
                </Field>
            )}
            <Field
                name="version"
                label="App version"
                helpText={
                    <>
                        The version of the application to use.<br />
                        {selectedVersion ? (
                            !selectedVersionIsLatest && (
                                <strong className="text-warning">
                                    <FontAwesomeIcon icon={faExclamationTriangle} className="me-2" />
                                    The selected version is not the most recent version.
                                </strong>
                            )
                        ) : (
                            <strong className="text-danger">
                                <FontAwesomeIcon icon={faExclamationCircle} className="me-2" />
                                The deployed version is no longer supported.
                            </strong>
                        )}
                    </>
                }
            >
                <BSForm.Control
                    as={Select}
                    required
                    options={formState.kubernetesAppTemplate.versions}
                    getOptionLabel={version => version.name}
                    getOptionValue={version => version.name}
                    sortOptions={versions => versions}
                    value={formState.version}
                    onChange={formState.setVersion}
                    // Prevent the user changing the version on create
                    disabled={!formState.isEdit}
                    // Disable versions that are older than the current version
                    isOptionDisabled={version => {
                        if( formState.kubernetesApp ) {
                            const versions = formState.kubernetesAppTemplate.versions;
                            const currentIdx = versions.findIndex(v => v.name === formState.kubernetesApp.version);
                            const versionIdx = versions.findIndex(v => v.name === version.name);
                            return currentIdx >= 0 && currentIdx < versionIdx;
                        }
                        else {
                            // If there is no initial version, only the latest version is available
                            return false;
                        }
                    }}
                />
            </Field>
            {selectedVersion && (
                <SchemaField
                    value={formState.values}
                    onChange={formState.setValues}
                    schema={selectedVersion.values_schema}
                    uiSchema={selectedVersion.ui_schema}
                />
            )}
        </Form>
    );
};


export const KubernetesAppModalForm = ({
    show,
    kubernetesAppTemplate,
    kubernetesApp,
    onSubmit,
    onCancel,
    tenancy,
    tenancyActions,
    capabilities,
    ...props
}) => {
    const formId = (
        kubernetesApp ?
            `kubernetes-app-update-${kubernetesApp.id}` :
            "kubernetes-app-create"
    );
    const [formState, resetForm] = useKubernetesAppFormState(kubernetesAppTemplate, kubernetesApp);
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
                    {kubernetesApp ?
                        `Update platform ${kubernetesApp.name}` :
                        'Create a new platform'
                    }
                </Modal.Title>
            </Modal.Header>
            <Modal.Body>
                {kubernetesAppTemplate && (
                    <Row className="justify-content-center">
                        <Col xs="auto">
                            <PlatformTypeCard
                                platformType={{
                                    name: kubernetesAppTemplate.label,
                                    logo: kubernetesAppTemplate.logo,
                                    description: kubernetesAppTemplate.description
                                }}
                            />
                        </Col>
                    </Row>
                )}
                <KubernetesAppForm
                    id={formId}
                    formState={formState}
                    onSubmit={onSubmit}
                    tenancy={tenancy}
                    tenancyActions={tenancyActions}
                    capabilities={capabilities}
                />
            </Modal.Body>
            <Modal.Footer>
                <Button variant="success" type="submit" form={formId}>
                    {kubernetesApp ? (
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
