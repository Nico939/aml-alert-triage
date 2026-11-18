# Case summaries for top alerts

Generated with: LLM (claude-sonnet-5-5). Ground-truth labels are shown for evaluation only; an investigator would not see them.

## Alert #1: 0225215_8098DA930  (label: laundering)

**Summary**
Account 0225215_8098DA930 (risk score 0.996, alert rank 1) received one ACH payment of 16906.1 USD on 2022-09-08. Within about two days, 2 outgoing Yen payments of 352.08 and 16906.11 USD went to one recipient. The pass-through ratio is 0.89.

**Red flags**
- **Rapid movement of funds / pass-through:** the largest payment received (16906.1 USD) almost exactly matches the largest payment sent (16906.11 USD), and the pass-through ratio is 0.89.
- **Currency conversion / layering:** a self-transfer exchanged Canadian Dollar to Yen (22768.72 CAD, 17258.18 USD) at 2022-09-10 15:43, immediately before the outgoing payments. Outgoing payments use 2 currencies.
- **Structuring-like splitting:** two outgoing payments went to 0210261_803B8BFC0 in the same minute (2 sent in one hour).
- **Single-channel pattern:** 1.0 of incoming and outgoing payments are ACH, and the account shows a single sender.

**Points of uncertainty**
- The 5-day window gives no baseline of normal activity.
- The exchanged amount (22768.72 CAD) exceeds the incoming 22304.22 CAD, and the evidence does not show where the difference came from.
- The relationships to the sender (007675_8093BA230) and the recipients are unknown.
- A legitimate business reason, such as an FX or trade payment, cannot be ruled out.

**Suggested next steps**
- Review longer account history and the source of funds for the 22768.72 CAD exchanged.
- Check the counterparties 007675_8093BA230 and 0210261_803B8BFC0 for links or prior alerts.
- Ask the relationship team or customer about the purpose of the Yen payments.

*Faithfulness check: all numbers traced to evidence*

## Alert #2: 00908_80419CF40  (label: laundering)

**Summary**
Account 00908_80419CF40 (risk score 0.996, alert rank 2) received one ACH payment of 15362.86 USD on 2022-09-09 at 00:26. At 16:53 the same day, it converted 17039.5 USD to Yuan and sent two Yuan payments to the same counterparty. The pattern warrants review, but the evidence alone does not show the activity is illicit.

**Red flags**
- **Rapid movement / pass-through:** The 15362.86 USD received was followed within about 16.5 hours by outgoing payments, one of which (102894.28 Yuan) is worth exactly 15362.86 USD. The pass-through ratio is 0.78.
- **Currency conversion:** A USD-to-Yuan self-transfer of 17039.5 immediately preceded the outgoing payments. The account used 2 currencies when sending.
- **Structuring-like splitting:** Two payments (11229.46 and 102894.28 Yuan) went to 018067_80467E970 in the same minute.
- **Layering indicators:** All activity ran via ACH, with a short dwell time and a different outgoing currency from the incoming one.

**Points of uncertainty**
- The pack covers only 2022-09-06 to 2022-09-10, with no prior history or baseline.
- The exchange (17039.5) exceeds the incoming amount, so the source of the difference is unclear (the 2582.51 USD out on 2022-09-07 is the only other flow shown).
- Nothing is known about the purpose or relationships of the counterparties, or the customer's business profile.

**Suggested next steps**
- Review the account's longer history and expected activity profile.
- Examine the sender (0134939_80CE705C0) and recipients (018067_80467E970, 021611_8041A4DD0) for links or other alerts.
- Request supporting documentation for the conversion and payments if concerns persist.

*Faithfulness check: UNSUPPORTED numbers: 16.5*

## Alert #3: 0116904_8064A8D40  (label: laundering)

**Summary**
Account 0116904_8064A8D40 (model risk score 0.996, alert rank 3) had 6 transactions between 2022-09-06 and 2022-09-10. A Ruble-to-USD self-exchange of 19,418.56 USD was followed within the same minute by two USD payments to one recipient. The alert warrants review, not a conclusion.

**Red flags**
- **Currency conversion / rapid movement of funds:** at 2022-09-06 16:14, 1510847.51 Ruble was exchanged to USD, and two outgoing USD payments (3727.36 and 15691.28) were sent at the same time.
- **Possible payment splitting:** both payments went to 001_8004BA030 in the same minute.
- **Outflows exceed inflows:** total sent was 23359.07 USD against 7382.47 USD received.
- **Single-channel, concentrated activity:** all payments were ACH, with 1 distinct sender and 2 distinct recipients.

**Points of uncertainty**
- The source of the 1510847.51 Ruble exchanged is unclear. The only Ruble inflows shown are 528864.89 and 45523.29.
- The pass-through ratio is 0.32, so this is not a clear pass-through pattern.
- There is no information on the customer's expected activity, business type, or relationship to the counterparties.
- USD values use dataset-implied rates, and the sample is only 6 transactions.

**Suggested next steps**
- Trace the funding of the Ruble balance before the 2022-09-06 exchange, and review activity before and after the window.
- Check the relationship and history with 001_8004BA030, 0016678_8064A8A20 and sender 0016792_8064A8610.
- Compare the activity against the customer's KYC profile and expected behaviour.

*Faithfulness check: all numbers traced to evidence*

## Alert #4: 012_8010D4440  (label: laundering)

**Summary**
Account 012_8010D4440 (alert rank 4, model risk score 0.996) was flagged for 2022-09-06 to 2022-09-10. It sent 1063543.49 USD across 12 outgoing payments but received only 34820.08 USD across 4. All payments were ACH, and sending involved 4 currencies. This is a reason to review, not a finding.

**Red flags**
- **Outflow far exceeds inflow:** the largest payment sent was 916645.83 USD, against a largest received of 14777.72 USD. This is a possible sign of funds from an undisclosed source or unusual activity relative to profile.
- **Currency conversion and multi-currency sending:** 4 currencies were used when sending. The shown transactions include USD→Euro and USD→Yuan exchanges, each followed by an outgoing payment in the same minute (12:20 on 2022-09-06; 07:38 on 2022-09-07). This fits currency conversion and rapid movement of funds.
- **Many recipients:** 11 distinct recipients versus 4 senders, which could indicate dispersal of funds.
- **100% ACH:** both incoming and outgoing payments used a single channel, so there is no variety to compare against.

**Points of uncertainty**
- Only 10 of 23 transactions are shown, and the 916645.83 USD payment is not among them.
- The pack gives no customer profile, business purpose or expected activity.
- The pass-through ratio of 0.03 and the "0.0" share of outgoing payments with conversion appear to exclude the 7 self-transfers, so they may understate currency activity.
- The source of funds for the outgoing payments is unclear.

**Suggested next steps**
- Retrieve all 23 transactions, especially the 916645.83 USD payment, and identify its funding source.
- Check the customer's KYC profile and expected activity against this volume.
- Review the recipient counterparties, and the purpose of the currency exchanges.

*Faithfulness check: all numbers traced to evidence*

## Alert #5: 001665_800F24BE0  (label: laundering)

**Summary**
Account 001665_800F24BE0 (alert rank 5, model risk score 0.995) received one ACH payment of 16389.14 USD (13986.49 Euro) on 2022-09-08. Within about two days it sent out three payments totalling 21423.05 USD, including one of 16389.14 USD, the same as the amount received. This warrants review but does not establish wrongdoing.

**Red flags**
- **Rapid movement of funds / pass-through:** The incoming 16389.14 USD is matched by an outgoing payment of 16389.14 USD on 2022-09-10 21:37. The pass-through ratio is 0.77.
- **Currency conversion:** A self-transfer exchanged 17014.34 Euro for US Dollar (19937.12 USD) at 21:37 on 2022-09-10, immediately before two outgoing USD payments. The account sent in 2 currencies.
- **Structuring/splitting pattern (possible):** Two payments (3547.98 USD and 16389.14 USD) went to the same recipient, 021258_8028E8460, in the same minute.
- **Dispersal to multiple recipients:** One sender, 023842_8019C0990, fed 2 distinct recipients.

**Points of uncertainty**
- The 17014.34 Euro exchanged exceeds the 13986.49 Euro received, so the source of the extra funds is not shown.
- The review window is only 5 days, so the account's normal behaviour is unknown.
- The evidence says nothing about the customer's business purpose or relationships with the counterparties.
- All payments were ACH, so this is not itself unusual without a baseline.

**Suggested next steps**
- Trace the source of the Euro balance used in the self-transfer and review earlier account activity.
- Review KYC and expected activity, and any links between 023842_8019C0990, 011_800F27210 and 021258_8028E8460.
- Request the customer's explanation or supporting documents if the review warrants it.

*Faithfulness check: all numbers traced to evidence*
