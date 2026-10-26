# Test Cases Suite for PR Summarizer

This directory contains 10 structured benchmark test cases for evaluating the Release Notes Checker and drafting pipeline.

Each case specifies the repository metadata, date boundary window, ground-truth merged PR list (with PR numbers, titles, summaries, URLs, merged timestamps, and `is_breaking` indicators), a candidate release notes markdown draft, and the expected validation outcome (`pass` or `reject`).

## Summary of Test Cases

| File Name | Description / Scenario | PR Count | Expected | Expected Problem |
| :--- | :--- | :---: | :---: | :--- |
| [`case_01_busy_week.json`](file:///c:/Users/nived/Documents/git-PR-summarizer/test_data/cases/case_01_busy_week.json) | High-volume week with 8 PRs (features, fixes, breaking change); draft covers all. | 8 | `pass` | `None` |
| [`case_02_quiet_week.json`](file:///c:/Users/nived/Documents/git-PR-summarizer/test_data/cases/case_02_quiet_week.json) | Minimal activity week with 1 PR; draft covers it. Other sections marked none. | 1 | `pass` | `None` |
| [`case_03_breaking_change.json`](file:///c:/Users/nived/Documents/git-PR-summarizer/test_data/cases/case_03_breaking_change.json) | Includes a breaking change (#133) properly categorized under Breaking Changes. | 3 | `pass` | `None` |
| [`case_04_fixes_only.json`](file:///c:/Users/nived/Documents/git-PR-summarizer/test_data/cases/case_04_fixes_only.json) | Maintenance sprint containing only bug fixes; all covered. | 3 | `pass` | `None` |
| [`case_05_boundary_date.json`](file:///c:/Users/nived/Documents/git-PR-summarizer/test_data/cases/case_05_boundary_date.json) | PR (#152) merged on the final day of the week window is correctly included. | 2 | `pass` | `None` |
| [`case_06_closed_not_merged.json`](file:///c:/Users/nived/Documents/git-PR-summarizer/test_data/cases/case_06_closed_not_merged.json) | Contains unmerged PR (#169) in `closed_not_merged`; draft correctly excludes it. | 2 | `pass` | `None` |
| [`case_07_planted_invented.json`](file:///c:/Users/nived/Documents/git-PR-summarizer/test_data/cases/case_07_planted_invented.json) | Draft includes invented line referencing nonexistent PR [#999]. | 2 | `reject` | `Invented line #999` |
| [`case_08_planted_missed_breaking.json`](file:///c:/Users/nived/Documents/git-PR-summarizer/test_data/cases/case_08_planted_missed_breaking.json) | Draft completely omits breaking change PR #183. | 3 | `reject` | `Missing PR #183` |
| [`case_09_planted_dropped_pr.json`](file:///c:/Users/nived/Documents/git-PR-summarizer/test_data/cases/case_09_planted_dropped_pr.json) | Draft accidentally drops standard feature PR #193. | 3 | `reject` | `Missing PR #193` |
| [`case_10_mixed_week.json`](file:///c:/Users/nived/Documents/git-PR-summarizer/test_data/cases/case_10_mixed_week.json) | Balanced week with features, fixes, and one breaking change; all 5 covered. | 5 | `pass` | `None` |
