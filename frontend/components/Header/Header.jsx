"use client";

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import styles from './Header.module.css';

const Header = () => {
  const pathname = usePathname();

  return (
    <header className={styles.header}>
      <div className={styles.container}>
        <div className={styles.logo}>
          <h1 className={styles.title}>SMF Yield Defect Detection</h1>
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

        <div className={styles.mongodbBadge}>
          <span className={styles.poweredBy}>Powered by</span>
          <span className={styles.mongodb}>MongoDB</span>
        </div>
      </div>
    </header>
  );
};

export default Header;