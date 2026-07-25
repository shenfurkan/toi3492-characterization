# Security Policy

## Reporting

Do not open a public issue containing credentials, tokens, private paths,
unreleased data, or an exploitable vulnerability. Report privately to the
repository owner using the contact listed in `CITATION.cff` or the current
manuscript metadata.

Include affected file/version, reproduction steps, impact, and any temporary
containment already applied. Do not include active secrets.

## Supported Scope

Security review applies to analysis scripts, network queries, dependencies,
release packages, CI, archive credentials, and externally obtained binaries or
data. Quarantined and diagnostic code is still in scope.

## Mandatory Controls

1. Do not disable TLS certificate verification globally.
2. Do not suppress certificate warnings as a substitute for fixing trust.
3. Do not commit secrets, API keys, cookies, private keys, or credentials.
4. Use least-privilege, short-lived credentials for archive and release tasks.
5. Record and hash external downloads used in scientific inference.
6. Isolate optional or legacy dependencies from the verified core environment.
7. Review dependencies and licenses before release.
8. Scan release archives for secrets, unsafe paths, and unexpected binaries.

## Insecure External Services

If an external service cannot be accessed with valid TLS:

1. Stop the network method.
2. Repair local CA trust or use the provider's supported secure endpoint.
3. If unavailable, obtain the data through a trusted channel and verify its
   digest and provenance offline.
4. Record any exception before use; exceptions are time-limited and cannot
   support release evidence without explicit risk acceptance.

## Incident Handling

1. Contain the affected code, credential, environment, or release object.
2. Preserve logs and hashes.
3. Rotate exposed credentials.
4. Determine whether scientific artifacts or manifests are affected.
5. Create a postmortem and corrective-action record.
6. Re-run verification and rebuild affected release objects.

## Current Known Issue

The quarantined TRICERATOPS method-development path has included TLS-verification
bypass behavior. It must not be used as release evidence and should not be run
over the network until the bypass is removed or secure offline inputs are used.
