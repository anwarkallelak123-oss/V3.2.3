"""Equivalency Studio: standardized workbook, auditable equipment comparison workflow."""
from branding import LOGO_PATH, VARIANCE_COLORS
from base64 import b64encode
from PIL import Image
import hashlib, io, json, zipfile, re
from pathlib import Path
import pandas as pd
import numpy as np
import streamlit as st
from engine import pair_layout
from pdf_export import generate
from equivalency_report import equivalency_report, combine_product_reports, variance_report
from study import StudyFields, calculate, comparison_review, exclusion_impact, field_id
from variance import VARIANCE_INTERPRETATION, VARIANCE_METHOD, variance_checks

from heatmap_view import render_heatmap
from interactive_heatmap import render_interactive_heatmap
from layout_visual import render_layout
from diagnostics import (NORMALITY_ALPHA, diagnostics_pdf, normality_detail, normality_diagnostics,
                         overlaid_probability_plot, probability_matrix, probability_plot)

st.set_page_config(page_title='Equivalency Studio · V3.2.3',layout='wide',page_icon='📊')

overlaid_probability_plot = st.cache_data(show_spinner=False, max_entries=64)(overlaid_probability_plot)
probability_plot = st.cache_data(show_spinner=False, max_entries=128)(probability_plot)
probability_matrix = st.cache_data(show_spinner=False, max_entries=8)(probability_matrix)
diagnostics_pdf = st.cache_data(show_spinner=False, max_entries=8)(diagnostics_pdf)
generate = st.cache_data(show_spinner=False, max_entries=8)(generate)
variance_report = st.cache_data(show_spinner=False, max_entries=8)(variance_report)
render_heatmap = st.cache_data(show_spinner=False, max_entries=16)(render_heatmap)
equivalency_report = st.cache_data(show_spinner=False, max_entries=8)(equivalency_report)
combine_product_reports = st.cache_data(show_spinner=False, max_entries=4)(combine_product_reports)
stylesheet = Path(__file__).with_name('studio.css').read_text(encoding='utf-8')
st.markdown(f'<style>{stylesheet}</style>', unsafe_allow_html=True)

with Image.open(LOGO_PATH) as logo:
    logo_bytes = io.BytesIO()
    logo.crop(logo.getbbox()).save(logo_bytes, format='PNG')
logo_src = b64encode(logo_bytes.getvalue()).decode('ascii')

st.html(f"""
<header class="studio-banner">
  <div class="studio-banner-copy">
    <p class="studio-eyebrow">Transfer engineering</p>
    <h1>Equivalency Studio <span class="studio-version">V3.2.3</span></h1>
    <p class="studio-banner-summary">Compare test equipment across sites and prepare equivalency reports.</p>
  </div>
  <div class="studio-banner-brand">
    <img src="data:image/png;base64,{logo_src}" alt="SHL Medical">
  </div>
</header>
""")

def safe_filename(name):
    return re.sub(r'[^A-Za-z0-9._-]+','_',name).strip('._') or 'Project'

def show_table(frame, assessment_colors=None, *, status_column="Assessment"):
    if assessment_colors:
        def color_status(value):
            return assessment_colors.get(value, '')
        html = frame.style.format(escape='html', na_rep='—').hide(axis='index').map(
            color_status, subset=[status_column]).to_html()
        st.markdown('<div class="studio-table">' + html + '</div>', unsafe_allow_html=True)
        return
    html = frame.to_html(index=False, escape=True, border=0, na_rep='—')
    st.markdown('<div class="studio-table">' + html + '</div>', unsafe_allow_html=True)

@st.cache_data(show_spinner=False)
def workbook(raw):
    return pd.read_excel(io.BytesIO(raw),sheet_name=None,engine='openpyxl')

def extract(frame):
    data={}; warnings=[]
    for col in frame.columns:
        name=str(col).strip()
        if not name or name.lower().startswith('unnamed'):continue
        values=pd.to_numeric(frame[col],errors='coerce')
        numeric = values.to_numpy(dtype=float)
        if np.isfinite(numeric).any():
            data[name] = numeric
        elif frame[col].notna().any():
            warnings.append(f'{name}: no usable numeric observations.')

    return data,warnings

with st.container(key='studio_upload'):
    st.markdown('### Study workbooks')
    uploads = st.file_uploader('Upload project workbooks (.xlsx)', type=['xlsx'], accept_multiple_files=True,
                               help='Use one workbook per product and one worksheet per equipment.')
if not uploads:
    st.info('Upload one or more standardized TMT Excel workbooks. Each workbook is treated as a separate product.')
    st.stop()

def generate_on_click(key, signature, label, message, build, *, disabled=False):
    if st.button(label, type='primary', key=f'generate_{key}', disabled=disabled):
        st.session_state.pop(key, None)
        try:
            with st.spinner(message, show_time=True):
                st.session_state[key] = (signature, build())
        except Exception as exc:
            st.error(f'PDF generation failed: {exc}')
    saved = st.session_state.get(key)
    if saved and saved[0] == signature and not disabled:
        return saved[1]
    return None


def product_pdfs(data, *, standalone=False):
    study, results = data['study'], data['results']
    normality = (diagnostics_pdf(data['diagnostic_rows'], data['diagnostic_images'],
                                 data['exclusion_log'], data['name'])
                 if data['diagnostic_rows'] or data['exclusion_log'] else None)
    variance = variance_report(study, data['variance_rows']) if data['variance_rows'] else None
    report = detailed = None
    if data['current']:
        embedded = generate(results, study, embedded=True) if results else None
        report = equivalency_report(study, data['review'], data['impact'], embedded,
                                    normality, variance, heatmap=data['heatmap'])
        if standalone and results:
            detailed = generate(results, study)
    return report, variance, normality, detailed


def batch_pdfs(ready):
    reports = [(label, product_pdfs(data)[0]) for label, data in ready]
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, 'w', zipfile.ZIP_DEFLATED) as archive:
        for label, report in reports:
            archive.writestr(f'{safe_filename(label)}_Equivalency_Report.pdf', report)
    return combine_product_reports(reports), archive_bytes.getvalue()


def render_product(selected_project, project, run_batch):
    raw = project['raw']
    digest = selected_project[:16]
    def download(label, data, *, key=None, **kwargs):
        return st.download_button(label, data, key=key or f'download_{digest}_{field_id(label)}', **kwargs)

    fields = StudyFields(st.session_state, selected_project)
    widget = fields.widget
    project_name = widget(st.text_input, 'Product name', 'project_name', project['name'])

    results_key = f'attachment_results_{digest}'
    errors_key = f'attachment_errors_{digest}'
    signature_key = f'attachment_signature_{digest}'
    heat = None


    def clear_analysis():
        for key in (results_key, errors_key, signature_key, f'heatmap_selection_{digest}',
                    f'heatmap_selection_overview_{digest}'):
            st.session_state.pop(key, None)


    try: sheets=workbook(raw)
    except Exception as exc:
        st.error(f'Cannot read product workbook: {exc}')
        clear_analysis()
        return None

    assign, design, exclusions, match, diagnostics, variance_tab, analysis, export = st.tabs([
        '1 · Equipment & import', '2 · Transfer layout', '3 · Exclude observations',
        '4 · Parameter mapping & EAC', '5 · Normality & probability plots', '6 · Equal variance',
        '7 · Equivalence analysis', '8 · Report export',
    ], key=f'workflow_tabs_{digest}', on_change='rerun')
    records=[];equipment=[];original={}
    with assign:
        st.subheader('Assign each worksheet to equipment and site')
        st.caption('Unassigned or excluded worksheets are not analyzed. Equipment IDs must be unique.')
        for idx,(sheet,frame) in enumerate(sheets.items()):
            data,warnings=extract(frame)
            with st.expander(f'{sheet} · {len(frame)} rows · {len(data)} numerical test items',expanded=idx<4):
                c1,c2,c3=st.columns([1,1.2,1.8])
                sheet_key = field_id(sheet)
                default_site = 'OU' if sheet.upper().startswith('OU') else 'RU' if sheet.upper().startswith('RU') else 'Exclude'
                site = widget(c1.selectbox, 'Site', f'site_{sheet_key}', default_site, options=['OU', 'RU', 'Exclude'])
                types=['Instron','FATM','Zwick','IBM','Other']
                guess=next((kind for kind in ('FATM', 'Instron', 'Zwick') if kind.upper() in sheet.upper()), 'Other')
                typ = widget(c2.selectbox, 'Equipment type', f'type_{sheet_key}', guess, options=types)
                eqid = widget(c3.text_input, 'Equipment ID', f'id_{sheet_key}', sheet)
                st.caption('Detected: '+(', '.join(data) if data else 'none'))
                for warning in warnings:st.warning(warning)
                if site!='Exclude':
                    equipment.append({'id':eqid.strip(),'site':site,'type':typ,'sheet':sheet})
                    original[eqid.strip()]=data
                    records.append({'Worksheet':sheet,'Equipment':eqid.strip(),'Site':site,'Type':typ,'Samples (max)':max(map(len,data.values()),default=0),'Test items':len(data)})
        if records:show_table(pd.DataFrame(records))
    if len(equipment) < 2:
        st.warning('Assign at least two worksheets to equipment.')
        clear_analysis()
        return None
    ids=[e['id'] for e in equipment]
    if any(not x for x in ids) or len(ids)!=len(set(ids)):
        st.error('Equipment IDs must be nonempty and unique.')
        clear_analysis()
        return None

    # Exclusions are scoped to a specific equipment, parameter and Excel row number.
    # Excel header is row 1; observation 1 corresponds to Excel row 2.
    filtered = {}
    exclusion_log = []
    sheet_by_id = {item['id']: item['sheet'] for item in equipment}
    with exclusions:
        st.subheader('Observation review & exclusions')
        st.caption('Select observation numbers to exclude per equipment and measurement. N13 and N15 mean the 13th and 15th captured rows, not the measured values 13 and 15. Excel row = N + 1. All exclusions are documented.')
        for eqid, data in original.items():
            filtered[eqid]={}
            with st.expander(f'{eqid} · {len(data)} test items',expanded=False):
                for parameter, values in data.items():
                    parameter_key = field_id(sheet_by_id[eqid], parameter)
                    positions = [k for k, value in enumerate(values) if np.isfinite(value)]
                    selected = widget(
                        st.multiselect, f'Exclude observations · {parameter}', f'exclude_{parameter_key}', [],
                        options=positions,
                        format_func=lambda k, arr=values: f'N{k+1} (Excel row {k+2}) · {float(arr[k]):.6g}',
                    )
                    clean = values.copy()
                    for k in sorted(selected):
                        reason = widget(st.text_input, f'Rationale for N{k+1} · {parameter}', f'reason_{parameter_key}_{k}', '').strip()
                        exclusion_log.append({
                            'Equipment': eqid, 'Parameter': parameter, 'Observation': f'N{k+1}',
                            'Excel row': k+2, 'Value': float(values[k]), 'Rationale': reason,
                        })
                        clean[k] = np.nan
                    filtered[eqid][parameter]=clean
                    remaining=int(np.isfinite(clean).sum())
                    st.caption(f'{remaining} included / {len(positions)} numeric observations · {len(selected)} excluded')
                    if remaining<2:st.error(f'{eqid} / {parameter}: fewer than 2 observations remain; comparisons cannot run.')
        if exclusion_log:
            if any(not entry['Rationale'] for entry in exclusion_log):
                st.warning('Enter a rationale for each excluded observation before running affected comparisons.')
            show_table(pd.DataFrame(exclusion_log))
            download('Download exclusion audit trail CSV',pd.DataFrame(exclusion_log).to_csv(index=False).encode(),file_name=f'{safe_filename(project_name)}_Exclusions.csv',mime='text/csv')
        else:st.info('No observations excluded.')

    all_names=sorted(set().union(*(set(d) for d in original.values())))
    mapping = {}
    settings = {}
    eac_methods = ['Calculated: 2 × 95% one-sided UCL of reference SD', 'Specification width percentage', 'Manual']
    with match:
        st.subheader('Parameter mapping & EAC')
        st.caption('Map imported headers to canonical parameters, then set an independent EAC for Core and Cross transfers.')
        with st.expander('Map imported parameter names'):
            for name in all_names:
                mapping[name] = widget(st.text_input, f'Canonical name · {name}', f'map_{field_id(name)}', name).strip()
        for name in sorted(set(mapping.values()) - {''}):
            parameter_key = field_id(name)
            with st.container(border=True):
                parameter_col, unit_col, core_col, cross_col = st.columns([1.4, .6, 2, 2])
                with parameter_col:
                    st.caption('Parameter')
                    st.text(name)
                unit = widget(unit_col.text_input, 'Unit', f'unit_{parameter_key}', 'N')
                settings[name] = {'unit': unit}
                for kind, column in (('Core', core_col), ('Cross', cross_col)):
                    with column:
                        eac_key = field_id(name, kind)
                        method = widget(st.selectbox, f'{kind} EAC method', f'method_{eac_key}',
                                        eac_methods[0], options=eac_methods)
                        value = None
                        if method == 'Specification width percentage':
                            lsl = widget(st.number_input, f'{kind} LSL', f'lsl_{eac_key}', 0., format='%.5f')
                            usl = widget(st.number_input, f'{kind} USL', f'usl_{eac_key}', 10., format='%.5f')
                            pct = widget(st.number_input, f'{kind} percent of specification width', f'pct_{eac_key}',
                                         10., format='%.5f', min_value=0.001, max_value=100., step=1.)
                            value = (lsl, usl, pct)
                            if usl > lsl:
                                st.caption(f'Equivalence limits: ±{(usl - lsl) * pct / 100:.5f} {unit}')
                            else:
                                st.warning(f'{kind} USL must be greater than LSL.')
                        elif method == 'Manual':
                            value = widget(st.number_input, f'{kind} absolute EAC', f'manual_{eac_key}',
                                           0., min_value=0., format='%.5f')
                            if value == 0:
                                st.warning(f'Enter a positive {kind} EAC.')
                        settings[name][kind] = (method, value, unit)
        st.caption('Calculated EAC = 2 × s(ref) × √[(n(ref) − 1) / χ²(0.05, n(ref) − 1)]. Assumes independent normal reference observations.')

    normalized={};original_mapped={};collisions=[]
    for eqid,data in filtered.items():
        norm={}
        for source,vals in data.items():
            target=mapping[source]
            if not target:continue
            if target in norm:collisions.append(f'{eqid}: {source} maps to duplicate {target}')
            else:norm[target]=vals
        normalized[eqid]=norm
        original_mapped[eqid] = {mapping[source]: values for source, values in original[eqid].items() if mapping[source]}
    if collisions:
        st.error('Duplicate mapped parameters: ' + ', '.join(collisions))
        clear_analysis()
        return None
    pairs=pair_layout(equipment)
    plan = []
    selection = []
    id_by_sheet = {sheet: equipment_id for equipment_id, sheet in sheet_by_id.items()}
    with design:
        st.subheader('Unique equipment comparisons')
        st.caption('Core: same equipment type. Cross: different types. Within-site comparisons are included. Choose the reference explicitly.')
        st.caption('Included comparisons are numbered consecutively in the order shown.')
        for i, p in enumerate(pairs):
            common = sorted(set(normalized[p['reference']]) & set(normalized[p['test']]))
            missing=sorted(set(normalized[p['reference']])^set(normalized[p['test']]))
            pair_key = field_id(*sorted((sheet_by_id[p['reference']], sheet_by_id[p['test']])))
            include_field = f'enabled_{pair_key}'
            included = fields.value(include_field, True)
            next_et = f'ET{len(selection) + 1}'
            label = next_et if included else 'Excluded'
            with st.expander(
                f'{label} · {p["reference"]} ↔ {p["test"]} · {p["location"]} / {p["kind"]}',
                expanded=i == 0,
                key=f'pair_{digest}_{pair_key}',
            ):
                a, b = st.columns([1, 2])
                enabled = widget(a.checkbox, 'Include', include_field, True)
                ref_sheet = widget(
                    a.selectbox, 'Reference equipment', f'ref_{pair_key}', sheet_by_id[p['reference']],
                    options=[sheet_by_id[p['reference']], sheet_by_id[p['test']]],
                    format_func=lambda sheet: id_by_sheet[sheet],
                )
                reference = id_by_sheet[ref_sheet]
                params = widget(b.multiselect, 'Common parameters', f'params_{pair_key}', common, options=common)
                if missing:
                    st.warning('Not common to both machines: ' + ', '.join(missing))
                comparison = {
                    **p, 'et': next_et if enabled else '—', 'reference': reference,
                    'test': p['test'] if reference == p['reference'] else p['reference'],
                    'parameters': params, 'enabled': enabled,
                }
                plan.append(comparison)
                if enabled:
                    selection.append(comparison)
        st.subheader('Visual transfer layout · interface only')
        st.caption('Instron, FATM, and Zwick use built-in reference photos. Other types use a generic illustration. Upload a photo to override the default for a specific machine. Photos appear in the preview and downloaded layout PNG.')
        photos={}
        cols=st.columns(min(3,len(equipment)))
        for j,e in enumerate(equipment):
            with cols[j%len(cols)]:
                uploaded_photo=st.file_uploader(f"Photo · {e['id']}",type=['png','jpg','jpeg','webp'],key=f"photo_{digest}_{e['sheet']}")
                if uploaded_photo is not None:photos[e['id']]=uploaded_photo.getvalue()
        oulabel,rulabel=st.columns(2)
        ou_name = widget(oulabel.text_input, 'OU label', 'ou_label', 'Origin Unit (OU)')
        ru_name = widget(rulabel.text_input, 'RU label', 'ru_label', 'Receiving Unit (RU)')
        try:
            layout=render_layout(equipment,photos=photos,ou_label=ou_name,ru_label=ru_name,selected=selection)

            st.image(layout,width='stretch')
            download('Download equipment layout PNG',layout,file_name='equipment_layout.png',mime='image/png')
        except Exception as exc:st.warning(f'Layout preview unavailable: {exc}')

    study = widget(export.text_input, 'Study name', 'study_name', project_name)
    unresolved = {
        (entry['Equipment'], mapping[entry['Parameter']])
        for entry in exclusion_log if not entry['Rationale']
    }
    config = {'file': selected_project, 'equipment': equipment, 'settings': settings,
              'mapping': mapping, 'plan': plan, 'exclusions': exclusion_log}
    signature = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    if st.session_state.get(signature_key) != signature:
        clear_analysis()

    variance_results = variance_checks(selection, normalized, unresolved)
    variance_rows = list(variance_results.values())
    with variance_tab:
        st.subheader('Equal variance study · before TOST')
        st.caption(VARIANCE_METHOD + ' ' + VARIANCE_INTERPRETATION)
        st.caption('The check runs automatically for each selected equipment pair and mapped parameter using the included observations.')
        if variance_rows:
            show_table(pd.DataFrame(variance_rows), {
                status: f'background-color:{background};color:{foreground}'
                for status, (background, foreground) in VARIANCE_COLORS.items()
            })
        else:
            st.info('Select at least one equipment pair and parameter in Transfer layout.')

    with analysis:
        st.subheader('Equivalence analysis')
        st.caption('Two-sample TOST with variance-based model selection, 90% confidence interval, α = 0.05. Observation exclusions require a documented rationale.')
        flagged = [row for row in variance_rows if row['Assessment'] == 'Evidence of unequal variances']
        unavailable = [row for row in variance_rows if row['Assessment'] == 'Unavailable']
        if flagged or unavailable:
            st.warning(f'Variance check: {len(flagged)} with evidence of unequal variances, '
                       f'{len(unavailable)} unavailable. Welch TOST is selected for these comparisons.')
        run_product = st.button('Run all selected comparisons', type='primary', key=f'run_{digest}')
        if run_product or run_batch:
            clear_analysis()
            results, errors = [], {}
            for p in selection:
                ref, test = p['reference'], p['test']
                for param in p['parameters']:
                    if any(np.isfinite(normalized[machine][param]).sum() < 2 for machine in (ref, test)):
                        continue
                    if {(ref, param), (test, param)} & unresolved:
                        continue
                    try:
                        result = calculate(normalized[ref][param], normalized[test][param], settings[param][p['kind']],
                                           equal_var=variance_results[p['et'], param]['TOST model'] == 'Pooled')
                    except ValueError as exc:
                        errors[p['et'], param] = str(exc)
                        continue
                    meta = {'reference': ref, 'test': test, 'endpoint': param, 'unit': settings[param]['unit'],
                            'location': p['location'], 'kind': p['kind'], 'et': p['et']}
                    results.append((meta, result))
            st.session_state[results_key] = results
            st.session_state[errors_key] = errors
            st.session_state[signature_key] = signature
        current = st.session_state.get(signature_key) == signature
        results = st.session_state.get(results_key, [])
        review = comparison_review(plan, sorted(settings), normalized, results,
                                   st.session_state.get(errors_key, {}), unresolved, current)
        impact = exclusion_impact(results, original_mapped, settings)
        st.subheader('Comparison completeness')
        st.caption('Scope includes every mapped parameter for every assigned equipment pair. Skipped rows reflect selections made in the transfer layout.')
        review_table = pd.DataFrame(review)
        statuses = ['Pass', 'Fail', 'Skipped', 'Missing data', 'Error', 'Pending']
        status_colors = {
            'Pass': ('green', '#dcfce7', '#14532d'),
            'Fail': ('red', '#fee2e2', '#7f1d1d'),
            'Skipped': ('gray', '#e5e7eb', '#374151'),
            'Missing data': ('orange', '#ffedd5', '#7c2d12'),
            'Error': ('red', '#fee2e2', '#7f1d1d'),
            'Pending': ('blue', '#dbeafe', '#1e3a8a'),
        }
        status_styles = {status: f'background-color:{bg};color:{fg};font-weight:600'
                         for status, (_, bg, fg) in status_colors.items()}
        counts = review_table['Status'].value_counts()
        for column, status in zip(st.columns(len(statuses)), statuses):
            with column.container(border=True):
                st.badge(status, color=status_colors[status][0])
                st.metric(status, int(counts.get(status, 0)), label_visibility='collapsed')
        status_filter = st.multiselect('Filter review by status', statuses, key=f'review_filter_{digest}')
        show_table(review_table[review_table['Status'].isin(status_filter)] if status_filter else review_table,
                   status_styles, status_column='Status')
        download('Download comparison review CSV', review_table.to_csv(index=False).encode(),
                           file_name=f'{safe_filename(project_name)}_Comparison_Review.csv', mime='text/csv')
        if not current:st.info('Run the analysis with the current settings to enable report exports.')
        else:
            if results:
                try:
                    render_interactive_heatmap(results, digest)
                except Exception as exc:
                    st.error(f'Interactive matrix generation failed: {exc}')
                st.subheader('Equivalence results summary')
                rows=[{'ET':m['et'],'Reference':m['reference'],'Test':m['test'],'Parameter':m['endpoint'],'Transfer type':m['kind'],'N ref':r['nr'],'N test':r['nt'],'EAC':r['margin'],'Difference':r['diff'],'CI low':r['ci_low'],'CI high':r['ci_high'],'Result':'Pass' if r['passed'] else 'Fail','EAC method':r['method'],
                       'TOST model':r['tost_model'], 'Variance assessment':variance_results[m['et'], m['endpoint']]['Assessment']} for m,r in results]
                df=pd.DataFrame(rows)
                show_table(df, status_styles, status_column='Result')
                download('Download analysis CSV',df.to_csv(index=False).encode(),file_name=f'{safe_filename(project_name)}_Equivalence_Results.csv',mime='text/csv')
                try:
                    heat=render_heatmap(results, equipment)
                    download('Download heatmap PNG · 300 DPI',heat,file_name=f'{safe_filename(project_name)}_Equivalence_Heatmap.png',mime='image/png')
                except Exception as exc:st.error(f'Heatmap generation failed: {exc}')
            else:st.warning('No comparisons completed. Check selected parameters and input data.')
        if impact:
            st.subheader('Exclusion impact')
            st.caption('Before and after use the same reference direction, EAC method, and TOST model. Calculated EAC is recalculated for each dataset.')
            impact_table = pd.DataFrame(impact)
            show_table(impact_table)
            download('Download exclusion impact CSV', impact_table.to_csv(index=False).encode(),
                               file_name=f'{safe_filename(project_name)}_Exclusion_Impact.csv', mime='text/csv')
    with diagnostics:
        st.subheader('Normality assessment · probability plots')
        st.caption('The label Normally distributed means Shapiro–Wilk p > 0.05 at the chosen threshold. The test did not detect a departure from normality.')
        st.caption('The default view overlays equipment by mapped test parameter. Colors and markers identify the same equipment across plots. The Shapiro–Wilk assessment is calculated separately for each equipment and parameter.')
        view = st.radio('Probability plot view', ['Compare equipment', 'Individual plots and matrix'], horizontal=True, key=f'plot_view_{digest}')
        diagnostic_rows, diagnostic_images = [], []
        for parameter in sorted(settings):
            series = []
            parameter_rows = []
            for machine in equipment:
                eqid, site = machine['id'], machine['site']
                values = normalized[eqid].get(parameter, [])
                series.append((site, eqid, values))
                if parameter in normalized[eqid]:
                    row = {'Equipment': eqid, 'Parameter': parameter, 'Site': site, **normality_diagnostics(values)}
                    parameter_rows.append(row)
                    diagnostic_rows.append(row)

            chart = overlaid_probability_plot(parameter, series, settings[parameter]['unit'])
            diagnostic_images.append(('Equipment comparison', parameter, chart))
            if view == 'Compare equipment':
                st.markdown(f'#### {parameter}')
                st.image(chart, width='stretch')
                download(f'Download overlay · {parameter}', chart,
                                   file_name=f'{safe_filename(project_name)}_{safe_filename(parameter)}_Probability_Overlay.png',
                                   mime='image/png', key=f'overlay_{digest}_{parameter}')
                with st.expander(f'Normality by equipment · {parameter}', expanded=True):
                    for row in parameter_rows:
                        if not np.isfinite(row['p_value']):
                            color = 'gray'
                        else:
                            color = 'red' if row['p_value'] <= NORMALITY_ALPHA else 'green'
                        st.badge(row['status'], color=color)
                        st.caption(f"{row['Site']} · {row['Equipment']} · n={row['n']}. {normality_detail(row)}")

        if view == 'Individual plots and matrix' and settings:
            st.caption('Individual plots show an approximate Anderson–Darling (AD) p-value and 95% pointwise reference bands.')
            st.markdown('#### Probability plot matrix · parameters × equipment')
            matrix = probability_matrix(equipment, sorted(settings), normalized)
            st.image(matrix, width='stretch')
            download('Download complete probability plot matrix PNG', matrix,
                               file_name=f'{safe_filename(project_name)}_Probability_Matrix.png', mime='image/png')
            for machine in equipment:
                eqid = machine['id']
                with st.expander(f"{machine['site']} · {eqid}"):
                    for parameter, values in normalized[eqid].items():
                        chart = probability_plot(values, eqid, parameter)
                        st.image(chart, width='stretch')
                        download(f'Download probability plot · {parameter}', chart,
                                           file_name=safe_filename(eqid + '_' + parameter) + '_probability.png',
                                           mime='image/png', key=f'prob_download_{digest}_{eqid}_{parameter}')

        if diagnostic_rows:
            show_table(pd.DataFrame(diagnostic_rows))
            download('Download normality results CSV',pd.DataFrame(diagnostic_rows).to_csv(index=False).encode(),file_name=f'{safe_filename(project_name)}_Normality.csv',mime='text/csv')

    data = {
        'name': project_name, 'study': study, 'results': results, 'current': current,
        'report_signature': (signature, project_name, study, current),
        'review': review, 'impact': impact, 'heatmap': heat, 'variance_rows': variance_rows,
        'diagnostic_rows': diagnostic_rows, 'diagnostic_images': diagnostic_images,
        'exclusion_log': exclusion_log,
        'open_items': sum(row['Status'] in {'Pending', 'Missing data', 'Error'} for row in review),
    }
    with export:
        st.subheader('Equivalency Report')
        st.caption(f'Product: {project_name}. These downloads cover this product.')
        if not current:
            st.info('Run TOST with the current settings to enable the equivalency report.')
        elif data['open_items']:
            st.warning(f"{data['open_items']} comparison rows are incomplete and will appear as open items.")
        prepared = generate_on_click(
            f'product_pdfs_{digest}', data['report_signature'],
            'Generate Equivalency Report' if current else 'Generate supporting PDFs',
            'Generating PDFs…', lambda: product_pdfs(data, standalone=True),
            disabled=not (current or variance_rows or diagnostic_rows or exclusion_log),
        )
        basename = safe_filename(project_name)
        if variance_rows:
            download('Download equal variance study CSV', pd.DataFrame(variance_rows).to_csv(index=False).encode(),
                     file_name=f'{basename}_Equal_Variance_Study.csv', mime='text/csv')
        if prepared:
            for blob, title, suffix in zip(prepared,
                    ['Equivalency Report', 'equal variance study', 'normality and probability plots', 'detailed TOST'],
                    ['Equivalency_Report', 'Equal_Variance_Study', 'Normality_Study', 'Detailed_TOST']):
                if blob:
                    download(f'Download {title} PDF', blob, file_name=f'{basename}_{suffix}.pdf',
                             mime='application/pdf', on_click='ignore')
    return data


# Use the name as well as the bytes so separate products can share identical data.
projects = {}
for item in uploads:
    content = item.getvalue()
    fingerprint = field_id(item.name, hashlib.sha256(content).hexdigest())
    if fingerprint in projects:
        st.warning(f'{item.name} was uploaded more than once with identical contents.')
        continue
    projects[fingerprint] = {'name': item.name.rsplit('.', 1)[0], 'raw': content, 'filename': item.name}

if len(projects) == 1:
    product_id, product = next(iter(projects.items()))
    render_product(product_id, product, False)
else:
    st.caption(f'{len(projects)} products loaded. Review the settings in each product tab before running the batch.')
    run_batch = st.button('Run comparisons for all products', type='primary', key='run_batch')
    total = len(projects)
    progress = st.progress(0, text=f'0% · Starting batch (0/{total} products processed)') if run_batch else None
    overview, *product_tabs = st.tabs(['Product overview', *[
        f'{index} · {product["name"]}' for index, product in enumerate(projects.values(), start=1)
    ]], key='product_tabs', on_change='rerun')
    summaries = []
    for index, ((product_id, product), tab) in enumerate(zip(projects.items(), product_tabs), start=1):
        if progress is not None:
            percent = 100 * (index - 1) // total
            progress.progress(percent, text=f'{percent}% · Processing {product["name"]} ({index}/{total})')
        with tab:
            summary = render_product(product_id, product, run_batch)
        name = summary['name'] if summary else product['name']
        summaries.append((product_id, f'{index} · {name}', summary))
        if progress is not None:
            percent = 100 * index // total
            progress.progress(percent, text=f'{percent}% · {index}/{total} products processed')

    with overview:
        st.subheader('Product overview')
        ready = [(label, summary) for _, label, summary in summaries if summary and summary['current']]
        status_rows = []
        for _, label, summary in summaries:
            results = summary['results'] if summary else []
            passed = sum(result['passed'] for _, result in results)
            status_rows.append({
                'Product': label, 'Pass': passed, 'Fail': len(results) - passed,
                'Open items': summary['open_items'] if summary else None,
                'Status': ('Check settings' if summary is None else 'Analysis complete' if summary['current'] else 'Run required'),
            })
        show_table(pd.DataFrame(status_rows))
        if len(ready) != len(summaries):
            st.info(f'{len(ready)} of {len(summaries)} products have current comparisons. Only those products can be exported.')
        prepared = generate_on_click(
            'batch_pdfs', tuple((label, data['report_signature']) for label, data in ready),
            'Generate batch Equivalency Report', 'Generating batch PDFs…',
            lambda: batch_pdfs(ready), disabled=not ready,
        )
        if prepared:
            combined, archive = prepared
            st.download_button('Download multi-product Equivalency Report PDF', combined,
                               file_name='Multi_Product_Equivalency_Report.pdf', mime='application/pdf',
                               on_click='ignore')
            st.download_button('Download all analyzed project reports (ZIP)', archive,
                               file_name='Project_Equivalency_Reports.zip', mime='application/zip', on_click='ignore')
        for product_id, label, summary in summaries:
            st.subheader(label)
            if summary and summary['results']:
                render_interactive_heatmap(summary['results'], f'overview_{product_id[:16]}')
            else:
                st.caption('No current equivalence results to display.')

st.caption('ENGINEERING PROTOTYPE · Verify parameter definitions, EAC, statistical assumptions, and report content before controlled use.')
