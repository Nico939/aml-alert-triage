"""PySpark version of the data preparation and account-level features.

Same logic as prepare_data.py + features.py, written with Spark DataFrames so it can run
on a cluster (e.g. Databricks) when the transaction table is too big for one machine.
"""
from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F

RAW_COLS = ["ts", "from_bank", "from_acct", "to_bank", "to_acct", "amt_recv", "recv_cur",
            "amt_paid", "pay_cur", "pay_format", "is_laundering"]
FORMATS = ["ACH", "Cash", "Cheque", "Credit Card", "Bitcoin", "Wire"]


def load_transactions(spark: SparkSession, path: str, end_date: str = "2022-09-11") -> DataFrame:
    """Read the raw IBM CSV, add account ids and USD amounts, keep dates before end_date."""
    raw = spark.read.csv(path, header=True, inferSchema=False).toDF(*RAW_COLS)
    df = (raw
          .withColumn("ts", F.to_timestamp("ts", "yyyy/MM/dd HH:mm"))
          .withColumn("amt_recv", F.col("amt_recv").cast("double"))
          .withColumn("amt_paid", F.col("amt_paid").cast("double"))
          .withColumn("is_laundering", F.col("is_laundering").cast("int"))
          .withColumn("from_id", F.concat_ws("_", "from_bank", "from_acct"))
          .withColumn("to_id", F.concat_ws("_", "to_bank", "to_acct")))

    # USD rate per currency = median of (received USD / paid) over cross-currency payments into USD
    rates = (df.where((F.col("recv_cur") == "US Dollar") & (F.col("pay_cur") != "US Dollar"))
               .groupBy("pay_cur")
               .agg(F.percentile_approx(F.col("amt_recv") / F.col("amt_paid"), 0.5, 100000).alias("usd_rate"))
               .unionByName(spark.createDataFrame([("US Dollar", 1.0)], ["pay_cur", "usd_rate"])))
    df = df.join(F.broadcast(rates), "pay_cur", "left").withColumn("amt_usd", F.col("amt_paid") * F.col("usd_rate"))
    return df.where(F.col("ts") < F.lit(end_date).cast("timestamp"))


def _side(tx: DataFrame, acct: str, cp: str, cp_bank: str, cur: str, prefix: str) -> DataFrame:
    """Aggregate one direction of flow (outgoing or incoming) per account."""
    per_hour = (tx.groupBy(acct, F.date_trunc("hour", "ts").alias("hour")).count()
                  .groupBy(acct).agg(F.max("count").alias("max_txn_per_hour")))
    aggs = [
        F.count("*").alias("n_txn"),
        F.sum("amt_usd").alias("usd_sum"),
        F.avg("amt_usd").alias("usd_mean"),
        F.max("amt_usd").alias("usd_max"),
        F.coalesce(F.stddev_samp("amt_usd"), F.lit(0.0)).alias("usd_std"),
        F.countDistinct(cp).alias("n_counterparties"),
        F.countDistinct(cp_bank).alias("n_banks"),
        F.countDistinct(cur).alias("n_currencies"),
        F.avg(F.col("cross_cur").cast("double")).alias("share_cross_currency"),
        F.avg(F.col("round_amt").cast("double")).alias("share_round_amount"),
        F.countDistinct(F.to_date("ts")).alias("active_days"),
    ] + [F.avg((F.col("pay_format") == f).cast("double")).alias("share_" + f.lower().replace(" ", "_"))
         for f in FORMATS]
    out = tx.groupBy(acct).agg(*aggs).join(per_hour, acct)
    return out.select(F.col(acct).alias("account"),
                      *[F.col(c).alias(prefix + c) for c in out.columns if c != acct])


def build_features(tx: DataFrame) -> DataFrame:
    """Account-level features and label for one time window. One row per account."""
    tx = (tx.where(F.col("from_id") != F.col("to_id"))
            .withColumn("cross_cur", F.col("recv_cur") != F.col("pay_cur"))
            .withColumn("round_amt", ((F.col("amt_paid") % 100) == 0) & (F.col("amt_paid") >= 100)))

    out_side = _side(tx, "from_id", "to_id", "to_bank", "pay_cur", "out_")
    in_side = _side(tx, "to_id", "from_id", "from_bank", "recv_cur", "in_")
    X = out_side.join(in_side, "account", "full_outer").fillna(0)

    lo = F.least("in_usd_sum", "out_usd_sum")
    hi = F.greatest("in_usd_sum", "out_usd_sum")
    net = F.col("in_usd_sum") - F.col("out_usd_sum")
    X = (X.withColumn("pass_through", F.when(hi > 0, lo / hi).otherwise(0.0))
          .withColumn("log_net_flow", F.signum(net) * F.log1p(F.abs(net)))
          .withColumn("fan_ratio", (F.col("out_n_counterparties") + 1) / (F.col("in_n_counterparties") + 1)))

    bad = (tx.where(F.col("is_laundering") == 1)
             .select(F.explode(F.array("from_id", "to_id")).alias("account")).distinct()
             .withColumn("label", F.lit(1)))
    return X.join(bad, "account", "left").fillna(0, subset=["label"])
