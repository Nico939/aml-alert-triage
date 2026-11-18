# Databricks notebook source
# MAGIC %md
# MAGIC # AML Alert Triage on Databricks (PySpark)
# MAGIC
# MAGIC Same pipeline as `aml_project.ipynb`, with data preparation and feature engineering written in **PySpark** so it scales beyond one machine.
# MAGIC
# MAGIC - **Spark** (`src/spark_features.py`): read raw CSV, convert to USD, build 39 account-level features per week, save as Delta tables
# MAGIC - **Python** (`xgboost`): train on the feature table, which is small after aggregation (one row per account)
# MAGIC - **MLflow**: track parameters and metrics for each run
# MAGIC
# MAGIC Before running: upload `HI-Small_Trans.csv.gz` to the volume created in the next cell.

# COMMAND ----------

# MAGIC %pip install xgboost -q

# COMMAND ----------

import os, sys
sys.path.insert(0, os.path.abspath("../src"))       # reuse the project's Python modules from the Git folder

from pyspark.sql import functions as F
from spark_features import load_transactions, build_features

CATALOG, SCHEMA, VOLUME = "workspace", "default", "aml_raw"
RAW_PATH = f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME}/HI-Small_Trans.csv.gz"
SPLIT = "2022-09-06"

spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.{VOLUME}")
print("Upload the data file to:", RAW_PATH)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Load transactions with Spark

# COMMAND ----------

tx = load_transactions(spark, RAW_PATH)
tx.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.aml_transactions")
tx = spark.table(f"{CATALOG}.{SCHEMA}.aml_transactions")
print(f"{tx.count():,} transactions")

# COMMAND ----------

# MAGIC %md
# MAGIC Laundering rate by payment format, with Spark SQL:

# COMMAND ----------

display(spark.sql(f"""
    SELECT pay_format,
           COUNT(*)                         AS transactions,
           SUM(is_laundering)               AS laundering,
           ROUND(AVG(is_laundering) * 100, 3) AS laundering_rate_pct
    FROM {CATALOG}.{SCHEMA}.aml_transactions
    GROUP BY pay_format
    ORDER BY laundering_rate_pct DESC
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Account-level features (PySpark), out-of-time split
# MAGIC Train week: Sep 1-5. Test week: Sep 6-10. Each week's features are saved as a Delta table.

# COMMAND ----------

for name, cond in [("train", F.col("ts") < SPLIT), ("test", F.col("ts") >= SPLIT)]:
    build_features(tx.where(cond)).write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.aml_features_{name}")

train_sdf = spark.table(f"{CATALOG}.{SCHEMA}.aml_features_train")
test_sdf = spark.table(f"{CATALOG}.{SCHEMA}.aml_features_test")
for name, sdf in [("train", train_sdf), ("test", test_sdf)]:
    r = sdf.agg(F.count("*").alias("accounts"), F.sum("label").alias("positives")).first()
    print(f"{name}: {r.accounts:,} accounts, {r.positives:,} positive ({r.positives / r.accounts:.2%})")

# COMMAND ----------

# MAGIC %md
# MAGIC These counts match the pandas version exactly (train: 404,273 accounts, 2,799 positive), which confirms the Spark features reproduce the original logic.
# MAGIC
# MAGIC ## 3. Train XGBoost and track the run with MLflow
# MAGIC After aggregation there is one row per account (~400K rows), small enough to train in memory.

# COMMAND ----------

import mlflow
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split
from train import evaluate, rules_score, SEED

train_pdf = train_sdf.toPandas().set_index("account")
test_pdf = test_sdf.toPandas().set_index("account")
y_tr, y_te = train_pdf.pop("label"), test_pdf.pop("label")
test_pdf = test_pdf[train_pdf.columns]

X_fit, X_val, y_fit, y_val = train_test_split(train_pdf, y_tr, test_size=0.2, stratify=y_tr, random_state=SEED)
params = dict(n_estimators=1000, learning_rate=0.05, max_depth=6, subsample=0.8, colsample_bytree=0.8,
              scale_pos_weight=float((1 - y_fit.mean()) / y_fit.mean()), eval_metric="aucpr",
              early_stopping_rounds=50, random_state=SEED, n_jobs=-1)

with mlflow.start_run(run_name="xgboost_account_features"):
    model = xgb.XGBClassifier(**params).fit(X_fit, y_fit, eval_set=[(X_val, y_val)], verbose=False)
    scores = {"Rules baseline": rules_score(test_pdf),
              "XGBoost": pd.Series(model.predict_proba(test_pdf)[:, 1], index=test_pdf.index)}
    results = {name: evaluate(y_te, s) for name, s in scores.items()}
    mlflow.log_params({k: v for k, v in params.items() if k != "n_jobs"} | {"best_iteration": model.best_iteration})
    mlflow.log_metrics({k.replace("@", "_at_"): float(v) for k, v in results["XGBoost"].items()})

display(pd.DataFrame(results).T.reset_index(names="model").round(3))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Save the alert queue as a Delta table
# MAGIC Top 500 accounts by risk score, ready for the LLM summary step or a dashboard.

# COMMAND ----------

alerts = (scores["XGBoost"].sort_values(ascending=False).head(500).rename("risk_score").reset_index()
          .assign(rank=lambda d: range(1, len(d) + 1)))
spark.createDataFrame(alerts).write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.aml_alert_queue")
display(spark.table(f"{CATALOG}.{SCHEMA}.aml_alert_queue").orderBy("rank").limit(10))
