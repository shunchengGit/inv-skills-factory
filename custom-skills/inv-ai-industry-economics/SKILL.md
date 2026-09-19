---
name: inv-ai-industry-economics
description: 分析AI产业成本曲线、价值迁移与利润池分布。用于判断AI产业链环节盈利归属时
version: 1.0.0
category: investment
tags: [ai, industry-economics, inference, value-chain, investment]
trigger:
  - AI产业经济
  - 推理成本
  - 价值迁移
  - 利润池
  - AI产业链
---

# AI Industry Economics Analysis

## Purpose

Analyze how changes in model capability, inference efficiency, deployment architecture, and application adoption reshape AI demand, competitive moats, and industry profit pools. Use for questions such as:

- Does cheaper inference reduce or increase total compute demand?
- Does strong local AI hurt cloud providers?
- Where does value migrate when foundation models commoditize?
- Which links in the AI value chain capture revenue versus durable profit?
- How should an industry thesis map into portfolio holdings?

This is an industry-economics framework, not a benchmark-comparison or single-stock valuation framework. For final buy/sell decisions, hand off to the relevant QARP/valuation and portfolio skills.

## Core analytical chain

Never jump directly from “models are cheaper/smaller” to “company X benefits.” Validate the complete chain:

1. **Capability-adjusted cost** — Is the cost falling for the same quality threshold, not merely per token?
2. **Effective task cost** — Include retries, tool calls, human review, error losses, and orchestration overhead.
3. **Demand elasticity** — Does lower cost unlock more users, more tasks per user, persistent agents, or new device categories?
4. **Compute location** — Split cloud, enterprise/private infrastructure, edge server, PC, phone, vehicle, and robot.
5. **Bottleneck migration** — Identify what remains scarce after model capability commoditizes.
6. **Monetization** — Determine who can charge for outcomes, workflow control, distribution, security, or hardware.
7. **Capital returns** — Compare incremental revenue/gross profit with capex, depreciation, power, and operating costs.
8. **Portfolio mapping** — Separate direct, indirect, and narrative-only exposure; check concentration before recommending action.

## Cost definitions

Distinguish four levels explicitly:

- **Per-token cost:** model serving price or direct inference resource cost.
- **Per-run cost:** all tokens, retrieval, tool calls, retries, and routing used in one run.
- **Cost per successful task:** `(inference + systems + review + expected error loss) / successful tasks`.
- **Enterprise TCO:** hardware/API spend plus power, utilization, deployment, updates, security, audit, and staffing.

The economically decisive measure is normally **cost per successful task**, not benchmark score or API list price.

## Demand and Jevons analysis

Use the identity:

`Total compute demand = users/devices × tasks per user × compute per task`

Efficiency reduces compute per task, but may increase the first two factors through broader task coverage, always-on agents, deeper reasoning, retries, multi-model verification, endpoint deployment, and escalation from cheap local models to frontier cloud models.

Present at least three scenarios:

- **Efficiency-dominant:** compute per task falls faster than usage grows.
- **Elastic-demand:** usage growth more than offsets efficiency gains.
- **Hybrid bifurcation:** routine tasks move local while difficult tasks and coordination remain cloud-based.

Do not assume Jevons effects automatically; state the adoption and elasticity evidence needed.

## Value-capture map

Assess each layer on scarcity, substitutability, switching cost, and pricing power:

1. **Foundation models:** frontier capability, serving efficiency, ecosystem, trust.
2. **Cloud/control plane:** hosting, routing, identity, security, observability, sovereign/private deployment.
3. **Semiconductor stack:** foundry, accelerators, memory, packaging, networking, power and cooling.
4. **Data layer:** legal rights, freshness, structure, feedback loops, exclusivity.
5. **Workflow/application layer:** integration depth, permissions, reliability, measurable business outcomes.
6. **Distribution/entry points:** OS, productivity suite, social platform, browser/search, commerce, developer tools, vehicle OS.

Test rather than presume the common thesis: general model capability may commoditize while scarce data, workflow permissions, distribution, and efficient silicon gain relative value.

## Local versus cloud analysis

Avoid the false binary “local replaces cloud.” Evaluate routing by task:

- Local/private: sensitive, frequent, predictable, low-latency, offline.
- Cloud/frontier: difficult, bursty, long-context, high-concurrency, frequently updated, externally connected.
- Human review: high-consequence or low-confidence decisions.

Check memory footprint, KV-cache/context overhead, throughput, power, utilization, and maintenance. A model that fits in memory is not automatically production-viable.

## Evidence hierarchy

Prioritize:

1. Official model cards and reproducible evaluations.
2. Company filings, earnings calls, and official product/adoption disclosures.
3. Independent capability-adjusted inference-cost datasets.
4. Third-party industry research with transparent methodology.
5. Social-media benchmark claims only as hypotheses.

Benchmark proximity on selected tests must never be translated into broad production equivalence without checking long-context behavior, tool use, stability, hallucinations, throughput, and task success rate.

## Investment translation

For each relevant holding or candidate, write:

- **Exposure type:** direct / enabling / indirect / narrative-only.
- **Benefit mechanism:** exact revenue, cost, or moat channel.
- **Countervailing risk:** commoditization, capex burden, price decline, substitution, execution.
- **Financial proof points:** revenue, ARPU, gross margin, utilization, capex/depreciation, FCF, adoption.
- **Trigger:** `if X then thesis strengthens; if Y then thesis weakens; otherwise hold/watch`.
- **Portfolio constraint:** current weight, correlated exposure, industry concentration, and better alternatives.

Do not recommend adding to an already concentrated theme solely because the industry narrative strengthened.

## Embodied AI and component profit capture

For robotics and other AI hardware supply chains, do not translate industry shipments or a BOM TAM directly into a listed supplier's earnings. Build the bridge from accepted deliveries through applicable product mix, component count, outsourcing, supplier share, realized ASP, product-level costs, and attributable ownership. Separate historical deliveries, operating pilots, orders, capacity targets, forecasts, and MOUs. A supplier map may explicitly include sample-only relationships; product launches are not revenue evidence.

Check both independent research authorship and underlying data provenance: translations and successive reports from the same broker are not independent confirmations, and different brokers quoting the same prospectus share a factual source. Distinguish forecast price deflation from observed same-specification transaction prices. Validate financial definitions before accepting automated ratings: static versus TTM PE, consolidated versus attributable profit, minority interests, and recurring versus fair-value-driven earnings.

When filing metadata is available but the body is not verified, say **segment disclosure not verified**, not **segment not disclosed** or **zero revenue**. Never recover chart percentages from broken text order without checking the visual legend. Keep stress-test parameters explicitly hypothetical, preserve gaps, and hand off final stock valuation to the valuation skill. Do not import portfolio weights, ETF replacement mandates, or return targets absent from the current request or retrieved user context. See `references/embodied-ai-component-profit-bridge.md` for the evidence ledger, profit bridge, and verification checklist.

## Research synthesis and production-readiness checks

When combining recent robotics/AI research, organize by original publication date rather than import date. Align geography, form factor, historical/forecast status, annual shipments, installed base, cumulative adoption, and annual hardware revenue before comparing estimates. Recompute derived growth rates with tools; if an older summary conflicts with a verified source, disclose the corrected interpretation without silently rewriting the source library.

Distinguish single-action success from end-to-end task reliability and autonomous failure recovery. Any compounded-success illustration must state independence and no-recovery assumptions and must not be presented as a vendor measurement. Assess cost per successfully completed task including integration, supervision/teleoperation, downtime, maintenance, compute, and depreciation. Separate research/data-collection purchases from recurring demand funded by customer productivity gains.

A knowledge-library-only report may support an industry-stage conclusion without supporting a current-price stock ranking. State the research cutoff, which original pages were verified, which claims remain broker/company reports, and which valuation or operating data are missing. Validate source paths in the delivered artifact and distinguish saved report from completed knowledge-base import. See `references/robotics-research-synthesis.md` for a reusable audit checklist.

## Software incumbents and AI pricing pressure

Separate professional workflow retention from lightweight consumer substitution. Validate paid customers × realized price + usage revenue, not free MAU or generation counts; free-access retail value is not an order or revenue. Reconcile constant-currency/reported and organic/acquisition-inclusive growth before calling sources contradictory. For financial proof, bridge official TTM cash flows, show SBC-adjusted owner-cash proxies, and avoid double-counting buybacks already embedded in EPS growth. Refresh prices and leadership facts before using older research. See `references/software-ai-monetization.md` for evidence reconciliation, cash-flow boundaries and verified filing retrieval; hand final valuation and trade decisions to the valuation/QARP skills.

## Ongoing thesis monitoring

For concentrated holdings in an AI investment cycle, organize monitoring around **core cash generation → incremental AI returns → per-share value**, not product-release or price-news volume. Separate confirmed business deterioration from investment-period cash pressure and portfolio concentration. Use a four-level status scale — green, yellow, red, and **gray for missing data, conflicting definitions, or failed collection**; no new evidence is not evidence of improvement. Freeze independent forecasts before earnings, version quarterly baselines, and never invent undisclosed retention/utilization metrics. Audit existing scheduled tasks before proposing duplicates; distinguish a design, an enabled job, a successful run, and verified delivery. See `references/ai-investment-thesis-monitoring.md` for metrics, evidence contracts, alert logic, and automation acceptance checks.

## Output structure

1. Conclusion first.
2. Causal chain and assumptions.
3. Cost decomposition.
4. Demand elasticity scenarios.
5. Profit-pool/value-capture map.
6. Winners, pressured layers, and ambiguous cases.
7. Failure modes and disconfirming evidence.
8. Portfolio-through analysis when holdings are relevant.
9. A compact monitoring dashboard with measurable triggers.

## Pitfalls

- Comparing parameter counts as if they measured deployed capability.
- Treating per-token price as total economic cost.
- Assuming lower unit cost necessarily lowers total compute demand.
- Equating model usage growth with profit growth.
- Calling all hardware vendors winners without identifying the constrained component.
- Treating data ownership as a moat without rights, quality, freshness, and feedback loops.
- Treating an application entry point as monetization without paid conversion or cost savings.
- Using AI as a new justification to add exposure despite existing portfolio concentration.

## Reference

See `references/inference-cost-and-value-migration.md` for the compact causal model, metrics, and validation checklist derived from prior analysis.
