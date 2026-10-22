# AgentGuard

**Team:** bug

AgentGuard is a local prototype showing how an AI agent can request sensitive access while people stay in control.

### 1. Vision & originality

AI agents should be able to do useful work without deciding for themselves what they can access. AgentGuard lets an agent request a permission, while separate administrators decide whether to approve it.

### 2. Trust constraint insight

Broad access can expose information an agent does not need; too little access can make it ineffective. AgentGuard separates public and sensitive resources and checks permissions on the server for every read.

### 3. Value & impact

This approach could help teams use AI for confidential work without handing over access decisions. In the prototype, Nova can read a public FAQ. Reading synthetic HR compensation data requires approval from two different administrators.

### 4. Why TideCloak matters

TideCloak is intended to provide the identity and trust layer for this workflow. Tide's licensing issue prevented a live setup, so, following Tide support's guidance, this prototype simulates identity and governance. **TideCloak is not connected.**

### 5. Prototype & storytelling

The demo shows Nova being denied access, requesting a role, and receiving it only after two distinct administrators approve. The server applies the quorum rule and records requests, denials, approvals, and role changes in an audit trail. HR data is synthetic.

## Demo video

The screen recording is included as [`demo.mov`](demo.mov). It is a 65-second source clip; export it as an MP4 before submission if the form requires the specified `.mp4` format.

## Setup

Requirements: Python 3.10 or later. The app uses the Python standard library.

Start the demo from this directory:

```bash
python3 server.py
```

Open http://127.0.0.1:8000.

Run the automated tests in a second terminal:

```bash
python3 -m unittest -v test_demo.py
```

**Limitations:** This local demo has simulated approver identities, no real authentication, and in-memory state. Use synthetic data only; do not deploy it publicly.
