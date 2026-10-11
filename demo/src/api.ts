export class ApiError extends Error { constructor(message:string,public status:number){super(message);this.name="ApiError";} }
let csrf = '';
export async function api<T = any>(path: string, data?: unknown, method = 'POST'): Promise<T> {
  const form = data instanceof FormData;
  const response = await fetch('/api' + path, {credentials: 'same-origin', method: data === undefined ? 'GET' : method,
    headers: { ...(form || data === undefined ? {} : {'Content-Type': 'application/json'}), ...(csrf ? {'X-CSRF-Token': csrf} : {}) },
    body: data === undefined ? undefined : form ? data : JSON.stringify(data)});
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(result.message || `Request failed (${response.status}). Check that Flask is running.`,response.status);
  if (result.csrf_token) csrf = result.csrf_token;
  return result as T;
}
export interface User { id:number; display_name:string; email:string; reputation:number; notifications_enabled:boolean }
export interface Listing {id:number;title:string;type:string;status:string;category:string;location:string;private_location?:string;private_description?:string;description:string;visibility:string;requires_ownership_evidence:boolean;attributes:Record<string,any>;images:{id:number;url:string;is_public:boolean}[]}
export interface Match {id:number;lost_id:number;found_id:number;score:number|null;active:boolean;requires_ownership_evidence:boolean;reasons:string[];candidate:{title?:string;location?:string;restricted?:boolean}}
export interface Claim {id:number;found_id:number;lost_id:number;evidence:string;status:string;review_note:string;requires_ownership_evidence:boolean;finder_first_name?:string;owner_first_name?:string;your_role:'finder'|'claimant'}
export interface Handoff {status:string;place:string;method:string;finder_confirmed:boolean;owner_confirmed:boolean}
