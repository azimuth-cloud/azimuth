import React, { useEffect, useState } from 'react';

import Button from 'react-bootstrap/Button';
import Col from 'react-bootstrap/Col';
import BSForm from 'react-bootstrap/Form';
import InputGroup from 'react-bootstrap/InputGroup';
import Modal from 'react-bootstrap/Modal';
import Row from 'react-bootstrap/Row';

import get from 'lodash/get';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faPlus, faSave, faSyncAlt } from '@fortawesome/free-solid-svg-icons';

import { Field, Form } from '../../../../utils';

import { SchemaField, getInitialValueFromSchema } from '../../../../json-schema-field';

import { KubernetesClusterSelectControl } from '../../resource-utils';

import { PlatformTypeCard } from '../utils';

import { KubernetesClusterModalForm } from '../kubernetes/form';

const KubernetesClusterSelectControlWithCreate = ({
    kubernetesClusterTemplates,
    kubernetesClusterTemplateActions,
    sizes,
    sizeActions,
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
            />
        </>
    );
};


const initialValues = (kubernetesAppTemplate, kubernetesApp) => {
    if( kubernetesApp ) {
        const version = kubernetesAppTemplate.versions.find(v => v === kubernetesApp.version);
        return getInitialValueFromSchema(
            version.values_schema,
            version.ui_schema,
            kubernetesApp.values
        );
    }
    else {
        const version = kubernetesAppTemplate.versions[0];
        return getInitialValueFromSchema(version.values_schema, version.ui_schema);
    }
};


export const useKubernetesAppFormState = (kubernetesAppTemplate, kubernetesApp) => {
    const [name, setName] = useState(kubernetesApp ? kubernetesApp.name : "");
    const [kubernetesCluster, setKubernetesCluster] = useState(
        kubernetesApp ? kubernetesApp.kubernetes_cluster.id : ""
    );
    const [values, setValues] = useState(initialValues(kubernetesAppTemplate, kubernetesApp));
    return [
        {
            kubernetesAppTemplate,
            isEdit: !!kubernetesApp,
            name,
            setName,
            kubernetesCluster,
            setKubernetesCluster,
            values,
            setValues
        },
        () => {
            setName("");
            setKubernetesCluster("");
            setValues(initialValues(kubernetesAppTemplate, kubernetesApp));
        }
    ]
};



export const KubernetesAppForm = ({
    formState,
    onSubmit,
    tenancy,
    tenancyActions,
    ...props
}) => {
    const handleNameChange = evt => formState.setName(evt.target.value);
    const handleSubmit = (evt) => {
        evt.preventDefault();
        onSubmit({
            name: formState.name,
            kubernetesCluster: formState.kubernetesCluster,
            values: formState.values
        });
    };

    // Use the first available version for now
    const version = formState.kubernetesAppTemplate.versions[0];

    const {
        kubernetesClusters,
        kubernetesClusterTemplates,
        sizes
    } = tenancy;
    const {
        kubernetesCluster: kubernetesClusterActions,
        kubernetesClusterTemplate: kubernetesClusterTemplateActions,
        size: sizeActions
    } = tenancyActions;

    return (
        <Form
            {...props}
            disabled={!kubernetesClusters.initialised || kubernetesClusters.creating}
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
                    pattern="^[a-z][a-z0-9-]+[a-z0-9]$"
                    autoComplete="off"
                    disabled={formState.isEdit}
                    value={formState.name}
                    onChange={handleNameChange}
                />
            </Field>
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
                />
            </Field>
            <SchemaField
                value={formState.values}
                onChange={formState.setValues}
                schema={version.values_schema}
                uiSchema={version.ui_schema}
            />
        </Form>
    );
};


// export const ClusterModalForm = ({
//     show,
//     clusterType,
//     cluster,
//     onSubmit,
//     onCancel,
//     tenancy,
//     tenancyActions,
//     ...props
// }) => {
//     const formId = (
//         cluster ?
//             `cluster-update-${cluster.id}` :
//             "cluster-create"
//     );
//     const [formState, clearForm] = useClusterFormState(clusterType, cluster);
//     return (
//         <Modal
//             backdrop="static"
//             onHide={onCancel}
//             onExited={clearForm}
//             size="lg"
//             show={show}
//             {...props}
//         >
//             <Modal.Header closeButton>
//                 <Modal.Title>
//                     {cluster ?
//                         `Update platform ${cluster.name}` :
//                         'Create a new platform'
//                     }
//                 </Modal.Title>
//             </Modal.Header>
//             <Modal.Body>
//                 {clusterType && (
//                     <Row className="justify-content-center">
//                         <Col xs="auto">
//                             <PlatformTypeCard
//                                 platformType={{
//                                     name: clusterType.label,
//                                     logo: clusterType.logo,
//                                     description: clusterType.description
//                                 }}
//                             />
//                         </Col>
//                     </Row>
//                 )}
//                 <ClusterForm
//                     id={formId}
//                     formState={formState}
//                     onSubmit={onSubmit}
//                     tenancy={tenancy}
//                     tenancyActions={tenancyActions}
//                 />
//             </Modal.Body>
//             <Modal.Footer>
//                 <Button variant="success" type="submit" form={formId}>
//                     {cluster ? (
//                         <>
//                             <FontAwesomeIcon icon={faSave} className="me-2" />
//                             Update platform
//                         </>
//                     ) : (
//                         <>
//                             <FontAwesomeIcon icon={faPlus} className="me-2" />
//                             Create platform
//                         </>
//                     )}
//                 </Button>
//             </Modal.Footer>
//         </Modal>
//     );
// };
