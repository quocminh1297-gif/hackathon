"""AgentGuard demo server. Uses synthetic data and in-memory state; NOT production auth."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import json, os, threading, time, uuid

ROOT = Path(__file__).resolve().parent
DOCS = {
    "public": {"title": "Product FAQ", "classification": "PUBLIC", "content": "Agent Nova may read this document. Demo content: our product supports account recovery and workspace collaboration."},
    "hr-confidential": {"title": "HR Compensation Plan", "classification": "CONFIDENTIAL", "content": "SYNTHETIC DATA ONLY. Employee salary bands and planned compensation adjustments."},
}
ROLE_GRANTS = {"nova": {"public-reader"}}
REQUIRED_APPROVALS = 2
requests = {}
audit = []
state_lock = threading.RLock()

def log(actor, action, detail, outcome):
    audit.insert(0, {"id": str(uuid.uuid4())[:8], "time": time.strftime('%H:%M:%S'), "actor": actor, "action": action, "detail": detail, "outcome": outcome})

def respond(handler, code, payload):
    raw = json.dumps(payload).encode()
    handler.send_response(code); handler.send_header('Content-Type','application/json'); handler.send_header('Content-Length',str(len(raw))); handler.send_header('Access-Control-Allow-Origin','*'); handler.send_header('Access-Control-Allow-Headers','Content-Type'); handler.send_header('Access-Control-Allow-Methods','GET,POST,OPTIONS'); handler.end_headers(); handler.wfile.write(raw)

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs): super().__init__(*args, directory=str(ROOT), **kwargs)
    def do_OPTIONS(self): self.send_response(204); self.send_header('Access-Control-Allow-Origin','*'); self.send_header('Access-Control-Allow-Headers','Content-Type'); self.send_header('Access-Control-Allow-Methods','GET,POST,OPTIONS'); self.end_headers()
    def body(self):
        n=int(self.headers.get('Content-Length',0)); return json.loads(self.rfile.read(n) or b'{}')
    def do_GET(self):
        if self.path == '/api/state': return respond(self,200,{'docs':[{'id':k,'title':v['title'],'classification':v['classification']} for k,v in DOCS.items()], 'roles':sorted(ROLE_GRANTS['nova']), 'requests':list(requests.values()), 'audit':audit[:30], 'requiredApprovals':REQUIRED_APPROVALS, 'mode':'SIMULATED GOVERNANCE — TideCloak not connected'})
        return super().do_GET()
    def do_POST(self):
        try: data=self.body()
        except Exception: return respond(self,400,{'error':'Invalid JSON'})
        if self.path == '/api/read':
            actor=data.get('actor','nova'); doc_id=data.get('docId','public'); doc=DOCS.get(doc_id)
            if not doc: return respond(self,404,{'error':'Document not found'})
            required='public-reader' if doc_id=='public' else 'sensitive-reader'
            # Server-side check: client-side UI is never trusted.
            if required not in ROLE_GRANTS.get(actor,set()):
                log(actor,'READ '+doc_id,'Required role: '+required,'DENIED'); return respond(self,403,{'ok':False,'error':'Access denied: missing role '+required})
            log(actor,'READ '+doc_id,'Required role: '+required,'ALLOWED'); return respond(self,200,{'ok':True,'document':doc})
        if self.path == '/api/request-access':
            # AI can request access, but cannot grant it or approve its own request.
            if data.get('actor') != 'nova':
                log(str(data.get('actor','unknown')),'REQUEST ROLE','sensitive-reader','DENIED: only nova may submit demo request')
                return respond(self,403,{'error':'Only the agent can submit this demo request'})
            with state_lock:
                rid=str(uuid.uuid4())[:8]; req={'id':rid,'requestedBy':'nova','role':'sensitive-reader','reason':'Agent requested access to HR-confidential document','approvals':[],'status':'PENDING'}; requests[rid]=req
                log('nova','REQUEST ROLE','sensitive-reader request '+rid,'PENDING GOVERNANCE'); return respond(self,201,req)
        if self.path == '/api/approve':
            rid=data.get('requestId'); admin=data.get('admin'); req=requests.get(rid)
            with state_lock:
                req=requests.get(rid)
                if not req:
                    log(str(admin or 'unknown'),'APPROVE ROLE',str(rid),'DENIED: request not found')
                    return respond(self,404,{'error':'Request not found'})
                if admin not in ('admin-alex','admin-blair') or admin == req['requestedBy']:
                    log(str(admin or 'unknown'),'APPROVE ROLE',rid,'DENIED: ineligible or self approval')
                    return respond(self,403,{'error':'Ineligible approver; requester cannot approve'})
                if admin in req['approvals']:
                    log(admin,'APPROVE ROLE',rid,'DENIED: duplicate approval')
                    return respond(self,409,{'error':'This admin already approved'})
                if req['status'] != 'PENDING':
                    log(admin,'APPROVE ROLE',rid,'DENIED: request is not pending')
                    return respond(self,409,{'error':'Request is not pending'})
                req['approvals'].append(admin); log(admin,'APPROVE ROLE',rid, 'APPROVED '+str(len(req['approvals']))+'/'+str(REQUIRED_APPROVALS))
                if len(req['approvals']) >= REQUIRED_APPROVALS:
                    # Demo simulation only; this is NOT TideCloak QEA/QEG.
                    ROLE_GRANTS['nova'].add(req['role']); req['status']='APPROVED_AND_APPLIED'; log('governance-demo','APPLY ROLE',req['role'],'APPLIED AFTER QUORUM')
                return respond(self,200,req)
        if self.path == '/api/reset':
            with state_lock:
                ROLE_GRANTS['nova']={'public-reader'}; requests.clear(); audit.clear(); log('system','RESET','Demo state reset','OK'); return respond(self,200,{'ok':True})
        return respond(self,404,{'error':'Unknown endpoint'})
    def log_message(self, *args): pass

if __name__ == '__main__':
    print('AgentGuard demo: http://127.0.0.1:8000')
    print('Warning: synthetic demo only; no real TideCloak integration or production authentication.')
    ThreadingHTTPServer((os.environ.get('AGENTGUARD_HOST','127.0.0.1'),int(os.environ.get('AGENTGUARD_PORT','8000'))),Handler).serve_forever()
