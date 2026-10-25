import sys, types, json, joblib
import numpy as np
import sklearn.linear_model
import sklearn.linear_model._sgd_fast as sgd_fast

# تخطي مشكلة Log
class DummyLog:
    def __init__(self, *args, **kwargs): pass
    def __setstate__(self, state): pass

proxy = types.ModuleType('sklearn.linear_model._sgd_fast')
for attr in dir(sgd_fast): setattr(proxy, attr, getattr(sgd_fast, attr))
proxy.Log = DummyLog
sys.modules['sklearn.linear_model._sgd_fast'] = proxy
sklearn.linear_model._sgd_fast = proxy

# قراءة ملفات artifacts_v5
clf = joblib.load('artifacts_v5/model.pkl')
mlb = joblib.load('artifacts_v5/label_encoder.pkl')
vec = joblib.load('artifacts_v5/skills_vectorizer.pkl')
try:
    aliases = joblib.load('artifacts_v5/skill_aliases.pkl')
except Exception:
    aliases = {}

# استخراج الأوزان والمهارات
vocab = vec.vocabulary_ # dict: skill -> index
idx_to_skill = {int(v): str(k) for k, v in vocab.items()}

# استخراج معاملات الموديل (OneVsRest أو SGD مباشر)
if hasattr(clf, 'estimators_'):
    coefs = [est.coef_[0].tolist() for est in clf.estimators_]
    intercepts = [float(est.intercept_[0]) for est in clf.estimators_]
else:
    coefs = clf.coef_.tolist()
    intercepts = clf.intercept_.tolist()

data = {
    "classes": [str(c) for c in mlb.classes_],
    "vocab": {str(k): int(v) for k, v in vocab.items()},
    "aliases": {str(k): str(v) for k, v in aliases.items()},
    "coefs": coefs,
    "intercepts": intercepts
}

with open("model_weights.json", "w", encoding="utf-8") as f:
    json.dump(data, f)

print("✅ تم استخراج model_weights.json بنجاح!")