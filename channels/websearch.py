#!/usr/bin/env python3
from ddgs import DDGS

def search_(query, max_results=10):
    with DDGS() as ddgs:
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", "")
            }
            for r in ddgs.text(query, max_results=max_results)
        ]

def search(query, max_results=10):
    try:
        ret = "("
        for r in search_(query):
            ret += "(TITLE: " + r["title"] + " SNIPPET: " + r["snippet"] + ") "
        ret += ")"
        return ret
    except Exception:
        return ""
