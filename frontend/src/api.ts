export async function api<T>(path:string, init?:RequestInit):Promise<T> {
  const res = await fetch(`/api${path}`, {...init, headers: {...(!(init?.body instanceof FormData) ? {'Content-Type':'application/json'} : {}), ...init?.headers}});
  if (!res.ok) {const body=await res.json().catch(()=>({detail:res.statusText})); throw new Error(typeof body.detail==='string'?body.detail:JSON.stringify(body.detail));}
  return res.status===204 ? undefined as T : res.json();
}
export const post = <T,>(path:string, body:unknown)=>api<T>(path,{method:'POST',body:JSON.stringify(body)});
