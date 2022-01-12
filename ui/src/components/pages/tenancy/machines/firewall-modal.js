/**
 * This module contains the React component for the machine firewall rules modal.
 */

import React, { useEffect, useState } from 'react';

import Alert from 'react-bootstrap/Alert';
import Button from 'react-bootstrap/Button';
import Col from 'react-bootstrap/Col';
import DropdownItem from 'react-bootstrap/DropdownItem';
import FormControl from 'react-bootstrap/FormControl';
import Modal from 'react-bootstrap/Modal';
import Row from 'react-bootstrap/Row';
import Table from 'react-bootstrap/Table';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faBan, faPlus, faSyncAlt } from '@fortawesome/free-solid-svg-icons';

import get from 'lodash/get';

import {
    sortBy,
    ControlWithValidationMessage,
    Error,
    Form,
    Loading,
    Select
} from '../../../utils';


const knownProtocols = ["ANY", "ICMP", "UDP", "TCP"];

const knownServices = {
    'SSH': { protocol: 'TCP', port: 22 },
    'HTTP': { protocol: 'TCP', port: 80 },
    'HTTPS': { protocol: 'TCP', port: 443 }
};

const knownPorts = Object.assign(
    {},
    ...Object.entries(knownServices).map(([service, { port }]) => ({ [port]: service }))
);


/**
 * Because form elements are not allowed inside a table, this cannot be a single
 * component containing a tbody with a form inside
 *
 * Instead, this function returns two components and a reset function:
 *   1. A form component, which should rendered outside the table
 *   2. A tbody component containing the form elements
 *
 * The form elements then use the HTML5 form attribute to link themselves with the form
 * even though they are not inside it
 */
const firewallRuleForm = (machine, machineActions) => {
    const [direction, setDirection] = useState('INBOUND');
    const [service, setService_] = useState('SSH');
    const [protocol, setProtocol] = useState(knownServices['SSH'].protocol);
    const [port, setPort] = useState(knownServices['SSH'].port);
    const [remoteCidr, setRemoteCidr] = useState('');

    // When a service is selected, set the protocol and port
    const setService = selected => {
        setService_(selected);
        // The service will either be a key from knownServices or "CUSTOM", in which case we default to TCP
        setProtocol(get(knownServices, [selected, 'protocol'], 'TCP'));
        setPort(get(knownServices, [selected, 'port'], ''));
    };

    const reset = () => {
        setDirection('INBOUND');
        setService('SSH');
        setRemoteCidr('');
    };
    const setStateFromEvent = setter => evt => setter(evt.target.value);

    // When the state changes from adding to not adding, reset the form
    useEffect(
        () => { if( !machine.addingFirewallRule ) reset(); },
        [machine.addingFirewallRule]
    );

    const handleSubmit = evt => {
        evt.preventDefault();
        machineActions.addFirewallRule({
            direction,
            protocol,
            port: port || null,
            remote_cidr: remoteCidr
        });
    };

    return [
        <Form id="add-firewall-rule" onSubmit={handleSubmit}></Form>,
        <tbody>
            <tr className="table-success">
                <th colSpan={7}>Add a firewall rule</th>
            </tr>
            <tr>
                <td>
                    <FormControl
                        form="add-firewall-rule"
                        id="direction"
                        as={Select}
                        required
                        options={[
                            { label: 'OUTBOUND', value: 'OUTBOUND' },
                            { label: 'INBOUND', value: 'INBOUND' }
                        ]}
                        // Render the options in the order we supplied them
                        sortOptions={options => options}
                        value={direction}
                        onChange={setDirection}
                        style={{ width: '150px' }}
                        disabled={
                            machine.addingFirewallRule ||
                            machine.removingFirewallRule
                        }
                    />
                </td>
                <td>
                    <ControlWithValidationMessage>
                        <FormControl
                            form="add-firewall-rule"
                            id="service"
                            as={Select}
                            required
                            options={[
                                ...Object.keys(knownServices).map(s => ({ label: s, value: s })),
                                { label: "CUSTOM", value: "CUSTOM" }
                            ]}
                            // Render the options in the order we supplied them
                            sortOptions={options => options}
                            value={service}
                            onChange={setService}
                            style={{ width: '120px' }}
                            disabled={
                                machine.addingFirewallRule ||
                                machine.removingFirewallRule
                            }
                        />
                    </ControlWithValidationMessage>
                </td>
                <td>
                    <ControlWithValidationMessage>
                        <FormControl
                            form="add-firewall-rule"
                            id="protocol"
                            as={Select}
                            required
                            options={knownProtocols.map(p => ({ label: p, value: p }))}
                            // Render the options in the order we supplied them
                            sortOptions={options => options}
                            value={protocol}
                            onChange={setProtocol}
                            style={{ width: '120px' }}
                            disabled={
                                machine.addingFirewallRule ||
                                machine.removingFirewallRule ||
                                service !== "CUSTOM"
                            }
                        />
                    </ControlWithValidationMessage>
                </td>
                <td>
                    <ControlWithValidationMessage>
                        <FormControl
                            form="add-firewall-rule"
                            id="port"
                            type="number"
                            step="1"
                            min="1"
                            max="65535"
                            autoComplete="off"
                            placeholder="ANY"
                            value={port}
                            onChange={setStateFromEvent(setPort)}
                            style={{ width: '120px' }}
                            disabled={
                                machine.addingFirewallRule ||
                                machine.removingFirewallRule ||
                                service !== "CUSTOM" ||
                                !["UDP", "TCP"].includes(protocol)
                            }
                        />
                    </ControlWithValidationMessage>
                </td>
                <td>
                    <ControlWithValidationMessage validationMessage="Please enter a valid IPv4 CIDR.">
                        <FormControl
                            form="add-firewall-rule"
                            id="remote_cidr"
                            type="text"
                            pattern="^((25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])\.){3}(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])/(3[0-2]|[1-2]?[0-9])$"
                            placeholder="0.0.0.0/0"
                            autoComplete="off"
                            value={remoteCidr}
                            onChange={setStateFromEvent(setRemoteCidr)}
                            style={{ width: '200px' }}
                            disabled={
                                machine.addingFirewallRule ||
                                machine.removingFirewallRule
                            }
                        />
                    </ControlWithValidationMessage>
                </td>
                <td></td>
                <td style={{ width: '1%' }}>
                    <Button
                        form="add-firewall-rule"
                        type="submit"
                        variant="success"
                        title="Add firewall rule"
                        disabled={
                            machine.addingFirewallRule ||
                            machine.removingFirewallRule
                        }
                    >
                        <FontAwesomeIcon
                            icon={machine.addingFirewallRule ? faSyncAlt : faPlus}
                            fixedWidth
                            spin={machine.addingFirewallRule}
                        />
                    </Button>
                </td>
            </tr>
        </tbody>,
        reset
    ];
};


export const MachineFirewallMenuItem = ({ machine, machineActions, ...props }) => {
    const [formComponent, formElementsComponent, formReset] = firewallRuleForm(machine, machineActions);

    const [visible, setVisible] = useState(false);
    const open = () => setVisible(true);
    const close = () => { setVisible(false); formReset(); };

    // When the modal opens, refresh the rules even if they are already loaded
    useEffect(
        () => {
            if(visible && !machine.fetchingFirewallRules) machineActions.fetchFirewallRules();
        },
        [visible]
    );

    // Order the firewall groups so that the editable groups are last
    const sortedGroups = sortBy(machine.firewallRules || [], group => [group.editable ? 1 : 0, group.name]);

    const sortRules = rules => sortBy(rules, r => [
        // Sort outbound rules before inbound
        r.direction === "OUTBOUND" ? 0 : 1,
        // Sort the protocol
        ['ANY', 'ICMP', 'UDP', 'TCP'].indexOf(r.protocol),
        // Then by ports
        r.port_range ? r.port_range[0] : 0,
        r.port_range ? r.port_range[1] : 0,
        // Then rules for groups before rules for IPs
        r.remote_group,
        r.remote_cidr
    ]);

    let rulesComponent = null;
    if( machine.firewallRules ) {
        rulesComponent = (
            <>
                {machine.fetchFirewallRulesError && (
                    <Row>
                        <Col>
                            <Error message={machine.fetchFirewallRulesError.message} />
                        </Col>
                    </Row>
                )}
                <Row>
                    <Col>
                        {formComponent}
                        <Table responsive className="mb-0 resource-table">
                            <thead>
                                <tr>
                                    <th>Direction</th>
                                    <th>Service</th>
                                    <th>Protocol</th>
                                    <th>Port(s)</th>
                                    <th>Remote IP range</th>
                                    <th>Remote group</th>
                                    <th style={{ width: '1%' }}></th>
                                </tr>
                            </thead>
                            {sortedGroups.filter(group => group.rules.length > 0).map(group => (
                                <tbody key={group.name}>
                                    <tr className={group.editable ? 'table-primary' : 'table-secondary text-muted'}>
                                        <th colSpan={7}>{group.name}</th>
                                    </tr>
                                    {sortRules(group.rules).map(rule => {
                                        let service = '-';
                                        let portRange = 'ANY';
                                        if( rule.port_range ) {
                                            const [minPort, maxPort] = rule.port_range;
                                            if( minPort === maxPort && knownPorts.hasOwnProperty(minPort) ) {
                                                service = knownPorts[minPort];
                                            }
                                            portRange = minPort === maxPort ? minPort : `${minPort} - ${maxPort}`;
                                        }
                                        return (
                                            <tr key={rule.id} className={group.editable ? undefined : 'text-muted'}>
                                                <td>{rule.direction}</td>
                                                <td>{service}</td>
                                                <td>{rule.protocol}</td>
                                                <td>{portRange}</td>
                                                <td>{rule.remote_cidr || '-'}</td>
                                                <td>{rule.remote_group || '-'}</td>
                                                <td style={{ width: '1%' }}>
                                                    {group.editable && (
                                                        <Button
                                                            variant="danger"
                                                            title="Remove firewall rule"
                                                            onClick={() => machineActions.removeFirewallRule(rule.id)}
                                                            disabled={
                                                                machine.addingFirewallRule ||
                                                                machine.removingFirewallRule
                                                            }
                                                        >
                                                            <FontAwesomeIcon
                                                                icon={
                                                                    machine.removingFirewallRule === rule.id ?
                                                                        faSyncAlt :
                                                                        faBan
                                                                }
                                                                fixedWidth
                                                                spin={machine.removingFirewallRule === rule.id}
                                                            />
                                                        </Button>
                                                    )}
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            ))}
                            {formElementsComponent}
                        </Table>
                    </Col>
                </Row>
            </>
        );
    }
    else if( machine.fetchingFirewallRules ) {
        rulesComponent = (
            <Row className="justify-content-center">
                <Col xs="auto py-5">
                    <Loading message="Fetching firewall rules..." size="lg" />
                </Col>
            </Row>
        );
    }
    else if( machine.fetchFirewallRulesError ) {
        rulesComponent = (
            <Row className="justify-content-center">
                <Col xs="auto">
                    <Error message={machine.fetchFirewallRulesError.message} />
                </Col>
            </Row>
        );
    }

    return (
        <>
            <DropdownItem onSelect={open} {...props}>
                Firewall rules
            </DropdownItem>
            <Modal size="xl" backdrop="static" onHide={close} show={visible}>
                <Modal.Header closeButton>
                    <Modal.Title>Firewall rules for {machine.name}</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <Row className="justify-content-center">
                        <Col xs="auto">
                            <Alert variant="warning" className="text-center">
                                Remember that traffic from outside the project cannot reach a{" "}
                                machine unless it has an external IP attached.
                            </Alert>
                        </Col>
                    </Row>
                    <Row className="justify-content-end mb-3">
                        <Col xs="auto">
                            <Button
                                variant="primary"
                                disabled={machine.fetchingFirewallRules}
                                onClick={machineActions.fetchFirewallRules}
                            >
                                <FontAwesomeIcon
                                    icon={faSyncAlt}
                                    spin={machine.fetchingFirewallRules}
                                    className="me-2"
                                />
                                Refresh
                            </Button>
                        </Col>
                    </Row>
                    {rulesComponent}
                </Modal.Body>
                <Modal.Footer>
                    <Button
                        variant="primary"
                        onClick={close}
                        // Ensure that the button appears over the margin for the
                        // responsive wrapper
                        style={{ zIndex: 9999 }}
                    >
                        Close
                    </Button>
                </Modal.Footer>
            </Modal>
        </>
    );
};
