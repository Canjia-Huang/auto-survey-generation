# Automated Survey Generator

This repository provides a workflow to automatically synchronize your private knowledge base (e.g., [**Obsidian**](https://obsidian.md/)) with a public repository's `README.md`. 

It is designed to help researchers easily maintain and share curated lists of papers or survey projects.

## :hammer: Setup Instructions

You can refer to this [example repository](https://github.com/Bigger-and-Stronger/direction-field-survey) for reference, or follow these steps:

1. Create your survey repository.
2. Create a `config.json` file in the root directory. Use the [sample file](./config.json) as a template and configure the following variables:
   - `database_repo_papers_dir`: Path to your `.md` files in the database repository.
   - `database_repo_img_dir`: Path to your image files in the database repository.
   - `filter_tag`: The specific tag used to filter which papers to include in the survey.
   - `readme_header`: The introductory text (header) for your survey `README.md`.
3. Add the GitHub Actions workflow: You can either copy the contents of [sync_and_update.yml](./sync_and_update.yml) into a new GitHub Actions workflow file or directly copy the file itself into the `.github/workflows/` directory in your repository (create this directory if it doesn't exist).
4. Configure Repository Secrets: Go to `Settings` -> `Secrets and variables` -> `Actions` -> `Repository secrets` and add:
   - `PRIVATE_REPO_NAME`: The full name of your database repository (e.g., `Username/repo-name`).
   - `PAT_TOKEN`: If your database repository is private, generate a [GitHub Personal Access Token (classic)](https://github.com/settings/tokens) with repository read access and add it here.

Once configured, you can trigger the `sync-and-update` action manually or rely on the scheduled trigger (default: 10:00 AM Beijing Time daily).

## :books: Database Requirements

This script parses Markdown files from your knowledge base. To ensure the survey is generated correctly, please include the following **Frontmatter** metadata in your `.md` files:

- `tags`: Categories/fields the paper belongs to.
- `teaser`: The filename of the teaser image (stored in `database_repo_img_dir`).
- `bibtex`: The BibTeX citation block.
- Optional: `code`, `project`, `slide`, `supplemental` (URLs to related resources).

### Example Markdown File:

```markdown
---
tags:
  - [tag_name_1]
  - [tag_name_2]
  - [tag_name_3]
  - [...]
teaser: [img_name.suffix]
code: [url]
data: [url]
project: [url]
slide: [url]
supplemental: [url]
bibtex: [bibtex]
---

Your content here...
```
