/**
 * This is the entrypoint for the Cloud Portal UI.
 */

import React from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { Provider } from 'react-redux';

import { Application } from './application';
import { store } from './redux';


const container = document.getElementById("react-root");
const root = createRoot(container);
root.render(
    <Provider store={store}>
        <BrowserRouter>
            <Application />
        </BrowserRouter>
    </Provider>
);
