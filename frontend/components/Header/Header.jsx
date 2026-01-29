"use client";

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import Button from '@leafygreen-ui/button';
import Icon from '@leafygreen-ui/icon';
import styles from './Header.module.css';

const Header = () => {
  const pathname = usePathname();

  return (
    <header className={styles.header}>
      <div className={styles.container}>
        <div className={styles.logoSection}>
          {/* MongoDB Leaf Icon with Circuit Board Traces */}
          <div className={styles.mongoIcon}>
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
              {/* Background */}
              <circle cx="16" cy="16" r="15" fill="#001E2B" opacity="0.08"/>
              
              {/* Circuit Board Traces - Left Side */}
              <path d="M4 10 L8 10 L8 12 L12 12" stroke="#00684A" strokeWidth="0.8" opacity="0.3" strokeLinecap="round"/>
              <path d="M4 14 L10 14 L10 16" stroke="#00684A" strokeWidth="0.8" opacity="0.3" strokeLinecap="round"/>
              <path d="M4 18 L8 18 L8 20 L11 20" stroke="#00684A" strokeWidth="0.8" opacity="0.3" strokeLinecap="round"/>
              
              {/* Circuit Board Traces - Right Side */}
              <path d="M28 10 L24 10 L24 12 L20 12" stroke="#00684A" strokeWidth="0.8" opacity="0.3" strokeLinecap="round"/>
              <path d="M28 14 L22 14 L22 16" stroke="#00684A" strokeWidth="0.8" opacity="0.3" strokeLinecap="round"/>
              <path d="M28 18 L24 18 L24 20 L21 20" stroke="#00684A" strokeWidth="0.8" opacity="0.3" strokeLinecap="round"/>
              
              {/* Circuit Board Traces - Bottom */}
              <path d="M12 24 L12 26 L16 26" stroke="#00684A" strokeWidth="0.8" opacity="0.3" strokeLinecap="round"/>
              <path d="M20 24 L20 26 L16 26" stroke="#00684A" strokeWidth="0.8" opacity="0.3" strokeLinecap="round"/>
              
              {/* Connection Vias (small circles at trace intersections) */}
              <circle cx="8" cy="10" r="0.8" fill="#00684A" opacity="0.4"/>
              <circle cx="8" cy="18" r="0.8" fill="#00684A" opacity="0.4"/>
              <circle cx="24" cy="10" r="0.8" fill="#00684A" opacity="0.4"/>
              <circle cx="24" cy="18" r="0.8" fill="#00684A" opacity="0.4"/>
              <circle cx="12" cy="24" r="0.8" fill="#00684A" opacity="0.4"/>
              <circle cx="20" cy="24" r="0.8" fill="#00684A" opacity="0.4"/>
              
              {/* MongoDB Leaf (Official shape) - Prominent in foreground */}
              <path 
                d="M16 6C13.5 7.5 10 10.5 10 15C10 19.5 13.5 23 16 24C18.5 23 22 19.5 22 15C22 10.5 18.5 7.5 16 6Z" 
                fill="#00ED64"
                opacity="0.95"
              />
              <path 
                d="M16 6C13.8 7.3 10.5 10 10.5 14.5C10.5 19 13.8 22.5 16 23.5C18.2 22.5 21.5 19 21.5 14.5C21.5 10 18.2 7.3 16 6Z" 
                fill="#00684A"
              />
              
              {/* Leaf stem - vertical line */}
              <path 
                d="M16 6L15.7 23.5L16 24L16.3 23.5L16 6Z" 
                fill="#00ED64"
              />
              
              {/* Center highlight */}
              <ellipse cx="16" cy="15" rx="2" ry="3" fill="#00ED64" opacity="0.6"/>
            </svg>
          </div>

          <div className={styles.brandingText}>
            <h1 className={styles.title}>Agentic Yield Analytics</h1>
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

        <div className={styles.actions}>
          <Link href="/documentation">
            <Button leftGlyph={<Icon glyph="Wizard" />}>
              Tell me more!
            </Button>
          </Link>
        </div>
      </div>
    </header>
  );
};

export default Header;