"""Account-level behavioural features for one time window.

Each row is one account. Features describe how money moves in and out of the account,
using signals that AML typologies point to: volume, fan-in / fan-out, pass-through
(money in and quickly out), payment channels, currency switching and bursts of activity.
"""
import numpy as np
import pandas as pd

# "Reinvestment" only appears as self-transfers, which are dropped below
FORMATS = ["ACH", "Cash", "Cheque", "Credit Card", "Bitcoin", "Wire"]


def _side(df, acct_col, cp_col, cur_col, prefix):
    """Aggregate one direction of flow (outgoing or incoming) per account."""
    g = df.groupby(acct_col)
    f = pd.DataFrame({
        "n_txn": g.size(),
        "usd_sum": g.amt_usd.sum(),
        "usd_mean": g.amt_usd.mean(),
        "usd_max": g.amt_usd.max(),
        "usd_std": g.amt_usd.std().fillna(0),
        "n_counterparties": g[cp_col].nunique(),
        "n_banks": g.cp_bank.nunique(),
        "n_currencies": g[cur_col].nunique(),
        "share_cross_currency": g.cross_cur.mean(),
        "share_round_amount": g.round_amt.mean(),
        "max_txn_per_hour": df.groupby([acct_col, "hour_bucket"]).size().groupby(level=0).max(),
        "active_days": g.day.nunique(),
    })
    shares = pd.crosstab(df[acct_col], df.pay_format, normalize="index")
    for fmt in FORMATS:
        name = "share_" + fmt.lower().replace(" ", "_")
        f[name] = shares[fmt] if fmt in shares else 0.0
    return f.add_prefix(prefix)


def build_features(tx):
    """tx: transactions in one window. Returns (features, labels) indexed by account id."""
    tx = tx[tx.from_id != tx.to_id].copy()          # drop self-transfers (account moving money to itself)
    tx["cross_cur"] = tx.recv_cur != tx.pay_cur
    tx["round_amt"] = (tx.amt_paid % 100 == 0) & (tx.amt_paid >= 100)
    tx["hour_bucket"] = tx.ts.dt.floor("h")
    tx["day"] = tx.ts.dt.date

    out_side = _side(tx.assign(cp_bank=tx.to_bank), "from_id", "to_id", "pay_cur", "out_")
    in_side = _side(tx.assign(cp_bank=tx.from_bank), "to_id", "from_id", "recv_cur", "in_")
    X = out_side.join(in_side, how="outer").fillna(0)

    # Pass-through: how closely money out matches money in (layering accounts tend to be close to 1)
    X["pass_through"] = np.minimum(X.in_usd_sum, X.out_usd_sum) / np.maximum(X.in_usd_sum, X.out_usd_sum).replace(0, np.nan)
    X["pass_through"] = X.pass_through.fillna(0)
    X["log_net_flow"] = np.sign(X.in_usd_sum - X.out_usd_sum) * np.log1p((X.in_usd_sum - X.out_usd_sum).abs())
    X["fan_ratio"] = (X.out_n_counterparties + 1) / (X.in_n_counterparties + 1)

    # Label: the account sent or received at least one laundering transaction in this window
    bad = pd.concat([tx.loc[tx.is_laundering == 1, "from_id"], tx.loc[tx.is_laundering == 1, "to_id"]]).unique()
    y = pd.Series(X.index.isin(bad).astype(int), index=X.index, name="label")
    return X, y
