# The Procurement Desk — Team Aquila (Data Sprint 2.0, Agentic AI Track)

A deterministic, rule-based Python agent that reads 2,000 supplier negotiation threads and outputs one label per thread in the format `ACTION:REASON:COUNTER_PRICE`. There are no runtime LLM calls and no API keys.

## 1. Overview
For every thread, the agent:
1. Isolates the latest supplier message (text after the last `[Latest message` marker). Earlier messages are kept only for `"% off our previous quote"` offers and for the prompt-injection scan.
2. Loads the rules from the playbook files (`categories/`, `amendments/`, and `suppliers/`) by parsing the Markdown files at start-up. Playbook values are parsed dynamically rather than hand-typed.
3. Applies the decision procedure in the playbook's fixed order; the first rule that fires wins:
   1. **Missing information** (no usable price, subscription price with no billing period, or unsupported currency) $\rightarrow$ `ESCALATE:MISSING_INFO:`
   2. **Blacklisted supplier** $\rightarrow$ `REJECT:BLACKLISTED_SUPPLIER:`
   3. **Prompt injection** anywhere in the thread $\rightarrow$ `ESCALATE:PROMPT_INJECTION:`
   4. **Banned contract term** in the latest message $\rightarrow$ `ESCALATE:BANNED_TERM:`
   5. **Price decision**: normalize the offer to $p$, compute $L(r)$, then accept, counter, or reject
   6. **Approval limit check** on acceptable deals $\rightarrow$ `ESCALATE:OVER_APPROVAL_LIMIT:` or `ACCEPT:ACCEPTABLE_PRICE:`
4. Writes `submission.csv` (`thread_id,label`).

- **Actions:** `ACCEPT`, `COUNTER`, `REJECT`, `ESCALATE`
- **Reason codes:** `ACCEPTABLE_PRICE`, `COUNTER_OFFER`, `ABOVE_WALKAWAY`, `OVER_APPROVAL_LIMIT`, `PROMPT_INJECTION`, `BANNED_TERM`, `BLACKLISTED_SUPPLIER`, `MISSING_INFO`

## 2. Mathematics
All arithmetic uses Python's `fractions.Fraction`, avoiding floating-point drift and keeping full precision until the final comparison.

### Price Normalization to $p$ (INR, excl. GST, per Category Normalized Unit)
- **Currency:** $p_{\text{INR}} = \text{amount} \times \text{rate}$. Default FX table: `USD = 84.5`, `EUR = 91`, `GBP = 106`. A supplier contract FX rate replaces the table rate for that supplier and currency.
- **Notation:** `lakh` / `lac` $= 10^5$, `crore` $= 10^7$, `k` $= 10^3$; amounts written in words (`"... rupees"`) are parsed via `words_to_num`.
- **Range (`"between A and B"`):** $p = \max(A, B)$ (never assuming the lower bound).
- **Tiered pricing (`"up to N units ... larger orders"`):** selects the tier matching the thread's `quantity`.
- **List-price discount:** $p = X \times \left(1 - \frac{D}{100}\right)$.
- **Total price (`"in total for all N"`):** $p = X / N$.
- **Previous-quote discount (`"D% off our previous quote"`):** $p = p_{\text{prev}} \times \left(1 - \frac{D}{100}\right)$, where $p_{\text{prev}}$ is the supplier's prior quote normalized in the same way.
- **Free units (`"plus k free for every n you pay for"`):** $p = p \times \frac{n}{n + k}$.
- **Volume discount (`"further D% off for orders of M or more"`):** applied only when `quantity >= M`.
- **GST-inclusive price:** $p = \frac{p}{1 + \text{gst\_rate}}$, using the category's GST rate (`5%`, `12%`, or `18%`).
- **Billing period (subscription categories):** `cloud-servers`, `crm-licenses`, and `design-software` are normalized to per year (`monthly * 12`); `cleaning` and `security-guards` are normalized to per month (`yearly / 12`).
- **Packs & units:** `"per pack of N"` $\rightarrow p / N$; `"per dozen"` $\rightarrow p / 12$; `led-lighting` pack $\rightarrow p / 4$; `printer-paper` ream $\rightarrow p \times 10$ (`1 box = 10 reams`).
- **Corrections (`"should read X, not Y"`):** only `X` is used.

### Values in Force for a Thread
Start from the category parameters, apply every amendment for that category whose effective date is on or before the thread's `date` (sorted chronologically so later amendments replace earlier ones), and apply any supplier contract price cap (replacing the walk-away price for that category).

### Concession Schedule
$$L(r) = \text{target} + (\text{walkaway} - \text{target}) \times \min\!\left(1,\; \frac{r - 1}{R - 1}\right)^{\beta}$$

Round $1$ gives $L(1) = \text{target}$; the final round $r = R$ gives $L(R) = \text{walkaway}$. For a supplier on `PROBATION`, there are no concessions: $L(r) = \text{target}$ in every round.

### Decision & Rounding
- If $p \le L(r)$:
  - $p \times \text{quantity} > \text{approval\_limit} \rightarrow$ `ESCALATE:OVER_APPROVAL_LIMIT:`
  - otherwise $\rightarrow$ `ACCEPT:ACCEPTABLE_PRICE:`
- If $p > L(r)$:
  - $r \ge R \rightarrow$ `REJECT:ABOVE_WALKAWAY:`
  - otherwise $\rightarrow$ `COUNTER` at `round_half_up(L(r))`

**Counter rounding:** $\text{round\_half\_up}(x) = \lfloor x + \tfrac{1}{2} \rfloor$ (nearest whole rupee, `.5` rounding up).

**Worked example:** For `cleaning` (`target = 85,000`, `walkaway = 100,000`, `R = 4`, `beta = 2`) at round $r = 2$:
$$L(2) = 85,000 + 15,000 \times \left(\frac{1}{3}\right)^2 = 86,666.67 \rightarrow \text{rounds to } 86,667$$

## 3. Architecture Diagram
```mermaid
flowchart LR
  P[Playbook markdown files] --> PARSE[Parse categories, amendments, suppliers]
  T[threads.csv] --> ISO[Isolate latest message]
  ISO --> EXT[Extract and normalize price p]
  PARSE --> EXT
  EXT -->|no usable price / unsupported currency / no period| MI[ESCALATE: MISSING_INFO]
  EXT --> BL{Blacklisted?}
  BL -->|yes| RB[REJECT: BLACKLISTED_SUPPLIER]
  BL -->|no| INJ{Prompt injection in thread?}
  INJ -->|yes| EI[ESCALATE: PROMPT_INJECTION]
  INJ -->|no| BAN{Banned term in latest message?}
  BAN -->|yes| EB[ESCALATE: BANNED_TERM]
  BAN -->|no| LR[Compute L of r with amendments, caps, probation]
  LR --> CMP{p <= L?}
  CMP -->|yes| LIM{p x qty > limit?}
  LIM -->|yes| EL[ESCALATE: OVER_APPROVAL_LIMIT]
  LIM -->|no| AC[ACCEPT: ACCEPTABLE_PRICE]
  CMP -->|no| FIN{final round?}
  FIN -->|yes| RW[REJECT: ABOVE_WALKAWAY]
  FIN -->|no| CO[COUNTER at L rounded]
  MI --> OUT[submission.csv]
  RB --> OUT
  EI --> OUT
  EB --> OUT
  EL --> OUT
  AC --> OUT
  RW --> OUT
  CO --> OUT