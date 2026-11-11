"""Read-only real-corpus readiness and common-window evidence for #40."""

import argparse
import json
from pathlib import Path

import pandas as pd

from community_signals import research
from data_diagnostics import DATA_ERRORS
from portfolio_data import ROOT
from portfolio_selection import analysis_date

REQUIRED=('MasterShiny CS2','rubyjetski','IAMJERM - CS2','TDM_Heyzeus','LeChineur')


def readiness(root=ROOT,as_of=None,*,research_result=None):
    root=Path(root);cutoff=analysis_date(as_of)
    manifest_path=root/'data/community/corpus.json'
    checks=[]
    def check(key,ready,detail):checks.append(dict(requirement=key,ready=bool(ready),detail=detail))
    if not manifest_path.exists():
        return dict(status='blocked',as_of=cutoff.isoformat(),checks=[dict(requirement='authorized_corpus',ready=False,detail='No local authorized transcript corpus; no predictive benefit can be measured.')],comparisons=[],predictive_benefit='not_established')
    try:
        manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
        result=research(root,as_of=cutoff) if research_result is None else research_result
        channels={c['name']:c for c in manifest['channels']}
        for name in REQUIRED:
            channel=channels.get(name,{})
            verified=channel.get('verified') is True and analysis_date(channel.get('verified_at'))<=cutoff if channel.get('verified_at') else False
            check('channel:'+name,verified,'Canonical channel identity verified at cutoff.' if verified else 'Exact canonical channel URL/ID and dated verification are required.')
        review=manifest.get('access_review',{})
        reviewed=review.get('authorized') is True and isinstance(review.get('method'),str) and bool(review['method'].strip()) and review.get('reviewed_at') and analysis_date(review['reviewed_at'])<=cutoff
        check('authorized_corpus',reviewed,'Acquisition method explicitly declared and dated; not an automatic grant of rights.')
        coverage=result['coverage']
        imported=set(coverage.loc[coverage.status.eq('imported') & coverage.segments.gt(0),'video_id']) if not coverage.empty else set()
        videos=[v for v in manifest['videos'] if v.get('status')=='available' and v['video_id'] in imported and analysis_date(v['published_at'])<=cutoff and analysis_date(v['collected_at'])<=cutoff]
        check('eligible_transcripts',bool(videos),str(len(videos))+' temporally eligible imported nonempty transcripts.')
        evaluation=result['evaluation']
        check('reviewed_extraction',bool(evaluation and evaluation['reviewed_passages']>0),'Extraction quality requires a dated reviewed sample including negatives and missed mentions.')
        comparisons=[]
        scores=result['scores']
        if not scores.empty:
            for item_id,group in scores.groupby('item_id'):
                named=group.set_index('method')
                if {'price_model','community_model'}.issubset(named.index) and group.windows.nunique()==1:
                    price=named.loc['price_model'];community=named.loc['community_model']
                    comparisons.append(dict(item_id=item_id,windows=int(price.windows),price_only_MAE=float(price.MAE),community_MAE=float(community.MAE),MAE_difference=float(community.MAE-price.MAE)))
        check('common_window_evaluation',bool(comparisons),'Price-only and community models must be measured on identical chronological windows.')
        ready=all(row['ready'] for row in checks)
        return dict(status='ready_for_empirical_review' if ready else 'blocked',as_of=cutoff.isoformat(),checks=checks,comparisons=comparisons,predictive_benefit='not_established',limits='A measured difference is descriptive, not significance, causality, an issued forecast or a trading instruction.')
    except DATA_ERRORS as error:
        return dict(status='invalid_corpus',as_of=cutoff.isoformat(),checks=[dict(requirement='valid_inputs',ready=False,detail=type(error).__name__+': corpus validation failed; no inputs rewritten.')],comparisons=[],predictive_benefit='not_established')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('environment',choices=['school'])
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--as-of')
    args=parser.parse_args()
    result=readiness(args.root,args.as_of)
    print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
    return 0 if result['status']=='ready_for_empirical_review' else 1


if __name__=='__main__':raise SystemExit(main())
