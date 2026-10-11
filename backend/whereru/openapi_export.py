"""Export the implemented route inventory with auth and request examples."""
import json
import re
from pathlib import Path

EXAMPLES={
 ('POST','/api/auth/request-code'):{'email':'owner@example.com'},
 ('POST','/api/auth/verify-code'):{'email':'owner@example.com','code':'123456'},
 ('PATCH','/api/me'):{'display_name':'Alex','notifications_enabled':True},
 ('POST','/api/listings'):{'type':'LOST','title':'Blue bottle','category':'bottle','occurred_at':'2026-10-10T14:00:00-04:00','visibility':'PUBLIC'},
 ('PATCH','/api/listings/{listing_id}'):{'title':'Updated bottle description'},
 ('POST','/api/listings/{listing_id}/close'):{'reason':'WITHDRAWN'},
 ('POST','/api/listings/{listing_id}/drop-off'):{'place':'Appropriate staffed desk'},
 ('PATCH','/api/images/{image_id}'):{'is_public':True},
 ('POST','/api/listings/{listing_id}/analyze'):{'consent_to_ai':True,'image_ids':[]},
 ('POST','/api/analyses/{analysis_id}/apply'):{'confirm':True,'corrections':{}},
 ('POST','/api/listings/{listing_id}/semantic-index'):{'consent_to_ai':True},
 ('POST','/api/listings/{listing_id}/recognize-room'):{'consent_to_ai':True,'image_id':1,'building':'Your building'},
 ('POST','/api/listings/{listing_id}/scan-items'):{'consent_to_ai':True,'image_id':1},
 ('POST','/api/matches/{match_id}/feedback'):{'decision':'NOT_MINE'},
 ('POST','/api/claims'):{'found_id':2,'lost_id':1,'evidence':'Private identifying evidence'},
 ('POST','/api/claims/{claim_id}/evidence'):{'evidence':'More private identifying evidence'},
 ('POST','/api/claims/{claim_id}/review'):{'decision':'ACCEPTED','note':''},
 ('POST','/api/claims/{claim_id}/messages'):{'body':'Meet at the student center?'},
 ('POST','/api/claims/{claim_id}/handoff'):{'method':'MEETUP','place':'Student center'},
 ('POST','/api/listings/{listing_id}/potential-locations'):{'locations':[{'label':'Library','latitude':40.503,'longitude':-74.452,'priority':2,'share_public':True}]},
 ('POST','/api/location-sessions'):{'consent':True},
 ('POST','/api/location-sessions/{sid}/points'):{'points':[{'latitude':40.503,'longitude':-74.452,'accuracy':20,'recorded_at':1791670000.0}]},
}


def export(app,destination):
    spec={'openapi':'3.0.3','info':{'title':'WhereRU? backend','version':'1.0.0','description':'Executable endpoint inventory and examples. See API.md for field limits, privacy rules and response contracts. Timestamps in examples must be replaced where current time is required.'},
      'servers':[{'url':'http://127.0.0.1:5001'}],'paths':{},'components':{'securitySchemes':{
        'SessionCookie':{'type':'apiKey','in':'cookie','name':'whereru_session'},
        'CsrfToken':{'type':'apiKey','in':'header','name':'X-CSRF-Token'}}}}
    public={'health','auth.request_code','auth.verify_code'}
    for rule in sorted(app.url_map.iter_rules(),key=lambda r:r.rule):
        if not rule.rule.startswith('/api/'):continue
        path=re.sub(r'<(?:int:)?([^>]+)>',r'{\1}',rule.rule)
        for method in sorted(rule.methods-{'OPTIONS','HEAD'}):
            write=method in ('POST','PATCH','PUT','DELETE')
            security={} if rule.endpoint in public else {'SessionCookie':[]}
            if security and write:security['CsrfToken']=[]
            created=rule.endpoint in {'listings.create','media.upload','recovery.create_claim','recovery.send_message','recovery.arrange','maps.start'}
            operation={'operationId':rule.endpoint.replace('.','_')+'_'+method.lower(),'summary':rule.endpoint.replace('.',' / ').replace('_',' '),
              'security':[security] if security else [],'responses':{('201' if created else '200'):{'description':'Success'},
                 '400':{'description':'Invalid input'},'401':{'description':'Sign in required'},'403':{'description':'Permission, origin, or CSRF denied'},
                 '404':{'description':'Resource not found or inaccessible'},'409':{'description':'State conflict'},'429':{'description':'Rate limited'}}}
            parameters=[{'name':name,'in':'path','required':True,'schema':{'type':'integer','minimum':1}} for name in re.findall(r'{([^}]+)}',path)]
            if method=='GET' and path in ('/api/listings','/api/me/listings','/api/matches','/api/claims','/api/notifications','/api/claims/{claim_id}/messages'):
                parameters += [{'name':'limit','in':'query','schema':{'type':'integer','minimum':1,'maximum':100,'default':30}},
                               {'name':'offset','in':'query','schema':{'type':'integer','minimum':0,'default':0}}]
            if method=='GET' and path in ('/api/listings','/api/maps/density'):
                for name in (('q','type','category','campus','from','to') if path=='/api/listings' else ('category','campus','from','to')):
                    parameters.append({'name':name,'in':'query','schema':{'type':'string'}})
            if parameters:operation['parameters']=parameters
            if write:
                if rule.endpoint=='media.upload':
                    body={'multipart/form-data':{'schema':{'type':'object','required':['image'],'properties':{'image':{'type':'string','format':'binary'}}}}}
                else:
                    example=EXAMPLES.get((method,path),{})
                    body={'application/json':{'schema':{'type':'object'},'example':example}}
                operation['requestBody']={'required':True,'content':body}
            if rule.endpoint=='media.view':operation['responses']['200']['content']={'image/jpeg':{'schema':{'type':'string','format':'binary'}}}
            spec['paths'].setdefault(path,{})[method.lower()]=operation
    Path(destination).write_text(json.dumps(spec,indent=2)+'\n')
    return spec
