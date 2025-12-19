# Shorthand Presentation: [Brief Title/Topic]

## 🎯 Purpose/Hypothesis
- [1-2 sentences: What are you testing/showing? E.g., "Exploring stale accrual in lending logic to validate invariant X."]
- Invariant: [What must always hold? E.g., "Debt balances must reflect latest index."]

## 🧰 Setup/Scope
- Environment: [Local sandbox, authorized program, etc. E.g., "Local fork of Protocol Y via Foundry."]
- Explicit Scope: [Boundaries/permission. E.g., "No live targets; repro only."]
- Avoid Harm: [Confirmation. E.g., "No user impact; disclosure intent."]

## 🔍 Key Findings/Derivation
- Root/Trigger: [Core flaw or path. E.g., "Function Z skips accrue() before calc."]
- Numeric PoC: [Simple example. E.g., "Principal=1000, delta=0.05 → effective=1000 (ignores 50)."]
- Artifacts: [Refs to repro/evidence. E.g., "See artifacts/evidence.jsonl line 42."]

## ⚖️ Impact & Next
- Severity/Impact: [Low/Med/High + why. E.g., "Med: Revenue loss via timing."]
- Mitigation Idea: [High-level fix. E.g., "Add accrue() modifier."]
- Feedback Needed: [What do you want? E.g., "Validate PoC? Suggest variants?"]

## 📄 Attachments/Refs
- [Links or snippets: E.g., "repro.sh output attached."]

## 🧭 Risk/Dup Check
- Duplicate Risk: [Low/Med/High + why.]

## ⚡ Quick Matrix Check (Optional Self-Review)
- Class: [E.g., Stale Accrual / Share Inflation / Arithmetic / Config]
- Duplicate Risk: [Low/Med/High + quick note, e.g., "Known pattern but new value flow"]
- Mitigation Cost: [One-line / Reorder / Economic / New Mech]
- Stop? [Yes/No + why if Yes]

## 🛡️ Ethics Checkbox
- [ ] Explicit permission / local-only / authorized scope
- [ ] No user/production impact
- [ ] Disclosure intent confirmed

## 🔗 Quick Repro (One-Liner)
- Command: `./repro.sh --test stale_accrual` (or equivalent)

## 🧪 Variant Exploration
- Related Variants: [E.g., overflow paths, boundary cases, alternative triggers.]

## 📎 Severity Scale Reference
- [Link to public scale, e.g., OWASP or CVSS.]

---

## Usage Example

When presenting to an AI/helper:

# Shorthand Presentation: Stale Interest in Hypothetical Vault

## 🎯 Purpose/Hypothesis
Testing if share conversion allows inflation. Invariant: Deposits must yield fair shares without external skew.

## 🧰 Setup/Scope
Environment: Local ERC-4626 sim. Explicit Scope: Owned sandbox only. Avoid Harm: No prod interaction.

## 🔍 Key Findings/Derivation
Root/Trigger: _convertToShares floors on small totals. Numeric PoC: Donate 1 wei → victim deposit 1000 gets 999 shares.
Artifacts: tests/inflation.t.sol

## ⚖️ Impact & Next
Severity/Impact: High: Drains liquidity providers. Mitigation Idea: Virtual shares min.
Feedback Needed: Run through matrix? Check dup risk?
