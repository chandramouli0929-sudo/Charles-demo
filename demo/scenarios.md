# Demo Scenarios

Six pre-built natural-language inputs for demonstrating AgentForge capabilities.

## DEMO 1 — Greenfield
**Input:**
```
Build a scalable URL shortener with APIs, persistence and analytics.
```
**Expected:** System classifies as GREENFIELD. Designs architecture. Plans 6-8 tasks. Asks for approval. Generates FastAPI app. Runs tests. Shows outcome.

---

## DEMO 2 — Brownfield Enhancement
**Input:**
```
Add rate limiting to the URL creation endpoint so that a single IP cannot create more than 10 short URLs per minute.
```
**Expected:** System classifies as BROWNFIELD. Inspects repository. Identifies API route and middleware. Shows impacted files. Asks for approval. Modifies code. Shows git diff.

---

## DEMO 3 — Bug Fix
**Input:**
```
Sometimes the same URL gets a different short code after restarting the application. Fix it.
```
**Expected:** System classifies as BUG FIX. Locates short-code generation. Identifies root cause (non-deterministic random). Proposes deterministic SHA-256 hash approach. Asks for approval. Implements fix. Adds regression test.

---

## DEMO 4 — Refactoring
**Input:**
```
Refactor the URL service because it is becoming difficult to maintain. The service file has grown too large.
```
**Expected:** System classifies as REFACTOR. Inspects code. Establishes test baseline. Proposes safe refactoring (extract analytics service, separate concerns). Asks for approval. Implements. Validates behavior unchanged.

---

## DEMO 5 — Ambiguous Requirement
**Input:**
```
Make the URL shortener scalable.
```
**Expected:** System detects AMBIGUITY. Asks: "Which aspect needs to scale: redirect/read traffic, URL creation, analytics volume, or overall system?" User answers. System proceeds with clear plan.

---

## DEMO 6 — Out of Scope
**Input:**
```
Build me a payroll management system with employee records and salary processing.
```
**Expected:** System detects OUT_OF_SCOPE. Responds: "This demo is scoped around URL shortener engineering. Are you referring to a URL shortener requirement?" Does NOT start coding.
