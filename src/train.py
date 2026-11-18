"""Train and compare three ways of ranking accounts for AML review.

Out-of-time setup: features and labels are built on Sep 1-5 (train) and, separately,
on Sep 6-10 (test). Models never see the test week, which mirrors how a bank would
deploy a model on next week's activity.

  1. Rules baseline      - a simple red-flag scorecard, like a traditional rule-based monitoring system
  2. Isolation Forest    - unsupervised anomaly detection, no labels needed
  3. XGBoost             - supervised, trained on labelled laundering accounts

Investigators can only review a limited number of alerts, so the main metrics are
precision and recall in the top-k ranked accounts, plus PR-AUC.
"""
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import xgboost as xgb
from sklearn.ensemble import IsolationForest
from sklearn.metrics import average_precision_score, roc_auc_score, precision_recall_curve
from sklearn.model_selection import train_test_split

from features import build_features

SPLIT = "2022-09-06"
TOP_K = [100, 500, 1000]
SEED = 42


def rules_score(X):
    """Red-flag scorecard: one point per flag, ties broken by total volume."""
    flags = (
        (X.out_share_ach > 0.5).astype(int)
        + (X.pass_through > 0.8)
        + (X.out_n_counterparties >= 5)
        + (X.in_n_counterparties >= 5)
        + (X.out_max_txn_per_hour >= 5)
        + (X.out_share_cross_currency > 0)
    )
    return flags + np.log1p(X.out_usd_sum + X.in_usd_sum) / 100


def evaluate(y, score):
    order = np.argsort(-score.values)
    res = {"pr_auc": average_precision_score(y, score), "roc_auc": roc_auc_score(y, score)}
    for k in TOP_K:
        hits = y.values[order[:k]].sum()
        res[f"precision@{k}"] = hits / k
        res[f"recall@{k}"] = hits / y.sum()
    return res


def main():
    tx = pd.read_parquet("data/transactions.parquet")
    X_tr, y_tr = build_features(tx[tx.ts < SPLIT])
    X_te, y_te = build_features(tx[tx.ts >= SPLIT])
    X_te = X_te[X_tr.columns]
    print(f"train accounts {len(X_tr):,} (positive {y_tr.mean():.2%}), test accounts {len(X_te):,} (positive {y_te.mean():.2%})")

    scores = {"Rules baseline": rules_score(X_te)}

    iso = IsolationForest(n_estimators=200, max_samples=50_000, random_state=SEED, n_jobs=-1)
    iso.fit(np.log1p(X_tr.clip(lower=0)))
    scores["Isolation Forest"] = pd.Series(-iso.score_samples(np.log1p(X_te.clip(lower=0))), index=X_te.index)

    X_fit, X_val, y_fit, y_val = train_test_split(X_tr, y_tr, test_size=0.2, stratify=y_tr, random_state=SEED)
    model = xgb.XGBClassifier(
        n_estimators=1000, learning_rate=0.05, max_depth=6, subsample=0.8, colsample_bytree=0.8,
        scale_pos_weight=(1 - y_fit.mean()) / y_fit.mean(),   # re-weight the rare positive class
        eval_metric="aucpr", early_stopping_rounds=50, random_state=SEED, n_jobs=-1,
    )
    model.fit(X_fit, y_fit, eval_set=[(X_val, y_val)], verbose=False)
    scores["XGBoost"] = pd.Series(model.predict_proba(X_te)[:, 1], index=X_te.index)
    model.save_model("outputs/xgb_model.json")

    # Ablation: the simulator strongly ties laundering to ACH and currency switching. Re-train without
    # payment-channel and currency features to see how much the model leans on those two signals.
    drop = [c for c in X_tr.columns if "share_" in c and c.split("share_")[1] in
            {"ach", "cash", "cheque", "credit_card", "bitcoin", "wire", "cross_currency"} or "n_currencies" in c]
    ablation = xgb.XGBClassifier(**{**model.get_params(), "early_stopping_rounds": 50})
    ablation.fit(X_fit.drop(columns=drop), y_fit, eval_set=[(X_val.drop(columns=drop), y_val)], verbose=False)
    scores["XGBoost (no channel/currency features)"] = pd.Series(
        ablation.predict_proba(X_te.drop(columns=drop))[:, 1], index=X_te.index)

    metrics = {name: evaluate(y_te, s) for name, s in scores.items()}
    metrics["_meta"] = {"test_positive_rate": float(y_te.mean()), "test_accounts": int(len(X_te)),
                        "test_positives": int(y_te.sum()), "best_iteration": int(model.best_iteration)}
    print(pd.DataFrame({k: v for k, v in metrics.items() if k != "_meta"}).T.round(3).to_string())
    json.dump(metrics, open("outputs/metrics.json", "w"), indent=2, default=float)

    # Precision-recall curves
    plt.figure(figsize=(6, 4.5))
    for name, s in scores.items():
        p, r, _ = precision_recall_curve(y_te, s)
        plt.plot(r, p, label=f"{name} (PR-AUC {metrics[name]['pr_auc']:.3f})")
    plt.axhline(y_te.mean(), color="grey", ls="--", lw=1, label=f"Random ({y_te.mean():.2%})")
    plt.xlabel("Recall"); plt.ylabel("Precision"); plt.title("Out-of-time test week (Sep 6-10)")
    plt.legend(fontsize=8); plt.tight_layout(); plt.savefig("outputs/figures/pr_curves.png", dpi=150)

    # Global feature importance (mean absolute contribution)
    contrib = model.get_booster().predict(xgb.DMatrix(X_te), pred_contribs=True)[:, :-1]
    imp = pd.Series(np.abs(contrib).mean(0), index=X_te.columns).sort_values().tail(15)
    plt.figure(figsize=(6, 5)); imp.plot.barh(color="#3b6ea5")
    plt.title("Top drivers (mean |contribution|)"); plt.tight_layout()
    plt.savefig("outputs/figures/feature_importance.png", dpi=150)

    # Alert queue: top accounts in the test week with their top drivers, for the LLM summary step
    contrib = pd.DataFrame(contrib, index=X_te.index, columns=X_te.columns)
    top = scores["XGBoost"].sort_values(ascending=False).head(50)
    rows = []
    for rank, (acct, p) in enumerate(top.items(), 1):
        drivers = contrib.loc[acct].sort_values(ascending=False).head(5)
        rows.append({"rank": rank, "account": acct, "risk_score": round(float(p), 4), "label": int(y_te[acct]),
                     "top_drivers": json.dumps({f: round(float(X_te.at[acct, f]), 4) for f in drivers.index})})
    pd.DataFrame(rows).to_csv("outputs/alert_queue.csv", index=False)
    X_te.loc[top.index].to_csv("outputs/alert_features.csv")


if __name__ == "__main__":
    main()
