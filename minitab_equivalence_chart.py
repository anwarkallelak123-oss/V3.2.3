"""Reusable Minitab-style equivalence plot for Equivalency Report.
Visual approximation of user-supplied 595x402 reference, using available fonts.
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator, FormatStrFormatter

def draw_equivalence_chart(test_label, reference_label, ci_lower, ci_upper,
                           lower_equivalence_limit, upper_equivalence_limit,
                           mean_difference, output_path, x_limits=None):
    if not (ci_lower <= mean_difference <= ci_upper):
        raise ValueError('Mean difference must lie within confidence interval')
    passed = ci_lower > lower_equivalence_limit and ci_upper < upper_equivalence_limit
    fig = plt.figure(figsize=(5.95, 4.02), dpi=100, facecolor='white')
    plt.rcParams['font.family'] = 'DejaVu Sans'
    # Frame matching the screenshot's pale outer border.
    from matplotlib.patches import Rectangle
    fig.add_artist(Rectangle((0.011,0.025),.965,.954,transform=fig.transFigure,
                             fill=False,edgecolor='#d9d9d9',linewidth=.75))
    fig.text(.5,.917, f'Equivalence Test: Mean({test_label}) - Mean({reference_label})',
             ha='center', va='center', fontsize=11, color='#252525')
    fig.text(.5,.871,'(LEL = Lower Equivalence Limit, UEL = Upper Equivalence Limit)',
             ha='center',va='center',fontsize=8.4,color='#4c4c4c')
    ax=fig.add_axes([.099,.185,.788,.598])
    if x_limits is None:
        span=max(upper_equivalence_limit-lower_equivalence_limit, ci_upper-ci_lower)
        lo=min(lower_equivalence_limit,ci_lower,0)-.06*span
        hi=max(upper_equivalence_limit,ci_upper,0)+.06*span
        x_limits=(lo,hi)
    ax.set_xlim(*x_limits)
    ax.set_ylim(0,1)
    ax.set_yticks([0,.5,1])
    ax.tick_params(axis='y',left=False,labelleft=False)
    ax.tick_params(axis='x',labelsize=8,length=0,pad=7)
    ax.grid(color='#e0e0e0',linewidth=.65)
    for s in ax.spines.values():s.set_color('#8c8c8c');s.set_linewidth(.65)
    ax.axvline(0,color='#999999',linewidth=.8,linestyle='--',dashes=(5,3))
    for x,lab in [(lower_equivalence_limit,'LEL'),(upper_equivalence_limit,'UEL')]:
        ax.axvline(x,color='#e12626',linewidth=.8,linestyle='--',dashes=(5,3))
        ax.text(x,1.006,lab,ha='center',va='bottom',color='#c52626',fontsize=8,clip_on=False)
    y=.5
    ax.plot([ci_lower,ci_upper],[y,y],color='#1261df',lw=.8)
    ax.vlines([ci_lower,ci_upper],y-.115,y+.115,color='#1261df',lw=.8)
    ax.scatter([mean_difference],[y],marker='D',s=14,facecolors='none',edgecolors='#1261df',linewidths=.8,zorder=3)
    ax.text(mean_difference+.015*(x_limits[1]-x_limits[0]),y-.045,'90% CI',fontsize=7,color='#242424',va='top')
    fig.text(.055,.105, f'90% CI for Mean({test_label}) - Mean({reference_label}): ({ci_lower:.5f}, {ci_upper:.5f})',
             fontsize=8.3,fontstyle='italic',color='#333333')
    verdict='Can claim equivalence.' if passed else 'Cannot claim equivalence.'
    fig.text(.055,.067, f'CI is {"within" if passed else "not within"} the equivalence interval of ({lower_equivalence_limit:.4f}, {upper_equivalence_limit:.4f}). {verdict}',
             fontsize=8.3,fontstyle='italic',color='#333333')
    fig.savefig(output_path,dpi=300,facecolor='white')
    plt.close(fig)
    return passed

if __name__=='__main__':
    draw_equivalence_chart('TW FATM LL','TW PPF LL',.26465,.36732,-.2861,.2861,.315985,
                           'example_equivalence.png',x_limits=(-.325,.415))
