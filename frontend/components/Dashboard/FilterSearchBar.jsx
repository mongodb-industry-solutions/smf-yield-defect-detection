"use client";

import React, { useState } from 'react';
import TextInput from '@leafygreen-ui/text-input';
import Button from '@leafygreen-ui/button';
// import SegmentedControl from '@leafygreen-ui/segmented-control'; // Commented out - library not installed
import Icon from '@leafygreen-ui/icon';
import { Body } from '@leafygreen-ui/typography';
import styles from './FilterSearchBar.module.css';

const FilterSearchBar = ({ onSearch, onFilter, onStatusFilter, onTypeFilter }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedStatus, setSelectedStatus] = useState('all');
  const [selectedType, setSelectedType] = useState('all');
  const [showFilters, setShowFilters] = useState(false);
  
  const statusOptions = [
    { label: 'All', value: 'all' },
    { label: 'Critical', value: 'critical' },
    { label: 'Warning', value: 'warning' },
    { label: 'Good', value: 'good' },
    { label: 'Idle', value: 'idle' },
    { label: 'Maintenance', value: 'maintenance' }
  ];
  
  const typeOptions = [
    { label: 'All', value: 'all' },
    { label: 'CMP', value: 'CMP' },
    { label: 'ETCH', value: 'ETCH' },
    { label: 'LITHO', value: 'LITHO' },
    { label: 'DEP', value: 'DEP' },
    { label: 'CLEAN', value: 'CLEAN' }
  ];
  
  const handleSearch = (value) => {
    setSearchTerm(value);
    onSearch?.(value);
  };
  
  const handleStatusChange = (value) => {
    setSelectedStatus(value);
    onStatusFilter?.(value);
  };
  
  const handleTypeChange = (value) => {
    setSelectedType(value);
    onTypeFilter?.(value);
  };
  
  const resetFilters = () => {
    setSearchTerm('');
    setSelectedStatus('all');
    setSelectedType('all');
    onSearch?.('');
    onStatusFilter?.('all');
    onTypeFilter?.('all');
  };
  
  const activeFiltersCount = (selectedStatus !== 'all' ? 1 : 0) + 
                             (selectedType !== 'all' ? 1 : 0) + 
                             (searchTerm ? 1 : 0);
  
  return (
    <div className={styles.filterSearchBar}>
      <div className={styles.searchSection}>
        <TextInput
          type="search"
          placeholder="Search equipment by name..."
          value={searchTerm}
          onChange={(e) => handleSearch(e.target.value)}
          aria-label="Search equipment"
          className={styles.searchInput}
        />
        
        <Button
          variant={showFilters ? 'primary' : 'default'}
          leftGlyph={<Icon glyph="Filter" />}
          onClick={() => setShowFilters(!showFilters)}
          className={styles.filterToggle}
        >
          Filters
          {activeFiltersCount > 0 && (
            <span className={styles.filterBadge}>{activeFiltersCount}</span>
          )}
        </Button>
        
        {activeFiltersCount > 0 && (
          <Button
            variant="default"
            leftGlyph={<Icon glyph="X" />}
            onClick={resetFilters}
            className={styles.clearButton}
          >
            Clear
          </Button>
        )}
      </div>
      
      {showFilters && (
        <div className={styles.filterPanel}>
          <div className={styles.filterGroup}>
            <Body weight="medium">Status</Body>
            <select 
              className={styles.filterSelect}
              value={selectedStatus}
              onChange={(e) => handleStatusChange(e.target.value)}
            >
              {statusOptions.map(option => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          
          <div className={styles.filterGroup}>
            <Body weight="medium">Equipment Type</Body>
            <select 
              className={styles.filterSelect}
              value={selectedType}
              onChange={(e) => handleTypeChange(e.target.value)}
            >
              {typeOptions.map(option => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}
    </div>
  );
};

export default FilterSearchBar;