import io
from xml.sax.saxutils import escape
from branding import draw_report_logo
from reportlab.platypus import BaseDocTemplate,PageTemplate,Frame,Paragraph,Spacer,Table,TableStyle,KeepTogether,Image,PageBreak
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.lib.units import inch
from minitab_equivalence_chart import draw_equivalence_chart

def generate(results,study,layout_png=None,*,embedded=False):
    buf=io.BytesIO()
    class ReportDoc(BaseDocTemplate):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            self.addPageTemplates(PageTemplate(id='normal',frames=[Frame(45,45,505,745,leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)],onPage=self.decorate))
        def decorate(self,canvas,doc):
            draw_report_logo(canvas, doc)
            canvas.saveState();canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#64748B'))
            canvas.drawString(45,28,'Detailed TOST results')
            if not embedded:
                canvas.drawRightString(550,28,f'Page {doc.page}')
            canvas.restoreState()
        def afterFlowable(self,flowable):
            if isinstance(flowable,Paragraph) and getattr(flowable,'_toc_heading',False):
                key=f'section_{self.seq.nextf("section")}'
                self.canv.bookmarkPage(key)
                self.notify('TOCEntry',(0,flowable.getPlainText(),self.page,key))
    doc=ReportDoc(buf,pagesize=(595,842))
    styles=getSampleStyleSheet();styles.add(ParagraphStyle(name='BlueSection',parent=styles['Heading3'],textColor=colors.HexColor('#0066a4'),spaceBefore=12))
    if embedded:
        story = []
    else:
        story=[Spacer(1,95),Paragraph('Equivalency Report',styles['Title']),Spacer(1,14),Paragraph(escape(study),styles['Heading2']),Spacer(1,15),Paragraph('Equipment-to-equipment equivalence analysis',styles['Normal']),Spacer(1,25),Paragraph('Verify approved criteria and calculations before regulated use.',styles['Normal']),PageBreak(),Paragraph('Table of Contents',styles['Heading1']),Spacer(1,18)]
        toc=TableOfContents();toc.levelStyles=[ParagraphStyle(name='TOCEntryStyle',fontName='Helvetica',fontSize=10,leading=16,leftIndent=10,firstLineIndent=-10,spaceBefore=5)]
        story.extend([toc,PageBreak()])
    def tab(rows,widths=None):
        t=Table([[str(c) for c in row] for row in rows],colWidths=widths,repeatRows=1,hAlign='LEFT');t.setStyle(TableStyle([('LINEBELOW',(0,0),(-1,0),.7,colors.black),('BOTTOMPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),5),('FONTSIZE',(0,0),(-1,-1),8)]));return t
    for i,(meta,r) in enumerate(results):
        if i:story.append(PageBreak())
        ref,test,endpoint=meta['reference'],meta['test'],meta['endpoint']
        heading=Paragraph(f"{i+1}. {meta['et']} | {meta['location']} | {meta['kind']} | {escape(endpoint)}",styles['Heading2'])
        heading._toc_heading=not embedded
        story += [heading,Paragraph(f'Two-Sample Equivalence Test: {escape(test)}, {escape(ref)}',styles['Heading3']),Paragraph('Method',styles['BlueSection']),Paragraph(f'Test mean = mean of {escape(test)}. Reference mean = mean of {escape(ref)}. TOST model: {r["tost_model"]}. EAC: {r["method"]}.',styles['Normal']),Paragraph('Descriptive Statistics',styles['BlueSection'])]
        story.append(tab([['Variable','N','Mean','StDev','SE Mean'],[test,r['nt'],f'{r["mean_t"]:.5f}',f'{r["sd_t"]:.5f}',f'{r["sem_t"]:.5f}'],[ref,r['nr'],f'{r["mean_r"]:.5f}',f'{r["sd_r"]:.5f}',f'{r["sem_r"]:.5f}']],[160,35,85,85,85]))
        story += [Spacer(1,7),Paragraph(f'Pooled StDev = {r["pooled"]:.5f}' if r["equal_var"] else "Welch–Satterthwaite degrees of freedom",styles['Normal']),Paragraph(f'Difference: Mean ({escape(test)}) − Mean ({escape(ref)})',styles['BlueSection']),tab([['Difference','SE','90% CI','Equivalence Interval'],[f'{r["diff"]:.5f}',f'{r["se"]:.5f}',f'({r["ci_low"]:.5f}, {r["ci_high"]:.5f})',f'({-r["margin"]:.5f}, {r["margin"]:.5f})']],[85,75,160,170]),Spacer(1,8),Paragraph('CI is within the equivalence interval. Can claim equivalence.' if r['passed'] else 'CI is not fully within the equivalence interval. Cannot claim equivalence.',styles['Normal']),Paragraph('Test',styles['BlueSection']),Paragraph(f'Null hypothesis: Difference ≤ {-r["margin"]:.5f} or Difference ≥ {r["margin"]:.5f}',styles['Normal']),Paragraph(f'Alternative hypothesis: {-r["margin"]:.5f} &lt; Difference &lt; {r["margin"]:.5f}',styles['Normal']),Paragraph('α level: 0.05',styles['Normal']),Spacer(1,7),tab([['Null Hypothesis','DF','T-Value','P-Value'],['Difference ≤ lower EAC',f'{r["df"]:.5g}',f'{r["t1"]:.4f}',f'{r["p1"]:.4f}'],['Difference ≥ upper EAC',f'{r["df"]:.5g}',f'{r["t2"]:.4f}',f'{r["p2"]:.4f}']],[240,50,90,90]),Spacer(1,8),Paragraph(f'The greater of the two P-values is {max(r["p1"],r["p2"]):.4f}. '+('Can claim equivalence.' if r['passed'] else 'Cannot claim equivalence.'),styles['Normal'])]
        img=io.BytesIO()
        draw_equivalence_chart(test,ref,r['ci_low'],r['ci_high'],-r['margin'],r['margin'],r['diff'],img)
        img.seek(0)
        story.append(Image(img,width=345,height=233,hAlign='LEFT'))
    if not results:story.append(Paragraph('No eligible comparisons generated.',styles['Normal']))
    doc.multiBuild(story);return buf.getvalue()
