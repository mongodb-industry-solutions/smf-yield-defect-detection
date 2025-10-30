"use client";

import React, { useState } from 'react';
import Card from '@leafygreen-ui/card';
import Button from '@leafygreen-ui/button';
import TextInput from '@leafygreen-ui/text-input';
import { Select, Option } from '@leafygreen-ui/select';
import Badge from '@leafygreen-ui/badge';
import Icon from '@leafygreen-ui/icon';
import { H3, Body, Description } from '@leafygreen-ui/typography';
import { searchAPI } from '@/lib/api';
import SearchResultModal from './SearchResultModal';
import styles from './UnifiedSearchPanel.module.css';

const UnifiedSearchPanel = () => {
  // Search state
  const [query, setQuery] = useState('');
  const [searchScope, setSearchScope] = useState('all'); // 'all', 'wafers', 'knowledge'
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState(null);

  // Filter state
  const [equipmentFilter, setEquipmentFilter] = useState('');
  const [limitFilter, setLimitFilter] = useState('10');
  const [showFilters, setShowFilters] = useState(false);

  // Results state
  const [results, setResults] = useState(null);
  const [activeTab, setActiveTab] = useState('wafers'); // 'wafers', 'knowledge'
  const [selectedResult, setSelectedResult] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);

  // Equipment options
  const equipmentOptions = [
    '', 'CMP_TOOL_01', 'CMP_TOOL_02', 'ETCH_01', 'ETCH_02', 'LITHO_01', 'LITHO_02'
  ];

  // Handle search execution
  const handleSearch = async () => {
    if (!query.trim()) {
      setSearchError('Please enter a search query');
      return;
    }

    setIsSearching(true);
    setSearchError(null);
    setResults(null);

    try {
      const limit = parseInt(limitFilter) || 10;
      let searchResults;

      if (searchScope === 'all') {
        searchResults = await searchAPI.searchAll(query, limit);
      } else if (searchScope === 'wafers') {
        searchResults = await searchAPI.searchWafers(
          query,
          equipmentFilter || null,
          limit
        );
      } else if (searchScope === 'knowledge') {
        searchResults = await searchAPI.searchKnowledge(query, null, limit);
      }

      setResults(searchResults);
      console.log('🔍 Search results:', searchResults);
    } catch (error) {
      console.error('Search error:', error);
      setSearchError('Search failed: ' + error.message);
    } finally {
      setIsSearching(false);
    }
  };

  // Handle result click
  const handleResultClick = (result, collectionType) => {
    setSelectedResult({ ...result, collectionType });
    setModalOpen(true);
  };

  // Get results for current tab
  const getTabResults = (tab) => {
    if (!results) return [];

    if (searchScope === 'all') {
      // Unified search results
      if (tab === 'wafers') return results.wafer_results || [];
      if (tab === 'knowledge') return results.knowledge_results || [];
    } else {
      // Single collection search
      return results.results || [];
    }
    return [];
  };

  // Get result counts
  const getResultCounts = () => {
    if (!results) return { wafers: 0, knowledge: 0 };

    if (searchScope === 'all') {
      return {
        wafers: results.wafer_results?.length || 0,
        knowledge: results.knowledge_results?.length || 0
      };
    } else {
      const count = results.results?.length || 0;
      return {
        wafers: searchScope === 'wafers' ? count : 0,
        knowledge: searchScope === 'knowledge' ? count : 0
      };
    }
  };

  const counts = getResultCounts();

  return (
    <div className={styles.container}>
      <Card className={styles.searchCard}>
        <div className={styles.header}>
          <H3><Icon glyph="MagnifyingGlass" /> Unified Database Search</H3>
        </div>

        {/* Search Input */}
        <div className={styles.searchInputRow}>
          <TextInput
            className={styles.searchInput}
            placeholder="Search for wafers, defects, or knowledge..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
            disabled={isSearching}
          />
          <Button
            onClick={handleSearch}
            variant="primary"
            disabled={isSearching || !query.trim()}
            leftGlyph={<Icon glyph="MagnifyingGlass" />}
          >
            {isSearching ? 'Searching...' : 'Search'}
          </Button>
        </div>

        {/* Search Scope Radio Buttons */}
        <div className={styles.scopeRow}>
          <Body weight="medium">Search Scope:</Body>
          <div className={styles.scopeButtons}>
            <label className={`${styles.scopeLabel} ${searchScope === 'all' ? styles.active : ''}`}>
              <input
                type="radio"
                value="all"
                checked={searchScope === 'all'}
                onChange={(e) => setSearchScope(e.target.value)}
              />
              <span>All Collections</span>
            </label>
            <label className={`${styles.scopeLabel} ${searchScope === 'wafers' ? styles.active : ''}`}>
              <input
                type="radio"
                value="wafers"
                checked={searchScope === 'wafers'}
                onChange={(e) => setSearchScope(e.target.value)}
              />
              <span>Wafers Only</span>
            </label>
            <label className={`${styles.scopeLabel} ${searchScope === 'knowledge' ? styles.active : ''}`}>
              <input
                type="radio"
                value="knowledge"
                checked={searchScope === 'knowledge'}
                onChange={(e) => setSearchScope(e.target.value)}
              />
              <span>Knowledge Base</span>
            </label>
          </div>
        </div>

        {/* Advanced Filters */}
        <div className={styles.filtersSection}>
          <Button
            size="small"
            variant="default"
            onClick={() => setShowFilters(!showFilters)}
            leftGlyph={<Icon glyph={showFilters ? 'ChevronUp' : 'ChevronDown'} />}
          >
            {showFilters ? 'Hide' : 'Show'} Advanced Filters
          </Button>

          {showFilters && (
            <div className={styles.filters}>
              <Select
                label="Equipment"
                value={equipmentFilter}
                onChange={(value) => setEquipmentFilter(value)}
                disabled={searchScope !== 'wafers' && searchScope !== 'all'}
              >
                <Option value="">All Equipment</Option>
                {equipmentOptions.slice(1).map(eq => (
                  <Option key={eq} value={eq}>{eq}</Option>
                ))}
              </Select>

              <Select
                label="Result Limit"
                value={limitFilter}
                onChange={(value) => setLimitFilter(value)}
              >
                <Option value="5">5 results</Option>
                <Option value="10">10 results</Option>
                <Option value="20">20 results</Option>
                <Option value="50">50 results</Option>
              </Select>
            </div>
          )}
        </div>

        {/* Error Message */}
        {searchError && (
          <div className={styles.error}>
            <Icon glyph="Warning" />
            <Body>{searchError}</Body>
          </div>
        )}
      </Card>

      {/* Search Results */}
      {results && (
        <Card className={styles.resultsCard}>
          <div className={styles.resultsHeader}>
            <H3><Icon glyph="Charts" /> Search Results</H3>
            <Description>
              Found {counts.wafers + counts.knowledge} results
              {results.summary?.execution_time_ms && ` in ${(results.summary.execution_time_ms / 1000).toFixed(2)}s`}
            </Description>
          </div>

          {/* Results Tabs */}
          {(searchScope === 'all' || counts.wafers + counts.knowledge > 0) && (
            <div className={styles.tabs}>
              <button
                className={`${styles.tab} ${activeTab === 'wafers' ? styles.activeTab : ''}`}
                onClick={() => setActiveTab('wafers')}
              >
                Wafers ({counts.wafers})
              </button>
              <button
                className={`${styles.tab} ${activeTab === 'knowledge' ? styles.activeTab : ''}`}
                onClick={() => setActiveTab('knowledge')}
              >
                Knowledge Base ({counts.knowledge})
              </button>
            </div>
          )}

          {/* Results Content */}
          <div className={styles.resultsContent}>
            {activeTab === 'wafers' && (
              <WaferResults
                results={getTabResults('wafers')}
                onResultClick={(r) => handleResultClick(r, 'wafer')}
              />
            )}
            {activeTab === 'knowledge' && (
              <KnowledgeResults
                results={getTabResults('knowledge')}
                onResultClick={(r) => handleResultClick(r, 'knowledge')}
              />
            )}
          </div>
        </Card>
      )}

      {/* Result Detail Modal */}
      {selectedResult && (
        <SearchResultModal
          result={selectedResult}
          open={modalOpen}
          onClose={() => setModalOpen(false)}
        />
      )}
    </div>
  );
};

// Wafer Results Component
const WaferResults = ({ results, onResultClick }) => {
  if (!results || results.length === 0) {
    return <div className={styles.emptyState}>No wafer results found</div>;
  }

  return (
    <div className={styles.resultsGrid}>
      {results.map((wafer, idx) => (
        <Card key={idx} className={styles.resultCard}>
          <div className={styles.resultHeader}>
            <Body weight="medium">{wafer.wafer_id}</Body>
            <Badge variant={wafer.severity === 'high' ? 'red' : wafer.severity === 'medium' ? 'yellow' : 'blue'}>
              {wafer.score?.toFixed(2) || 'N/A'}
            </Badge>
          </div>

          <div className={styles.resultBody}>
            <Description>Lot: {wafer.lot_id}</Description>
            <Description>Pattern: {wafer.defect_pattern}</Description>
            <Description>Yield: {wafer.yield_percentage}% ({wafer.failed_dies} fails)</Description>
            <Description>Equipment: {wafer.equipment_id}</Description>

            {wafer.ink_map?.thumbnail_base64 && (
              <div className={styles.thumbnail}>
                <img
                  src={`data:image/png;base64,${wafer.ink_map.thumbnail_base64}`}
                  alt={`Wafer ${wafer.wafer_id}`}
                />
              </div>
            )}

            {wafer.description && (
              <Description className={styles.description}>
                {wafer.description}
              </Description>
            )}
          </div>

          <div className={styles.resultActions}>
            <Button size="small" onClick={() => onResultClick(wafer)}>
              View Details
            </Button>
            <Button
              size="small"
              variant="default"
              onClick={() => navigator.clipboard.writeText(wafer.wafer_id)}
            >
              Copy ID
            </Button>
          </div>
        </Card>
      ))}
    </div>
  );
};

// Knowledge Base Results Component
const KnowledgeResults = ({ results, onResultClick }) => {
  if (!results || results.length === 0) {
    return <div className={styles.emptyState}>No knowledge base results found</div>;
  }

  return (
    <div className={styles.resultsGrid}>
      {results.map((doc, idx) => (
        <Card key={idx} className={styles.resultCard}>
          <div className={styles.resultHeader}>
            <Body weight="medium">
              <Icon glyph={doc.document_type === 'RCA Reports' ? 'Folder' : 'University'} size="small" />{' '}
              {doc.title}
            </Body>
            <Badge variant="blue">{doc.score?.toFixed(2) || 'N/A'}</Badge>
          </div>

          <div className={styles.resultBody}>
            <Badge variant={doc.document_type === 'RCA Reports' ? 'yellow' : 'blue'}>
              {doc.document_type}
            </Badge>

            {doc.process_area && (
              <Description>Process Area: {doc.process_area}</Description>
            )}
            {doc.defect_type && (
              <Description>Defect Type: {doc.defect_type}</Description>
            )}
            {doc.root_cause && (
              <Description className={styles.highlight}>
                Root Cause: {doc.root_cause}
              </Description>
            )}
            {doc.solutions && doc.solutions.length > 0 && (
              <Description>
                Solutions: ({doc.solutions.length}) {doc.solutions[0]?.action || 'View details...'}
              </Description>
            )}
            {doc.estimated_resolution_time && (
              <Description>
                Est. Resolution: {doc.estimated_resolution_time}
              </Description>
            )}
          </div>

          <div className={styles.resultActions}>
            <Button size="small" onClick={() => onResultClick(doc)}>
              View Details
            </Button>
            <Button
              size="small"
              variant="default"
              onClick={() => navigator.clipboard.writeText(doc.document_id)}
            >
              Copy ID
            </Button>
          </div>
        </Card>
      ))}
    </div>
  );
};

export default UnifiedSearchPanel;
