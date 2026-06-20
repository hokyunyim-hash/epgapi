name: Daily Radio Schedule XML Generator

on:
  schedule:
    - cron: '0 20 * * *'  # UTC 20:00 = KST 05:00
  workflow_dispatch:

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run Script (Fetch via Google AI)
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: python update_schedule.py

      - name: Deploy to Cloudflare Pages
        uses: cloudflare/pages-action@v1
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          projectName: 'radio-schedule'
          directory: 'public'
