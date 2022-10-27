import React, { useEffect } from 'react';

import FormControl from 'react-bootstrap/FormControl';

import { withCustomValidity } from '../../utils';

import { getValueAtPath } from '../schema-utils';


const InputWithCustomValidity = withCustomValidity("input");


export const MirrorControl = ({
    path,
    schema,
    required,
    value,
    onChange,
    errors,
    root,
    uiSchemaControlProps: { path: mirrorPath },
    ...props
}) => {
    // Make sure that the value matches the mirror value
    const mirrorValue = getValueAtPath(root, mirrorPath);
    useEffect(
        () => { if( value !== mirrorValue ) onChange(mirrorValue); },
        [value, mirrorValue]
    );
    /*
     * Although there are built-in validations for pattern, email, url, ...,
     * the errors produced by ajv are better so we use them instead
     */
    return (
        <FormControl
            as={InputWithCustomValidity}
            readOnly
            autoComplete="off"
            placeholder={schema.title || path}
            value={value || ""}
            {...props}
        />
    );
};
