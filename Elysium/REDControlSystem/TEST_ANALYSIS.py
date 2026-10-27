# TEST_ANALYSIS.py
# Pure (no Qt) sample smoothing + decay analysis for hold tests such as the leak check.
#
# A SeriesTrack accumulates the raw (time, value) samples of one sensor from the moment a
# test starts and, on demand, returns a TrackResult: a median-binned raw trace, a causal
# smoothed trace, the baseline, the delta since baseline and the rate of change (psi/min).
#
# Everything here is causal (a sample only ever uses samples at or before it), so the live
# trace is exactly what a post-test pass would produce - no lag-free zero-phase filter, which
# would need future samples. The raw samples are never modified.
import math
from dataclasses import dataclass, field

import numpy as np

SMOOTH_NONE   = "None"
SMOOTH_MEAN   = "Moving average"
SMOOTH_MEDIAN = "Rolling median"
SMOOTH_METHODS = (SMOOTH_MEAN, SMOOTH_MEDIAN, SMOOTH_NONE)

BASELINE_S    = 2.0     # the start value is the median of this many seconds of data
MIN_FIT_S     = 20.0    # no rate is reported until the fit spans at least this long
MIN_FIT_BINS  = 10
MAX_PLOT_BINS = 3000    # plot resolution: bins widen for long tests instead of growing


@dataclass
class TrackResult:
    t_raw: np.ndarray = field(default_factory=lambda: np.empty(0))
    raw: np.ndarray = field(default_factory=lambda: np.empty(0))
    t_smooth: np.ndarray = field(default_factory=lambda: np.empty(0))
    smooth: np.ndarray = field(default_factory=lambda: np.empty(0))
    baseline: float = math.nan       # start value
    current: float = math.nan        # latest smoothed value
    delta: float = math.nan          # current - baseline
    rate: float = math.nan           # units per minute
    rate_err: float = math.nan       # standard error of the rate, units per minute
    n_samples: int = 0


def _bin_median(t: np.ndarray, v: np.ndarray, width: float):
    """Median of v per time bin. Returns (bin centre times, medians) for non-empty bins."""
    if len(t) == 0:
        return np.empty(0), np.empty(0)
    idx = np.floor(t / width).astype(np.int64)
    cuts = np.flatnonzero(np.diff(idx)) + 1
    starts = np.concatenate(([0], cuts))
    ends = np.concatenate((cuts, [len(t)]))
    bt = np.empty(len(starts))
    bv = np.empty(len(starts))
    for k, (a, b) in enumerate(zip(starts, ends)):
        bt[k] = (idx[a] + 0.5) * width
        bv[k] = np.median(v[a:b])
    return bt, bv


def smooth_trailing(bt: np.ndarray, bv: np.ndarray, window_s: float, method: str) -> np.ndarray:
    """Causal smoothing over a trailing time window (seconds), not a sample count, so uneven
    sample spacing doesn't change what 'a 3 s average' means."""
    if method == SMOOTH_NONE or window_s <= 0 or len(bt) == 0:
        return bv.copy()
    lo = np.searchsorted(bt, bt - window_s, side="right")    # first bin inside each window
    if method == SMOOTH_MEAN:
        cs = np.concatenate(([0.0], np.cumsum(bv)))
        hi = np.arange(1, len(bt) + 1)
        return (cs[hi] - cs[lo]) / (hi - lo)
    out = np.empty(len(bt))
    for i in range(len(bt)):
        out[i] = np.median(bv[lo[i]:i + 1])
    return out


def fit_rate(t: np.ndarray, v: np.ndarray):
    """Least-squares slope of v against t. Returns (slope, standard_error) per second, or
    (nan, nan) when there is too little data. The standard error is corrected for
    correlated residuals (see below), but it is still an estimate, not a guarantee."""
    n = len(t)
    if n < MIN_FIT_BINS or (t[-1] - t[0]) < MIN_FIT_S:
        return math.nan, math.nan
    tm, vm = t.mean(), v.mean()
    sxx = float(np.sum((t - tm) ** 2))
    if sxx <= 0:
        return math.nan, math.nan
    slope = float(np.sum((t - tm) * (v - vm)) / sxx)
    resid = v - (vm + slope * (t - tm))
    s2 = float(np.sum(resid ** 2) / (n - 2)) if n > 2 else 0.0
    # Slow drift makes neighbouring residuals alike, so there are fewer independent samples
    # than bins. Inflate by the lag-1 autocorrelation (AR(1) effective-sample correction).
    rho = 0.0
    den = float(np.sum(resid ** 2))
    if den > 0:
        rho = min(max(float(np.sum(resid[1:] * resid[:-1]) / den), 0.0), 0.95)
    return slope, math.sqrt(s2 / sxx * (1 + rho) / (1 - rho))


class SeriesTrack:
    """Raw samples of one sensor, with time measured from the test start (seconds)."""

    def __init__(self):
        self._t: list = []
        self._v: list = []

    def __len__(self):
        return len(self._t)

    def add(self, t: float, value: float):
        """Record a sample. NaN (a sensor reporting no signal) is skipped."""
        if value is None or math.isnan(value) or t < 0:
            return
        if self._t and t < self._t[-1]:
            return                      # out-of-order: keep time monotonic
        self._t.append(float(t))
        self._v.append(float(value))

    def raw_arrays(self):
        return np.asarray(self._t), np.asarray(self._v)

    def analyze(self, method: str = SMOOTH_MEAN, window_s: float = 3.0,
                settle_s: float = 0.0) -> TrackResult:
        res = TrackResult(n_samples=len(self._t))
        if not self._t:
            return res
        t, v = self.raw_arrays()

        width = max(0.1, (t[-1] - t[0]) / MAX_PLOT_BINS)
        bt, bv = _bin_median(t, v, width)
        sm = smooth_trailing(bt, bv, window_s, method)
        res.t_raw, res.raw, res.t_smooth, res.smooth = bt, bv, bt, sm
        res.current = float(sm[-1])

        # Baseline: median of the first BASELINE_S of data after the settle period.
        if t[-1] >= settle_s + BASELINE_S:
            m = (t >= settle_s) & (t < settle_s + BASELINE_S)
            if m.sum() >= 3:
                res.baseline = float(np.median(v[m]))
                res.delta = res.current - res.baseline

        # Rate: fit 1 s medians (independent of the display smoothing) after the settle period.
        m = t >= settle_s
        if m.any():
            ft, fv = _bin_median(t[m], v[m], 1.0)
            slope, err = fit_rate(ft, fv)
            res.rate, res.rate_err = slope * 60.0, err * 60.0
        return res

    def summary(self, method: str, window_s: float, settle_s: float) -> dict:
        r = self.analyze(method, window_s, settle_s)
        f = lambda x: None if math.isnan(x) else x
        return {"baseline": f(r.baseline), "final_smoothed": f(r.current),
                "delta": f(r.delta), "rate_per_min": f(r.rate),
                "rate_stderr_per_min": f(r.rate_err), "samples": r.n_samples}
