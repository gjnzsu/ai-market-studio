# Diagram Design Notes

Use these notes when creating or updating AI Market Studio architecture diagrams.

## User-Readable Architecture Diagrams

- Start from the reader's path, not the code structure: user request, backend orchestration, runtime logic, connector layer, external data sources.
- Keep the main flow as a clean vertical or horizontal path. Avoid unnecessary bends, step-backs, and crossing lines.
- Put equivalent concepts on the same visual layer. For example, FX data, news data, FRED API, and RAG service are all external data sources and should sit on the same row.
- Use fan-out patterns for one-to-many relationships. A connector layer should branch once into a horizontal bus, then split evenly to each data source.
- Keep platform services such as AI Gateway, observability, and runtime config visually separate from the main product/data flow.
- Show playbook runtime primitives as part of the workflow/playbook runtime layer. They are backend definitions for identity, source contracts, output contracts, runtime profiles, and rules; they are not external data providers.
- Keep synthetic specialist data visually separate from external market data sources. It supports workflow/playbook runtime and should not sit on the same row as FX Data, News Data, FRED API, or RAG Service.
- Avoid long edge labels. Prefer short labels or no labels, and place explanatory details in a nearby note box.
- Use large text and fewer nodes so the PNG remains readable when embedded in README.
- If a diagram needs a reading tip, add it explicitly rather than relying on layout alone.

## Sequence Diagrams

- For README-facing diagrams, prefer a user-readable phase flow over a dense technical lifeline diagram.
- Use phases such as Request, Tool Choice, Runtime, Data Collection, and Response.
- Keep arrow labels short. Put payload examples and detailed fields in side notes or bottom summary boxes.
- Highlight user-visible outputs: `tool_used`, `playbook`, `source_grounding`, `synthetic_sources`, `specialist_data`, `carry_metrics`, `data_gaps`, and research-only stance.
- Generate a scaled preview before finishing. If it is not readable at roughly 900-1000px wide, simplify the design.
