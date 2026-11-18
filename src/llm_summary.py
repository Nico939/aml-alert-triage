"""Turn model alerts into investigator-ready case summaries with an LLM.

For each top-ranked account we build an evidence pack (risk score, the features that drove
the score, and the account's transactions in the test week) and ask the LLM to write a short
case summary. Two guardrails address known LLM limitations:

  - Grounding: the prompt restricts the model to facts in the evidence pack and forbids
    conclusions about guilt; the alert is a reason to investigate, not a finding.
  - Faithfulness check: every number in the generated summary is checked against the evidence
    pack. Numbers that cannot be traced back are flagged as possible hallucinations.

If ANTHROPIC_API_KEY is not set, a rule-based template writes the summary instead, so the
pipeline runs end to end without an API key.

Usage: python src/llm_summary.py [number_of_alerts]
"""
import json
import os
import re
import sys
import pandas as pd

try:                                     # read ANTHROPIC_API_KEY from a local .env file if present
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")
SPLIT = "2022-09-06"

FEATURE_NAMES = {
    "out_n_txn": "outgoing transactions", "in_n_txn": "incoming transactions",
    "out_usd_sum": "total sent (USD)", "in_usd_sum": "total received (USD)",
    "out_usd_max": "largest payment sent (USD)", "in_usd_max": "largest payment received (USD)",
    "out_n_counterparties": "distinct recipients", "in_n_counterparties": "distinct senders",
    "out_n_currencies": "currencies used when sending", "pass_through": "pass-through ratio (0-1)",
    "out_share_ach": "share of outgoing payments via ACH", "in_share_ach": "share of incoming payments via ACH",
    "out_max_txn_per_hour": "most payments sent in one hour", "out_share_cross_currency": "share of outgoing payments with currency conversion",
}

SYSTEM_PROMPT = """You are assisting an anti-money-laundering (AML) investigator at a bank.
You will receive an evidence pack for one account flagged by a machine learning model.
Write a concise case summary in Markdown with these sections:
**Summary** (2-3 sentences), **Red flags** (bullets, link each to a known AML typology where it fits,
e.g. layering, rapid movement of funds, currency conversion), **Points of uncertainty**
(what the evidence cannot tell us), **Suggested next steps** (2-3 bullets).

Rules:
- Use only facts in the evidence pack. Do not invent amounts, dates, names or counterparties.
- Quote numbers exactly as they appear in the evidence pack.
- Do not state or imply that the customer is guilty. The alert is a reason to review, not a finding.
- Keep it under 220 words."""


def evidence_pack(alert, feats, tx):
    acct = alert.account
    f = feats.loc[acct]
    acct_tx = tx[(tx.from_id == acct) | (tx.to_id == acct)].sort_values("ts")
    sample = acct_tx.head(10).assign(
        direction=lambda d: (d.from_id == acct).map({True: "OUT", False: "IN"}),
        counterparty=lambda d: d.to_id.where(d.from_id == acct, d.from_id),
        ts=lambda d: d.ts.dt.strftime("%Y-%m-%d %H:%M"),
        amount=lambda d: d.amt_paid.round(2),
    )[["ts", "direction", "counterparty", "amount", "pay_cur", "recv_cur", "pay_format"]]
    return {
        "account": acct,
        "review_window": f"{SPLIT} to 2022-09-10",
        "model_risk_score": round(float(alert.risk_score), 3),
        "alert_rank": int(alert["rank"]),
        "top_model_drivers": json.loads(alert.top_drivers),
        "account_profile": {name: round(float(f[col]), 2) for col, name in FEATURE_NAMES.items()},
        "transactions": sample.to_dict(orient="records"),
        "transactions_shown": f"{len(sample)} of {len(acct_tx)}",
    }


def summarise_with_llm(pack):
    import anthropic
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=MODEL, max_tokens=600, system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": "Evidence pack:\n```json\n" + json.dumps(pack, indent=2) + "\n```"}],
    )
    return msg.content[0].text


def summarise_with_template(pack):
    p = pack["account_profile"]
    flags = []
    if p["pass-through ratio (0-1)"] >= 0.7:
        flags.append(f"Funds received are largely sent back out (pass-through ratio {p['pass-through ratio (0-1)']}), consistent with layering.")
    if p["currencies used when sending"] >= 2:
        flags.append(f"Outgoing payments are made in {p['currencies used when sending']:.0f} different currencies, which can indicate funds being moved across currencies.")
    if p["share of outgoing payments via ACH"] >= 0.8:
        flags.append(f"Outgoing payments are concentrated in ACH (share {p['share of outgoing payments via ACH']}).")
    if p["distinct recipients"] >= 5:
        flags.append(f"Funds fan out to {p['distinct recipients']:.0f} distinct recipients.")
    flags = flags or ["No single dominant red flag; score is driven by a combination of features."]
    return "\n".join([
        f"**Summary**\nAccount {pack['account']} ranked #{pack['alert_rank']} in the review window "
        f"(risk score {pack['model_risk_score']}). It received {p['total received (USD)']:,} USD and sent "
        f"{p['total sent (USD)']:,} USD across {p['outgoing transactions']:.0f} outgoing transactions.",
        "**Red flags**", *[f"- {x}" for x in flags],
        "**Points of uncertainty**\n- Customer profile, KYC information and the purpose of payments are not available.",
        "**Suggested next steps**\n- Review KYC and expected activity for this account.\n- Trace the counterparties that received the funds.",
    ])


def _numbers(obj):
    """All numbers that appear anywhere in the evidence pack."""
    found = set()
    for v in re.findall(r"-?\d[\d,]*\.?\d*", json.dumps(obj)):
        try:
            found.add(float(v.replace(",", "")))
        except ValueError:
            pass
    return found


def faithfulness_check(text, pack):
    """Flag numbers in the summary that do not match anything in the evidence pack."""
    allowed = _numbers(pack)
    allowed |= {round(a * 100, 1) for a in allowed if 0 <= a <= 1}     # 0.85 may be written as 85%
    unsupported = []
    for raw in re.findall(r"\d[\d,]*\.?\d*", text):
        n = float(raw.replace(",", "").rstrip("."))
        if n in allowed or n < 10 or any(abs(n - a) <= 0.01 * max(abs(a), 1) for a in allowed):
            continue          # small counts (e.g. "2 currencies") and rounding differences are tolerated
        unsupported.append(raw)
    return unsupported


def main():
    n_alerts = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    alerts = pd.read_csv("outputs/alert_queue.csv").head(n_alerts)
    feats = pd.read_csv("outputs/alert_features.csv", index_col=0)
    tx = pd.read_parquet("data/transactions.parquet")
    tx = tx[tx.ts >= SPLIT]
    use_llm = bool(os.environ.get("ANTHROPIC_API_KEY"))
    print(f"Writing {len(alerts)} case summaries with {'LLM: ' + MODEL if use_llm else 'template fallback (no API key)'}")

    out = ["# Case summaries for top alerts\n",
           f"Generated with: {'LLM (' + MODEL + ')' if use_llm else 'template fallback'}. "
           "Ground-truth labels are shown for evaluation only; an investigator would not see them.\n"]
    for _, alert in alerts.iterrows():
        pack = evidence_pack(alert, feats, tx)
        text = summarise_with_llm(pack) if use_llm else summarise_with_template(pack)
        issues = faithfulness_check(text, pack)
        out += [f"## Alert #{alert['rank']}: {alert.account}  (label: {'laundering' if alert.label else 'clean'})\n",
                text, "",
                f"*Faithfulness check: {'all numbers traced to evidence' if not issues else 'UNSUPPORTED numbers: ' + ', '.join(issues)}*\n"]
        json.dump(pack, open(f"outputs/evidence/{alert.account}.json", "w"), indent=2, default=str)
    open("outputs/case_summaries.md", "w").write("\n".join(out))
    print("Saved outputs/case_summaries.md")


if __name__ == "__main__":
    main()
