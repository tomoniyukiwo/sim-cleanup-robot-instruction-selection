"""Semantic routing among registered tasks; no scene understanding implied."""
import unicodedata
import numpy as np

def normalize(s):return ' '.join(unicodedata.normalize('NFKC',s).casefold().split())

def choose(scores,threshold,margin):
    scores=np.asarray(scores,dtype=float)
    if scores.ndim!=1 or len(scores)==0 or not np.isfinite(scores).all():
        raise ValueError('Invalid similarity scores')
    order=np.argsort(-scores,kind='stable'); i=int(order[0])
    gap=float(scores[i]-scores[order[1]]) if len(scores)>1 else 2.0
    return {'index':i,'score':float(scores[i]),'margin':gap,
            'accepted':bool(scores[i]>=threshold and gap>=margin)}

class Router:
    def __init__(self,catalog,model_path,cfg):
        from sentence_transformers import SentenceTransformer
        self.tasks=catalog['tasks'];self.cfg=cfg
        self.model=SentenceTransformer(str(model_path),device='cpu',local_files_only=True)
        self.texts=[];self.owners=[]
        for i,t in enumerate(self.tasks):
            for text in [t['instruction']]+t.get('aliases',[]):
                self.texts.append(text);self.owners.append(i)
        self.vectors=self.model.encode(self.texts,normalize_embeddings=True)
    def route(self,text,forced_id=None):
        if forced_id is not None:
            matches=[t for t in self.tasks if t['task_id']==forced_id]
            if len(matches)!=1:raise ValueError('Task ID absent from catalog')
            return {'accepted':True,'task':matches[0],'method':'explicit_task_id','score':None,'margin':None}
        exact={self.owners[i] for i,s in enumerate(self.texts) if normalize(s)==normalize(text)}
        if len(exact)==1:
            return {'accepted':True,'task':self.tasks[exact.pop()],'method':'registered_exact','score':1.,'margin':None}
        query=self.model.encode([text],normalize_embeddings=True)[0]
        raw=np.asarray(self.vectors)@query
        scores=np.full(len(self.tasks),-1.)
        for owner,score in zip(self.owners,raw):scores[owner]=max(scores[owner],score)
        result=choose(scores,self.cfg['min_similarity'],self.cfg['min_margin'])
        result.update(task=self.tasks[result.pop('index')],method='multilingual_embedding')
        return result
