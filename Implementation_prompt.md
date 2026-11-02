# General Implementation Instructions — INDUX Prototype

You are implementing a specific part of the INDUX project using the attached Product Requirements Document (PRD) and architectural specifications.

Your primary objective is to build a **functional, visually polished, and testable prototype**. Prioritize getting the system running over production-scale scalability, excessive abstraction, or premature optimization.

Before writing code, inspect the existing repository, directory structure, dependencies, configuration, and relevant specification files. Identify what already exists and what must be implemented. Reuse existing code and finalized decisions wherever possible. Do not overwrite or restructure existing work without a concrete reason. If the repository is empty, initialize only the minimum required structure.

## 1. Strict PRD Scope

- Treat the attached PRD as the primary source of truth for the implementation.
- Implement only the features, components, and functionality explicitly required by the PRD.
- Do not implement features belonging to another part of the project.
- A frontend PRD must not introduce backend code, database schemas, API endpoints, or server-side logic.
- A backend PRD must not introduce frontend components, styling, or UI logic.
- Do not silently modify finalized architectural decisions.
- If a requirement is ambiguous, make the simplest reasonable decision consistent with the existing architecture.
- If a decision materially affects another subsystem, document it and create the necessary handoff file.

## 2. Minimal Architecture

Build the simplest architecture that correctly implements the requirements.

- Keep the directory structure minimal and easy to understand.
- Avoid production-ready directory structures, excessive modularization, and unnecessary abstraction layers.
- Do not introduce microservices, complex design patterns, dependency injection frameworks, or elaborate state management without a demonstrated requirement.
- Keep related code together.
- Avoid creating separate files for trivial functions or components.
- Use existing project dependencies wherever possible.
- Do not introduce new dependencies unless they provide meaningful value.
- Prefer readable, straightforward code over clever or unnecessarily generic implementations.

The goal is a prototype that can be developed, debugged, and modified quickly.

## 3. Functional Implementation

- Implement the actual functionality specified in the PRD.
- Do not replace required functionality with mockups, placeholder buttons, or simulated interactions unless explicitly permitted.
- Use mock data only where the PRD allows it or where an external dependency is unavailable.
- Clearly distinguish mocked functionality from implemented functionality.
- Ensure that the application starts and its primary workflows function correctly.
- Do not leave critical functionality unfinished while spending time on unnecessary refinements.

## 4. Frontend Quality

When implementing frontend functionality:

- Prioritize a visually polished, cohesive, and modern interface.
- Follow the supplied design specifications, layouts, visual references, and interaction requirements.
- Implement the required animations and interactions without introducing unnecessary complexity.
- Ensure the interface is responsive and usable at the required screen sizes.
- Avoid generic-looking UI components when the PRD specifies a distinct visual identity.
- Prioritize visual quality, usability, and functional interactions over excessive component abstraction.

## 5. Basic Logging and Troubleshooting

Implement only lightweight logging and error handling.

- Log important application events and meaningful errors.
- Provide useful error messages that help identify the source of a failure.
- Handle common failure cases gracefully.
- Include basic troubleshooting instructions for running and debugging the application.
- Avoid verbose logs, complex logging infrastructure, monitoring systems, or unnecessary observability tools.

Logging should help a developer understand what went wrong without overwhelming them.

## 6. Cross-Subsystem Contracts

The INDUX project consists of multiple independently implemented subsystems.

If your implementation creates or modifies an interface that another subsystem depends on:

- Create a separate Markdown contract file in the project directory.
- Document the exact interface that the other subsystem must follow.
- Include relevant API endpoints, request and response formats, data structures, event formats, configuration requirements, and assumptions.
- Do not invent functionality that the other subsystem has not implemented.
- Ensure that the contract reflects the actual implementation, not an idealized future architecture.
- Maintain consistency with existing contracts and architectural specifications.

For example, a backend implementation must provide an API contract that the frontend can follow without guessing endpoint names, payload structures, or response formats.

Do not create unnecessary contract files for internal implementation details that have no external dependencies.

## 7. Implementation Explanation

After completing the implementation, create an explanatory Markdown document in the project directory.

The document must explain:

1. The architecture implemented for the specific PRD.
2. The directory structure and the purpose of each important file.
3. The major implementation decisions and their rationale.
4. The trade-offs made to keep the implementation simple.
5. How the main functionality works.
6. Important components, functions, data flows, and interactions.
7. Dependencies and configuration requirements.
8. How to run the application.
9. Basic troubleshooting steps.
10. Known limitations, mocked functionality, and unfinished requirements.

The document must describe the code that actually exists. Do not document planned functionality as implemented functionality.

## 8. Validation

Before declaring the implementation complete:

- Verify that the application starts successfully.
- Test the primary workflows required by the PRD.
- Check for obvious runtime errors.
- Verify that the implementation respects the specified architecture.
- Confirm that no functionality outside the PRD scope was introduced.
- Confirm that all required handoff contracts and explanatory documents have been created.
- Report any requirements that could not be implemented or verified.

Do not claim that something was tested if it was not actually tested.

## 9. Final Deliverables

At the end of the implementation, provide:

- A concise summary of the functionality implemented.
- The final directory structure.
- The important architectural decisions and trade-offs.
- The commands required to run the application.
- The validation and testing results.
- The paths to the explanatory Markdown file and any cross-subsystem contract files.
- Any remaining limitations or unresolved issues.

## Guiding Principle

Build the smallest complete implementation that satisfies the PRD.

Do not optimize for hypothetical future requirements. Do not over-engineer the prototype. Do not sacrifice functionality or visual quality for unnecessary architectural sophistication.

The priority is a working, polished, understandable prototype that can be improved through actual usage and testing.
