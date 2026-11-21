import {render,screen,fireEvent,cleanup} from '@testing-library/react';
import {afterEach,describe,it,expect,vi} from 'vitest';
import {FindingCard,Notice,Status} from './components';
import type {Finding} from './types';
afterEach(cleanup);
const finding:Finding={id:'1',path:'main.py',start_line:4,end_line:4,category:'bug',severity:'high',title:'Mutable default argument',explanation:'State is shared between calls.',evidence:'def add(x, items=[]):',assumptions:'Called without a list.',suggested_fix:'Use None and create a list.',verification_test:'Call twice.',sources:['ruff'],validation:'evidence_matched',feedback:null,rule_id:'B006'};
describe('review feedback',()=>{
 it('shows actual evidence and sends the selected verdict',()=>{const feedback=vi.fn();render(<FindingCard finding={finding} selected onSelect={()=>{}} onFeedback={feedback}/>);expect(screen.getByText('def add(x, items=[]):')).toBeInTheDocument();expect(screen.getByText('main.py:4')).toBeInTheDocument();fireEvent.click(screen.getByRole('button',{name:'false positive'}));expect(feedback).toHaveBeenCalledWith('false_positive');});
 it('keeps details collapsed until selected',()=>{const select=vi.fn();render(<FindingCard finding={finding} selected={false} onSelect={select} onFeedback={()=>{}}/>);expect(screen.queryByText(finding.explanation)).not.toBeInTheDocument();fireEvent.click(screen.getByRole('button'));expect(select).toHaveBeenCalledOnce();});
 it('presents partial failures accessibly',()=>{render(<><Status status="partial"/><Notice>Ollama unavailable; static results preserved.</Notice></>);expect(screen.getByRole('alert')).toHaveTextContent('static results preserved');expect(screen.getByText('partial')).toBeInTheDocument();});
});
