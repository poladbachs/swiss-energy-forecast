import pandas as pd
import numpy as np
import holidays as hl

CH_HOLIDAYS = hl.Switzerland()
_LAGS = [1, 24, 48, 168]
_WEATHER_COLS = ["temperature", "solar_radiation", "wind_speed", "cloud_cover"]

_STATIC_COLS = [
    "hour_of_day", "day_of_week", "month", "is_weekend", "is_swiss_holiday",
    "temperature", "solar_radiation", "wind_speed", "cloud_cover",
    "hours_ahead",
]


def build_features(df: pd.DataFrame, target: str, hours_ahead: int) -> pd.DataFrame:
    """
    Training feature builder. df rows are BASE times t; training target is
    df[target].shift(-hours_ahead) (i.e. the value at t + hours_ahead).

    Feature semantics:
      - Calendar: at TARGET time t+hours_ahead (drives demand patterns at that moment)
      - Weather:  at TARGET time t+hours_ahead (shifted forward in historical df)
      - Lags:     at BASE time t and earlier  (always known at inference without recursion)
    """
    df = df.copy().sort_values("timestamp").reset_index(drop=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    # Force one row per hour so the positional shift()s below equal true
    # hour-offsets even if the source data has gaps. A missing hour becomes
    # an all-NaN row here, which propagates into "label" and the feature
    # cols and gets dropped by build_training_frame's dropna — instead of
    # silently shifting lag/weather values across the gap onto the wrong hour.
    full_index = pd.date_range(df["timestamp"].min(), df["timestamp"].max(), freq="h", tz="UTC")
    df = df.set_index("timestamp").reindex(full_index).rename_axis("timestamp").reset_index()

    # Calendar at TARGET time t+hours_ahead
    target_ts = df["timestamp"] + pd.Timedelta(hours=hours_ahead)
    df["hour_of_day"]      = target_ts.dt.hour
    df["day_of_week"]      = target_ts.dt.dayofweek
    df["month"]            = target_ts.dt.month
    df["is_weekend"]       = target_ts.dt.dayofweek.isin([5, 6]).astype(int)
    df["is_swiss_holiday"] = target_ts.dt.date.apply(lambda d: int(d in CH_HOLIDAYS))

    # Lag features at BASE time t (no future knowledge needed)
    for lag in _LAGS:
        df[f"{target}_lag_{lag}h"] = df[target].shift(lag)
    df[f"{target}_rolling_24h_mean"] = df[target].shift(1).rolling(24).mean()
    df[f"{target}_rolling_24h_std"]  = df[target].shift(1).rolling(24).std()

    # Weather at TARGET time t+hours_ahead: shift(-h) pulls the value at t+h
    # onto the row for base time t
    for col in _WEATHER_COLS:
        df[col] = df[col].shift(-hours_ahead)

    df["hours_ahead"] = hours_ahead
    return df


def inference_features(
    history: pd.DataFrame,
    target: str,
    weather_forecast: pd.DataFrame,
    now: pd.Timestamp,
    horizon: int = 48,
) -> pd.DataFrame:
    """
    Build the inference feature matrix, one row per forecast hour h=1..horizon.

    Lag/rolling features are computed once from history at base time 'now'
    (identical across all horizons, no recursive forecasting needed).
    Calendar and weather features are at each target time now+h.

    Returns DataFrame with columns == get_feature_cols(target).
    """
    hist = history.copy().sort_values("timestamp")
    hist["timestamp"] = pd.to_datetime(hist["timestamp"], utc=True)
    if isinstance(now, pd.Timestamp):
        now = now.tz_convert("UTC") if now.tzinfo else now.tz_localize("UTC")
    else:
        now = pd.Timestamp(now, tz="UTC")

    # Base lags, fixed for all forecast horizons
    base = {}
    for lag in _LAGS:
        lag_ts = now - pd.Timedelta(hours=lag)
        vals = hist.loc[hist["timestamp"] <= lag_ts, target].values
        base[f"{target}_lag_{lag}h"] = float(vals[-1]) if len(vals) else np.nan

    recent = hist.loc[hist["timestamp"] < now, target].values[-24:]
    base[f"{target}_rolling_24h_mean"] = float(recent.mean()) if len(recent) >= 24 else np.nan
    base[f"{target}_rolling_24h_std"]  = float(recent.std())  if len(recent) >= 24 else np.nan

    wdf = weather_forecast.copy()
    wdf["timestamp"] = pd.to_datetime(wdf["timestamp"], utc=True)
    wdf = wdf.set_index("timestamp")

    rows = []
    for h in range(1, horizon + 1):
        target_ts = now + pd.Timedelta(hours=h)
        w = wdf.loc[target_ts] if target_ts in wdf.index else pd.Series(dtype=float)
        rows.append({
            **base,
            "hour_of_day":      target_ts.hour,
            "day_of_week":      target_ts.dayofweek,
            "month":            target_ts.month,
            "is_weekend":       int(target_ts.dayofweek >= 5),
            "is_swiss_holiday": int(target_ts.date() in CH_HOLIDAYS),
            "temperature":      float(w["temperature"])     if "temperature"     in w.index else np.nan,
            "solar_radiation":  float(w["solar_radiation"]) if "solar_radiation" in w.index else np.nan,
            "wind_speed":       float(w["wind_speed"])      if "wind_speed"      in w.index else np.nan,
            "cloud_cover":      float(w["cloud_cover"])     if "cloud_cover"     in w.index else np.nan,
            "hours_ahead":      h,
        })
    return pd.DataFrame(rows)[get_feature_cols(target)]


def build_training_frame(df: pd.DataFrame, target: str, horizons=range(1, 49)) -> pd.DataFrame:
    """
    Multi-horizon training frame: for each h, build features and a "label" column
    (the target value h hours ahead), then concatenate all horizons.
    Shared by train.train() and conformal.calibrate() so both see identical data.
    """
    frames = []
    for h in horizons:
        f = build_features(df, target, h)
        f["label"] = f[target].shift(-h)
        f = f.dropna(subset=get_feature_cols(target) + ["label"])
        frames.append(f)
    return pd.concat(frames, ignore_index=True)


def get_feature_cols(target: str) -> list[str]:
    lag_cols  = [f"{target}_lag_{h}h" for h in _LAGS]
    roll_cols = [f"{target}_rolling_24h_mean", f"{target}_rolling_24h_std"]
    return _STATIC_COLS + lag_cols + roll_cols
