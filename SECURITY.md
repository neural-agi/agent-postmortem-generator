# Security Policy

## Supported Versions

Agent Postmortem Generator is under active development.

At this stage, only the latest version on the `main` branch is considered supported and receives security fixes.

| Version | Supported |
|----------|-----------|
| Latest (`main`) | ✅ |
| Older commits/releases | ❌ |

---

## Reporting a Vulnerability

If you believe you have found a security vulnerability, **please do not open a public GitHub issue**.

Instead, report it privately by contacting the maintainer.

Include as much information as possible:

- Description of the vulnerability
- Steps to reproduce
- Expected behavior
- Actual behavior
- A minimal proof of concept (if available)
- Environment details (OS, Python version, package versions)

We will acknowledge reports as soon as reasonably possible.

---

## Response Process

Our general process is:

1. Acknowledge receipt of the report.
2. Reproduce and verify the issue.
3. Develop and test a fix.
4. Release the fix.
5. Publicly disclose the issue after a patch is available when appropriate.

We appreciate responsible disclosure and ask that vulnerabilities remain private until a fix has been released.

---

## Scope

Security reports are welcome for issues affecting the project itself, including:

- Code execution vulnerabilities
- Dependency-related vulnerabilities
- Unsafe file handling
- Path traversal
- Denial of service
- Serialization or deserialization issues
- Supply chain concerns
- CLI security issues
- Unsafe parsing behavior

Reports outside the scope of this repository (such as vulnerabilities in third-party frameworks) should be reported to the appropriate upstream maintainers.

---

## Best Practices

Although this project analyzes AI agent traces, it should **not** be used as a security boundary.

Always:

- Validate untrusted input.
- Keep dependencies up to date.
- Review generated reports before acting on them.
- Run the tool with the minimum required privileges.

---

## Thank You

We appreciate everyone who takes the time to responsibly report security issues and help improve the safety and reliability of the project.
