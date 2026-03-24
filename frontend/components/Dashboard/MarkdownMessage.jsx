"use client";

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/cjs/styles/prism';
import styles from './MarkdownMessage.module.css';

export default function MarkdownMessage({ content }) {
  return (
    <div className={styles.markdownContent}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Code blocks
          code({ node, inline, className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || '');
            const language = match ? match[1] : '';

            return !inline && language ? (
              <SyntaxHighlighter
                style={vscDarkPlus}
                language={language}
                PreTag="div"
                className={styles.codeBlock}
                {...props}
              >
                {String(children).replace(/\n$/, '')}
              </SyntaxHighlighter>
            ) : (
              <code className={styles.inlineCode} {...props}>
                {children}
              </code>
            );
          },

          // Paragraphs
          p({ children }) {
            return <p className={styles.paragraph}>{children}</p>;
          },

          // Headers
          h1({ children }) {
            return <h1 className={styles.h1}>{children}</h1>;
          },
          h2({ children }) {
            return <h2 className={styles.h2}>{children}</h2>;
          },
          h3({ children }) {
            return <h3 className={styles.h3}>{children}</h3>;
          },

          // Lists
          ul({ children }) {
            return <ul className={styles.ul}>{children}</ul>;
          },
          ol({ children }) {
            return <ol className={styles.ol}>{children}</ol>;
          },
          li({ children }) {
            return <li className={styles.li}>{children}</li>;
          },

          // Links
          a({ href, children }) {
            return (
              <a href={href} className={styles.link} target="_blank" rel="noopener noreferrer">
                {children}
              </a>
            );
          },

          // Blockquotes
          blockquote({ children }) {
            return <blockquote className={styles.blockquote}>{children}</blockquote>;
          },

          // Tables
          table({ children }) {
            return <table className={styles.table}>{children}</table>;
          },
          th({ children }) {
            return <th className={styles.th}>{children}</th>;
          },
          td({ children }) {
            return <td className={styles.td}>{children}</td>;
          },

          // Strong/Bold
          strong({ children }) {
            return <strong className={styles.strong}>{children}</strong>;
          },

          // Emphasis/Italic
          em({ children }) {
            return <em className={styles.em}>{children}</em>;
          }
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
