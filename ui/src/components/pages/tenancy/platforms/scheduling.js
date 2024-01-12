import React, { useEffect } from 'react';

import Button from 'react-bootstrap/Button';
import Col from 'react-bootstrap/Col';
import Modal from 'react-bootstrap/Modal';
import ProgressBar from 'react-bootstrap/ProgressBar';
import Row from 'react-bootstrap/Row';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faCheckCircle } from '@fortawesome/free-solid-svg-icons';

import { Error, Loading, formatSize, sortBy } from '../../../utils';


// The ordering for standard quotas
const quotaOrdering = ["machines", "volumes", "external_ips", "cpus", "ram", "storage"];


const ProjectedQuotaProgressBar = ({ quota }) => {
    const max = quota.allocated >= 0 ? quota.allocated : quota.projected;
    const exceeded = quota.allocated >= 0 && quota.projected > quota.allocated;
    // We want the total size of the progress bar to be at most max
    // If the projected quota is greater than the allocation, we just render it
    // as danger instead of warning
    const delta = Math.min(
        quota.delta,
        quota.allocated >= 0 ? quota.allocated - quota.current : quota.delta
    );
    const formatAmount = amount => (
        ["MB", "GB"].includes(quota.units) ?
            formatSize(amount, quota.units) :
            `${amount}`
    );
    return (
        <div className="scheduling-projected-quota mb-2">
            {quota.label}
            <ProgressBar>
                <ProgressBar variant="primary" now={quota.current} max={max} />
                <ProgressBar
                    variant={exceeded ? "danger" : "warning"}
                    now={delta}
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

    // If the platform fits within the quotas, just inform the user and create it
    useEffect(
        () => {
            if( loading || !fits ) return;
            const timeout = setTimeout(onConfirm, 1500);
            return () => { clearTimeout(timeout); };
        },
        [loading, fits]
    );

    return (
        <Modal show={true} backdrop="static" keyboard={false} size="md">
            <Modal.Header>
                <Modal.Title>Platform scheduling</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                {(loading || error || fits) ? (
                    <Row className="justify-content-center">
                        <Col xs={`auto py-${loading || fits ? 3 : 2}`}>
                            {loading && <Loading message="Checking scheduling constraints..." />}
                            {error && <Error message="Error checking scheduling constraints" />}
                            {fits && (
                                <div className="text-success fw-bold">
                                    <FontAwesomeIcon icon={faCheckCircle} className="me-2" />
                                    Platform can be scheduled now
                                </div>
                            )}
                        </Col>
                    </Row>
                ) : (
                    <Row>
                        <Col>
                            <p className="text-danger fw-bold">
                                The selected options do not fit within your quotas:
                            </p>
                            <ProjectedQuotas quotas={quotas} />
                            <p className="mb-0">
                                Please revise the selected options and try again.
                            </p>
                        </Col>
                    </Row>
                )}
            </Modal.Body>
            <Modal.Footer>
                <Button variant="secondary" disabled={loading || fits} onClick={onCancel}>
                    Close
                </Button>
            </Modal.Footer>
        </Modal>
    );
};
