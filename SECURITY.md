# Security policy

## Reporting a vulnerability

Report suspected vulnerabilities privately to the designated Fratres-X-AI
repository maintainers through the organization's approved private security
channel. Do not open a public issue or disclose exploit details, proprietary
source, credentials, mission data, or affected artifacts publicly.

Include, when authorized:

- the affected revision and environment;
- a concise description and potential impact;
- minimal reproduction steps or a proof of concept;
- whether secrets, data, package integrity, or unsafe outputs are involved; and
- any known mitigation.

Maintainers will acknowledge, triage, and coordinate remediation according to
internal priority and disclosure procedures. No public response-time or
remediation-time guarantee is made.

## Supported code

Security fixes target the current maintained source and package release.
Historical revisions, experimental modules, and the paused console may require
an upgrade or removal rather than a backport.

## Security boundary

Charybdis processes numerical sensor and map inputs but does not provide a
deployment security architecture. Integrators remain responsible for input
authentication, file and model provenance, dependency integrity, least
privilege, network isolation, secret management, update signing, audit logging,
and independent safety controls.

Treat external maps, NumPy archives, model files, logs, and sensor streams as
untrusted until validated. Do not load untrusted serialized model or data
formats in a privileged environment.

## Safety notice

This repository is proprietary research and simulation software. It is not
certified vehicle software and must not be relied on as the sole navigation,
control, collision-avoidance, or emergency system. A navigation-health flag or
zero-velocity guidance command is not a complete safety mechanism.
