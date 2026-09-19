/**
 * Single source of truth for every acronym the interface can show.
 *
 * `caution` exists because naming is not standard across operators -- the same
 * three letters mean different subsystems at different depots, so the glossary
 * says what WE mean rather than implying an industry-wide definition.
 *
 * Kept out of Glossary.jsx so that file only exports components (fast refresh).
 */
export const TERMS = {
  ACV: {
    expansion: "Air Con Ventilation",
    detail: "Saloon air conditioning and ventilation for each car of the train.",
    caution: "Other operators use ACV for different subsystems -- confirm against local naming.",
  },
  SHM: {
    expansion: "Structural Health Monitoring",
    detail: "Long-term dynamic stress monitoring of load-bearing structures such as carbodies and bogie frames.",
  },
  CSV: {
    expansion: "Comma-Separated Values",
    detail: "Plain-text table format used for both the recordings and the prediction files.",
  },
  IoU: {
    expansion: "Intersection over Union",
    detail: "Overlap between a predicted event window and the true one: 1.0 is an exact match.",
  },
  F1: {
    expansion: "F1 score",
    detail: "Balance of precision and recall on a 0-1 scale, where 1.0 means no false alarms and no misses.",
  },
  MAPE: {
    expansion: "Mean Absolute Percentage Error",
    detail: "Average prediction error relative to the true value, so 0.05 is 5% average error.",
  },
  MAD: {
    expansion: "Median Absolute Deviation",
    detail: "Robust spread measure used to judge how far one car sits from its peers.",
  },
};
