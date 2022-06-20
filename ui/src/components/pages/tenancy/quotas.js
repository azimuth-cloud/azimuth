/**
 * This module contains components for the tenancy machines page.
 */

import React from 'react';

import Card from 'react-bootstrap/Card';
import Col from 'react-bootstrap/Col';
import Row from 'react-bootstrap/Row';

import Progress from 'react-circle-progress-bar';

import { usePageTitle } from '../../utils';

import { ResourcePanel } from './resource-utils';


const QuotaProgress = ({ title, quota: { units, allocated, used } }) => {
    const percent = allocated > 0 ? (used * 100) / allocated : 0;
    const label = `${used}${units || ''} of ${allocated}${units || ''} used`;
    const colour = (percent <= 60 ? '#5cb85c' : (percent <= 80 ? '#f0ad4e' : '#d9534f'));
    return (
        <Col>
            <Card className="mb-3">
                <Card.Header><strong>{title}</strong></Card.Header>
                <Card.Body className="p-1">
                    <Progress
                        progress={percent}
                        subtitle={title}
                        reduction={0}
                        strokeWidth={12}
                        ballStrokeWidth={24}
                        gradient={[{ color: colour, stop: 1 }]}
                    />
                </Card.Body>
                <Card.Footer className="text-muted">{label}</Card.Footer>
            </Card>
        </Col>
    );
};


const Quotas = (props) => (
    // The volume service is optional, so quotas might not always be available for it
    <Row className="justify-content-center" xl={6} md={4} xs={2}>
        <QuotaProgress title="Machines" quota={props.resourceData.machines} />
        {props.resourceData.volumes &&
            <QuotaProgress title="Volumes" quota={props.resourceData.volumes} />
        }
        <QuotaProgress title="External IPs" quota={props.resourceData.external_ips} />
        <QuotaProgress title="CPUs" quota={props.resourceData.cpus} />
        <QuotaProgress title="RAM" quota={props.resourceData.ram} />
        {props.resourceData.storage &&
            <QuotaProgress title="Storage" quota={props.resourceData.storage} />
        }
    </Row>
);


export const TenancyQuotasPanel = ({ tenancy, tenancyActions }) => {
    usePageTitle("Quotas");
    return (
        <ResourcePanel
            resource={tenancy.quotas}
            resourceActions={tenancyActions.quota}
            resourceName="quotas"
        >
            <Quotas />
        </ResourcePanel>
    );
};
