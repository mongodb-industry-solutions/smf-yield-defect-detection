"use client";

import React, { useState } from "react";
import Modal from "@leafygreen-ui/modal";
import { H3, Body } from "@leafygreen-ui/typography";
import Icon from "@leafygreen-ui/icon";
import PropTypes from "prop-types";
import styles from "./InfoWizard.module.css";
import Button from "@leafygreen-ui/button";
import { Tabs, Tab } from "@leafygreen-ui/tabs";
import IconButton from "@leafygreen-ui/icon-button";
import Tooltip from "@leafygreen-ui/tooltip";

const InfoWizard = ({
  open,
  setOpen,
  tooltipText = "Learn more",
  iconGlyph = "Wizard",
  openModalIsButton = true,
  sections = [],
}) => {
  const [selected, setSelected] = useState(0);

  return (
    <>
      {
        openModalIsButton
          /* Bigger button for navbars */
          ? <Button onClick={() => setOpen((prev) => !prev)} leftGlyph={<Icon glyph={iconGlyph} />}>
            {tooltipText}
          </Button>
          /* Small icon button */
          : <Tooltip
            trigger={
              <IconButton aria-label="Info" onClick={() => setOpen((prev) => !prev)}>
                <Icon glyph={iconGlyph} />
              </IconButton>
            }
          >
            {tooltipText}
          </Tooltip>
      }

      {/* Updated Modal without the ref prop */}
      <Modal
        open={open}
        setOpen={setOpen}
        className={styles.modal} // Removed the `ref` prop
      >
        <div className={styles.modalContent}>
          <Tabs aria-label="info wizard tabs" setSelected={setSelected} selected={selected}>
            {sections.map((tab, tabIndex) => (
              <Tab key={tabIndex} name={tab.heading}>
                {tab.content.map((section, sectionIndex) => (
                  <div key={sectionIndex} className={styles.section}>
                    {section.heading && <H3 className={styles.modalH3}>{section.heading}</H3>}
                    {
                      section.body && section.isHTML === true
                        ? <div className={styles.htmlRender}  dangerouslySetInnerHTML={{ __html: section.body }}></div>
                        : section.body && Array.isArray(section.body)
                          ? <ul className={styles.list}>
                            {
                              section.body.map((item, idx) => (
                                typeof (item) == 'object'
                                  ? <li>
                                    {item.heading}
                                    <ul className={styles.list}>
                                      {
                                        item.body.map((subItem, idx) => (
                                          <li key={idx}><Body>{subItem}</Body></li>
                                        ))
                                      }
                                    </ul>
                                  </li>
                                  : <li key={idx}><Body>{item}</Body></li>
                              )
                              )
                            }
                          </ul>
                          : <Body>{section.body}</Body>
                    }

                    {section.image && (
                      <img
                        src={section.image.src}
                        alt={section.image.alt}
                        width={section.image.width || 550}
                        className={styles.modalImage}
                      />
                    )}
                  </div>
                ))}
              </Tab>
            ))}
          </Tabs>
        </div>
      </Modal>
    </>
  );
};

InfoWizard.propTypes = {
  open: PropTypes.bool.isRequired,
  setOpen: PropTypes.func.isRequired,
  tooltipText: PropTypes.string,
  iconGlyph: PropTypes.string,
  openModalIsButton: PropTypes.bool,
  sections: PropTypes.arrayOf(
    PropTypes.shape({
      heading: PropTypes.string.isRequired, // Tab title
      content: PropTypes.arrayOf(
        PropTypes.shape({
          heading: PropTypes.string,
          body: PropTypes.string,
          isHTML: PropTypes.bool,
          image: PropTypes.shape({
            src: PropTypes.string.isRequired,
            alt: PropTypes.string.isRequired,
            width: PropTypes.number,
          }),
          images: PropTypes.arrayOf(
            PropTypes.shape({
              src: PropTypes.string.isRequired,
              alt: PropTypes.string.isRequired,
            })
          ),
        })
      ).isRequired,
    })
  ),
};

export default InfoWizard;