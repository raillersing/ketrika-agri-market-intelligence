"""Evaluation of macroeconomic and agroclimatic exogenous features for price forecasting (R3.6, ADR-105).

Implements:
1. Feature matrix construction with strict as-of temporal constraints (lag >= 1, zero lookahead).
2. LightGBM / MLForecast exogenous model fitting with deterministic fallback.
3. Rigorous 4-way feature ablation on identical rolling-origin folds:
   - price_only (autoregressive + seasonal sin/cos)
   - price_plus_macro (adds currency exchange and fuel price lags)
   - price_plus_climate (adds rainfall anomaly and temperature lags)
   - price_full (combines all feature families)
4. Parsimony decision rule with strict phase separation: selection folds choose the
   candidate, an independent holdout must confirm the gain; no statistical
   significance claim, explicit abstention on insufficient history.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Any, cast

import numpy as np

try:
    import lightgbm as lgb
except ImportError:
    lgb = None  # type: ignore


@dataclass(frozen=True)
class ExogenousFeatureConfig:
    """Configuration for exogenous feature engineering."""

    lags: tuple[int, ...] = (1, 2, 3, 12)
    include_seasonal_sin_cos: bool = True
    include_macro: bool = True
    include_climate: bool = True

    def __post_init__(self) -> None:
        """Validate lag constraints to prevent target leakage (C022)."""
        if not self.lags:
            raise ValueError("At least one lag must be specified in lags")
        for lag in self.lags:
            if not isinstance(lag, int) or lag < 1:
                raise ValueError(
                    f"Lag must be an integer >= 1 to prevent lookahead target leakage, got {lag}"
                )


@dataclass(frozen=True)
class AblationFamilyResult:
    """Metrics evaluated for one feature ablation family."""

    family_name: str
    feature_names: list[str]
    wape: float
    mae: float
    smape: float
    delta_wape_pct: float
    n_samples: int
    n_folds: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "family_name": self.family_name,
            "feature_names": self.feature_names,
            "wape": round(self.wape, 4),
            "mae": round(self.mae, 2),
            "smape": round(self.smape, 4),
            "delta_wape_pct": round(self.delta_wape_pct, 2),
            "n_samples": self.n_samples,
            "n_folds": self.n_folds,
        }


@dataclass(frozen=True)
class ExogenousAblationReport:
    """Complete multi-family ablation report enforcing ADR-105 parsimony."""

    series_id: str
    product_code: str
    location: str
    baseline_wape: float
    best_family: str
    retained: bool
    decision_reason: str
    family_results: dict[str, AblationFamilyResult] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "series_id": self.series_id,
            "product_code": self.product_code,
            "location": self.location,
            "baseline_wape": round(self.baseline_wape, 4),
            "best_family": self.best_family,
            "retained": self.retained,
            "decision_reason": self.decision_reason,
            "family_results": {k: v.to_dict() for k, v in self.family_results.items()},
        }


def build_exogenous_features(
    dates: list[date],
    prices: np.ndarray,
    macro_series: dict[str, np.ndarray] | None = None,
    climate_series: dict[str, np.ndarray] | None = None,
    config: ExogenousFeatureConfig | None = None,
    series_as_of: dict[str, list[date]] | None = None,
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Build tabular feature matrix X and target y with strict anti-leakage temporal alignment.

    At index t (origin date dates[t]), feature values MUST strictly depend on data known
    at or before t-1. Lags are verified to guarantee zero future information leakage.

    Exogenous arrays are aligned with ``dates`` by index. This alignment alone does not
    prove real publication as-of (C022) : each exogenous series may additionally declare
    its real availability dates through ``series_as_of`` with keys ``macro:<name>`` and
    ``climate:<name>``. When declared, the audit compares the ACTUAL availability date of
    the value used in each row against the target date and refuses any delayed publication
    that would still be consumed as if it were known. When not declared, the aligned
    observation date remains the documented availability convention already audited.
    """
    if config is None:
        config = ExogenousFeatureConfig()

    n = len(prices)
    if n != len(dates):
        raise ValueError(f"Length mismatch: {len(dates)} dates vs {n} prices")

    max_lag = max(config.lags)
    if n <= max_lag:
        raise ValueError(f"Insufficient history: length {n} must be > max_lag {max_lag}")

    # Validate strictly monotonic date sequence (C022)
    for i in range(1, n):
        if dates[i] <= dates[i - 1]:
            raise ValueError(
                f"Dates must be strictly monotonically increasing, got {dates[i - 1]} followed by {dates[i]}"
            )

    def resolve_as_of(kind: str, name: str) -> list[date] | None:
        if series_as_of is None:
            return None
        key = f"{kind}:{name}"
        if key not in series_as_of:
            raise ValueError(
                f"Missing declared as-of availability dates for {key}; "
                "declare the real publication availability per value (C022)"
            )
        declared = series_as_of[key]
        if len(declared) != n:
            raise ValueError(
                f"As-of availability dates for {key} length {len(declared)} != prices length {n}"
            )
        return list(declared)

    macro_as_of: dict[str, list[date] | None] = {}
    climate_as_of: dict[str, list[date] | None] = {}

    # Build feature columns
    feature_names: list[str] = []
    columns: list[list[float]] = []

    # 1. Autoregressive price lags
    for lag in config.lags:
        feature_names.append(f"price_lag_{lag}")
        col = [float(prices[i - lag]) for i in range(max_lag, n)]
        columns.append(col)

    # 2. Seasonal cycle features
    if config.include_seasonal_sin_cos:
        feature_names.append("month_sin")
        feature_names.append("month_cos")
        sin_col: list[float] = []
        cos_col: list[float] = []
        for i in range(max_lag, n):
            m = dates[i].month
            sin_col.append(math.sin(2.0 * math.pi * m / 12.0))
            cos_col.append(math.cos(2.0 * math.pi * m / 12.0))
        columns.append(sin_col)
        columns.append(cos_col)

    # 3. Macroeconomic features (strictly lagged by >= 1)
    if config.include_macro and macro_series:
        for name, series in sorted(macro_series.items()):
            if len(series) != n:
                raise ValueError(f"Macro series {name} length {len(series)} != prices length {n}")
            feature_names.append(f"macro_{name}_lag1")
            col = [float(series[i - 1]) for i in range(max_lag, n)]
            columns.append(col)
            macro_as_of[name] = resolve_as_of("macro", name)

    # 4. Agroclimatic features (strictly lagged by >= 1)
    if config.include_climate and climate_series:
        for name, series in sorted(climate_series.items()):
            if len(series) != n:
                raise ValueError(f"Climate series {name} length {len(series)} != prices length {n}")
            feature_names.append(f"climate_{name}_lag1")
            col = [float(series[i - 1]) for i in range(max_lag, n)]
            columns.append(col)
            climate_as_of[name] = resolve_as_of("climate", name)

    # Strict anti-leakage audit: actively verify each observation row (C022)
    for i in range(max_lag, n):
        row_feature_dates = [dates[i - lag] for lag in config.lags]
        if config.include_macro and macro_series:
            for name in sorted(macro_series):
                declared = macro_as_of[name]
                row_feature_dates.append(declared[i - 1] if declared is not None else dates[i - 1])
        if config.include_climate and climate_series:
            for name in sorted(climate_series):
                declared = climate_as_of[name]
                row_feature_dates.append(declared[i - 1] if declared is not None else dates[i - 1])
        validate_no_lookahead_leakage(dates, origin_index=i, feature_timestamps=row_feature_dates)

    X = np.column_stack(columns)
    y = prices[max_lag:].astype(float)
    return X, y, feature_names


def validate_no_lookahead_leakage(
    dates: list[date],
    origin_index: int,
    feature_timestamps: list[date],
) -> None:
    """Verifies that all features used at origin_index strictly precede the target date.

    Raises:
        ValueError: If any feature timestamp >= target date (fatal leakage detection).
    """
    target_date = dates[origin_index]
    for ts in feature_timestamps:
        if ts >= target_date:
            raise ValueError(
                f"Lookahead leakage detected: feature date {ts} is not strictly prior to target date {target_date}"
            )


class ExogenousGradientBoostedModel:
    """LightGBM / GBDT regressor for exogenous price forecasting with strict fallback."""

    def __init__(
        self,
        n_estimators: int = 50,
        learning_rate: float = 0.05,
        max_depth: int = 4,
        random_state: int = 42,
    ) -> None:
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.max_depth = max_depth
        self.random_state = random_state
        self.model: Any = None
        self.is_fitted = False

    def fit(self, X: np.ndarray, y: np.ndarray) -> ExogenousGradientBoostedModel:
        """Fit the gradient boosted model on training features and targets."""
        if len(y) < 10:
            raise ValueError(f"Insufficient training observations: {len(y)} < 10")

        if lgb is not None:
            self.model = lgb.LGBMRegressor(
                n_estimators=self.n_estimators,
                learning_rate=self.learning_rate,
                max_depth=self.max_depth,
                random_state=self.random_state,
                verbosity=-1,
            )
            self.model.fit(X, y)
        else:
            # Deterministic linear ridge fallback if lightgbm not installed
            X_with_bias = np.column_stack([np.ones(len(X)), X])
            lambda_reg = 1.0
            XtX = X_with_bias.T @ X_with_bias + lambda_reg * np.eye(X_with_bias.shape[1])
            weights = np.linalg.solve(XtX, X_with_bias.T @ y)
            self.model = ("ridge_fallback", weights)

        self.is_fitted = True
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Generate point forecasts for feature vector(s)."""
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted")

        if isinstance(self.model, tuple) and self.model[0] == "ridge_fallback":
            weights = self.model[1]
            X_with_bias = np.column_stack([np.ones(len(X)), X])
            return cast(np.ndarray, X_with_bias @ weights)

        preds = self.model.predict(X)
        return cast(np.ndarray, np.asarray(preds, dtype=float))


def evaluate_feature_ablation(
    dates: list[date],
    prices: np.ndarray,
    macro_series: dict[str, np.ndarray] | None = None,
    climate_series: dict[str, np.ndarray] | None = None,
    series_id: str = "MDG-PRICE-001",
    product_code: str = "rice_local",
    location: str = "Analamanga",
    n_folds: int = 5,
    min_train_size: int = 24,
    significance_threshold_pct: float = -2.0,  # Must improve WAPE by >= 2% to be retained
    holdout_folds: int = 2,  # Independent out-of-sample evaluation folds (C022)
) -> ExogenousAblationReport:
    """Runs a strict 4-way feature ablation over identical rolling-origin folds.

    Compares:
    1. 'price_only' (Baseline)
    2. 'price_plus_macro'
    3. 'price_plus_climate'
    4. 'price_full'

    Enforces ADR-105 parsimony & C022 scientific rigor:
    - Model selection uses ONLY the selection folds that precede the final holdout.
    - The final holdout folds are NEVER used for selection; a candidate must also
      confirm its gain on that independent holdout to be retained.
    - No statistical significance is claimed: thresholds are heuristic gains and
      abstention is explicit when history cannot support selection plus holdout.
    """
    if n_folds < 1 or holdout_folds < 1:
        raise ValueError("Ablation requires at least one selection fold and one holdout fold")
    configs: dict[str, ExogenousFeatureConfig] = {
        "price_only": ExogenousFeatureConfig(
            include_seasonal_sin_cos=True, include_macro=False, include_climate=False
        ),
        "price_plus_macro": ExogenousFeatureConfig(
            include_seasonal_sin_cos=True, include_macro=True, include_climate=False
        ),
        "price_plus_climate": ExogenousFeatureConfig(
            include_seasonal_sin_cos=True, include_macro=False, include_climate=True
        ),
        "price_full": ExogenousFeatureConfig(
            include_seasonal_sin_cos=True, include_macro=True, include_climate=True
        ),
    }

    # Verify minimum length for training + selection folds + holdout folds
    max_lag = 12
    n = len(prices)
    required_history = min_train_size + n_folds + holdout_folds + max_lag
    if n < required_history:
        return ExogenousAblationReport(
            series_id=series_id,
            product_code=product_code,
            location=location,
            baseline_wape=0.0,
            best_family="price_only",
            retained=False,
            decision_reason=(
                f"Insufficient history ({n} observations) for minimum training ({min_train_size}), "
                f"rolling selection ({n_folds} folds), and independent holdout ({holdout_folds} folds). "
                f"Required >= {required_history}. Explicit parsimony abstention (C022, ADR-105)."
            ),
            family_results={},
        )

    # Strict phase separation (C022): the model selection NEVER sees the holdout folds.
    selection_evaluations: dict[str, list[tuple[float, float]]] = {k: [] for k in configs}
    holdout_evaluations: dict[str, list[tuple[float, float]]] = {k: [] for k in configs}
    family_features: dict[str, list[str]] = {}

    # Build matrices for each family
    family_matrices = {}
    for fam_name, cfg in configs.items():
        X, y, f_names = build_exogenous_features(
            dates=dates,
            prices=prices,
            macro_series=macro_series,
            climate_series=climate_series,
            config=cfg,
        )
        family_matrices[fam_name] = (X, y)
        family_features[fam_name] = f_names

    # Run rolling-origin splits: selection folds strictly separated from holdout folds
    total_effective_samples = len(family_matrices["price_only"][1])
    selection_origins = range(
        total_effective_samples - n_folds - holdout_folds, total_effective_samples - holdout_folds
    )
    holdout_origins = range(total_effective_samples - holdout_folds, total_effective_samples)

    def run_folds(fam_name: str, origins: range) -> list[tuple[float, float]]:
        X, y = family_matrices[fam_name]
        pairs: list[tuple[float, float]] = []
        for origin in origins:
            X_train, y_train = X[:origin], y[:origin]
            X_test, y_test = X[origin : origin + 1], y[origin : origin + 1]
            model = ExogenousGradientBoostedModel()
            model.fit(X_train, y_train)
            pred = model.predict(X_test)[0]
            pairs.append((float(y_test[0]), float(pred)))
        return pairs

    for fam_name in configs:
        selection_evaluations[fam_name] = run_folds(fam_name, selection_origins)
        holdout_evaluations[fam_name] = run_folds(fam_name, holdout_origins)

    def aggregate(pairs: list[tuple[float, float]]) -> tuple[float, float, float]:
        """Return (wape, mae, smape) over the given (actual, predicted) pairs."""
        if not pairs:
            return 0.0, 0.0, 0.0
        actuals = np.array([p[0] for p in pairs])
        preds = np.array([p[1] for p in pairs])
        errors = np.abs(actuals - preds)
        denom = float(np.sum(actuals))
        wape = float(np.sum(errors) / denom) if denom > 0 else 0.0
        mae = float(np.mean(errors))
        smape = float(np.mean(2.0 * errors / np.maximum(np.abs(actuals) + np.abs(preds), 1e-6)))
        return wape, mae, smape

    # Phase 1 - model selection on selection folds ONLY
    selection_metrics: dict[str, tuple[float, float, float]] = {
        fam: aggregate(pairs) for fam, pairs in selection_evaluations.items()
    }
    selection_baseline = selection_metrics["price_only"][0]
    selection_delta: dict[str, float] = {}
    for fam, (wape, _mae, _smape) in selection_metrics.items():
        if fam == "price_only":
            selection_delta[fam] = 0.0
            continue
        delta = (
            ((wape - selection_baseline) / selection_baseline) * 100.0
            if selection_baseline > 0
            else 0.0
        )
        selection_delta[fam] = delta

    sel_best_family, sel_best_wape = "price_only", selection_baseline
    for fam, (wape, _mae, _smape) in selection_metrics.items():
        if wape < sel_best_wape:
            sel_best_family, sel_best_wape = fam, wape
    sel_best_delta = selection_delta[sel_best_family]

    selection_improved = (
        sel_best_family != "price_only" and sel_best_delta <= significance_threshold_pct
    )

    # Phase 2 - independent holdout evaluation of every family (reported metrics)
    holdout_metrics: dict[str, tuple[float, float, float]] = {
        fam: aggregate(pairs) for fam, pairs in holdout_evaluations.items()
    }
    baseline_wape = holdout_metrics["price_only"][0]

    family_results: dict[str, AblationFamilyResult] = {}
    for fam_name in configs:
        wape, mae, smape = holdout_metrics[fam_name]
        delta = ((wape - baseline_wape) / baseline_wape) * 100.0 if baseline_wape > 0 else 0.0
        family_results[fam_name] = AblationFamilyResult(
            family_name=fam_name,
            feature_names=family_features[fam_name],
            wape=wape,
            mae=mae,
            smape=smape,
            delta_wape_pct=delta,
            n_samples=holdout_folds,
            n_folds=n_folds,
        )

    # Parsimony rule: selection-phase improvement must ALSO be confirmed on the
    # independent holdout before any exogenous candidate is retained.
    best_family = "price_only"
    retained = False
    if not selection_improved:
        decision_reason = (
            f"Univariable baseline 'price_only' retained by parsimony: best candidate '{sel_best_family}' "
            f"achieved {sel_best_delta:+.1f}% WAPE delta on {n_folds} selection folds "
            f"(required improvement <= {significance_threshold_pct:.1f}%). "
            f"Independent holdout measured on {holdout_folds} final folds only."
        )
    else:
        holdout_baseline = baseline_wape
        holdout_candidate = holdout_metrics[sel_best_family][0]
        holdout_delta = (
            ((holdout_candidate - holdout_baseline) / holdout_baseline) * 100.0
            if holdout_baseline > 0
            else 0.0
        )
        if holdout_delta <= significance_threshold_pct:
            retained = True
            best_family = sel_best_family
            decision_reason = (
                f"Exogenous family '{best_family}' retained: heuristic WAPE reduction of "
                f"{abs(sel_best_delta):.1f}% over the univariable baseline on {n_folds} selection folds, "
                f"confirmed on the {holdout_folds}-fold independent holdout ({abs(holdout_delta):.1f}% "
                f"reduction). Threshold {abs(significance_threshold_pct):.1f}%; heuristic gain, "
                "not a statistical significance claim."
            )
        else:
            decision_reason = (
                f"Exogenous candidate '{sel_best_family}' improved WAPE by {abs(sel_best_delta):.1f}% "
                f"on the {n_folds} selection folds but FAILED independent holdout confirmation "
                f"({holdout_delta:+.1f}% on {holdout_folds} final folds; required improvement "
                f"<= {significance_threshold_pct:.1f}%). Univariable baseline 'price_only' retained. "
                "Heuristic gains are not statistical significance."
            )

    return ExogenousAblationReport(
        series_id=series_id,
        product_code=product_code,
        location=location,
        baseline_wape=baseline_wape,
        best_family=best_family,
        retained=retained,
        decision_reason=decision_reason,
        family_results=family_results,
    )
