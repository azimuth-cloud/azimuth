/**
 * Module containing utilities for working with forms.
 */

import React, { useEffect, useMemo, useRef, useState } from 'react';

import Alert from 'react-bootstrap/Alert';
import BSForm from 'react-bootstrap/Form';

import { useSelector } from 'react-redux';
import { createSelector } from 'reselect';

import ReactSelect from 'react-select';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
    faCaretDown,
    faCaretUp,
    faExclamationCircle,
    faSyncAlt
} from '@fortawesome/free-solid-svg-icons';

import get from 'lodash/get';


/**
 * This function takes an "actions" object, which is a map of name => function,
 * and returns a new object with the same names where each function has the given
 * args bound.
 */
export const bindArgsToActions = (actions, ...args) => Object.assign(
    {},
    ...Object.entries(actions)
        .map(([key, func]) => ({
            [key]: (...moreArgs) => func(...args, ...moreArgs)
        }))
);


const compare = (x, y) => (x > y ? 1 : (x < y ? -1 : 0));


/**
 * Compare two arrays elementwise.
 */
export const compareElementwise = (x, y) => {
    // Compare the arrays element by element until the comparison function is
    // non-zero or one of the arrays is exhausted
    const result = [...Array(Math.min(x.length, y.length)).keys()]
        .map(i => compare(x[i], y[i]))
        .find(i => i !== 0);
    // If the result is undefined after comparing the elements, i.e. the arrays
    // share the first N elements, then the longer array is greater
    return result == undefined ? compare(x.length, y.length) : result;
}


/**
 * This function sorts an array using the given key function.
 * 
 * It also supports the case where the key function returns an array by doing
 * an element-wise comparison.
 * 
 * Unlike lodash/sortBy, it supports a reverse argument indicating whether
 * the result should be in reverse order.
 */
export const sortBy = (data, keyFn, reverse = false) => [...data].sort(
    (e1, e2) => {
        const [k1, k2] = [keyFn(e1), keyFn(e2)];
        const result = Array.isArray(k1) ? compareElementwise(k1, k2) : compare(k1, k2);
        return reverse ? -result : result;
    }
);


const SIZE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];

/**
 * This function formats a size by increasing the units when it is possible
 * to do so without reducing the precision.
 */
export const formatSize = (amount, originalUnits) => {
    // If the amount is zero, then use the given units
    if( amount === 0 ) return `0${originalUnits}`;
    var exponent = Math.floor(Math.log(amount) / Math.log(1024));
    // The '*1' is to convert back to a number, so we get 1GB instead of 1.00GB
    const formattedAmount = Number((amount / Math.pow(1024, exponent)).toFixed(2) * 1);
    const unitsIndex = SIZE_UNITS.indexOf(originalUnits) + exponent;
    return `${formattedAmount}${SIZE_UNITS[unitsIndex]}`;
};


/**
 * Hook to set the page title. 
 */
export const usePageTitle = title => {
    const suffix = useSelector(
        createSelector(
            state => state.clouds.available_clouds,
            state => state.clouds.current_cloud,
            state => state.tenancies.current,
            (clouds, currentCloud, currentTenancy) => {
                const cloudLabel = get(clouds, [currentCloud, "label"]);
                const tenancyName = get(currentTenancy, 'name');
                return `${tenancyName ? tenancyName + " | " : ""}${cloudLabel || ""}`;
            }
        )
    );
    const pageTitle = suffix ? `${title} | ${suffix}` : title;
    // Get the current cloud name from the redux store
    // When the title changes, set the title of the page
    useEffect(() => { document.title = pageTitle }, [pageTitle]);
};


/**
 * Hook to use the value of a variable from the previous rendering cycle.
 */
export const usePrevious = value => {
    const ref = useRef();
    useEffect(() => { ref.current = value; }, [value]);
    return ref.current;
};


/**
 * Hook to provide a sortable array.
 */
export const useSortable = (
    // The data that will be sorted
    data,
    {
        // A map of field name to the key function for the field
        keyFunctions,
        // The initial field to sort by
        initialField,
        // Whether the initial sort should be in reverse
        initialReverse = false 
    }
) => {
    const [sortField, setSortField] = useState(initialField);
    const [sortReverse, setSortReverse] = useState(initialReverse);
    // This function toggles the sort states
    const toggleSort = field => () => {
        if( field === sortField ) {
            setSortReverse(reverse => !reverse);
        }
        else {
            setSortField(field);
            setSortReverse(false);
        }
    };
    // Sort the machines by the specified field and direction
    // We memoize this to avoid re-running the sort if nothing has changed
    const sortedData = useMemo(
        () => {
            // Get the key function, which defaults to a fetch of the field
            const keyFn = get(keyFunctions, sortField, d => get(d, sortField));
            return sortBy(data, keyFn, sortReverse);
        },
        [data, keyFunctions, sortField, sortReverse]
    );
    // Return the sorted data and a component for rendering sortable column headings
    return [
        sortedData,
        ({ children, field, ...props }) => (
            <th
                style={{ cursor: 'pointer' }}
                {...props}
                onClick={toggleSort(field)}
            >
                {children}
                {sortField === field &&
                    <FontAwesomeIcon
                        icon={sortReverse ? faCaretDown : faCaretUp}
                        className="ms-2"
                    />
                }
            </th>
        )
    ];
};


const fontSizes = {
    xs: '0.7rem',
    sm: '0.8rem',
    md: '1rem',
    lg: '1.25rem',
    xl: '1.5rem',
    xxl: '1.75rem'
};

/**
 * Component that shows a spinner with some text.
 */
export const Loading = ({
    message,
    // Controls the size of the icon RELATIVE TO THE TEXT
    iconSize,
    // Controls the size of the text INCLUDING THE ICON
    size = '1rem',
    // Indicates if the text should be muted
    muted = true,
    // Indicates if the text should be visually hidden
    visuallyHidden = false,
    // The wrapper component to use
    wrapperComponent: WrapperComponent = "div",
    ...props
}) => (
    <WrapperComponent
        className={muted ? "text-muted" : undefined}
        style={{ fontSize: get(fontSizes, size, size) }}
        {...props}
    >
        <FontAwesomeIcon icon={faSyncAlt} spin size={iconSize} className="me-2" />
        <span className={visuallyHidden ? "visually-hidden" : undefined}>{message}</span>
    </WrapperComponent>
);


/**
 * Component that renders an error alert with an icon. 
 */
export const Error = ({
    message,
    iconSize = "lg",
    ...props
}) => (
    <Alert variant="danger" {...props}>
        <FontAwesomeIcon icon={faExclamationCircle} size={iconSize} className="me-2" />
        {message}
    </Alert>
)


/**
 * React component for a form that can be disabled.
 * 
 * It also intercepts the submit event to apply HTML5 validations.
 */
export const Form = ({ children, disabled = false, onSubmit, ...props }) => {
    const handleSubmit = evt => {
        // Force the form validations to run on submit
        // We only call the onSubmit function if the values are valid
        if( evt.currentTarget.checkValidity() ) {
            onSubmit(evt);
        }
        else {
            evt.preventDefault();
            evt.stopPropagation();
        }
    };
    return (
        <BSForm
            {...props}
            // Don't run the validation automatically, as this calls reportValidity
            // when we actually just want checkValidity
            noValidate
            onSubmit={handleSubmit}
        >
            <fieldset disabled={disabled}>
                {children}
            </fieldset>
        </BSForm>
    );
};


/**
 * Component that renders a Bootstrap form control with the HTML5 validation state
 */
export const ControlWithValidationMessage = ({
    children,
    validationMessage: customValidationMessage,
    wrapperComponent: WrapperComponent = "div",
    ...props
}) => {
    // Maintain the validation message from the last invalid event as internal state
    const [validationMessage, setValidationMessage] = useState('');
    // The control is invalid if the message is non-empty
    const isInvalid = validationMessage !== '';
    // When the invalid event is raised, set the validation message
    const onInvalid = evt => setValidationMessage(
        evt.target.value ?
            customValidationMessage || evt.target.validationMessage :
            evt.target.validationMessage
    );
    // When the value is changed, clear the validation message until the next
    // validation is requested
    const onChange = (...args) => {
        setValidationMessage('');
        // We assume that there is a single Form.Control as the "children"
        children.props.onChange(...args);
    };
    // The relative-positioned div is required for validation tooltips to position
    // correctly as they use absolute positioning which anchors on the closest
    // explicitly positioned ancestor
    return (
        <WrapperComponent className="position-relative">
            {React.cloneElement(
                children,
                { isInvalid, onInvalid, onChange }
            )}
            {validationMessage !== '' && (
                <BSForm.Control.Feedback type="invalid" tooltip>
                    {validationMessage}
                </BSForm.Control.Feedback>
            )}
        </WrapperComponent>
    );
};


/**
 * React component for a Bootstrap formatted form field. The actual form elements
 * should be 'react-bootstrap' form elements, given as children.
 */
export const Field = ({
    children,
    name,
    label = null,
    helpText = null,
    className = "",
    wrapperComponent = "div",
    ...props
}) => (
    <BSForm.Group controlId={name} className={`mb-3 ${className}`} {...props}>
        {label && <BSForm.Label>{label}</BSForm.Label>}
        <ControlWithValidationMessage wrapperComponent={wrapperComponent}>
            {children}
        </ControlWithValidationMessage>
        {helpText && <BSForm.Text>{helpText}</BSForm.Text>}
    </BSForm.Group>
);


// Hook that allows access to a forwarded ref, even if that ref is not
// used outside
const useForwardedRef = (forwardedRef) => {
    const ref = useRef(null);
    // Keep the forwarded ref up-to-date with our ref
    useEffect(
        () => {
            // If no ref was actually given, we are done
            if( !forwardedRef ) return;
            // If a ref is given, it is either an object with a 'current'
            // property or it is a function
            if( forwardedRef.hasOwnProperty('current') ) {
                forwardedRef.current = ref.current;
            }
            else {
                forwardedRef(ref.current);
            }
        },
        [forwardedRef, ref.current]
    );
    // Return our ref to be used in the forwarding component
    return ref;
};


/**
 * Higher-order component that sets the custom validity for the
 * underlying field. 
 */
export const withCustomValidity = Component => React.forwardRef(
    ({ validationMessage, ...props }, forwardedRef) => {
        const inputRef = useForwardedRef(forwardedRef);
        // When the validation message changes, update the custom validity for the input
        useEffect(
            () => { inputRef.current.setCustomValidity(validationMessage); },
            [validationMessage]
        );
        return <Component ref={inputRef} {...props} />;
    }
);


/**
 * Wrapper for react-select that supports the required property.
 *
 * It also ensures that the options are sorted by label.
 */
export const Select = React.forwardRef(
    (
        {
            options,
            value,
            onChange,
            onInvalid,
            disabled,
            required,
            className,
            sortOptions,
            getOptionLabel = option => option.label,
            getOptionValue = option => option.value,
            form,
            style,
            ...props
        },
        forwardedRef
    ) => {
        // We allow the reference to the hidden field to be forwarded as it gives
        // control over the validation state
        const hiddenInputRef = useForwardedRef(forwardedRef);
        // Store the current value as internal state
        const [state, setState] = useState(value || '');
        // When the value changes, use it to set the state
        useEffect(() => { setState(value); }, [value]);
        // Maintain a reference to the select that we will use to correctly maintain focus
        const selectRef = useRef(null);
        // When the select is changed, update the internal state and call the handler
        const handleSelectChange = option => {
            const optionValue = getOptionValue(option);
            setState(optionValue);
            onChange(optionValue);
        };
        // By default, sort the options by the label
        const sortFn = sortOptions || (options => sortBy(options, getOptionLabel));
        // Sort the options by the label
        const sortedOptions = sortFn(options);
        // Select the option that corresponds to the given value
        const selectedOption = sortedOptions.find(opt => getOptionValue(opt) === state);
        // Calculate the classes to add
        const classNames = ["react-select__wrapper"];
        if( className ) classNames.push(className);
        return (
            <div className={classNames.join(' ')} style={style}>
                <ReactSelect
                    {...props}
                    options={sortedOptions}
                    value={selectedOption}
                    onChange={handleSelectChange}
                    ref={selectRef}
                    isDisabled={disabled}
                    getOptionLabel={getOptionLabel}
                    getOptionValue={getOptionValue}
                    classNamePrefix="react-select"
                />
                <input
                    ref={hiddenInputRef}
                    tabIndex={-1}
                    autoComplete="off"
                    style={{
                        opacity: 0,
                        width: "100%",
                        height: 0,
                        border: 0,
                        position: "absolute"
                    }}
                    value={state}
                    onChange={() => {/* NOOP */}}
                    onInvalid={onInvalid}
                    // When the hidden input is focused as part of the required validation,
                    // pass the focus onto the select
                    onFocus={() => selectRef.current.focus()}
                    form={form}
                    required={required}
                    disabled={disabled}
                />
            </div>
        );
    }
);
