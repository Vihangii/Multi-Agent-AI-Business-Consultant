"""
Stub package that stands in for matplotlib.

Prophet declares matplotlib as a hard dependency but only imports it inside a
try/except in prophet.plot, purely for optional plotting. This project never
plots, and the real matplotlib (with fontTools, pillow, kiwisolver, ...) adds
~90 MB to the serverless bundle. Raising ImportError here makes prophet take
its "plotting unavailable" branch.
"""

raise ImportError(
    "matplotlib is stubbed out in this deployment (see vendor/matplotlib-stub). "
    "Plotting is not available."
)
