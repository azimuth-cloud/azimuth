import React from 'react';

import Button from 'react-bootstrap/Button';
import Col from 'react-bootstrap/Col';
import Modal from 'react-bootstrap/Modal';
import ProgressBar from 'react-bootstrap/ProgressBar';
import Row from 'react-bootstrap/Row';

import { Error, Loading, formatSize, sortBy } from '../../../utils';


// The ordering for standard quotas
const quotaOrdering = ["machines", "volumes", "external_ips", "cpus", "ram", "storage"];


const ProjectedQuotaProgressBar = ({ quota }) => {
    const max = quota.allocated >= 0 ? quota.allocated : Math.max(quota.projected, quota.current);
    const exceeded = quota.allocated >= 0 && quota.projected > quota.allocated;
    const reduction = quota.delta < 0 ? Math.abs(quota.delta) : 0;
    // For aesthetics, cap the size of the increase at the remaining space
    // so that the progress bar never grows bigger than the allocated amount
    // If the increase goes over the allocated, just render the increase as danger
    const increase = Math.min(quota.delta >= 0 ? quota.delta : 0, max - quota.current);
    const formatAmount = amount => (
        ["MB", "GB"].includes(quota.units) ?
            formatSize(amount, quota.units) :
            `${amount}`
    );
    return (
        <div className="scheduling-projected-quota mb-2">
            {quota.label}
            <ProgressBar>
                <ProgressBar variant="primary" now={quota.current - reduction} max={max} />
                <ProgressBar variant="secondary" now={reduction} max={max} />
                <ProgressBar
                    variant={exceeded ? "danger" : "warning"}
                    now={increase}
                    max={max}
                />
            </ProgressBar>
            <small className="text-muted">
                {formatAmount(quota.current)} current
                {" "}/{" "}
                <span className={exceeded ? "text-danger fw-bold" : undefined}>
                    {formatAmount(quota.projected)} projected
                </span>
                {" "}/{" "}
                {
                    quota.allocated >= 0 ?
                        `${formatAmount(quota.allocated)} allocated` :
                        "no limit"
                }
            </small>
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
    return sortedQuotas.map(
        quota => <ProjectedQuotaProgressBar
            key={quota.resource}
            quota={quota}
        />
    );
};


export const PlatformSchedulingModal = ({ useSchedulingData, onCancel, onConfirm }) => {
    const { loading, fits, quotas, error } = useSchedulingData();

    return (
        <Modal show={true} backdrop="static" keyboard={false} size="md">
            <Modal.Header>
                <Modal.Title>Review usage</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                {(loading || error) ? (
                    <Row className="justify-content-center">
                        <Col xs={`auto py-${loading || fits ? 3 : 2}`}>
                            {loading && <Loading message="Checking quotas..." />}
                            {error && <Error message="Error checking quotas" />}
                        </Col>
                    </Row>
                ) : (
                    <Row>
                        <Col>
                            {fits ? (
                                <p>
                                    Please confirm that you are happy with the resources
                                    that your platform will consume.
                                </p>
                            ) : (
                                <Error
                                    message={(
                                        "The requested platform does not fit within your quota. " +
                                        "Revise the selected options and try again."
                                    )}
                                />
                            )}
                            <ProjectedQuotas quotas={quotas} />
                        </Col>
                    </Row>
                )}
            </Modal.Body>
            <Modal.Footer>
                <Button variant="secondary" disabled={loading} onClick={onCancel}>
                    Back
                </Button>
                {!loading && !error && fits && (
                    <Button variant="success" onClick={onConfirm} autoFocus>
                        Confirm
                    </Button>
                )}
            </Modal.Footer>
        </Modal>
    );
};
