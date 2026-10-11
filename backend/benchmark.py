"""Small synthetic benchmark; --gemini explicitly sends synthetic text to Google."""
import argparse
import json
import math
import re
import time
from pathlib import Path
from whereru.matching import compare


def record(data,kind):
    return dict(type=kind,title=data['title'],description=data.get('description',''),category=data.get('category','other'),
      attributes=json.dumps({k:data[k] for k in ('color','brand','model','material') if data.get(k)}),
      campus=data.get('campus',''),location='',private_description='',occurred_at='2026-10-10T14:00:00+00:00')


def plain(a,b):
    x=set(re.findall(r'\w+',a.lower()));y=set(re.findall(r'\w+',b.lower()))
    return 100*len(x&y)/max(1,len(x|y))


def run(use_gemini=False):
    cases=json.loads((Path(__file__).parent/'data/matching_examples.json').read_text())
    results=[];modes=['keyword_baseline','attribute_matcher']+(['gemini_semantic'] if use_gemini else [])
    for mode in modes:
        correct=total=fp=negative=tied=0;start=time.perf_counter();details=[]
        for case in cases:
            lost=record(case['lost'],'LOST');scores=[]
            for candidate in case['found']:
                found=record(candidate,'FOUND')
                if mode=='keyword_baseline': score=plain(lost['title']+' '+lost['description'],found['title']+' '+found['description'])
                else:
                    score,reasons=compare(lost,found)
                    if mode=='gemini_semantic' and reasons not in (['Different categories'],['Found before the plausible loss window']):
                        from whereru.ai import embed
                        a=embed(lost['title']+' '+lost['description']);b=embed(found['title']+' '+found['description'])
                        denom=math.sqrt(sum(x*x for x in a)*sum(x*x for x in b));cos=sum(x*y for x,y in zip(a,b))/denom if denom else 0
                        score=min(100,score+30*max(0,min(1,(cos-0.3)/0.7)))
                scores.append(round(score,2))
            expected=case['expected'];best=max(range(len(scores)),key=lambda i:scores[i]);prediction=best if scores[best]>=35 else None
            ties=sum(s==scores[best] for s in scores)>1 and prediction is not None
            if ties:tied+=1
            if expected is not None:
                total+=1;correct+=int(prediction==expected and not ties)
            for i,s in enumerate(scores):
                if i!=expected:negative+=1;fp+=int(s>=35)
            details.append(dict(case=case['name'],scores=scores,expected=expected,predicted=prediction,tied=ties))
        results.append(dict(mode=mode,top1_unique_correct=correct,positive_cases=total,top1_unique_rate=correct/total,
            negative_candidates_above_threshold=fp,negative_candidates=negative,false_positive_candidate_rate=fp/negative,
            tied_cases=tied,elapsed_ms=round(1000*(time.perf_counter()-start),2),cases=details))
    return dict(dataset='Six synthetic examples; engineering sanity check, not a real-world accuracy estimate',threshold=35,
      gemini_tested=use_gemini,results=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--gemini',action='store_true');args=parser.parse_args()
    if args.gemini:
        from whereru import create_app
        app=create_app()
        with app.app_context():print(json.dumps(run(True),indent=2))
    else:print(json.dumps(run(),indent=2))
