import { useState } from "react";
import Icon from "./Icon";
import { TERMS } from "../terms";

/** Inline acronym with a hover/focus tooltip. Usage: <Term k="ACV" /> */
export function Term({ k, children }) {
  const entry = TERMS[k];
  if (!entry) return <>{children ?? k}</>;
  const summary = `${k} -- ${entry.expansion}. ${entry.detail}`;
  return (
    <span className="term" tabIndex={0} title={summary}>
      {children ?? k}
      <span className="term__tip" role="tooltip">
        <strong>{entry.expansion}</strong>
        <span>{entry.detail}</span>
        {entry.caution && <em>{entry.caution}</em>}
      </span>
    </span>
  );
}

/** Header control that opens the full acronym list. */
export default function Glossary() {
  const [open, setOpen] = useState(false);
  return (
    <div className="glossary">
      <button
        className="glossary__toggle"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <Icon name="info" size={15} />
        Glossary
      </button>
      {open && (
        <div className="glossary__panel">
          <p className="glossary__note">
            Terminology differs between operators. These are the definitions used in this tool.
          </p>
          <dl className="glossary__list">
            {Object.entries(TERMS).map(([key, entry]) => (
              <div className="glossary__item" key={key}>
                <dt>{key}</dt>
                <dd>
                  <strong>{entry.expansion}</strong>
                  <span>{entry.detail}</span>
                  {entry.caution && <em>{entry.caution}</em>}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </div>
  );
}
