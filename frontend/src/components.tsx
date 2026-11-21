import {Check, AlertTriangle, ChevronRight, ThumbsUp, ThumbsDown, HelpCircle} from 'lucide-react';
import type {Finding} from './types';

export function Status({status}:{status:string}){return <span className={`status ${status}`}><span/>{status.replaceAll('_',' ')}</span>}
export function Notice({children}:{children:React.ReactNode}) {return <div className="notice" role="alert"><AlertTriangle size={16}/><div>{children}</div></div>}
export function FindingCard({finding:f,selected,onSelect,onFeedback}:{finding:Finding;selected:boolean;onSelect:()=>void;onFeedback:(v:string)=>void}){
return <article className={`finding ${selected?'selected':''}`}>
  <button className="finding-head" onClick={onSelect}><span className={`severity ${f.severity}`}>{f.severity}</span><span className="finding-category">{f.category}</span><ChevronRight size={15}/><strong>{f.title}</strong><small>{f.path}:{f.start_line}{f.end_line!==f.start_line?`–${f.end_line}`:''}</small></button>
  {selected&&<div className="finding-body"><p>{f.explanation}</p><pre>{f.evidence}</pre><p className="source-line">{f.validation==='evidence_matched'?<Check size={13}/>:<AlertTriangle size={13}/>} {f.validation.replaceAll('_',' ')} · {f.sources.join(' + ')} {f.rule_id&&`· ${f.rule_id}`}</p>
  {f.assumptions&&<><h4>When it matters</h4><p>{f.assumptions}</p></>}
  {f.suggested_fix&&<><h4>Suggested fix</h4><p>{f.suggested_fix}</p></>}
  {f.verification_test&&<><h4>How to verify</h4><p>{f.verification_test}</p></>}
  <div className="feedback">{[['useful',ThumbsUp],['false_positive',ThumbsDown],['unclear',HelpCircle]].map(([value,Icon])=>{const I=Icon as typeof Check;return <button key={value as string} aria-pressed={f.feedback===value} className={f.feedback===value?'chosen':''} onClick={()=>onFeedback(value as string)}><I size={13}/>{(value as string).replaceAll('_',' ')}</button>})}</div></div>}
</article>}
