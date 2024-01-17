import React from 'react';

import FormControl from 'react-bootstrap/FormControl';

import { withCustomValidity } from '../../utils';


const InputWithCustomValidity = withCustomValidity("input");


export const TextControl = ({
    path,
    schema,
    required,
    value,
    onChange,
    errors,
    root,
    uiSchemaControlProps,
    ...props
}) => {
    /*
     * Although there are built-in validations for pattern, email, url, ...,
     * the errors produced by ajv are better so we use them instead
     */
    return (
        <FormControl
            as={InputWithCustomValidity}
            autoComplete="off"
            placeholder={schema.title || path}
            type={schema.secret ? "password" : "text"}
            required={required}
            minLength={schema.minLength}
            maxLength={schema.maxLength}
            value={value || ""}
            onChange={evt => onChange(evt.target.value)}
            validationMessage={
                errors.length > 0 ?
                    errors[0].message :
                    undefined
            }
            {...props}
        />
    );
};
