"use client";

import React from 'react';
import Card from '@leafygreen-ui/card';
import Icon from '@leafygreen-ui/icon';
import { Body, H3 } from '@leafygreen-ui/typography';

class AgentErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    console.error('[AgentErrorBoundary] Caught error:', error);
    console.error('[AgentErrorBoundary] Error info:', errorInfo);
    this.setState({
      error,
      errorInfo
    });
  }

  render() {
    if (this.state.hasError) {
      return (
        <Card style={{ padding: '24px', textAlign: 'center' }}>
          <Icon glyph="Warning" size="xlarge" style={{ color: '#C1271C', marginBottom: '16px' }} />
          <H3 style={{ marginBottom: '12px' }}>Agent Analysis Display Error</H3>
          <Body style={{ marginBottom: '16px', color: '#666' }}>
            Unable to display agent analysis results. The backend processed the analysis successfully,
            but there was an error rendering the data.
          </Body>
          <Body style={{ fontSize: '12px', color: '#999', fontFamily: 'monospace', textAlign: 'left', background: '#f5f5f5', padding: '12px', borderRadius: '4px', overflow: 'auto' }}>
            {this.state.error?.toString()}
          </Body>
          <button
            onClick={() => this.setState({ hasError: false, error: null, errorInfo: null })}
            style={{
              marginTop: '16px',
              padding: '8px 16px',
              background: '#00684A',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Try Again
          </button>
        </Card>
      );
    }

    return this.props.children;
  }
}

export default AgentErrorBoundary;
