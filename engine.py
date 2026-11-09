import numpy as np
from scipy import stats
from itertools import combinations

def pair_layout(equipment):
    pairs=[]
    for a,b in combinations(equipment,2):
        location='OU → RU' if a['site']!=b['site'] else f"Within {a['site']}"
        kind='Core' if a['type'].strip().casefold()==b['type'].strip().casefold() else 'Cross'
        if a['site']=='RU' and b['site']=='OU': a,b=b,a
        pairs.append({'reference':a['id'],'test':b['id'],'location':location,'kind':kind})
    return pairs

def analyze(ref,test,method='Calculated',manual=None, *, equal_var=True):
    x=np.asarray(ref,dtype=float);y=np.asarray(test,dtype=float)
    x=x[np.isfinite(x)];y=y[np.isfinite(y)]
    if len(x)<2 or len(y)<2: raise ValueError('At least 2 observations required in each group')
    nr,nt=len(x),len(y); sr=np.std(x,ddof=1);st=np.std(y,ddof=1)
    df = nr + nt - 2
    sp = None
    if equal_var:
        sp = np.sqrt(((nr-1)*sr**2+(nt-1)*st**2)/df)
        se = sp * np.sqrt(1/nr + 1/nt)
    else:
        ref_term, test_term = sr**2 / nr, st**2 / nt
        total = ref_term + test_term
        if total == 0:
            raise ValueError('Welch TOST requires positive variance in at least one group.')
        se = np.sqrt(total)
        df = 1 / ((ref_term / total)**2 / (nr-1) + (test_term / total)**2 / (nt-1))
    if method=='Calculated':
        margin=2*sr*np.sqrt((nr-1)/stats.chi2.ppf(.05,nr-1))
    else:
        margin=float(manual)
    if not np.isfinite(margin) or margin<=0:raise ValueError('EAC must be positive and finite')
    diff=np.mean(y)-np.mean(x)
    ci=(diff-stats.t.ppf(.95,df)*se,diff+stats.t.ppf(.95,df)*se)
    if se==0:
        p1=0. if diff>-margin else 1.;p2=0. if diff<margin else 1.
        t1=t2=float('nan')
    else:
        t1=(diff+margin)/se;t2=(diff-margin)/se
        p1=stats.t.sf(t1,df);p2=stats.t.cdf(t2,df)
    return dict(nr=nr,nt=nt,mean_r=np.mean(x),mean_t=np.mean(y),sd_r=sr,sd_t=st,sem_r=sr/np.sqrt(nr),sem_t=st/np.sqrt(nt),pooled=sp,diff=diff,se=se,ci_low=ci[0],ci_high=ci[1],margin=margin,df=df,t1=t1,t2=t2,p1=p1,p2=p2,passed=bool(ci[0]>-margin and ci[1]<margin),method=method,equal_var=equal_var,tost_model="Pooled" if equal_var else "Welch")
