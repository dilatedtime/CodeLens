export type Project = {id:string; name:string; created_at?:string};
export type Source = {path:string;content:string;index:{symbols:{name:string;start:number;end:number}[];syntax_error:string|null}};
export type Submission = {id:string;project_id:string;content_hash:string;skipped:string[];files:Source[]};
export type Finding = {id:string;path:string;start_line:number;end_line:number;category:string;severity:string;title:string;explanation:string;evidence:string;assumptions:string;suggested_fix:string;verification_test:string;sources:string[];validation:string;feedback:string|null;rule_id:string};
export type Artifact = {id:string;kind:string;markdown:string;proposed_code:string;path:string|null;syntax_valid:boolean|null;warning:string};
export type Run = {id:string;model:string;status:string;error:string;metrics:{latency_seconds:number;finding_count:number;schema_failures?:number;digest?:string;prompt_version?:string};coverage:{included_lines:number;total_lines:number;complete:boolean;note:string;omitted_units:unknown[]};findings:Finding[];artifacts:Artifact[]};
export type Job = {id:string;submission_id:string;status:string;stage:string;created_at:string;errors:string[];request:{mode:string;task:string;models:string[]};runs:Run[]};
export type Models = {models:{name:string;installed:boolean}[];default:string;error:string|null;settings:Record<string,number>};
