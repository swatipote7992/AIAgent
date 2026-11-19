# Scripts

Commands and templates used for the distributed tracing work. Run the PowerShell commands from the repo root with `az login` done. The log of what was done and why is in [README.md](README.md) (section "Distributed tracing").

## 1. Targeted deploy of the backend

Builds the image with a new tag and updates the running app. The API key stays the same (do not use `deploy.ps1` for small backend changes).

```powershell
$tag = "trace-" + (Get-Date -Format "yyyyMMddHHmmss")
az acr build --registry insurragacr --image "insur-rag-api:$tag" --no-logs backend
if ($LASTEXITCODE -eq 0) {
  az containerapp update --name insur-rag-api --resource-group insu_rag_rg --image "insurragacr.azurecr.io/insur-rag-api:$tag" --query "properties.latestRevisionName" -o tsv
}
```

Then check `/health` and `/ready` on the app's address.

## 2. KQL queries (Application Insights, Monitoring, Logs)

In the portal Logs the table is `dependencies`. In a Log Analytics workspace it is `AppDependencies`. Durations are in milliseconds.

Time per stage (p50, p95, p99):

```kusto
dependencies
| where timestamp > ago(24h)
| where name in ("retrieval", "embedding", "prompt", "llm_generation", "ask_llm")
| summarize n = count(), p50 = percentile(duration, 50), p95 = percentile(duration, 95), p99 = percentile(duration, 99) by name
| order by p95 desc
```

Tokens per question:

```kusto
dependencies
| where name == "llm_generation" and timestamp > ago(24h)
| extend input_tokens = toint(coalesce(tostring(customDimensions["gen_ai.usage.input_tokens"]), tostring(customDimensions["llm.input_tokens"])))
| extend output_tokens = toint(coalesce(tostring(customDimensions["gen_ai.usage.output_tokens"]), tostring(customDimensions["llm.output_tokens"])))
| project timestamp, input_tokens, output_tokens, duration
| order by timestamp desc
```

Finish reason per question (`stop` is a normal end, `length` means the `LLM_MAX_TOKENS` cap cut the reply). Only questions answered after the finish-reason change was released have a value:

```kusto
dependencies
| where name == "llm_generation" and timestamp > ago(24h)
| extend finish_reason = tostring(customDimensions["gen_ai.response.finish_reasons"]), max_tokens = toint(customDimensions["gen_ai.request.max_tokens"]), continuations = toint(customDimensions["llm.continuations"])
| extend output_tokens = toint(coalesce(tostring(customDimensions["gen_ai.usage.output_tokens"]), tostring(customDimensions["llm.output_tokens"])))
| project timestamp, finish_reason, continuations, output_tokens, max_tokens, success, duration
| order by timestamp desc
```

Count by finish reason: replace the last two lines with `| summarize n = count() by finish_reason`. A list such as `["length","stop"]` is an answer that was cut once and then continued (`continuations` = 1). Rows that stay `length` after 3 continuations show `success == false`. Other values you may see: `content_filter` (stopped by the content filter) and `error:<exception class>` (the call failed, for example `error:OpenAIAPIError`); both also show `success == false`.

The same queries from the command line:

```powershell
az monitor app-insights query --app insur-rag-insights --resource-group insu_rag_rg --analytics-query "<query on one line>" --query "tables[0].rows" -o json
```

## 3. p95 alert (ARM template)

Fires when the p95 of the `llm_generation` span is above 5000 ms over 15 minutes, checked every 5 minutes. It has no action group, so it only shows in Azure Monitor, Alerts and sends no message. Save the template as `p95-alert.json`:

```json
{
  "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
  "contentVersion": "1.0.0.0",
  "parameters": {
    "appInsightsId": { "type": "string" },
    "location": { "type": "string" }
  },
  "resources": [
    {
      "type": "Microsoft.Insights/scheduledQueryRules",
      "apiVersion": "2022-06-15",
      "name": "insur-rag-p95-llm",
      "location": "[parameters('location')]",
      "properties": {
        "displayName": "insur-rag-p95-llm",
        "description": "p95 of the llm_generation span is above 5 seconds over the last 15 minutes.",
        "severity": 2,
        "enabled": true,
        "evaluationFrequency": "PT5M",
        "windowSize": "PT15M",
        "scopes": [ "[parameters('appInsightsId')]" ],
        "criteria": {
          "allOf": [
            {
              "query": "dependencies | where name == \"llm_generation\" | summarize p95 = percentile(duration, 95)",
              "timeAggregation": "Maximum",
              "metricMeasureColumn": "p95",
              "operator": "GreaterThan",
              "threshold": 5000,
              "failingPeriods": { "numberOfEvaluationPeriods": 1, "minFailingPeriodsToAlert": 1 }
            }
          ]
        }
      }
    }
  ]
}
```

Deploy it:

```powershell
$aiId = az monitor app-insights component show --app insur-rag-insights --resource-group insu_rag_rg --query id -o tsv
az deployment group create --resource-group insu_rag_rg --name insur-p95-alert --template-file p95-alert.json --parameters appInsightsId=$aiId location=uksouth
```

To change the limit, edit `threshold` (milliseconds) and deploy again; the same name updates the rule. To get a notification, add an action group (Monitor, Alerts, Action groups) and list it in the rule's `actions`.

## 4. Latency workbook (ARM template)

A shared workbook named `insur-rag-latency` with a percentile table, a p95-over-time chart and a tokens table. Save as `latency-workbook.json`:

```json
{
  "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
  "contentVersion": "1.0.0.0",
  "parameters": {
    "appInsightsId": { "type": "string" },
    "location": { "type": "string" }
  },
  "variables": {
    "workbook": {
      "version": "Notebook/1.0",
      "fallbackResourceIds": [ "[parameters('appInsightsId')]" ],
      "items": [
        {
          "type": 1,
          "content": { "json": "## Time per stage of one question\nPercentiles in milliseconds, last 24 hours. With only a few questions the percentiles are not meaningful." },
          "name": "title"
        },
        {
          "type": 3,
          "content": {
            "version": "KqlItem/1.0",
            "query": "dependencies | where timestamp > ago(24h) | where name in (\"retrieval\", \"embedding\", \"prompt\", \"llm_generation\", \"ask_llm\") | summarize n = count(), p50 = percentile(duration, 50), p95 = percentile(duration, 95), p99 = percentile(duration, 99) by name | order by p95 desc",
            "size": 1,
            "queryType": 0,
            "resourceType": "microsoft.insights/components",
            "visualization": "table"
          },
          "name": "percentiles"
        },
        {
          "type": 3,
          "content": {
            "version": "KqlItem/1.0",
            "query": "dependencies | where timestamp > ago(24h) | where name in (\"retrieval\", \"embedding\", \"prompt\", \"llm_generation\") | summarize p95 = percentile(duration, 95) by bin(timestamp, 1h), name | render timechart",
            "size": 0,
            "queryType": 0,
            "resourceType": "microsoft.insights/components",
            "visualization": "timechart"
          },
          "name": "p95-over-time"
        },
        {
          "type": 3,
          "content": {
            "version": "KqlItem/1.0",
            "query": "dependencies | where name == \"llm_generation\" and timestamp > ago(24h) | extend input_tokens = toint(coalesce(tostring(customDimensions[\"gen_ai.usage.input_tokens\"]), tostring(customDimensions[\"llm.input_tokens\"]))), output_tokens = toint(coalesce(tostring(customDimensions[\"gen_ai.usage.output_tokens\"]), tostring(customDimensions[\"llm.output_tokens\"]))) | project timestamp, input_tokens, output_tokens, duration | order by timestamp desc",
            "size": 0,
            "queryType": 0,
            "resourceType": "microsoft.insights/components",
            "visualization": "table"
          },
          "name": "tokens"
        }
      ]
    }
  },
  "resources": [
    {
      "type": "Microsoft.Insights/workbooks",
      "apiVersion": "2022-04-01",
      "name": "[guid('insur-rag-latency')]",
      "location": "[parameters('location')]",
      "kind": "shared",
      "properties": {
        "displayName": "insur-rag-latency",
        "category": "workbook",
        "sourceId": "[parameters('appInsightsId')]",
        "serializedData": "[string(variables('workbook'))]"
      }
    }
  ]
}
```

Deploy it (the name is a fixed GUID, so running it again updates the same workbook):

```powershell
$aiId = az monitor app-insights component show --app insur-rag-insights --resource-group insu_rag_rg --query id -o tsv
az deployment group create --resource-group insu_rag_rg --name insur-latency-workbook --template-file latency-workbook.json --parameters appInsightsId=$aiId location=uksouth
```

Open it in the portal: insur-rag-insights, Workbooks, `insur-rag-latency`.

## 5. Offline check that a failing request leaks no error text

Run from `backend/` with the virtual environment active. It fakes a failure with a marker in the error message, sends a request through the FastAPI app and prints, per span, whether the marker appears. It calls no Azure service. Save as `failcheck.py` (as UTF-8 without a byte-order mark).

```python
from unittest.mock import patch
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

exp = InMemorySpanExporter()
tp = TracerProvider()
tp.add_span_processor(SimpleSpanProcessor(exp))
trace.set_tracer_provider(tp)

from fastapi.testclient import TestClient
import retrieval.insur_llm as m
from api.ragapi import app

MARK = "LEAKMARKER123"
with patch.object(m, "get_cached_retriever", side_effect=RuntimeError("boom " + MARK)):
    r = TestClient(app, raise_server_exceptions=False).post("/api/ask", json={"question": "hello"})
print("http status:", r.status_code)
print("marker in HTTP body:", MARK in r.text)
for s in exp.get_finished_spans():
    dump = str(s.status.description) + str(dict(s.attributes)) + " ".join(str(dict(e.attributes)) + e.name for e in s.events)
    print(f"{s.name:28} status={s.status.status_code.name:6} marker_in_span={MARK in dump}")
```

```powershell
$env:AZURE_OPENAI_ENDPOINT = "https://example.invalid"; $env:AZURE_OPENAI_API_KEY = "x"
$env:AZURE_SEARCH_ENDPOINT = "https://example.invalid"; $env:AZURE_SEARCH_KEY = "x"
python failcheck.py
```

Expected: every span prints `marker_in_span=False`. The HTTP body still repeats the error text (a known gap in `ask()`, not a span).
