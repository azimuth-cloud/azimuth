
import React from 'react';
import Col from 'react-bootstrap/Col';
import Row from 'react-bootstrap/Row';
import { Error } from "./utils"

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
    faPersonFallingBurst,
} from '@fortawesome/free-solid-svg-icons';

// Based on example in official docs here:
// https://react.dev/reference/react/Component#catching-rendering-errors-with-an-error-boundary
export class ApplicationErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false };
    }
  
    static getDerivedStateFromError(error) {
        // Update state so the next render will show the fallback UI.
        return { hasError: true };
    }
  
    componentDidCatch(error, info) {
        // Example "componentStack":
        //   in ComponentThatThrows (created by App)
        //   in ErrorBoundary (created by App)
        //   in div (created by App)
        //   in App
        console.log(error, info.componentStack);
    }
  
    render() {
        if (this.state.hasError) {
            // Render fallback UI
            return (
                <>
                    <Row className="justify-content-center align-items-end" style={{height: "50vh"}}>
                        <Col xs="auto py-3">
                            <FontAwesomeIcon icon={faPersonFallingBurst} size="10x" />
                        </Col>
                    </Row>
                    <Row className="justify-content-center">
                        <Col xs="auto py-3">
                            <Error message={this.props.message} />
                        </Col>
                    </Row>
                </>
            )
        }
  
        return this.props.children;
    }
  }