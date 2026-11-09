"""Exploratory normality assessment with per-observation exclusions already applied."""
import io
from textwrap import fill
from xml.sax.saxutils import escape
from branding import draw_report_logo
import numpy as np
from scipy import stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors


NORMALITY_ALPHA = 0.05


def normality_diagnostics(values):
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 3:
        note = 'At least 3 observations are required for Shapiro–Wilk.'
    elif np.ptp(x) == 0:
        note = 'All measurements are identical.'
    elif n > 5000:
        note = 'Shapiro–Wilk p-values may be unreliable above 5,000 observations. Review the probability plot.'
    else:
        w, p = stats.shapiro(x)
        if np.isfinite(w) and np.isfinite(p):
            status = 'Evidence of departure from normality' if p <= NORMALITY_ALPHA else 'Normally distributed'
            return dict(n=n, w_stat=float(w), p_value=float(p), status=status, note='')
        note = 'Shapiro–Wilk did not return a finite result.'
    return dict(n=n, w_stat=float('nan'), p_value=float('nan'), status='Assessment unavailable', note=note)


def normality_detail(result):
    p = result['p_value']
    if not np.isfinite(p):
        return result['note']
    display = f'{p:.4g}'
    if float(display) == NORMALITY_ALPHA and p != NORMALITY_ALPHA:
        display = repr(p)
    return f"Shapiro–Wilk p = {display}, α = {NORMALITY_ALPHA:g}."


def normal_probability_positions(n):
    ranks = np.arange(1, n + 1)
    return stats.norm.ppf((ranks - .375) / (n + .25))


def overlaid_probability_plot(parameter, series, unit):
    """Compare one mapped parameter across equipment on a common scale."""
    markers = ('o', 's', '^', 'D', 'v', 'P', 'X', '<', '>', 'h')
    colors_by_equipment = plt.get_cmap('tab10').colors
    columns = min(3, max(1, len(series)))
    legend_rows = (len(series) + columns - 1) // columns
    fig, ax = plt.subplots(figsize=(9.5, 4.8 + .42 * legend_rows), layout='constrained')
    fig.suptitle(f'Normal probability plot | {parameter}', fontsize=14)
    ax.set_xlabel(f'{parameter} ({unit})' if unit else parameter)
    ax.set_ylabel('Cumulative probability (%)')
    ax.grid(True, linewidth=.6, alpha=.35)
    ax.set_axisbelow(True)

    edge = stats.norm.ppf(.99)
    for index, (site, equipment_id, values) in enumerate(series):
        data = np.asarray(values, dtype=float)
        data = np.sort(data[np.isfinite(data)])
        n = len(data)
        color = colors_by_equipment[index % len(colors_by_equipment)]
        marker = markers[(index + index // len(colors_by_equipment)) % len(markers)]
        label = fill(f'{site} · {equipment_id} (n={n})' if n else f'{site} · {equipment_id} (no usable data)', 34)
        if n == 0:
            ax.plot([], [], linestyle='none', marker='x', color='#64748B', label=label)
            continue
        z = normal_probability_positions(n)
        edge = max(edge, abs(z[0]), abs(z[-1]))
        ax.scatter(data, z, label=label, marker=marker, color=color, s=26, alpha=.75, zorder=3)
        if n >= 3 and data[0] != data[-1]:
            z_line = z[[0, -1]]
            ax.plot(data.mean() + data.std(ddof=1) * z_line, z_line, color=color, linewidth=1.15)

    probabilities = [.1, 1, 2, 5, 10, 20, 30, 50, 70, 80, 90, 95, 98, 99, 99.9]
    ticks = [(p, stats.norm.ppf(p / 100)) for p in probabilities]
    ticks = [(p, z) for p, z in ticks if abs(z) <= edge + .07]
    ax.set_yticks([z for _, z in ticks], [f'{p:g}' for p, _ in ticks])
    ax.set_ylim(-edge - .07, edge + .07)
    if not ax.collections:
        ax.text(.5, .5, 'No usable observations', transform=ax.transAxes, ha='center', va='center')
    if series:
        fig.legend(loc='outside lower center', ncols=columns, fontsize=8, frameon=False)
    out = io.BytesIO()
    try:
        fig.savefig(out, format='png', dpi=170, facecolor='white')
    finally:
        plt.close(fig)
    return out.getvalue()


def probability_plot(values,equipment,parameter):
    """Minitab-inspired normal probability paper, with 95% pointwise bands.

    Anderson-Darling is descriptive; its p-value is estimated by the
    documented Stephens approximation, not claimed to be Minitab-identical.
    """
    x=np.asarray(values,dtype=float);x=np.sort(x[np.isfinite(x)])
    n=len(x);fig=plt.figure(figsize=(8.8,5.3),dpi=160,facecolor='white')
    ax=fig.add_axes([.105,.18,.69,.68]);ax.set_facecolor('#FCFCFC')
    fig.text(.45,.955,f'Probability Plot of {parameter}',ha='center',va='top',fontsize=15,color='#303030')
    fig.text(.45,.895,'Normal fit with 95% pointwise reference bands',ha='center',va='top',fontsize=10,color='#555555')
    probs=np.array([.01,.02,.05,.10,.20,.30,.40,.50,.60,.70,.80,.90,.95,.99]);zs=stats.norm.ppf(probs)
    ax.set_yticks(zs);ax.set_yticklabels([f'{p*100:g}' for p in probs]);ax.set_ylim(stats.norm.ppf(.01),stats.norm.ppf(.99))
    ax.set_ylabel('Percent',fontsize=10);ax.set_xlabel(parameter,fontsize=10)
    ax.grid(True,color='#DEDEDE',lw=.6);ax.tick_params(labelsize=8)
    for spine in ax.spines.values():spine.set_color('#9B9B9B')
    if n>=3 and np.ptp(x)>0:
        mean=float(x.mean());sd=float(x.std(ddof=1));i=np.arange(1,n+1)
        # Median-rank plotting positions on a normal probability scale.
        z = normal_probability_positions(n)
        xx=np.linspace(mean-3.3*sd,mean+3.3*sd,350);zline=(xx-mean)/sd
        ax.plot(xx,zline,color='#C52922',lw=.9)
        # 95% pointwise order-statistic envelopes for fitted normal distribution.
        lower=stats.beta.ppf(.025,i,n+1-i);upper=stats.beta.ppf(.975,i,n+1-i)
        # Horizontal (measurement) envelope, plotted at fixed percentile rank.
        xl=mean+sd*stats.norm.ppf(np.clip(lower,1e-8,1-1e-8));xu=mean+sd*stats.norm.ppf(np.clip(upper,1e-8,1-1e-8))
        ax.plot(xl,z,color='#C52922',lw=.75);ax.plot(xu,z,color='#C52922',lw=.75)
        ax.scatter(x,z,s=21,c='#006CB7',edgecolors='#003F7A',linewidths=.45,zorder=4)
        ax.set_xlim(min(x.min(),xl.min(),mean-3*sd)-.15*sd,max(x.max(),xu.max(),mean+3*sd)+.15*sd)
        try:
            ad=stats.anderson(x,dist='norm').statistic
            # Stephens (1974) adjusted AD statistic and approximate p-value.
            aa=ad*(1+.75/n+2.25/n**2)
            if aa<.2:pval=1-np.exp(-13.436+101.14*aa-223.73*aa*aa)
            elif aa<.34:pval=1-np.exp(-8.318+42.796*aa-59.938*aa*aa)
            elif aa<.6:pval=np.exp(.9177-4.279*aa-1.38*aa*aa)
            else:pval=np.exp(1.2937-5.709*aa+.0186*aa*aa)
            pval=float(np.clip(pval,0,1))
        except Exception:ad=float('nan');pval=float('nan')
        stat=f'Mean     {mean:.4g}\nStDev    {sd:.4g}\nN        {n}\nAD       {ad:.3f}\nAD p     {pval:.3f}'
    else:
        ax.text(.5,.5,'Insufficient variable observations',transform=ax.transAxes,ha='center',va='center')
        stat=f'N        {n}\nAD       N/A\nAD p     N/A'
    fig.text(.815,.76,stat,fontsize=9,family='monospace',linespacing=1.7,va='top',color='#292929')
    fig.text(.5,.04,f'{equipment} · Pointwise 95% reference bands; AD p-value approximate',ha='center',fontsize=8,color='#777777')
    out=io.BytesIO();fig.savefig(out,format='png',dpi=180,facecolor='white');plt.close(fig);return out.getvalue()


def probability_matrix(equipment,parameters,normalized):
    """One matrix: rows=parameters, columns=equipment, each cell a probability plot."""
    from PIL import Image,ImageDraw,ImageFont
    eqs=[e['id'] for e in equipment]
    items=sorted(parameters)
    w,h=730,455;gap=12;header=72
    canvas=Image.new('RGB',(w*len(eqs)+gap*(len(eqs)+1),header+(h+gap)*len(items)+gap),'#F1F5F9')
    d=ImageDraw.Draw(canvas)
    for c,eq in enumerate(eqs):
        x=gap+c*(w+gap)
        d.rounded_rectangle((x,12,x+w,header-8),radius=12,fill='#17324F')
        d.text((x+18,23),eq[:70],fill='white')
    for r,param in enumerate(items):
        for c,eq in enumerate(eqs):
            x=gap+c*(w+gap);y=header+r*(h+gap)
            if param in normalized.get(eq,{}):
                blob=probability_plot(normalized[eq][param],eq,param)
                im=Image.open(io.BytesIO(blob)).convert('RGB').resize((w,h),Image.Resampling.LANCZOS)
                canvas.paste(im,(x,y))
            else:
                d.rounded_rectangle((x,y,x+w,y+h),radius=12,fill='white')
                d.text((x+25,y+35),f'{param} — Not captured',fill='#667085')
    out=io.BytesIO();canvas.save(out,format='PNG',dpi=(200,200));return out.getvalue()

def diagnostics_pdf(rows,images,exclusions,study):
    out=io.BytesIO();doc=SimpleDocTemplate(out,pagesize=(595,842),leftMargin=42,rightMargin=42,topMargin=52,bottomMargin=40)
    styles=getSampleStyleSheet();story=[Paragraph('Equivalency Report — Normality & Exclusions Appendix',styles['Title']),Spacer(1,14),Paragraph(escape(study),styles['Heading2']),Spacer(1,10),Paragraph('The normality summary uses Shapiro–Wilk. The label Normally distributed means the test did not detect a departure from normality at alpha = 0.05. The overlaid probability plots compare equipment on a common scale. Each series uses its own observed values and fitted normal line where available.',styles['Normal']),Spacer(1,15)]
    story.append(Paragraph('Exclusion audit trail',styles['Heading2']))
    if exclusions:
        for e in exclusions:story.append(Paragraph(escape(f"{e['Equipment']} / {e['Parameter']} — {e['Observation']} (Excel row {e['Excel row']}), original value {e['Value']:.6g}. Rationale: {e.get('Rationale') or 'Pending'}"),styles['Normal']))
    else:story.append(Paragraph('No observations excluded.',styles['Normal']))
    story.extend([Spacer(1,12),Paragraph('Normality summary',styles['Heading2'])])
    for r in rows:
        story.append(Paragraph(escape(f"{r['Equipment']} / {r['Parameter']} — n={r['n']}. {r['status']}. {normality_detail(r)}"),styles['Normal']))
        story.append(Spacer(1,4))
    for equipment,parameter,blob in images:
        chart = Image(io.BytesIO(blob))
        scale = min(495 / chart.imageWidth, 650 / chart.imageHeight)
        chart.drawWidth = chart.imageWidth * scale
        chart.drawHeight = chart.imageHeight * scale
        story.extend([PageBreak(), Paragraph(escape(f'{equipment} — {parameter}'), styles['Heading2']),
                      Spacer(1, 12), chart])
    doc.build(story, onFirstPage=draw_report_logo, onLaterPages=draw_report_logo);return out.getvalue()
