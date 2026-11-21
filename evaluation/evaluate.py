"""Run actual reviews against the API; never execute evaluation source files."""
import argparse
import json
import platform
import time
from pathlib import Path
import httpx


def score(predictions, labels):
    """One-to-one candidate matching; semantic adjudication is still required."""
    matched=set()
    for prediction in predictions:
        for i,label in enumerate(labels):
            if i not in matched and prediction['path']==label['path'] and prediction['category']==label['category'] and prediction['start_line']<=label['end_line'] and prediction['end_line']>=label['start_line']:
                matched.add(i)
                break
    return {'tp':len(matched),'fp':len(predictions)-len(matched),'fn':len(labels)-len(matched)}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--url',default='http://127.0.0.1:8000/api')
    parser.add_argument('--model',default='qwen2.5-coder:1.5b')
    parser.add_argument('--modes',nargs='+',choices=['static','ai','hybrid'],default=['static'])
    parser.add_argument('--split',choices=['development','holdout','all'],default='development')
    parser.add_argument('--output',default=str(Path(__file__).with_name('results.json')))
    args=parser.parse_args()
    dataset=json.loads(Path(__file__).with_name('dataset.json').read_text(encoding='utf-8'))
    cases=[c for c in dataset if args.split=='all' or c['split']==args.split]
    results=[]
    with httpx.Client(base_url=args.url,timeout=15) as client:
        def post(path,data):
            response=client.post(path,json=data);response.raise_for_status();return response.json()
        def get(path):
            response=client.get(path);response.raise_for_status();return response.json()
        project=post('/projects',{'name':f'Evaluation {args.split}'})
        config=get('/models')
        for case in cases:
            # Only source crosses into inference, never labels or rationales.
            submission=post(f"/projects/{project['id']}/submissions",{'path':'main.py','code':case['files']['main.py']})
            for mode in args.modes:
                start=time.monotonic()
                job=post(f"/submissions/{submission['id']}/jobs",{'mode':mode,'models':[args.model]})
                while True:
                    result=get(f"/jobs/{job['id']}")
                    if result['status'] not in ('queued','running'):
                        break
                    if time.monotonic()-start>2500:
                        raise TimeoutError(f"Job {job['id']} exceeded evaluation deadline")
                    time.sleep(.5)
                predictions=result['runs'][0]['findings'] if result['runs'] else []
                # Failed/partial runs are not silently treated as valid benchmarks.
                candidate_score=score(predictions,case['labels']) if result['status']=='completed' else None
                row={'case':case['id'],'mode':mode,'status':result['status'],'latency_seconds':round(time.monotonic()-start,3),'candidate_score':candidate_score,'clean':not case['labels'],'job':result}
                results.append(row)
                print(f"{case['id']:28} {mode:7} {result['status']:10} {candidate_score}",flush=True)
                Path(args.output).write_text(json.dumps({'project_id':project['id'],'hardware':platform.platform(),'processor':platform.processor(),'model':args.model,'config':config,'results':results,'note':'Provisional location/category matching. Human issue-type adjudication required; dataset is synthetic.'},indent=2),encoding='utf-8')
    summary={}
    for mode in args.modes:
        rows=[r for r in results if r['mode']==mode]
        scored=[r for r in rows if r['candidate_score'] is not None]
        totals={k:sum(r['candidate_score'][k] for r in scored) for k in ['tp','fp','fn']}
        tp,fp,fn=(totals[k] for k in ['tp','fp','fn'])
        precision=tp/(tp+fp) if tp+fp else 0
        recall=tp/(tp+fn) if tp+fn else 0
        summary[mode]={**totals,'precision':precision,'recall':recall,'f1':2*precision*recall/(precision+recall) if precision+recall else 0,'completed':len(scored),'excluded_incomplete':len(rows)-len(scored),'clean_false_positives':sum(r['candidate_score']['fp'] for r in scored if r['clean']),'schema_failures':sum(run['metrics'].get('schema_failures',0) for r in rows for run in r['job']['runs'])}
    output=json.loads(Path(args.output).read_text(encoding='utf-8'));output['summary']=summary
    Path(args.output).write_text(json.dumps(output,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    main()
