# Publish Docs

The repository includes a MkDocs Material configuration and a GitHub Actions workflow for GitHub Pages.

## Local preview

Install MkDocs Material:

```bash
pip install mkdocs-material
```

Serve the docs locally:

```bash
mkdocs serve
```

Open:

```text
http://127.0.0.1:8000
```

Build the static site:

```bash
mkdocs build --strict
```

The generated site is written to `site/`.

## GitHub Pages setup

1. Push the repository to GitHub.
2. Open the repository settings.
3. Go to `Pages`.
4. Under `Build and deployment`, set the source to `GitHub Actions`.
5. Push to the default branch.
6. Open the `Deploy Trimmy docs` workflow run.
7. When it finishes, open the Pages URL shown by GitHub.

For this repository, the expected URL is:

```text
https://musantro.github.io/trimmy/
```

## Manual publish alternative

You can also publish from your machine with:

```bash
pip install mkdocs-material
mkdocs gh-deploy --force
```

That command builds the site and pushes it to the `gh-pages` branch.
