"""
NOT YET IMPLEMENTED.

Intended design (architecture review Section 05): rainflow-cycle-counting
features feeding a Ridge/Elastic Net or compact tree regressor for
cumulative fatigue damage, with a physics (Miner's-rule) baseline where
material parameters are supplied. Metric: max(0, 1 - MAPE).

Wire this up the same way door/ and acv/ are structured:
  loader.py              - SHM dataset loading
  rainflow_features.py    - cycle counting, amplitude/range features
  regression.py            - damage-oriented regressor + physics baseline
  pipeline.py (this file)  - SHMPipeline.fit/predict/evaluate, same shape as DoorPipeline
"""

raise NotImplementedError(
    "SHM pipeline not yet implemented. See architecture review Section 05 "
    "and SHM_Info_Kit.md before starting."
)
