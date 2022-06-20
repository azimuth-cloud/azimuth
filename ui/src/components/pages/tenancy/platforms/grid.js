import React from 'react';

import Badge from 'react-bootstrap/Badge';
import Button from 'react-bootstrap/Button';
import Card from 'react-bootstrap/Card';
import Col from 'react-bootstrap/Col';
import ListGroup from 'react-bootstrap/ListGroup';
import Row from 'react-bootstrap/Row';

import get from 'lodash/get';

import ReactMarkdown from 'react-markdown';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
    faBookmark,
    faExternalLinkAlt,
} from '@fortawesome/free-solid-svg-icons';

import { bindArgsToActions, sortBy, Loading } from '../../../utils';


const clustersWithLinks = (clusterTypes, clusters) => {
    const linkedParams = Object.assign(
        {},
        ...Object.values(clusterTypes).map(ct => ({
            [ct.name]: ct.parameters
                .filter(p => p.kind === "cloud.cluster")
                .map(p => p.name)
        }))
    );
    // Find the clusters that are linked to by other clusters by looking for
    // the values of the related parameters in each cluster
    const linkedClusters = Object.values(clusters)
        // Map each cluster to the list of clusters that it links to
        .map(c => get(linkedParams, c.cluster_type, []).map(p => c.parameter_values[p]))
        .flat();
    // Attach a "linkedTo" property to each cluster and sort them by name to
    // ensure a consistent rendering
    const clustersWithLinkedTo = Object.values(clusters)
        .map(c => ({ ...c, linkedTo: linkedClusters.includes(c.name) }));
    return clustersWithLinkedTo;
};


const statusBadgeBg = {
    'CONFIGURING': 'primary',
    'READY': 'success',
    'DELETING': 'danger',
    'ERROR': 'danger'
};


const ClusterCard = ({ cluster, clusterTypes, ...props }) => {
    const clusterType = clusterTypes.data[cluster.cluster_type] || {};
    const sortedServices = sortBy(cluster.services, service => service.name);
    return (
        <Card className="platform-card platform-type-cluster">
            <Card.Header>
                <Badge bg={statusBadgeBg[cluster.status]}>{cluster.status}</Badge>
            </Card.Header>
            <Card.Img variant="top" src={clusterType.logo} />
            <Card.Body>
                <Card.Title>{cluster.name}</Card.Title>
                <Card.Subtitle>{clusterType.label}</Card.Subtitle>
            </Card.Body>
            <Card.Body>
                <ReactMarkdown children={clusterType.description} />
            </Card.Body>
            {sortedServices.length > 0 && (
                <ListGroup variant="flush" activeKey={null}>
                    {sortedServices.map(service => (
                        <ListGroup.Item
                            key={service.name}
                            action
                            href={service.url}
                            target="_blank"
                            className="service-list-group-item"
                        >
                            <span>
                                {service.icon_url ? (
                                    <img src={service.icon_url} alt={`${service.label} icon`} />
                                ) : (
                                    <FontAwesomeIcon icon={faBookmark} />
                                )}
                            </span>
                            <span>{service.label}</span>
                            <span><FontAwesomeIcon icon={faExternalLinkAlt} /></span>
                        </ListGroup.Item>
                    ))}
                </ListGroup>
            )}
            <Card.Footer>
                <Button>
                    Details
                </Button>
            </Card.Footer>
        </Card>
    );
};


export const PlatformsGrid = ({
    clusters,
    clusterActions,
    tenancy,
    tenancyActions
}) => {
    const clusterTypes = get(tenancy, ['clusterTypes', 'data']) || {};
    const sortedClusters = sortBy(clustersWithLinks(clusterTypes, clusters), c => c.name);
    if( sortedClusters.length > 0 ) {
        return (
            <Row xs={1} md={2} lg={3} xl={4}>
                {sortedClusters.map((c, i) => (
                    <Col key={i}>
                        <ClusterCard
                            cluster={c}
                            clusterTypes={tenancy.clusterTypes}
                        />
                    </Col>
                ))}
            </Row>
        );
    }
    else {
        return (
            <Row>
                <Col className="text-center text-muted py-5">
                    No platforms have been created yet.
                </Col>
            </Row>
        );
    }
};
