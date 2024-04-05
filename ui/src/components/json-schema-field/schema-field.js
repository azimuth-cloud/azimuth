import React, { useMemo } from 'react';

import Ajv from 'ajv';
import addFormats from 'ajv-formats';

import get from 'lodash/get';

import { PropertyField } from './property-field';


const getSchemaLeafNodes = schema => {
    // Generator that yields all the leaf nodes, i.e. non-object fields, for a schema
    // as [key, value] pairs that can be turned into a map
    const leafNodePairs = function*(schema, path) {
        if( schema.type === "object" ) {
            if(
                schema.hasOwnProperty("patternProperties") ||
                schema.hasOwnProperty("additionalProperties") ||
                schema.hasOwnProperty("unevaluatedProperties") ||
                schema.hasOwnProperty("propertyNames") ||
                schema.hasOwnProperty("minProperties") ||
                schema.hasOwnProperty("maxProperties")
            ) {
                console.warn("Dynamic properties are not currently supported");
            }
            if(
                schema.hasOwnProperty("allOf") ||
                schema.hasOwnProperty("anyOf") ||
                schema.hasOwnProperty("oneOf") ||
                schema.hasOwnProperty("not")
            ) {
                console.warn("Schema composition is not currently supported");
            }
            if(
                schema.hasOwnProperty("dependentRequired") ||
                schema.hasOwnProperty("dependentSchemas") ||
                schema.hasOwnProperty("if")
            ) {
                console.warn("Conditional subschemas are not currently supported");
            }

            const requiredProperties = schema.required || [];

            for(const propertyName in schema.properties) {
                const propertyPath = `${path || ''}/${propertyName}`;
                const propertySchema = schema.properties[propertyName];
                if( propertySchema.type === "object" ) {
                    yield* leafNodePairs(propertySchema, propertyPath);
                }
                else {
                    yield [
                        propertyPath,
                        {
                            path: propertyPath,
                            schema: propertySchema,
                            required: requiredProperties.includes(propertyName)
                        }
                    ]
                }
            }
        }
        else {
            throw new Error("schema must be an object schema");
        }
    };

    return [...leafNodePairs(schema)];
};


export const SchemaField = ({ value, onChange, schema, uiSchema }) => {
    // Validate the current value
    // Use memoization to only recompute the validation function and errors when required
    const validate = useMemo(
        () => {
            const ajv = new Ajv({ allErrors: true });
            addFormats(ajv);
            return ajv.compile(schema);
        },
        [schema]
    );
    const errors = useMemo(
        () => {
            const _ = validate(value);
            // Make sure the error messages are capitalised and end with a full stop
            return (validate.errors || []).map(
                error => ({
                    ...error,
                    message: (
                        [error.message || ""]
                            .map(s => s.charAt(0).toUpperCase() + s.slice(1))
                            .map(s => s.endsWith(".") ? s : s + ".")
                            .at(0)
                    )
                })
            );
        },
        [value, validate]
    );

    // Get the leaf nodes of the schema for which fields will be produced
    // Use memoization to avoid recomputing this unless the schema changes
    const schemaLeafNodes = useMemo(() => getSchemaLeafNodes(schema), [schema]);

    // Get the sorting function for the nodes
    const sortFn = useMemo(
        () => {
            const sortOrder = get(uiSchema, "sortOrder") || [];
            return ([pathA, _], [pathB, __]) => {
                const idxA = [...sortOrder, pathA].indexOf(pathA);
                const idxB = [...sortOrder, pathB].indexOf(pathB);
                return idxA < idxB ? -1 : (idxA > idxB ? 1 : 0);
            };
        },
        [uiSchema]
    );

   // Get the sorted leaf nodes of the schema
    // Use memoization to avoid recomputing this unless the leaf nodes or the uiSchema changes
    const sortedLeafNodes = useMemo(
        () => [...schemaLeafNodes].sort(sortFn),
        [schemaLeafNodes, sortFn]
    );

    // Produce a property field for each leaf node
    return sortedLeafNodes.map(
        ([path, props]) => (
            <PropertyField
                key={path}
                {...props}
                value={value}
                onChange={onChange}
                errors={errors}
                uiSchema={uiSchema}
            />
        )
    );
};
