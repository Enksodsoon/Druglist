# Cleaner Workflow + Deep Data Plan

## What changed in current UI
- Added a **workflow strip** at top with a simple 5-step path.
- Added expandable "click to reveal" details so advanced context is hidden by default.
- Reduced visual noise in Main and Pediatric builders by collapsing rationale and context into `<details>` blocks.

## Current workflow (recommended)
1. Search and select complaint.
2. Confirm regimen for each selected complaint.
3. Review smart add-ons and include only needed lines.
4. Export in desired mode (OPD / pharmacist / patient / pediatric).
5. Validate before final copy using Validation tab.

## Data-driven simplification strategy
Use the workbook as source-of-truth, but generate two UX tiers:

### Tier 1 (Simple default)
- Only show: drug, dose, duration, dispense.
- Hide: rationale, stock notes, age gates, parse details behind collapsible controls.

### Tier 2 (Deep review)
- Expandable details include:
  - pediatric target status
  - age gate rationale
  - parsed concentration details
  - regimen rationale notes
  - source/version metadata

## Next integration passes
- Import additional workbook sheets into feature toggles:
  - `Price_Estimates_Online` for richer compare tab
  - `Clinic_Defaults` + `Top_50_Defaults` for guided quick picks
  - category option sheets for contextual suggestions
- Add user mode switch:
  - Basic mode (minimal fields)
  - Advanced mode (full details visible by default)

