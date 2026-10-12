# n8n workflows

Two ways to plug the prototype into a self-hosted n8n:

| File | Trigger | Use when |
|---|---|---|
| `aecdi_webhook_notify.json` | Webhook `POST /webhook/aecdi-run` | **Recommended.** The watcher runs as a service on the analysis machine and posts a summary after every run: `aecdi watch <inbox> --out <out> --interval 300 --notify-url https://<n8n-host>/webhook/aecdi-run` |
| `aecdi_scheduled_execute_command.json` | Every 15 minutes, Execute Command `aecdi watch ... --once --json` | n8n runs on the same machine and the Execute Command node is enabled. Recent n8n versions disable it by default for security. |

Both workflows: if the run has high-severity findings or failed, e-mail the QC lead with the counts and the paths to the issue log and the marked-up PDF.

**Before use:** set the e-mail addresses, attach SMTP credentials to the *Email QC lead* node, and adjust the paths.

## Tested (12 Oct 2026, n8n 1.123.84, local)

1. Both files imported with `n8n import:workflow`: "Successfully imported 1 workflow" each.
2. The webhook workflow was activated and n8n started. `aecdi watch <inbox> --out <out> --once --notify-url http://localhost:5678/webhook/aecdi-run` analysed the sample project (33 findings, 15 high) and n8n accepted the summary (`"notified": true`).
3. n8n's execution record shows the webhook received `riverside_clinic` with `high: 15`, and *High findings or error?* routed it to *Email QC lead*. That node stopped with a credentials error, as expected for a template without SMTP credentials.

Not tested: the Execute Command variant inside n8n (the node is disabled in the default configuration), and actual e-mail delivery.
