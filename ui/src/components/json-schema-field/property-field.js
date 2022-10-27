import React from 'react';

import ReactMarkdown from 'react-markdown';

import get from 'lodash/get';

import { Field } from '../utils';

import { getValueAtPath, setValueAtPath } from './schema-utils';
import { CONTROL_COMPONENTS_BY_NAME } from './controls';


const defaultControlsBySchemaType = {
    "integer": "IntegerControl",
    "number": "NumberControl",
    "string": "TextControl",
};


export const PropertyField = ({
    path,
    schema,
    uiSchema,
    required,
    value,
    onChange,
    errors
}) => {
    // Get the control component to use
    // This can be overridden in the ui schema if required
    const { type: controlName, ...uiSchemaControlProps } = Object.assign(
        {},
        { type: defaultControlsBySchemaType[schema.type || "string"] },
        get(uiSchema, ["controls", path])
    );
    let ControlComponent;
    if( CONTROL_COMPONENTS_BY_NAME.hasOwnProperty(controlName) ) {
        ControlComponent = CONTROL_COMPONENTS_BY_NAME[controlName];
    }
    else {
        const fallbackControlName = defaultControlsBySchemaType[schema.type] || "TextControl";
        console.warn(`Invalid control '${controlName}' - using ${fallbackControlName}`);
        ControlComponent = CONTROL_COMPONENTS_BY_NAME[fallbackControlName];
    }

    // Extract the property value from the value object
    const propertyValue = getValueAtPath(value, path);
    // Get the change function for the property
    const onPropertyChange = newValue => onChange(setValueAtPath(value, path, newValue));
    // Extract any errors for the property
    const propertyErrors = errors.filter(e => e.instancePath.startsWith(path));

    return (
        <Field
            name={path}
            label={schema.title || path}
            helpText={
                schema.description ?
                    <ReactMarkdown
                        components={{
                            // Links should open in a new tab
                            a: ({ node, children, ...props }) => (
                                <a target="_blank" {...props}>{children}</a>
                            )
                        }}
                        children={schema.description}
                    /> :
                    undefined
            }
        >
            <ControlComponent
                path={path}
                schema={schema}
                required={required}
                value={propertyValue}
                onChange={onPropertyChange}
                errors={propertyErrors}
                root={value}
                uiSchemaControlProps={uiSchemaControlProps}
            />
        </Field>
    );
};
