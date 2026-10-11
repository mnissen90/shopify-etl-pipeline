# Pushing this project to GitHub

These steps assume you have [Git](https://git-scm.com/downloads) installed
and a GitHub account. Takes about five minutes.

## 1. Create the repo (on github.com)

1. Go to https://github.com/new
2. Repository name: `shopify-etl-pipeline`
3. Description: "Production-style ETL: Shopify orders API → SQL Server, with data quality checks and alerting (Python, pandas, SQL Server)"
4. Public (hiring managers need to see it without a login)
5. Do NOT initialize with a README (we already have one)
6. Click "Create repository"

## 2. Push from your machine

Open a terminal in the unzipped project folder and run:

```bash
git init
git add .
git commit -m "Shopify ETL pipeline: extract, transform, load, validate, alert"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/shopify-etl-pipeline.git
git push -u origin main
```

Replace `YOUR-USERNAME` with your GitHub username.

## 3. Sanity checks before you push

- [ ] No `.env` file in the folder (only `.env.example`)
- [ ] No real API keys, passwords, or server names anywhere
  (`grep -ri "password\s*=" --include="*.py" --include="*.ini" .` should show nothing hardcoded)
- [ ] `clients/` contains only `.gitkeep` and `example.ini.example`
- [ ] `pytest` passes

## 4. Link it on your resume and LinkedIn

- Resume: replace `[GitHub URL]` with `github.com/YOUR-USERNAME/shopify-etl-pipeline`
- LinkedIn: add it under Featured or in your About section with one line:
  "Open-source ETL pipeline (Python/SQL Server): Shopify API ingestion with
  incremental loads, data reconciliation checks, and failure alerting."

## Topics (on the repo's About settings)

Add these topics so recruiters find it: `python` `etl` `data-engineering`
`sql-server` `pandas` `shopify`
