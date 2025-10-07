"use client";

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import Badge from '@leafygreen-ui/badge';
import Icon from '@leafygreen-ui/icon';
import styles from './Header.module.css';

const Header = () => {
  const pathname = usePathname();

  return (
    <header className={styles.header}>
      <div className={styles.container}>
        <div className={styles.logoSection}>
          {/* MongoDB Leaf Icon */}
          <div className={styles.mongoIcon}>
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M10 2L9.5 17.5L10 18L10.5 17.5L10 2Z" fill="#00ED64"/>
              <path d="M10 2C7 3 3 6 3 10C3 14 6 17 10 18C14 17 17 14 17 10C17 6 13 3 10 2Z" fill="#00684A"/>
              <circle cx="10" cy="10" r="1.5" fill="#00ED64"/>
            </svg>
          </div>

          <div className={styles.brandingText}>
            <h1 className={styles.title}>Yield Analytics & Quality Control</h1>
            <p className={styles.subtitle}>
              <span>Powered by MongoDB Atlas</span>
            </p>
          </div>
        </div>

        <nav className={styles.nav}>
          <Link
            href="/"
            className={`${styles.navLink} ${pathname === '/' ? styles.active : ''}`}
          >
            Home
          </Link>
          <Link
            href="/live-monitoring"
            className={`${styles.navLink} ${pathname === '/live-monitoring' ? styles.active : ''}`}
          >
            Live Monitoring
          </Link>
        </nav>
      </div>
    </header>
  );
};

export default Header;