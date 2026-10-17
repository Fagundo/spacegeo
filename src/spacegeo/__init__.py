"""spacegeo: does space weather add predictive information to earthquake forecasts?

Layers (dependencies point downward only, enforced by import-linter):

    training     orchestrates fitting models on temporal splits
    evaluation   scores fitted models (information gain, calibration)
    models       forecast models (ETAS baseline, ETAS + covariates, ...)
    features     leakage-safe covariates computed at forecast times
    data         scraping -> io -> preprocessing (mutually independent)
    common       shared utilities; imports nothing else from spacegeo
"""

__version__ = "0.1.0"
