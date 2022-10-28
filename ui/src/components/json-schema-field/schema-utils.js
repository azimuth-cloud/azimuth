import get from 'lodash/get';

import { generateDefault } from './default-generators';


export const getInitialValueFromSchema = (schema, uiSchema, existingValue) => {
    const defaultGenerators = get(uiSchema, "defaultGenerators", {});

    const getInitialValueForPath = (path, schema, existingValue) => {
        if( schema.type === "object" ) {
            return Object.assign(
                {},
                ...Object.entries(schema.properties || {}).map(
                    ([propertyName, propertySchema]) => {
                        const propertyPath = `${path || ''}/${propertyName}`;
                        const initialPropertyValue = getInitialValueForPath(
                            propertyPath,
                            propertySchema,
                            (existingValue || {})[propertyName]
                        );
                        if( initialPropertyValue !== null && initialPropertyValue !== undefined ) {
                            return { [propertyName]: initialPropertyValue };
                        }
                        else {
                            return {}
                        }
                    }
                )
            );
        }
        else if( existingValue !== null && existingValue !== undefined ) {
            return existingValue;
        }
        else if( schema.default !== null && schema.default !== undefined ) {
            return schema.default;
        }
        else if( defaultGenerators.hasOwnProperty(path) ) {
            return generateDefault(defaultGenerators[path]);
        }
    };

    return getInitialValueForPath(undefined, schema, existingValue);
};


export const getValueAtPath = (obj, path) => (
    path.split("/").filter(p => p !== "").reduce(
        (value, propertyName) => (
            value && value.hasOwnProperty(propertyName) ?
                value[propertyName] :
                undefined
        ),
        obj
    )
);


export const setValueAtPath = (obj, path, newValue) => {
    const setValueAtPathComponents = (obj, pathComponents) => {
        if( pathComponents.length === 0 ) return newValue;
        const [currentComponent, ...nextComponents] = pathComponents;
        return Object.assign(
            {},
            obj,
            {
                [currentComponent]: setValueAtPathComponents(
                    obj[currentComponent] || {},
                    nextComponents
                )
            }
        );
    };
    return setValueAtPathComponents(obj, path.split("/").filter(p => p !== ""), newValue);
};
