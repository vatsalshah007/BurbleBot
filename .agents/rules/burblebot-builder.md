---
trigger: always_on
---

Act as project execution engine and blueprint tracker. Wait for explicit user commands before writing code. Never build ahead of current instructions. Only build specifically requested tasks.

Project Context & Architecture Guidelines:
* Building 24/7 continuous web screenshot automation system.
* Target deployment hardware is Raspberry Pi 5 running native ARM64 Linux.
* Implementation mandates strict security-first infrastructure design.
* Configuration must rely exclusively on environment variables. Zero hardcoded sensitive data.
* Architecture must utilize Python, Playwright, and fully modular OOP principles.

Pre-execution command: 
Before executing Task 1, trigger predefined scaffolding skill. Validate project structure strictly aligns with modular OOP architecture and security-first guidelines defined above. Prevent generation of hallucinated files or incorrect project structures.

Project Blueprint:

Task 1: Scaffolding Validation & Browser Initialization
* Execute scaffolding skill. Validate structure against project context.
* Write Python script utilizing Playwright and OOP principles.
* Ingest TARGET_URL securely from environment variables.
* Initialize headless Chromium browser context explicitly for ARM64 deployment.
* Navigate to target URL.
* Implement robust error handling for missing variables and network timeouts.
* Gracefully terminate browser session to prevent memory leaks.