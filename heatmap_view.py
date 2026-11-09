"""Modern, high-resolution matrix; N/A is never misrepresented as Pass."""
import io
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

def render_heatmap(results,equipment,title='Equivalence overview'):
    pairs=[]
    for m,r in results:
        key=m['et']
        if key not in [p[0] for p in pairs]:pairs.append((key,m['reference'],m['test'],m['kind']))
    endpoints=sorted({m['endpoint'] for m,r in results})
    if not pairs or not endpoints:raise ValueError('No results to display')
    lookup={(m['et'],m['endpoint']):r['passed'] for m,r in results}
    n=len(pairs);k=len(endpoints);fig,ax=plt.subplots(figsize=(max(8,2.6+n*1.5),max(4,2.7+k*.7)),dpi=300)
    fig.patch.set_facecolor('#F7F9FC');ax.set_facecolor('#F7F9FC');ax.set_xlim(-2.5,n+.1);ax.set_ylim(-1.65,k+.45);ax.invert_yaxis();ax.axis('off')
    ax.text(-2.35,-1.33,title,fontsize=18,fontweight='bold',color='#172B45')
    ax.text(-2.35,-.82,'90% CI entirely inside ±EAC = PASS',fontsize=10,color='#64748B')
    for j,(et,ref,test,kind) in enumerate(pairs):
        ax.text(j+.5,-.48,et,ha='center',fontsize=12,fontweight='bold',color='#172B45')
        ax.text(j+.5,-.16,f'{ref} → {test}',ha='center',fontsize=8,color='#64748B')
    for i,ep in enumerate(endpoints):
        ax.text(-2.34,i+.45,ep,va='center',fontsize=10,fontweight='bold',color='#243B53')
        for j,(et,*_) in enumerate(pairs):
            status=lookup.get((et,ep));face='#D9E2EC' if status is None else '#D8F4E5' if status else '#FCE0E1';ink='#526477' if status is None else '#087443' if status else '#B42331'
            patch=FancyBboxPatch((j+.04,i+.08),.92,.74,boxstyle='round,pad=0.015,rounding_size=0.09',linewidth=0,facecolor=face)
            ax.add_patch(patch);ax.text(j+.5,i+.45,'—' if status is None else '✓ PASS' if status else '✕ FAIL',ha='center',va='center',fontsize=10,fontweight='bold',color=ink)
    fig.subplots_adjust(left=.035,right=.99,top=.96,bottom=.06)
    out=io.BytesIO();fig.savefig(out,format='png',dpi=300,facecolor=fig.get_facecolor());plt.close(fig);return out.getvalue()
