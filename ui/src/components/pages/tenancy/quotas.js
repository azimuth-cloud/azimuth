/**
 * This module contains components for the tenancy quotas page.
 */

import React from 'react';

import Card from 'react-bootstrap/Card';
import Col from 'react-bootstrap/Col';
import Row from 'react-bootstrap/Row';

import { CircularProgressbar, buildStyles } from 'react-circular-progressbar';
import 'react-circular-progressbar/dist/styles.css';

import { sortBy, usePageTitle, formatSize } from '../../utils';

import { ResourcePanel } from './resource-utils';


const QuotaProgress = ({ quota: { label, units, allocated, used } }) => {
    const percent = allocated > 0 ? (used * 100) / allocated : 0;
    const formatAmount = amount => (
        ["MB", "GB"].includes(units) ?
            formatSize(amount, units) :
            `${amount}`
    );
    const usage = (
        allocated >= 0 ?
            `${formatAmount(used)} of ${formatAmount(allocated)} used` :
            `${formatAmount(used)} used`
    );
    const colour = (percent <= 60 ? '#5cb85c' : (percent <= 80 ? '#f0ad4e' : '#d9534f'));
    return (
        <Col className="quota-card-wrapper">
            <Card className="h-100">
                <Card.Header><strong>{label}</strong></Card.Header>
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
                <Card.Footer className="text-muted">{usage}</Card.Footer>
            </Card>
        </Col>
    );
};


// The ordering for standard quotas
const quotaOrdering = ["machines", "volumes", "external_ips", "cpus", "ram", "storage"];


const Quotas = ({ resourceData }) => {
    let sortedQuotas = sortBy(
        Object.values(resourceData),
        q => {
            // Use a tuple of (index, name) so we can support unknown quotas
            const index = quotaOrdering.findIndex(el => el === q.resource);
            return [index >= 0 ? index : quotaOrdering.length, q.resource];
        }
    );

    // Add labels showing quota type (Coral or resource quota) if Coral
    // quotas included
    const hasMixedCoralAndResourceQuotas = new Set(sortedQuotas.map((q) => q.is_coral_quota)).size > 1
    if(hasMixedCoralAndResourceQuotas){
        for(let i = 0;i < sortedQuotas.length;i++){
            const prefix = sortedQuotas[i].is_coral_quota ? "Credits: " : "Quota: ";
            sortedQuotas[i].label = prefix + sortedQuotas[i].label;
        }
    }
    
    // If quota is unlimited but has an associated Coral quota, hide it
    const resourceNames = sortedQuotas.map((q) => q.resource)
    sortedQuotas = sortedQuotas.filter((q) =>
        !(q.related_resource_names.some(r => resourceNames.includes(r))
          && q.allocated < 0)
    )

    return (
        // The volume service is optional, so quotas might not always be available for it
        <Row className="g-3 justify-content-center">
            {sortedQuotas.map(quota => (
                <QuotaProgress key={quota.resource} quota={quota} />)
            )}
        </Row>
    );
};


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
