"""Native Streamlit interactive heatmap; one clickable control per analyzed cell."""
import io
import streamlit as st
from minitab_equivalence_chart import draw_equivalence_chart


@st.cache_data(show_spinner=False, max_entries=64)
def equivalence_chart_png(test, reference, ci_low, ci_high, margin, difference):
    out = io.BytesIO()
    draw_equivalence_chart(test, reference, ci_low, ci_high, -margin, margin, difference, out)
    return out.getvalue()


@st.fragment
def render_interactive_heatmap(results, project_key):
    if not results:
        return
    pairs = list(dict.fromkeys(m['et'] for m, _ in results))
    endpoints = sorted({m['endpoint'] for m, _ in results})
    lookup = {(m['et'], m['endpoint']): (m, r) for m, r in results}
    st.markdown('#### Interactive equivalence matrix')
    st.caption('Select a PASS or FAIL cell to inspect its TOST details. Click the selected cell again to hide them.')
    header = st.columns([2.2] + [1] * len(pairs))
    header[0].markdown('**Measurement**')
    for j, et in enumerate(pairs):
        first = next(m for m, _ in results if m['et'] == et)
        header[j + 1].markdown(f"**{et}**")
        header[j + 1].caption(f"{first['reference']} → {first['test']}")
    selected_key = f'heatmap_selection_{project_key}'
    st.session_state.setdefault(selected_key, None)
    selected = st.session_state[selected_key]
    if selected is not None and selected not in lookup:
        selected = st.session_state[selected_key] = None

    def toggle_selection(cell):
        st.session_state[selected_key] = None if st.session_state[selected_key] == cell else cell

    cell_styles = []
    for i, endpoint in enumerate(endpoints):
        cols = st.columns([2.2] + [1] * len(pairs))
        cols[0].markdown(f'**{endpoint}**')
        for j, et in enumerate(pairs):
            entry = lookup.get((et, endpoint))
            if entry is None:
                cols[j + 1].button('— N/A', key=f'na_{project_key}_{i}_{j}', disabled=True, width='stretch')
                continue
            _, r = entry
            chosen = selected == (et, endpoint)
            label = ('✓ PASS' if r['passed'] else '✕ FAIL') + (' · Selected' if chosen else '')
            # Scope styling to the individual Streamlit button key, never to all buttons.
            # Colors are based on the actual statistical outcome, not on the label.
            key = f'cell_{project_key}_{i}_{j}'
            if r['passed']:
                bg, border, hover = ('#14532d', '#22c55e', '#166534') if chosen else ('#dcfce7', '#86efac', '#bbf7d0')
                fg = '#ffffff' if chosen else '#14532d'
            else:
                bg, border, hover = ('#7f1d1d', '#f87171', '#991b1b') if chosen else ('#fee2e2', '#fca5a5', '#fecaca')
                fg = '#ffffff' if chosen else '#991b1b'
            cell_styles.append(f'''
            .st-key-{key} button {{background: {bg} !important; color: {fg} !important;
              border: 2px solid {border} !important; border-radius: 10px !important;
              font-weight: 750 !important; min-height: 45px !important;
              box-shadow: {'0 0 0 2px ' + border + '55' if chosen else 'none'} !important;}}
            .st-key-{key} button:hover {{background: {hover} !important; color: {fg} !important;
              border-color: {border} !important;}}
            .st-key-{key} button:focus-visible {{outline: 3px solid {border} !important;
              outline-offset: 2px !important;}}
            ''')
            cols[j + 1].button(label, key=key, type='secondary', width='stretch',
                               on_click=toggle_selection, args=((et, endpoint),))
    st.markdown('<style>' + '\n'.join(cell_styles) + '</style>', unsafe_allow_html=True)
    if selected is None:
        return
    meta, result = lookup[selected]
    st.divider()
    st.markdown(f"#### {meta['et']} · {meta['endpoint']}")
    st.caption(f"Mean({meta['test']}) − Mean({meta['reference']}) · {meta['kind']} · {meta['location']}")
    chart_bytes = equivalence_chart_png(
        meta['test'], meta['reference'], result['ci_low'], result['ci_high'],
        result['margin'], result['diff'],
    )
    st.image(chart_bytes, width='stretch')
    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Result', 'PASS' if result['passed'] else 'FAIL')
    c2.metric('Mean difference', f"{result['diff']:.5f} {meta['unit']}")
    c3.metric('EAC', f"±{result['margin']:.5f} {meta['unit']}")
    c4.metric('90% CI', f"[{result['ci_low']:.4f}, {result['ci_high']:.4f}]")
    st.caption(f"Reference n={result['nr']}, test n={result['nt']} · TOST model: {result['tost_model']} · EAC method: {result['method']} · TOST p(lower)={result['p1']:.5g}, p(upper)={result['p2']:.5g}")
    st.download_button('Download selected equivalence chart (PNG · 300 DPI)', chart_bytes,
                       file_name=f"{meta['et']}_{meta['endpoint'].replace(' ', '_')}_equivalence.png", mime='image/png',
                       key=f'chart_download_{project_key}', on_click='ignore')
