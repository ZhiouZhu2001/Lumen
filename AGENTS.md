# Lumen Project Rules

These rules apply to the entire repository. Before starting work, read `CLAUDE.md`, `Lumen_Specifications.md`, and any `AGENTS.md` files applicable to the working directory. Rules in subdirectories supplement this file.

## Working Process

- Implementation, necessary verification, and change documentation are handled as part of each assigned task. Follow requests for teaching or discussion when the user asks for them.
- Use the project specification and decisions already approved by the user as the basis for routine implementation, bug fixes, and documentation maintenance.
- Inspect the working tree before editing. Identify existing user changes, preserve unrelated work, and do not overwrite, revert, or claim it as part of the current round.
- At the end of each round, report the implementation, verification results, unresolved issues, and next steps.

## Repository Language

- English is the primary language for all content prepared for upload, including code identifiers, comments, docstrings, documentation, configuration explanations, update records, commit titles and bodies, and GitHub descriptions.
- Write new project documents and update records in English. Do not introduce Chinese explanatory text into repository files unless the user explicitly requests a language-specific artifact.
- Preserve intentional localization required by the specification, including Spanish interface messages, original bibliographic descriptions, and language-specific queries or fixtures. The English policy does not remove the product's English and Spanish support.
- Before preparing an upload, check changed files and submission text for compliance with this policy.
- Conversation replies may use the user's preferred language.

## Authorship and Upload Attribution

- `ZhiouZhu2001` is the sole author and distributor of this project.
- Do not add Codex, OpenAI, Claude, Anthropic, any other AI tool, or any other person as a project author, co-author, collaborator, contributor, maintainer, or distributor.
- Do not add co-author or assistant credits, tool-generated attribution, or acknowledgements to commit titles or bodies, GitHub descriptions, pull requests, README files, source code, package metadata, update records, or other project documents.
- Do not add `Co-Authored-By` trailers or attribution such as `Generated with ...` or `Assisted by ...`.
- Before committing, verify the Git author and committer identities. Use the user's verified configuration. If the identity is missing or does not match the user, ask for clarification rather than inventing a name or email.
- Before uploading, review pending content and commit metadata for compliance. Do not independently invite or add GitHub collaborators.

## Separate Branches and Confirmed GitHub Uploads

- Before each implementation round, automatically create and switch to a new local Git branch with the `codex/` prefix and a descriptive task name, such as `codex/update-5-search-workflow`. Configuration and project-rule changes follow the same process.
- One branch represents one coherent round. Keep verification and corrections for that round on the same branch. Read-only checks, questions, and planning do not require a new branch.
- Check the current branch, baseline, and working tree before creating the branch. Preserve existing user changes. Review the file scope before committing and include only changes relevant to the round.
- If an earlier round is awaiting confirmation, establish the new round's baseline and dependencies first. Do not silently mix unrelated or unapproved work into the submission.
- After implementation, verification, and the update record are complete, provide the branch name, actual change scope, verification results, known impacts, and a clear commit title and description for review.
- Push to GitHub only after the user explicitly confirms the upload for that round. Confirmation applies only to the reviewed branch and scope. Subsequent substantive changes require renewed upload confirmation.
- The description must explain the problem, resulting behavior, main changes, verification, compatibility, and future impact, and reference the round's `update_version/` record. Include it in the Git commit body when uploading.
- After confirmation, push the round's branch. Creating a pull request, merging into `main`, releasing, and deploying each require the corresponding explicit authorization; branch-upload confirmation does not authorize those actions.
- Approval of a major technical decision and confirmation of a GitHub upload are separate. Approval of one does not approve the other.

## Approval Before Major Changes or Decisions

Prepare a concrete proposal and obtain explicit user approval before implementing:

- System architecture changes or replacement of the primary stack, model provider, or major data source.
- Addition or removal of core product capabilities, changes to MVP scope, or significant departures from the specification.
- Incompatible API, database-schema, or data-format changes, or irreversible data migrations or deletion.
- Changes to core constraints such as real-book validation, privacy protections, or spending limits.
- The first production release, new paid services, recurring costs, or other significant external effects.
- Other decisions that materially affect usage, maintenance cost, compatibility, or future development direction.

Before requesting approval, complete the necessary investigation and prepare the rationale, recommended approach, main alternatives, and impacts. Include a rollback approach when migration or deployment is involved. Wait for an explicit answer; silence is not approval.

Do not request approval again for an already approved decision. Proceed with routine implementation and reversible minor changes within the specification. When uncertain, first check whether existing authorization already covers the action.

## A New Update Record for Each Implementation Round

- After each completed round of code, configuration, or project-rule changes, add a Markdown file under the root `update_version/` directory.
- Name it `Lumen_Update_Version_<N>.md`, for example `Lumen_Update_Version_1.md` or `Lumen_Update_Version_2.md`.
- Start at 1. Before creating a record, inspect existing numeric suffixes and use the highest number plus one. Do not overwrite, reuse, or renumber existing records.
- One record covers one coherent round; do not create a separate record for every changed file. The number identifies an implementation round, not an application release version.
- Read-only reviews, questions, and discussions do not create implementation records. Do not present unapproved or unimplemented proposals as completed work.
- Write records in English and explain the actual implementation in detail. Retain technical names and explain their role in the round.
- Complete the record before the final reply and provide a link to it.

### Required Contents

1. **Basic information:** number, date in Europe/Madrid, branch, known baseline, objective, and actual scope.
2. **Technologies used:** frameworks, libraries, tools, or mechanisms actually involved, what they do, and why they were used. State when no new technology was introduced.
3. **Implementation:** features, processing flow, key logic, and edge cases.
4. **File changes:** added, modified, and deleted files, each file's purpose, and the behavior or rule before and after the change.
5. **Project benefits:** the problem solved and practical effects on correctness, user experience, maintenance, performance, or cost.
6. **Future impact:** relevant effects on APIs, databases, dependencies, deployment, compatibility, and later features. Distinguish actual effects from possible future effects.
7. **Verification:** checks actually performed and their results, plus omitted checks and reasons. Do not describe planned or simulated verification as a successful live-service test.
8. **Approvals and remaining work:** major decisions and their approval status, known limitations, and follow-up work. State when there was no major decision.
9. **GitHub submission:** a clear commit title and description, and the actual upload-confirmation and push status.

Do not include keys, tokens, passwords, or other sensitive information. Correct errors in earlier records through a later record while preserving the original. An explicit user request to translate earlier documents permits updating their language in place, provided historical events and results remain unchanged and the translation is documented in a new record.

## Core Project Constraints

- The AI may choose only from candidates retrieved from real bibliographic APIs. Verify recommended ISBNs in code and use the established foreign-key constraints when persisting results.
- Keep the fixed search flow and the limit of two search-broadening retries required by the specification.
- Perform verification appropriate to the changes and retain verifiable results. Do not hide failures by changing or bypassing checks.
- Follow the authorship, Git, secret-management, and other project conventions in `CLAUDE.md`.
