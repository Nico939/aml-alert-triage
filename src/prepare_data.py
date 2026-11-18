"""Load the IBM AML transactions (HI-Small), convert amounts to USD, save as parquet."""
import sys
import pandas as pd

RAW = sys.argv[1] if len(sys.argv) > 1 else "data/HI-Small_Trans.csv"
OUT = "data/transactions.parquet"

COLS = ["ts", "from_bank", "from_acct", "to_bank", "to_acct", "amt_recv", "recv_cur",
        "amt_paid", "pay_cur", "pay_format", "is_laundering"]


def usd_rates(df):
    """Estimate each currency's USD rate from cross-currency transactions (median of received / paid)."""
    x = df[(df.recv_cur == "US Dollar") & (df.pay_cur != "US Dollar")]
    rates = (x.amt_recv / x.amt_paid).groupby(x.pay_cur).median()
    rates["US Dollar"] = 1.0
    return rates


def main():
    df = pd.read_csv(RAW, dtype={"From Bank": str, "To Bank": str, "Account": str, "Account.1": str})
    df.columns = COLS
    df["ts"] = pd.to_datetime(df["ts"], format="%Y/%m/%d %H:%M")
    df["from_id"] = df.from_bank + "_" + df.from_acct
    df["to_id"] = df.to_bank + "_" + df.to_acct
    df["amt_usd"] = df.amt_paid * df.pay_cur.map(usd_rates(df))

    # After Sep 10 the data has only a few hundred transactions, mostly laundering (a simulation tail),
    # so we keep Sep 1-10 where volumes are realistic.
    df = df[df.ts < "2022-09-11"].reset_index(drop=True)
    df.to_parquet(OUT)
    print(f"{len(df):,} transactions, laundering rate {df.is_laundering.mean():.4%}, saved to {OUT}")


if __name__ == "__main__":
    main()
