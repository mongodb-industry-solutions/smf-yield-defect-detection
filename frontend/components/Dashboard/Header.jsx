"use client";

import React from 'react';
import { H1, Subtitle } from '@leafygreen-ui/typography';
import { appPalette } from '@/lib/palette';
import styles from './Header.module.css';

const Header = () => {
  return (
    <header className={styles.header}>
      <div className={styles.topSection}>
        <div className={styles.branding}>
          <div className={styles.titleContainer}>
            <H1 className={styles.title}>Smart Yield and Defect Detection System</H1>
            <Subtitle className={styles.subtitle}>
              Real-time semiconductor manufacturing analytics powered by MongoDB Atlas
            </Subtitle>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;