import React, { useEffect, useState } from 'react';

import Button from 'react-bootstrap/Button';
import Card from 'react-bootstrap/Card';
import Col from 'react-bootstrap/Col';
import BSForm from 'react-bootstrap/Form';
import InputGroup from 'react-bootstrap/InputGroup';
import Modal from 'react-bootstrap/Modal';
import ProgressBar from 'react-bootstrap/ProgressBar';
import Row from 'react-bootstrap/Row';

import { DateTime } from 'luxon';

import { Error, Field, Form, Loading, Select, formatSize, sortBy } from '../../../utils';


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


const PLATFORM_LIFETIME_UNITS = ["minutes", "hours", "days", "months", "years"];


const PlatformLifetimeControl = ({ isInvalid, value, onChange, ...props }) => {
    const [count, setCount] = useState(value ? value.count : null);
    const [units, setUnits] = useState(value ? value.units : "days");

    const handleCountChange = evt => {
        const newCount = parseInt(evt.target.value, 10);
        setCount(!isNaN(newCount) ? newCount : null);
    };

    useEffect(
        () => { onChange(count ? ({count, units}) : null) },
        [count, units]
    );

    return (
        <InputGroup className={isInvalid ? "is-invalid" : undefined}>
            <BSForm.Control
                isInvalid={isInvalid}
                type="number"
                min="1"
                step="1"
                value={count || ""}
                onChange={handleCountChange}
                {...props}
            />
            <BSForm.Control
                as={Select}
                required
                options={PLATFORM_LIFETIME_UNITS.map(u => ({label: u, value: u}))}
                // Sort the options by their index in the units
                sortOptions={opts => sortBy(opts, opt => PLATFORM_LIFETIME_UNITS.indexOf(opt.value))}
                value={units}
                onChange={setUnits}
            />
            <InputGroup.Text>from now</InputGroup.Text>
        </InputGroup>
    );
};


export const PlatformSchedulingModal = ({
    useSchedulingData,
    isEdit,
    onCancel,
    onConfirm
}) => {
    const { loading, fits, quotas, error } = useSchedulingData();

    const [platformLifetime, setPlatformLifetime] = useState(null);

    const handleConfirm = () => {
        let newSchedule = null;
        if( platformLifetime ) {
            // On confirmation, convert the lifetime to an ISO-formatted end time
            const duration = { [platformLifetime.units]: platformLifetime.count };
            const endTime = DateTime.now().plus(duration);
            newSchedule = { end_time: endTime.toUTC().toISO() };
        }
        onConfirm(newSchedule);
    };

    return (
        <Modal show={true} backdrop="static" onHide={onCancel} size="md">
            <Modal.Header closeButton>
                <Modal.Title>Platform scheduling</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <Form
                    id="platform-scheduling"
                    disabled={loading || error || !fits}
                    onSubmit={handleConfirm}
                >
                    {isEdit ? undefined : (
                        <Field
                            name="platform_lifetime"
                            label="Maximum platform lifetime"
                            helpText="The platform will be automatically deleted after this time."
                        >
                            <PlatformLifetimeControl
                                required
                                value={platformLifetime}
                                onChange={setPlatformLifetime}
                            />
                        </Field>
                    )}
                    <Card>
                        <Card.Header>Platform resource consumption</Card.Header>
                        <Card.Body className="py-2">
                            {(loading || error) ? (
                                <Row className="justify-content-center">
                                    <Col xs="auto py-3">
                                        {loading && <Loading message="Checking quotas..." />}
                                        {error && <Error message="Error checking quotas" />}
                                    </Col>
                                </Row>
                            ) : (
                                <>
                                    <Row>
                                        <Col>
                                            {!fits && (
                                                <Error
                                                    message={
                                                        <>
                                                            The requested platform does not fit within your quota.<br />
                                                            Revise the selected options and try again.
                                                        </>
                                                    }
                                                />
                                            )}
                                            <ProjectedQuotas quotas={quotas} />
                                        </Col>
                                    </Row>
                                </>
                            )}
                        </Card.Body>
                    </Card>
                </Form>
            </Modal.Body>
            <Modal.Footer>
                <Button variant="secondary" disabled={loading} onClick={onCancel}>
                    Back
                </Button>
                <Button
                    variant="success"
                    type="submit"
                    form="platform-scheduling"
                    disabled={loading || error || !fits}
                >
                    Confirm
                </Button>
            </Modal.Footer>
        </Modal>
    );
};
