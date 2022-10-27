import React from 'react';

import FormControl from 'react-bootstrap/FormControl';

import { withCustomValidity } from '../../utils';


const InputWithCustomValidity = withCustomValidity("input");


export const NumberControl = ({
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
    // Make sure that the number is converted to a float
    const handleChange = evt => onChange(
        evt.target.value !== "" ?
            parseFloat(evt.target.value) :
            undefined
    );

    return (
        <FormControl
            as={InputWithCustomValidity}
            type="number"
            step="any"
            autoComplete="off"
            placeholder={schema.title || path}
            required={required}
            min={schema.minimum}
            max={schema.maximum}
            value={value !== null && value !== undefined ? value : ""}
            onChange={handleChange}
            validationMessage={
                errors.length > 0 ?
                    errors[0].message :
                    undefined
            }
            {...props}
        />
    );
};


export const IntegerControl = ({ schema, ...props }) => {
    // We can enforce exclusiveMinimum and exclusiveMaximum for integers using HTML5 validations
    let min, max;
    if( schema.hasOwnProperty("minimum") ) {
        min = schema.minimum;
    }
    else if( schema.hasOwnProperty("exclusiveMinimum") ) {
        min = schema.exclusiveMinimum + 1;
    }
    if( schema.hasOwnProperty("maximum") ) {
        max = schema.maximum;
    }
    else if( schema.hasOwnProperty("exclusiveMaximum") ) {
        max = schema.exclusiveMaximum - 1;
    }

    return (
        <NumberControl
            {...props}
            schema={schema}
            step="1"
            // The step only takes effect with a minimum
            // So make sure that one is always set
            min={min || Number.MIN_SAFE_INTEGER}
            max={max}
        />
    );
};
