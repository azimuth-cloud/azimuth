import { useState } from "react";
import { Table } from "react-bootstrap";

const ConditionRow = ({ condition }) => {
    const [expanded, setExpanded] = useState(false);
    const hasMessage = Boolean(condition.message);

    return (
        <>
            <tr
                onClick={() => hasMessage && setExpanded(!expanded)}
                role={hasMessage ? 'button' : undefined}
                className={expanded ? 'table-active' : ''}
                style={{ cursor: hasMessage ? 'pointer' : 'default' }}
            >
                <td className="fw-semibold">
                    {hasMessage && (
                        <span className="me-2 text-muted user-select-none">
                            {expanded ? '▾' : '▸'}
                        </span>
                    )}
                    {condition.type}
                </td>
                <td>{condition.status}</td>
                <td>
                    {new Date(condition.last_transition_time).toLocaleString()}
                </td>
                <td><code>{condition.reason}</code></td>
            </tr>

            {expanded && hasMessage && (
                <tr className="bg-light">
                    <td colSpan={4} className="p-3">
                        <pre
                            className="mb-0 bg-white text-dark p-2 border rounded text-break"
                            style={{ whiteSpace: 'pre-wrap', maxHeight: '200px', overflowY: 'auto' }}
                        >
                            {condition.message}
                        </pre>
                    </td>
                </tr>
            )}
        </>
    );
};

export const ConditionsTable = ({ kubernetesCluster}) => {
    const conditions = [...(kubernetesCluster?.conditions || [])].sort((a, b) =>
        (b.last_transition_time || '').localeCompare(a.last_transition_time || '')
    );

    return (

        <Table striped hover responsive className="resource-table mb-0">
            <caption className="px-2">
                {conditions.length} condition{conditions.length !== 1 && 's'}
            </caption>
            <thead>
                <tr>
                    <th>Condition</th>
                    <th>Status</th>
                    <th>Last Transition</th>
                    <th>Reason</th>
                </tr>
            </thead>
            <tbody>
                {conditions.map(condition => (
                    <ConditionRow key={`${condition.type}-${condition.last_transition_time}`} condition={condition} />
                ))}
            </tbody>
        </Table>
    );
};