import React from 'react';

import FormControl from 'react-bootstrap/FormControl';
import InputGroup from 'react-bootstrap/InputGroup';

import { withCustomValidity } from '../../utils';


const InputWithCustomValidity = withCustomValidity("input");


export const NumberWithUnitsControl = ({
    path,
    schema,
    required,
    value,
    onChange,
    errors,
    root,
    uiSchemaControlProps: {
        units,
        displayUnits,
        minimum,
        maximum,
        step = "any"
    },
    ...props
}) => {
    // Strip the units from the end of the value before trying to parse it as a number
    const valueWithoutUnits = (
        (value || "").endsWith(units) ?
            (value || "").slice(0, -1 * units.length) :
            (value || "")
    );
    const valueAsNumber = parseFloat(valueWithoutUnits);

    // Add the units back on to the number before returning it
    const handleChange = evt => onChange(
        evt.target.value !== "" ?
            `${parseFloat(evt.target.value)}${units}` :
            undefined
    );

    return (
        <InputGroup>
            <FormControl
                as={InputWithCustomValidity}
                type="number"
                step={step}
                autoComplete="off"
                placeholder={schema.title || path}
                required={required}
                min={minimum}
                max={maximum}
                value={!isNaN(valueAsNumber) ? valueAsNumber : ""}
                onChange={handleChange}
                validationMessage={
                    errors.length > 0 ?
                        errors[0].message :
                        undefined
                }
                {...props}
            />
            <InputGroup.Text>{displayUnits || units}</InputGroup.Text>
        </InputGroup>
    );
};
