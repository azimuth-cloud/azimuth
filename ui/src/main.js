/**
 * This is the entrypoint for the Cloud Portal UI.
 */

import React from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { Provider } from 'react-redux';

import { Application } from './application';
import { ApplicationErrorBoundary } from './components/errors';
import { store } from './redux';


const container = document.getElementById("react-root");
const root = createRoot(container);
root.render(
    <Provider store={store}>
        <BrowserRouter>
            <ApplicationErrorBoundary
                message={
                    <>
                        <p>An unexpected error occurred, please try refreshing the page.</p>
                        <p className="mb-0">If the problem persists, raise an issue with your Azimuth operator.</p>
                    </>
                }
            >
                <Application />
            </ApplicationErrorBoundary>
        </BrowserRouter>
    </Provider>
);