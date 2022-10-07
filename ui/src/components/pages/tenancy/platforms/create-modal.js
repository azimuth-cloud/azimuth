import React, { useState } from 'react';

import Button from 'react-bootstrap/Button';
import Card from 'react-bootstrap/Card';
import Col from 'react-bootstrap/Col';
import Modal from 'react-bootstrap/Modal';
import Nav from 'react-bootstrap/Nav';
import Row from 'react-bootstrap/Row';

import { StatusCodes } from 'http-status-codes';

import get from 'lodash/get';

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

import { sortBy, Loading, Error } from '../../../utils';
import { ConnectedSSHKeyUpdateModal } from '../../../ssh-key-update-modal';

import { PlatformTypeCard } from './utils';

import { useClusterFormState, ClusterForm } from './clusters/form';

import { useKubernetesClusterFormState, KubernetesClusterForm } from './kubernetes/form';
import KubernetesIcon from './kubernetes/kubernetes-logo.png';


const PlatformTypeSelectCard = ({ platformType, selected, onSelect }) => (
    <Card className="platform-type-select-card">
        <Card.Header as="h5">{platformType.name}</Card.Header>
        <Card.Img src={platformType.logo} />
        <Card.Body className="small">
            <ReactMarkdown
                components={{
                    // Links should open in a new tab
                    a: ({ node, children, ...props }) => (
                        <a target="_blank" {...props}>{children}</a>
                    )
                }}
                children={platformType.description}
            />
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


const PlatformTypeForm = ({ platformTypes, selected, onSelect, goNext }) => {
    const sortedPlatformTypes = sortBy(Object.values(platformTypes), pt => pt.name);
    return (
        <>
            <Modal.Body>
                <Row className="justify-content-center g-3">
                    {sortedPlatformTypes.length > 0 ? (
                        sortedPlatformTypes.map(pt => (
                            <Col key={pt.id} className="platform-type-select-card-wrapper">
                                <PlatformTypeSelectCard
                                    platformType={pt}
                                    selected={pt.id === selected}
                                    onSelect={() => onSelect(pt.id)}
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


const ClusterConfigurationForm = ({
    formId,
    clusterType,
    onSuccess,
    onCancel,
    sshKey,
    tenancy,
    tenancyActions
}) => {
    const [formState, _] = useClusterFormState(clusterType, undefined);

    const showSSHKeyModal = (
        clusterType &&
        clusterType.requires_ssh_key &&
        !sshKey.ssh_public_key
    );

    return (
        <>
            <ClusterForm
                id={formId}
                formState={formState}
                onSubmit={data => {
                    tenancyActions.cluster.create({
                        name: data.name,
                        cluster_type: clusterType.name,
                        parameter_values: data.parameterValues
                    });
                    onSuccess();
                }}
                tenancy={tenancy}
                tenancyActions={tenancyActions}
            />
            <ConnectedSSHKeyUpdateModal
                show={showSSHKeyModal}
                onCancel={onCancel}
                warningText="The platform you have selected requires an SSH public key to be set."
            />
        </>
    );
};


const KubernetesConfigurationForm = ({
    formId,
    onSuccess,
    kubernetesClusterActions,
    kubernetesClusterTemplates,
    kubernetesClusterTemplateActions,
    sizes,
    sizeActions
}) => {
    const [formState, _] = useKubernetesClusterFormState(undefined);
    return (
        <KubernetesClusterForm
            id={formId}
            formState={formState}
            onSubmit={data => {
                kubernetesClusterActions.create(data);
                onSuccess();
            }}
            kubernetesClusterTemplates={kubernetesClusterTemplates}
            kubernetesClusterTemplateActions={kubernetesClusterTemplateActions}
            sizes={sizes}
            sizeActions={sizeActions}
        />
    );
};


const PlatformConfigurationForm = ({
    platformType,
    sshKey,
    tenancy,
    tenancyActions,
    goBack,
    onSuccess
}) => {
    return (
        <>
            <Modal.Body>
                <Row className="justify-content-center">
                    <Col xs="auto">
                        <PlatformTypeCard platformType={platformType} />
                    </Col>
                </Row>
                {platformType.kind === "clusterType" && (
                    <ClusterConfigurationForm
                        formId="platform-create"
                        clusterType={platformType.object}
                        onSuccess={onSuccess}
                        onCancel={goBack}
                        sshKey={sshKey}
                        tenancy={tenancy}
                        tenancyActions={tenancyActions}
                    />
                )}
                {platformType.kind === "kubernetes" && (
                    <KubernetesConfigurationForm
                        formId="platform-create"
                        onSuccess={onSuccess}
                        kubernetesClusterActions={tenancyActions.kubernetesCluster}
                        kubernetesClusterTemplates={tenancy.kubernetesClusterTemplates}
                        kubernetesClusterTemplateActions={tenancyActions.kubernetesClusterTemplate}
                        sizes={tenancy.sizes}
                        sizeActions={tenancyActions.size}
                    />
                )}
            </Modal.Body>
            <Modal.Footer>
                <Button variant="primary" onClick={goBack}>
                    <FontAwesomeIcon icon={faArrowCircleLeft} className="me-2" />
                    Back
                </Button>
                <Button variant="success" type="submit" form="platform-create">
                    <FontAwesomeIcon icon={faPlus} className="me-2" />
                    Create platform
                </Button>
            </Modal.Footer>
        </>
    );
};


const CreatePlatformModal = ({
    show,
    onSuccess,
    onCancel,
    sshKey,
    tenancy,
    tenancyActions
}) => {
    const [activeTab, setActiveTab] = useState("platformType");
    const [platformTypeId, setPlatformTypeId] = useState("");
    const reset = () => {
        setActiveTab("platformType");
        setPlatformTypeId("");
    };

    const clusterTypesNotFound = (
        get(tenancy.clusterTypes.fetchError, "statusCode") === StatusCodes.NOT_FOUND
    );
    const kubernetesClusterTemplatesNotFound = (
        get(tenancy.kubernetesClusterTemplates.fetchError, "statusCode") === StatusCodes.NOT_FOUND
    );
    const platformTypesNotFound = clusterTypesNotFound && kubernetesClusterTemplatesNotFound;

    // Get the aggregate resource for available cluster types + Kubernetes
    // Kubernetes is just a static resource that is available when Kubernetes templates are
    const resource = {
        initialised: (
            // When both are not found, we don't want to become initialised
            !platformTypesNotFound &&
            (tenancy.clusterTypes.initialised || clusterTypesNotFound) &&
            (tenancy.kubernetesClusterTemplates.initialised || kubernetesClusterTemplatesNotFound)
        ),
        fetching: tenancy.clusterTypes.fetching || tenancy.kubernetesClusterTemplates.fetching,
        data: Object.assign(
            {},
            (
                !kubernetesClusterTemplatesNotFound ?
                    {
                        kubernetes: {
                            id: "kubernetes",
                            kind: "kubernetes",
                            name: "Kubernetes",
                            logo: KubernetesIcon,
                            description: (
                                "Kubernetes cluster with optional addons including Kubernetes dashboard, " +
                                "monitoring, ingress and application dashboard."
                            )
                        }
                    } :
                    undefined
            ),
            ...Object.entries(tenancy.clusterTypes.data || {}).map(
                ([key, value]) => ({
                    [`clusterTypes/${key}`]: {
                        id: `clusterTypes/${key}`,
                        kind: "clusterType",
                        name: value.label,
                        logo: value.logo,
                        description: value.description,
                        object: value
                    }
                })
            )
        ),
        // Not found isn't really an error for platforms, so exclude them
        fetchErrors: Object.assign(
            {},
            ...[
                ["clusterTypes", tenancy.clusterTypes.fetchError],
                ["kubernetesClusterTemplates", tenancy.kubernetesClusterTemplates.fetchError]
            ].filter(
                ([_, e]) => !!e && e.statusCode !== StatusCodes.NOT_FOUND
            ).map(
                ([k, e]) => ({ [k]: e })
            )
        )
    };

    return (
        <Modal
            backdrop="static"
            onHide={onCancel}
            onExited={reset}
            // Use a large modal for the cluster type selection
            size={activeTab === "platformType" ? "xl" : "lg"}
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
                        <Nav.Link eventKey="platformType" className="p-3">
                            Pick a platform type
                        </Nav.Link>
                    </Nav.Item>
                    <Nav.Item>
                        <Nav.Link
                            eventKey="platformConfiguration"
                            disabled={!platformTypeId}
                            className="p-3"
                        >
                            Configure platform
                        </Nav.Link>
                    </Nav.Item>
                </Nav>
            </Modal.Body>
            {resource.initialised ? (
                activeTab === "platformType" ? (
                    <PlatformTypeForm
                        platformTypes={resource.data}
                        selected={platformTypeId}
                        onSelect={setPlatformTypeId}
                        goNext={() => setActiveTab("platformConfiguration")}
                    />
                ) : (
                    <PlatformConfigurationForm
                        platformType={resource.data[platformTypeId]}
                        sshKey={sshKey}
                        tenancy={tenancy}
                        tenancyActions={tenancyActions}
                        goBack={() => setActiveTab("platformType")}
                        onSuccess={onSuccess}
                    />
                )
            ) : (
                <Modal.Body>
                    <Row className="justify-content-center">
                        {platformTypesNotFound ? (
                            <Col xs="auto py-3">
                                <Error message="Platforms are not supported." />
                            </Col>
                        ) : (
                            (resource.fetchErrors && !resource.fetching) ? (
                                <Col xs="auto py-3">
                                    {Object.entries(resource.fetchErrors).map(([k, e]) =>
                                        <Error key={k} message={e.message} />
                                    )}
                                </Col>
                            ) : (
                                <Col xs="auto py-5">
                                    <Loading
                                        size="lg"
                                        iconSize="lg"
                                        message={`Loading platform types...`}
                                    />
                                </Col>
                            )
                        )}
                    </Row>
                </Modal.Body>
            )}
        </Modal>
    );
};


export const CreatePlatformButton = ({
    visible,
    setVisible,
    disabled,
    creating,
    ...props
}) => {
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
            <CreatePlatformModal
                show={visible}
                onSuccess={close}
                onCancel={close}
                creating={creating}
                {...props}
            />
        </>
    );
};
