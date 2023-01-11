import React from 'react';

import Button from 'react-bootstrap/Button';
import Card from 'react-bootstrap/Card';
import Col from 'react-bootstrap/Col';
import ListGroup from 'react-bootstrap/ListGroup';
import Row from 'react-bootstrap/Row';

import get from 'lodash/get';
import { StatusCodes } from 'http-status-codes';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
    faCheck,
    faExternalLink,
    faPowerOff,
    faSyncAlt,
    faTimes
} from '@fortawesome/free-solid-svg-icons';

import { usePageTitle, Loading, Error } from '../../utils';

import { useResourceInitialised } from './resource-utils';


export const TenancyIdpPanel = ({
    tenancy: { idp },
    tenancyActions: { idp: idpActions }
}) => {
    usePageTitle("Identity provider");

    // Make sure that the resource is initialised when the panel loads
    useResourceInitialised(idp, idpActions.fetch);
    // If the resource failed to load because it was not found, disable the refresh button
    const notFound = get(idp.fetchError, 'statusCode') === StatusCodes.NOT_FOUND;
    return (
        <>
            <Row className="justify-content-end mb-3">
                <Col xs="auto">
                    <Button
                        variant="primary"
                        disabled={notFound || idp.fetching}
                        onClick={idpActions.fetch}
                        title="Refresh identity provider"
                    >
                        <FontAwesomeIcon
                            icon={faSyncAlt}
                            spin={idp.fetching}
                            className="me-2"
                        />
                        Refresh
                    </Button>
                </Col>
            </Row>
            <Row className="justify-content-center">
                {idp.initialised ? (
                    <Col xs="auto">
                        <Card className="idp-card">
                            <Card.Body>
                                <Row>
                                    <Col lg={4} className="mb-3">
                                        <div className="d-grid gap-2">
                                            <ListGroup>
                                                <ListGroup.Item className={idp.enabled ? "text-success fw-bold" : "text-muted"}>
                                                    <FontAwesomeIcon
                                                        fixedWidth
                                                        icon={idp.enabled ? faCheck : faTimes}
                                                        className="me-2"
                                                    />
                                                    Identity provider enabled
                                                </ListGroup.Item>
                                                <ListGroup.Item className={idp.status === "Ready" ? "text-success fw-bold" : "text-muted"}>
                                                    <FontAwesomeIcon
                                                        fixedWidth
                                                        icon={idp.status === "Ready" ? faCheck : faTimes}
                                                        className="me-2"
                                                    />
                                                    Identity provider ready
                                                </ListGroup.Item>
                                            </ListGroup>
                                            {idp.enabled ? (
                                                <Button
                                                    size="lg"
                                                    variant="primary"
                                                    disabled={idp.status !== "Ready"}
                                                    href={idp.admin_url || "#"}
                                                    target="_blank"
                                                >
                                                    <FontAwesomeIcon
                                                        icon={faExternalLink}
                                                        className="me-2"
                                                    />
                                                    Open identity provider
                                                </Button>
                                            ) : (
                                                <Button
                                                    size="lg"
                                                    variant="success"
                                                    disabled={idp.updating}
                                                    onClick={idpActions.enable}
                                                >
                                                    <FontAwesomeIcon
                                                        icon={idp.updating ? faSyncAlt : faPowerOff}
                                                        spin={idp.updating}
                                                        className="me-2"
                                                    />
                                                    Enable identity provider
                                                </Button>
                                            )}
                                        </div>
                                    </Col>
                                    <Col lg={8}>
                                        <p>
                                            Each tenancy has an associated identity provider that controls access
                                            to platforms deployed in the tenancy.
                                        </p>
                                        <p>
                                            The identity provider is based on the{" "}
                                            <a href="https://www.keycloak.org/" target="_blank">Keycloak</a>{" "}
                                            open-source identity and access management platform, and each tenancy
                                            is given a Keycloak realm that manages the users, roles and groups
                                            for platforms in that tenancy.
                                        </p>
                                        <p>
                                            By default the realm is configured so that users who can access the
                                            tenancy in Azimuth are able to access the administration console for
                                            the realm. These users are also able to access all platforms deployed
                                            in the tenancy.
                                        </p>
                                        <p className="mb-0">
                                            Using the administration console, additional local users and federated
                                            identity providers (e.g. GitHub, Google or your institution IDP) can be
                                            configured. Those users will not be able to access Azimuth to deploy
                                            platforms, but can be granted access to platforms provisioned by others.
                                        </p>
                                    </Col>
                                </Row>
                            </Card.Body>
                        </Card>
                    </Col>
                ) : (
                    <Col xs="auto py-5">
                        {idp.fetchError && !idp.fetching ? (
                            <Error message={idp.fetchError.message} />
                        ) : (
                            <Loading
                                size="lg"
                                iconSize="lg"
                                message="Loading identity provider..."
                            />
                        )}
                    </Col>
                )}
            </Row>
        </>
    );
};
