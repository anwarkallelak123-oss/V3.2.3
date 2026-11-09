# Equivalency Studio V3.2.3

## Launch on Windows

Install 64-bit Python 3.12. Open Command Prompt in the extracted project directory and run:

```cmd
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements.txt
.venv\Scripts\python.exe -m streamlit run app.py
```

For Streamlit Community Cloud, select **Python 3.12** in the deployment settings and set the entry point to `app.py` in the same directory as `requirements.txt`. The wheel-only local install prevents pip from attempting a source build if a dependency lacks a compatible wheel.

## V3.2.3 release

Included comparisons are numbered consecutively from ET1. Excluding a pair closes the numbering
gap and leaves the pair visible as skipped in the review. Re-run comparisons after changing the
selection to generate results and reports with the new IDs.

## V3.2.2 release

The transfer layout preview and PNG export use the routed map with separate comparison labels, equipment photos, and reference-to-test arrows.

## V3.2.1 release

Select **Generate Equivalency Report** in **Report export** or **Generate batch Equivalency Report**
in **Product overview**. A spinner shows elapsed time during PDF generation. The download buttons
appear when the files are ready.

## V3.2 release

The app has a redesigned banner and uses **Equivalency Report** for product and batch PDF exports.

## V3.1 release

- Selecting a heatmap cell refreshes only that heatmap and its TOST details. This applies to Product overview and the individual product analysis tab. Reopening a recently viewed cell reuses its cached chart.

## V3 release

- Run comparisons without building PDFs. Generate PDFs after running the comparisons.
- Review the transfer layout and equipment photos in tab 2. Each parameter name and its EAC method selector share a row in tab 4.

## Workflow

- **Core and Cross EAC.** In **Parameter mapping & EAC** (tab 4), set the method and limits separately for each canonical parameter and transfer type. Core compares the same equipment type, while Cross compares different equipment types.

- **Multiple products.** Upload one workbook per product in the same upload control. Each workbook opens in a separate product tab with its own equipment, parameter, EAC, and exclusion settings. Review those settings, then select **Run comparisons for all products**. A percentage bar updates as each product is processed. **Product overview** shows each product's result counts and interactive equivalence matrix, and exports a single bookmarked Equivalency Report PDF for products with current reports. Individual reports and a ZIP of reports are also available.

- **Observation exclusions.** In tab 3, choose the equipment and parameter, then select observation numbers. N13 corresponds to Excel row 14 when the header is in row 1. Enter a rationale for each excluded observation. Affected comparisons stay pending until the rationale is supplied. The source workbook is preserved. Export the audit CSV in tab 3 and the before/after impact CSV in tab 7. For reference-based EAC, the impact table recalculates the limit for each dataset.
- **EAC by specification width:** For each parameter choose `Specification width percentage`, then input LSL, USL, and percentage. For a fixed symmetric limit, select `Manual` and enter the positive EAC in the parameter’s units. Equivalence bounds are ±(USL−LSL)×percentage/100. The existing 2× one-sided 95% upper confidence limit of reference SD remains available.
- **Normality diagnostics:** Tab 5 defaults to one overlaid normal probability plot per mapped test parameter, with separate site/equipment series after exclusions. Download each overlay as a PNG. The PDF appendix and combined report use the same overlays, and the Shapiro–Wilk summary remains equipment-specific. Select **Individual plots and matrix** for separate equipment plots and the matrix PNG.
- **Equal variance study.** Tab 6 runs a Brown–Forsythe test (median-centered Levene) at alpha 0.05 for each selected equipment pair and parameter. The app uses pooled TOST when p > 0.05 and Welch TOST when p ≤ 0.05 or the variance check is unavailable. Tab 8 offers separate PDFs for the variance study and normal probability plots, as well as a variance CSV.
- **Completeness and report.** Tab 7 reviews every mapped parameter across all assigned pairs. It distinguishes Pass, Fail, Skipped, Missing data, Error and Pending. Tab 8 exports a Equivalency Report PDF with a review summary, comparison matrix, open items, exclusion impact, equal variance, detailed TOST, normality and the exclusion audit. Incomplete runs are identified in the report. The standalone analysis report and normality appendix remain available, and each product report includes its equivalence heatmap when results are available.

## Statistical notes

A Shapiro–Wilk p-value above 0.05 is reported as **Normally distributed** in green, meaning the test did not detect a departure at alpha 0.05. Evidence of departure appears in red when p ≤ 0.05. Unavailable results appear in gray. The probability plot separately shows an approximate Anderson–Darling p-value. A roughly straight probability plot supports a normal distribution fit. Measurement linearity requires a separate study against reference values. Data exclusions require a documented, justified rationale before use in regulated analysis. Exclusions affect the sample SD and therefore the calculated reference-based EAC. The variance check is diagnostic. The TOST output records which model was selected.

## Probability matrix and layout

Normal probability plots show measurement values on the X axis and probability percent on the Y axis, with a fitted normal line, approximate 95% pointwise bands, AD statistic and approximate p-value. Download a single matrix with parameters as rows and equipment as columns. The layout automatically uses the supplied reference photos for Instron, FATM, and Zwick in both the preview and PNG export. Equipment-specific uploads override the built-in photos. Other types use generic schematics. The layout uses the same comparison IDs and reference direction as the analysis.

Engineering prototype. Formal method verification is required before controlled use.
