---
name: reddit-lead-hunter
slug: reddit_lead_hunter
description: Scannt Reddit nach High-Intent-Posts und generiert Reply-Drafts
trigger_keywords: [Reddit, Lead, Leads scannen, Social Listening, Reddit Scan, Reddit Monitoring, Leads finden, Reddit suchen, Community Monitoring]
tools_required: [reddit_scan, reddit_leads, reddit_reply]
category: marketing
priority: 7
enabled: true
agent: ""
---

# Reddit Lead Hunter

## Wann anwenden
Wenn der Benutzer Reddit nach Leads scannen moechte, Social Listening betreiben will, oder nach relevanten Reddit-Diskussionen sucht.

## Ablauf

1. **Scan starten**: Rufe `reddit_scan` auf mit den konfigurierten Subreddits
2. **Ergebnisse praesentieren**: Zeige die gefundenen Leads mit Score, Titel und Subreddit
3. **Bei Nachfrage**: Rufe `reddit_leads` auf um gespeicherte Leads zu listen
4. **Reply posten**: Wenn der User eine Antwort posten will, nutze `reddit_reply` mit der Lead-ID

## Beispiel-Interaktionen

- "Scanne Reddit nach Leads" -> `reddit_scan`
- "Zeig mir die besten Leads" -> `reddit_leads` mit min_score=70
- "Antworte auf den ersten Lead" -> `reddit_reply` mit lead_id und mode=clipboard
- "Scanne r/Python und r/SaaS" -> `reddit_scan` mit subreddits="Python,SaaS"

## Hinweise
- Ergebnisse werden in der Datenbank gespeichert (Duplikate automatisch erkannt)
- Leads koennen auch ueber die Flutter UI verwaltet werden
- Auto-Post (Playwright) nur wenn vom User explizit aktiviert
