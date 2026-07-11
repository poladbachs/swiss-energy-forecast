"""
Signal experiment: does a "bridge day" flag improve the demand forecast?

The job this project targets explicitly calls out this kind of work: adding
a new signal to a demand forecast and testing whether it actually helps,
not assuming it does. A bridge day (a working day squeezed between a public
holiday and the weekend, e.g. the Friday after a Thursday holiday) isn't
caught by the existing is_swiss_holiday flag, but real demand on those days
looks much closer to a holiday than an ordinary weekday.

This script:
  1. Checks the raw historical effect (is it even real?).
  2. Retrains the demand model with the feature added.
  3. Tests specifically on held-out bridge-day hours, not the aggregate
     metric, since the aggregate is dominated by the 99.5% of hours that
     aren't bridge days and won't move either way.
  4. Reports the honest result, including why it came out the way it did.

Conclusion (see README): the raw effect is real and large (~12% lower
daytime demand), but only 11 bridge days exist in 6 years of history, too
few for the model to learn a reliable split. Adding the feature made
held-out bridge-day accuracy worse, not better, and the model itself ranks
it near-zero importance. Not shipped in production for that reason
(features/engineer.py keeps is_bridge_day() for this script to import, but
excludes it from _STATIC_COLS).

Run:
    python -m scripts.experiment_bridge_day
"""
import numpy as np
from lightgbm import LGBMRegressor

from dotenv import load_dotenv
load_dotenv()

from features.engineer import build_training_frame, get_feature_cols, is_bridge_day, CH_HOLIDAYS
from models.train import DEFAULT_PARAMS
from storage.db import query as db_query

TARGET = "demand_mw"


def check_raw_historical_effect(df) -> None:
    """Is the bridge-day effect even real, before spending a model run on it?"""
    d = df.dropna(subset=[TARGET]).copy()
    d["date"] = d["timestamp"].dt.date
    d["weekday"] = d["timestamp"].dt.dayofweek
    d["is_holiday"] = d["date"].apply(lambda x: x in CH_HOLIDAYS)
    d["is_bridge"] = d.apply(lambda r: bool(is_bridge_day(r["date"])), axis=1)

    daytime = d[d["timestamp"].dt.hour.between(9, 17) & ~d["is_holiday"]]
    bridge_avg = daytime.loc[daytime["is_bridge"], TARGET].mean()
    ordinary_avg = daytime.loc[~daytime["is_bridge"] & daytime["weekday"].isin([0, 4]), TARGET].mean()
    n_bridge_days = d.loc[d["is_bridge"], "date"].nunique()

    print(f"[raw check] {n_bridge_days} bridge days in the dataset")
    print(f"[raw check] bridge daytime avg: {bridge_avg:.0f} MW, ordinary Mon/Fri daytime avg: {ordinary_avg:.0f} MW "
          f"({100 * (bridge_avg - ordinary_avg) / ordinary_avg:+.1f}%)")


def compare_with_and_without_feature(df) -> None:
    """Retrain with the feature added, test specifically on bridge-day hours."""
    frame = build_training_frame(df, TARGET, range(1, 49)).sort_values("timestamp").reset_index(drop=True)
    frame["is_bridge_day"] = frame["timestamp"].dt.date.apply(is_bridge_day)

    split = int(len(frame) * 0.8)
    train_df, val_df = frame.iloc[:split], frame.iloc[split:]

    cols_without = get_feature_cols(TARGET)
    cols_with = cols_without + ["is_bridge_day"]

    model_without = LGBMRegressor(**DEFAULT_PARAMS, verbose=-1).fit(train_df[cols_without], train_df["label"])
    model_with = LGBMRegressor(**DEFAULT_PARAMS, verbose=-1).fit(train_df[cols_with], train_df["label"])

    pred_without = model_without.predict(val_df[cols_without])
    pred_with = model_with.predict(val_df[cols_with])

    bridge_mask = (val_df["is_bridge_day"] == 1).values
    n_bridge_val = int(bridge_mask.sum())
    y_val = val_df["label"].values

    mae_without = np.abs(y_val[bridge_mask] - pred_without[bridge_mask]).mean()
    mae_with = np.abs(y_val[bridge_mask] - pred_with[bridge_mask]).mean()
    overall_without = np.abs(y_val - pred_without).mean()
    overall_with = np.abs(y_val - pred_with).mean()

    importance = dict(zip(cols_with, model_with.feature_importances_))
    rank = sorted(importance, key=importance.get, reverse=True).index("is_bridge_day") + 1

    print(f"[held-out test] {n_bridge_val} bridge-day rows in the validation split")
    print(f"[held-out test] bridge-day MAE without feature: {mae_without:.1f} MW")
    print(f"[held-out test] bridge-day MAE with feature:    {mae_with:.1f} MW "
          f"({100 * (1 - mae_with / mae_without):+.1f}%)")
    print(f"[held-out test] overall MAE without: {overall_without:.1f} MW, with: {overall_with:.1f} MW")
    print(f"[held-out test] is_bridge_day feature-importance rank: {rank}/{len(cols_with)}")


def main() -> None:
    df = db_query()
    check_raw_historical_effect(df)
    compare_with_and_without_feature(df)


if __name__ == "__main__":
    main()
