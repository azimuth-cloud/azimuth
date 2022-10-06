/**
 * This module contains components for the tenancy machines page.
 */

import React from 'react';

import Card from 'react-bootstrap/Card';
import Col from 'react-bootstrap/Col';
import Row from 'react-bootstrap/Row';

import { CircularProgressbar, buildStyles } from 'react-circular-progressbar';
import 'react-circular-progressbar/dist/styles.css';

import { usePageTitle, formatSize } from '../../utils';

import { ResourcePanel } from './resource-utils';


const QuotaProgress = ({ title, quota: { units, allocated, used } }) => {
    const percent = allocated > 0 ? (used * 100) / allocated : 0;
    const formatAmount = amount => (
        ["MB", "GB"].includes(units) ?
            formatSize(amount, units) :
            `${amount}`
    );
    const label = (
        allocated >= 0 ?
            `${formatAmount(used)} of ${formatAmount(allocated)} used` :
            `${formatAmount(used)} used`
    );
    const colour = (percent <= 60 ? '#5cb85c' : (percent <= 80 ? '#f0ad4e' : '#d9534f'));
    return (
        <Col className="quota-card-wrapper">
            <Card className="h-100">
                <Card.Header><strong>{title}</strong></Card.Header>
                <Card.Body>
                    <CircularProgressbar
                        className={allocated < 0 ? "quota-no-limit" : undefined}
                        value={percent}
                        text={allocated >= 0 ? `${Math.round(percent)}%` : "No limit"}
                        styles={buildStyles({
                            rotation: 0.5,
                            pathColor: colour
                        })}
                    />
                </Card.Body>
                <Card.Footer className="text-muted">{label}</Card.Footer>
            </Card>
        </Col>
    );
};


const Quotas = ({ resourceData }) => (
    // The volume service is optional, so quotas might not always be available for it
    <Row className="g-3 justify-content-center">
        <QuotaProgress title="Machines" quota={resourceData.machines} />
        {resourceData.volumes &&
            <QuotaProgress title="Volumes" quota={resourceData.volumes} />
        }
        <QuotaProgress title="External IPs" quota={resourceData.external_ips} />
        <QuotaProgress title="CPUs" quota={resourceData.cpus} />
        <QuotaProgress title="RAM" quota={resourceData.ram} />
        {resourceData.storage &&
            <QuotaProgress title="Storage" quota={resourceData.storage} />
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
