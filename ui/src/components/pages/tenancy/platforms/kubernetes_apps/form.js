import React, { useState } from 'react';

import Button from 'react-bootstrap/Button';
import Col from 'react-bootstrap/Col';
import BSForm from 'react-bootstrap/Form';
import Modal from 'react-bootstrap/Modal';
import Row from 'react-bootstrap/Row';

import get from 'lodash/get';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faSave } from '@fortawesome/free-solid-svg-icons';

import { Field, Form } from '../../../../utils';

import { KubernetesClusterSelectControl } from '../../resource-utils';

import { PlatformTypeCard } from '../utils';


export const useKubernetesAppFormState = (kubernetesAppTemplate, kubernetesApp) => {
    const [name, setName] = useState(kubernetesApp ? kubernetesApp.name : "");
    const [kubernetesCluster, setKubernetesCluster] = useState(
        kubernetesApp ? kubernetesApp.kubernetes_cluster.id : ""
    );
    const [parameterValues, setParameterValues] = useState({});
    return [
        {
            kubernetesAppTemplate,
            isEdit: !!kubernetesApp,
            name,
            setName,
            kubernetesCluster,
            setKubernetesCluster,
            parameterValues,
            setParameterValues
        },
        () => {
            setName("");
            setKubernetesCluster("");
            setParameterValues({});
        }
    ]
};



export const KubernetesAppForm = ({
    formState,
    onSubmit,
    kubernetesClusters,
    kubernetesClusterActions,
    ...props
}) => {
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
        onSubmit({
            name: formState.name,
            kubernetesCluster: formState.kubernetesCluster,
            parameterValues: formState.parameterValues
        });
    };

    return (
        <Form
            {...props}
            disabled={!kubernetesClusters.initialised}
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
                <KubernetesClusterSelectControl
                    resource={kubernetesClusters}
                    resourceActions={kubernetesClusterActions}
                    required
                    disabled={formState.isEdit}
                    value={formState.kubernetesCluster}
                    onChange={formState.setKubernetesCluster}
                />
            </Field>
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
